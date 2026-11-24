"""Helius RPC (Solana) — SOLA LETTURA. Doc: https://www.helius.dev/docs

Usiamo solo metodi standard di lettura di Solana:
- getAccountInfo (jsonParsed) sul mint: autorità di mint/freeze, programma
  (Token o Token-2022) ed estensioni pericolose (transfer fee, hook, delegato permanente);
- getTokenLargestAccounts: i 20 conti più grandi del token;
- getMultipleAccounts (jsonParsed): a chi appartengono quei conti, per escludere
  il pool di liquidità dal calcolo della concentrazione.

La chiave va nell'URL (?api-key=...): non viene mai scritta nei log né negli
errori (vedi `_redacted`). Nessun metodo che invia transazioni.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx

from trade.config import redact
from trade.ratelimit import MinIntervalLimiter
from trade.sources import SourceError

RPC_URL = "https://mainnet.helius-rpc.com/"
SOURCE = "helius"

TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

# Metodi ammessi: solo lettura. Qualsiasi altro nome viene rifiutato.
READ_ONLY_METHODS = frozenset({
    "getHealth", "getAccountInfo", "getTokenLargestAccounts", "getMultipleAccounts",
    "getSignaturesForAddress", "getTransaction", "getTokenAccountsByOwner",
})

# Programmi di scambio (AMM / curve di lancio). Un conto token il cui proprietario
# è un account di questi programmi è liquidità, non un "possessore".
# Indirizzi dei programmi ufficiali; da riconfermare se un DEX migra.
AMM_PROGRAMS = frozenset({
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM v4
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C",  # Raydium CPMM
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",  # Raydium CLMM
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",  # Orca Whirlpool
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",  # Meteora DLMM
    "Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB",  # Meteora pools
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",  # PumpSwap
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",  # pump.fun (curva)
})
# Autorità dei pool che non hanno un account proprio (PDA senza dati).
KNOWN_POOL_AUTHORITIES = frozenset({
    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",  # Raydium AMM v4 authority
})
MAX_SIGNATURE_PAGES = 3  # oltre 3000 transazioni il creatore resta "sconosciuto"


@dataclass(frozen=True)
class MintInfo:
    program: str
    is_token_2022: bool
    mint_authority_active: bool
    freeze_authority_active: bool
    supply: int
    decimals: int
    transfer_fee_bps: int
    has_transfer_hook: bool
    has_permanent_delegate: bool
    extensions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LargestAccount:
    address: str
    amount: int


def _require_dict(value: Any, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SourceError(f"{SOURCE}: {what} non valido")
    return value


def parse_mint_info(result: Any) -> MintInfo:
    """`result` di getAccountInfo(mint, jsonParsed). Errore se non è un mint."""
    value = _require_dict(_require_dict(result, "risultato").get("value"), "account del mint (inesistente?)")
    program = value.get("owner")
    if program not in (TOKEN_PROGRAM, TOKEN_2022_PROGRAM):
        raise SourceError(f"{SOURCE}: l'account non appartiene a un programma token")
    parsed = _require_dict(_require_dict(value.get("data"), "data").get("parsed"), "parsed")
    if parsed.get("type") != "mint":
        raise SourceError(f"{SOURCE}: l'account non è un mint")
    info = _require_dict(parsed.get("info"), "info")
    supply = int(info["supply"])
    decimals = int(info["decimals"])

    fee_bps = 0
    hook = False
    delegate = False
    names: list[str] = []
    for ext in info.get("extensions") or []:
        if not isinstance(ext, dict):
            continue
        name = ext.get("extension")
        state = ext.get("state") if isinstance(ext.get("state"), dict) else {}
        names.append(str(name))
        if name == "transferFeeConfig":
            # Prendiamo la tassa più alta tra quella attuale e quella programmata.
            for key in ("olderTransferFee", "newerTransferFee"):
                fee = state.get(key)
                if isinstance(fee, dict):
                    fee_bps = max(fee_bps, int(fee.get("transferFeeBasisPoints") or 0))
        elif name == "transferHook":
            hook = bool(state.get("programId"))
        elif name == "permanentDelegate":
            delegate = bool(state.get("delegate"))

    return MintInfo(
        program=program,
        is_token_2022=program == TOKEN_2022_PROGRAM,
        mint_authority_active=info.get("mintAuthority") is not None,
        freeze_authority_active=info.get("freezeAuthority") is not None,
        supply=supply,
        decimals=decimals,
        transfer_fee_bps=fee_bps,
        has_transfer_hook=hook,
        has_permanent_delegate=delegate,
        extensions=tuple(names),
    )


def parse_largest_accounts(result: Any) -> list[LargestAccount]:
    items = _require_dict(result, "risultato").get("value")
    if not isinstance(items, list):
        raise SourceError(f"{SOURCE}: lista dei conti più grandi non valida")
    out = []
    for item in items:
        if isinstance(item, dict) and item.get("address") and item.get("amount") is not None:
            out.append(LargestAccount(item["address"], int(item["amount"])))
    return out


def parse_account_owners(result: Any, addresses: list[str]) -> dict[str, str | None]:
    """getMultipleAccounts(jsonParsed) -> {conto token: proprietario}."""
    values = _require_dict(result, "risultato").get("value")
    if not isinstance(values, list) or len(values) != len(addresses):
        raise SourceError(f"{SOURCE}: risposta getMultipleAccounts non valida")
    owners: dict[str, str | None] = {}
    for addr, acc in zip(addresses, values, strict=True):
        owner = None
        if isinstance(acc, dict):
            info = (((acc.get("data") or {}).get("parsed") or {}).get("info") or {})
            owner = info.get("owner") if isinstance(info, dict) else None
        owners[addr] = owner
    return owners


def top_holders_pct(
    accounts: list[LargestAccount],
    owners: dict[str, str | None],
    supply: int,
    excluded_owners: set[str],
    top_n: int = 10,
) -> Decimal | None:
    """% dell'offerta nei `top_n` conti più grandi, esclusi quelli del pool.

    Se il proprietario di un conto è sconosciuto, il conto resta nel conteggio
    (prudenza: meglio sovrastimare la concentrazione che sottostimarla).
    """
    if supply <= 0:
        return None
    kept = [a for a in accounts if owners.get(a.address) not in excluded_owners]
    kept.sort(key=lambda a: a.amount, reverse=True)
    total = sum(a.amount for a in kept[:top_n])
    return (Decimal(total) * 100 / Decimal(supply)).quantize(Decimal("0.01"))


def parse_signatures(result: Any) -> list[str]:
    if not isinstance(result, list):
        raise SourceError(f"{SOURCE}: lista delle firme non valida")
    return [x["signature"] for x in result if isinstance(x, dict) and x.get("signature")]


def parse_fee_payer(result: Any) -> str:
    """Chi ha pagato (e firmato per primo) la transazione: per il mint, il creatore."""
    tx = _require_dict(_require_dict(result, "transazione (inesistente?)").get("transaction"), "transaction")
    keys = _require_dict(tx.get("message"), "message").get("accountKeys")
    if not isinstance(keys, list) or not keys:
        raise SourceError(f"{SOURCE}: accountKeys mancanti")
    first = keys[0]
    payer = first.get("pubkey") if isinstance(first, dict) else first
    if not isinstance(payer, str) or not payer:
        raise SourceError(f"{SOURCE}: pagatore non valido")
    return payer


def parse_owner_balance(result: Any) -> int:
    values = _require_dict(result, "risultato").get("value")
    if not isinstance(values, list):
        raise SourceError(f"{SOURCE}: conti del proprietario non validi")
    total = 0
    for acc in values:
        info = (((acc.get("account") or {}).get("data") or {}).get("parsed") or {}).get("info") or {}
        amount = (info.get("tokenAmount") or {}).get("amount")
        if amount is None:
            raise SourceError(f"{SOURCE}: saldo mancante")
        total += int(amount)
    return total


def parse_programs(result: Any, addresses: list[str]) -> dict[str, str | None]:
    """getMultipleAccounts -> {indirizzo: programma proprietario} (None se l'account non esiste)."""
    values = _require_dict(result, "risultato").get("value")
    if not isinstance(values, list) or len(values) != len(addresses):
        raise SourceError(f"{SOURCE}: risposta getMultipleAccounts non valida")
    return {a: (v.get("owner") if isinstance(v, dict) else None) for a, v in zip(addresses, values, strict=True)}


def liquidity_owners(owner_programs: dict[str, str | None], pool_addresses: set[str]) -> set[str]:
    """Quali proprietari sono pool/curve: indirizzo del pool, autorità nota o account di un AMM."""
    return {
        owner for owner, program in owner_programs.items()
        if owner in pool_addresses or owner in KNOWN_POOL_AUTHORITIES or program in AMM_PROGRAMS
    }


class HeliusClient:
    def __init__(
        self, client: httpx.AsyncClient, api_key: str, limiter: MinIntervalLimiter | None = None
    ) -> None:
        if not api_key:
            raise SourceError(f"{SOURCE}: chiave mancante")
        self._client = client
        self._key = api_key
        # Piano Free: 10 richieste/s documentate -> ne usiamo al massimo ~5.
        self._limiter = limiter or MinIntervalLimiter(0.2)

    def _redacted(self, text: str) -> str:
        return redact(text, [self._key])

    async def rpc(self, method: str, params: list[Any]) -> Any:
        if method not in READ_ONLY_METHODS:
            raise SourceError(f"{SOURCE}: metodo non ammesso (solo lettura): {method}")
        await self._limiter.wait()
        try:
            r = await self._client.post(
                RPC_URL,
                params={"api-key": self._key},
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            )
        except httpx.HTTPError as exc:
            raise SourceError(self._redacted(f"{SOURCE}: errore di rete ({type(exc).__name__}) su {method}")) from None
        if r.status_code == 429:
            self._limiter.penalize(10)
            raise SourceError(f"{SOURCE}: limite di richieste superato (429) su {method}")
        if r.status_code != 200:
            raise SourceError(f"{SOURCE}: HTTP {r.status_code} su {method}")
        try:
            body = r.json()
        except ValueError:
            raise SourceError(f"{SOURCE}: risposta non JSON su {method}") from None
        if not isinstance(body, dict) or "error" in body:
            err = body.get("error") if isinstance(body, dict) else None
            msg = err.get("message") if isinstance(err, dict) else "risposta non valida"
            raise SourceError(self._redacted(f"{SOURCE}: errore RPC su {method}: {msg}"))
        return body.get("result")

    async def mint_info(self, mint: str) -> MintInfo:
        return parse_mint_info(await self.rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}]))

    async def top10_pct(self, mint: str, supply: int, pool_addresses: set[str]) -> Decimal | None:
        accounts = parse_largest_accounts(await self.rpc("getTokenLargestAccounts", [mint]))
        if not accounts:
            return None
        addrs = [a.address for a in accounts]
        owners = parse_account_owners(
            await self.rpc("getMultipleAccounts", [addrs, {"encoding": "jsonParsed"}]), addrs
        )
        unique = sorted({o for o in owners.values() if o})
        programs = parse_programs(
            await self.rpc("getMultipleAccounts", [unique, {"encoding": "base64", "dataSlice": {"offset": 0, "length": 0}}]),
            unique,
        ) if unique else {}
        return top_holders_pct(accounts, owners, supply, liquidity_owners(programs, pool_addresses))

    async def find_creator(self, mint: str) -> str | None:
        """Pagatore della prima transazione del mint. None se ce ne sono troppe."""
        before: str | None = None
        oldest: str | None = None
        for _ in range(MAX_SIGNATURE_PAGES):
            opts: dict[str, Any] = {"limit": 1000}
            if before:
                opts["before"] = before
            sigs = parse_signatures(await self.rpc("getSignaturesForAddress", [mint, opts]))
            if not sigs:
                break
            oldest = sigs[-1]
            if len(sigs) < 1000:
                break
            before = oldest
        else:
            return None  # storia troppo lunga: non sappiamo chi è il creatore
        if oldest is None:
            return None
        tx = await self.rpc("getTransaction", [oldest, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        return parse_fee_payer(tx)

    async def owner_balance(self, owner: str, mint: str) -> int:
        result = await self.rpc("getTokenAccountsByOwner", [owner, {"mint": mint}, {"encoding": "jsonParsed"}])
        return parse_owner_balance(result)


__all__ = [
    "HeliusClient",
    "LargestAccount",
    "MintInfo",
    "parse_account_owners",
    "parse_largest_accounts",
    "parse_mint_info",
    "top_holders_pct",
]
