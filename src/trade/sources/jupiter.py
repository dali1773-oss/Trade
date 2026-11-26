"""Jupiter — SOLO QUOTAZIONI (nessuno swap, nessuna transazione).

Prova di rivendibilità ("anti-honeypot"): chiediamo a Jupiter
1) quanti token otterremmo comprando con una piccola somma in SOL;
2) quanti SOL otterremmo rivendendo subito quei token.
La perdita del giro completo (commissioni dei pool + impatto sul prezzo) è la
misura che usiamo: non dipende da come Jupiter calcola il proprio priceImpact.

Se la vendita non trova nessuna rotta mentre l'acquisto sì, è un segnale forte
di honeypot (FAIL). Errori di rete o limiti di richieste = dato sconosciuto.

Doc: https://dev.jup.ag  · La chiave va solo nell'header x-api-key.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

from trade.config import redact
from trade.ratelimit import MinIntervalLimiter
from trade.sources import SourceError

QUOTE_URL = "https://api.jup.ag/swap/v1/quote"
SOURCE = "jupiter"
SOL_MINT = "So11111111111111111111111111111111111111112"
DEFAULT_PROBE_LAMPORTS = 30_000_000  # 0,03 SOL: ordine di grandezza di una posizione pilota
DEFAULT_SLIPPAGE_BPS = 300


class NoRoute(SourceError):
    """Jupiter ha risposto che non esiste una rotta per questo scambio."""


@dataclass(frozen=True)
class SellCheck:
    sell_route_found: bool | None
    roundtrip_loss_pct: Decimal | None
    note: str


def parse_out_amount(body: Any) -> int:
    if not isinstance(body, dict):
        raise SourceError(f"{SOURCE}: risposta non valida")
    out = body.get("outAmount")
    try:
        value = int(out)
    except (TypeError, ValueError):
        raise SourceError(f"{SOURCE}: outAmount mancante") from None
    if value <= 0:
        raise NoRoute(f"{SOURCE}: quantità in uscita nulla")
    return value


def roundtrip_loss_pct(sol_in: int, sol_back: int) -> Decimal:
    return ((Decimal(sol_in) - Decimal(sol_back)) * 100 / Decimal(sol_in)).quantize(Decimal("0.01"))


class JupiterClient:
    def __init__(
        self, client: httpx.AsyncClient, api_key: str, limiter: MinIntervalLimiter | None = None
    ) -> None:
        if not api_key:
            raise SourceError(f"{SOURCE}: chiave mancante")
        self._client = client
        self._key = api_key
        # Piano Free: 60 richieste/min -> una ogni 1,1 s.
        self._limiter = limiter or MinIntervalLimiter(1.1)

    async def quote_out(self, input_mint: str, output_mint: str, amount: int,
                        slippage_bps: int = DEFAULT_SLIPPAGE_BPS) -> int:
        await self._limiter.wait()
        try:
            r = await self._client.get(
                QUOTE_URL,
                headers={"x-api-key": self._key},
                params={
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "amount": str(amount),
                    "slippageBps": str(slippage_bps),
                },
            )
        except httpx.HTTPError as exc:
            raise SourceError(redact(f"{SOURCE}: errore di rete ({type(exc).__name__})", [self._key])) from None
        if r.status_code == 429:
            self._limiter.penalize(60)
            raise SourceError(f"{SOURCE}: limite di richieste superato (429)")
        if r.status_code in (401, 403):
            raise SourceError(f"{SOURCE}: chiave non valida (HTTP {r.status_code})")
        if r.status_code == 400:
            # Jupiter usa 400 per "nessuna rotta" e "token non scambiabile".
            code = ""
            try:
                body = r.json()
                code = str(body.get("errorCode") or body.get("error") or "") if isinstance(body, dict) else ""
            except ValueError:
                pass
            raise NoRoute(f"{SOURCE}: nessuna rotta ({code or 'HTTP 400'})")
        if r.status_code != 200:
            raise SourceError(f"{SOURCE}: HTTP {r.status_code}")
        try:
            return parse_out_amount(r.json())
        except ValueError:
            raise SourceError(f"{SOURCE}: risposta non JSON") from None

    async def sell_check(self, mint: str, probe_lamports: int = DEFAULT_PROBE_LAMPORTS) -> SellCheck:
        try:
            tokens = await self.quote_out(SOL_MINT, mint, probe_lamports)
        except NoRoute as exc:
            # Senza acquisto possibile non possiamo dire nulla sulla vendita.
            return SellCheck(None, None, f"acquisto non quotabile: {exc}")
        except SourceError as exc:
            return SellCheck(None, None, str(exc))
        try:
            sol_back = await self.quote_out(mint, SOL_MINT, tokens)
        except NoRoute as exc:
            return SellCheck(False, None, f"vendita impossibile: {exc}")
        except SourceError as exc:
            return SellCheck(None, None, str(exc))
        return SellCheck(True, roundtrip_loss_pct(probe_lamports, sol_back), "ok")
