"""Raccoglie i dati on-chain di un token e produce il verdetto anti-truffa.

SOLA LETTURA: Helius (RPC di lettura) + Jupiter (solo quotazioni) + DexScreener.
Ogni dato che non si riesce a ottenere resta None -> UNKNOWN -> nessun trade.

Uso:  uv run trade-scan <indirizzo-del-token>
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx

from trade.config import DEFAULT_FILE, load_settings
from trade.models import PoolSnapshot
from trade.scam import ScamVerdict, TokenSecurityInfo, Verdict, evaluate
from trade.sources import SourceError, make_client
from trade.sources.dexscreener import DexScreenerClient
from trade.sources.helius import HeliusClient
from trade.sources.jupiter import JupiterClient

log = logging.getLogger("trade.security")


@dataclass
class SecurityReport:
    info: TokenSecurityInfo
    notes: list[str] = field(default_factory=list)


async def gather_security_info(
    mint: str,
    *,
    helius: HeliusClient,
    jupiter: JupiterClient,
    pool_addresses: set[str] | None = None,
) -> SecurityReport:
    notes: list[str] = []
    fields: dict[str, object] = {}

    try:
        mi = await helius.mint_info(mint)
        fields.update(
            mint_authority_active=mi.mint_authority_active,
            freeze_authority_active=mi.freeze_authority_active,
            is_token_2022=mi.is_token_2022,
            transfer_fee_bps=mi.transfer_fee_bps,
            has_transfer_hook=mi.has_transfer_hook,
            has_permanent_delegate=mi.has_permanent_delegate,
        )
        try:
            # I conti di proprietà del pool sono liquidità, non "balene".
            fields["top10_holders_pct"] = await helius.top10_pct(mint, mi.supply, set(pool_addresses or ()))
        except SourceError as exc:
            notes.append(f"concentrazione: {exc}")
        try:
            creator = await helius.find_creator(mint)
            if creator is None:
                notes.append("creatore: storia troppo lunga o vuota, quota sconosciuta")
            elif mi.supply > 0:
                bal = await helius.owner_balance(creator, mint)
                fields["creator_holding_pct"] = (Decimal(bal) * 100 / Decimal(mi.supply)).quantize(Decimal("0.01"))
                notes.append(f"creatore: {creator[:6]}… (primo firmatario del mint)")
        except SourceError as exc:
            notes.append(f"creatore: {exc}")
    except (SourceError, KeyError, ValueError, TypeError) as exc:
        notes.append(f"mint: {exc}")

    sell = await jupiter.sell_check(mint)
    fields["sell_route_found"] = sell.sell_route_found
    fields["sell_price_impact_pct"] = sell.roundtrip_loss_pct
    if sell.note != "ok":
        notes.append(f"vendibilità: {sell.note}")

    return SecurityReport(TokenSecurityInfo(**fields), notes)  # type: ignore[arg-type]


def pick_main_pool(pairs: list[PoolSnapshot]) -> PoolSnapshot | None:
    solana = [p for p in pairs if p.chain == "solana"]
    if not solana:
        return None
    return max(solana, key=lambda p: p.liquidity_usd or 0)


async def scan(
    mint: str,
    settings_file: Path = DEFAULT_FILE,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[ScamVerdict | None, SecurityReport | None, str]:
    settings = load_settings(settings_file)
    helius_key = settings.get("HELIUS_API_KEY")
    jupiter_key = settings.get("JUPITER_API_KEY")
    if not helius_key or not jupiter_key:
        return None, None, "chiavi mancanti: esegui prima `uv run trade-check-keys`"
    async with make_client(transport) as client:
        try:
            pairs = await DexScreenerClient(client).token_pairs(mint)
        except SourceError as exc:
            return None, None, f"dexscreener: {exc}"
        main = pick_main_pool(pairs)
        if main is None:
            return None, None, "nessun pool trovato su DexScreener per questo token"
        report = await gather_security_info(
            mint,
            helius=HeliusClient(client, helius_key),
            jupiter=JupiterClient(client, jupiter_key),
            pool_addresses={p.pool_address for p in pairs},
        )
    verdict = evaluate(main, report.info, now=datetime.now(UTC))
    return verdict, report, "ok"


ICON = {Verdict.PASS: "✅", Verdict.FAIL: "❌", Verdict.UNKNOWN: "❔"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Controllo anti-truffa di un token Solana (sola lettura).")
    p.add_argument("mint", help="indirizzo del token (mint)")
    p.add_argument("--file", type=Path, default=DEFAULT_FILE)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # gli URL di Helius contengono la chiave

    verdict, report, msg = asyncio.run(scan(args.mint, args.file))
    if verdict is None or report is None:
        print(f"Impossibile valutare: {msg}")
        return 2
    print(f"Token {args.mint}")
    print(f"VERDETTO: {ICON[verdict.verdict]} {verdict.verdict.value}"
          + ("  (si può comprare)" if verdict.verdict is Verdict.PASS else "  (NON si compra)"))
    for c in verdict.checks:
        print(f"  {ICON[c.verdict]} {c.name}: {c.reason}")
    for n in report.notes:
        print(f"  · {n}")
    return 0 if verdict.verdict is Verdict.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
