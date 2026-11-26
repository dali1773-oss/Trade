"""Bitvavo, API pubblica delle candele (gratuita, SENZA chiave, sola lettura).

Doc: https://docs.bitvavo.com/  (GET /v2/{market}/candles)
Risposta: lista di [timestamp_ms, open, high, low, close, volume], dalla più
recente alla più vecchia, al massimo 1440 candele per richiesta.

Questo modulo non usa chiavi dell'exchange e non può inviare ordini.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from trade.ratelimit import MinIntervalLimiter
from trade.sources import SourceError

BASE_URL = "https://api.bitvavo.com/v2"
MAX_LIMIT = 1440
DAY_MS = 86_400_000


@dataclass(frozen=True)
class Candle:
    day: datetime  # apertura della candela, UTC
    open: float
    high: float
    low: float
    close: float
    volume: float


def parse_candles(payload: Any) -> list[Candle]:
    """Converte la risposta in candele ordinate dalla più vecchia. Scarta righe malformate."""
    if not isinstance(payload, list):
        raise SourceError("candles: attesa una lista")
    out: dict[int, Candle] = {}
    for row in payload:
        if not isinstance(row, list) or len(row) < 6:
            continue
        try:
            ts = int(row[0])
            o, h, lo, c, v = (float(x) for x in row[1:6])
        except (TypeError, ValueError):
            continue
        if min(o, h, lo, c) <= 0:
            continue
        out[ts] = Candle(datetime.fromtimestamp(ts / 1000, UTC), o, h, lo, c, v)
    return [out[k] for k in sorted(out)]


class BitvavoClient:
    def __init__(self, client: httpx.AsyncClient, limiter: MinIntervalLimiter | None = None) -> None:
        self.client = client
        # Il limite pubblico è ampio (1000 "pesi"/min); restiamo molto sotto.
        self.limiter = limiter or MinIntervalLimiter(0.5)

    async def candles(self, market: str, *, end_ms: int | None = None, limit: int = MAX_LIMIT) -> list[Candle]:
        params: dict[str, Any] = {"interval": "1d", "limit": min(limit, MAX_LIMIT)}
        if end_ms is not None:
            params["end"] = end_ms
        await self.limiter.wait()
        try:
            resp = await self.client.get(f"{BASE_URL}/{market}/candles", params=params)
        except httpx.HTTPError as exc:
            raise SourceError(f"bitvavo {market}: {exc}") from exc
        if resp.status_code != 200:
            raise SourceError(f"bitvavo {market}: HTTP {resp.status_code}")
        return parse_candles(resp.json())

    async def daily_history(self, market: str, *, max_pages: int = 10) -> list[Candle]:
        """Tutto lo storico giornaliero disponibile, andando indietro a pagine da 1440 giorni."""
        found: dict[datetime, Candle] = {}
        end_ms: int | None = None
        for _ in range(max_pages):
            page = await self.candles(market, end_ms=end_ms)
            new = [c for c in page if c.day not in found]
            for c in new:
                found[c.day] = c
            if len(page) < MAX_LIMIT or not new:
                break
            end_ms = int(page[0].day.timestamp() * 1000) - 1
        return [found[k] for k in sorted(found)]


CSV_FIELDS = ("day", "open", "high", "low", "close", "volume")


def save_csv(path: Path, candles: list[Candle]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_FIELDS)
        for c in candles:
            w.writerow([c.day.date().isoformat(), c.open, c.high, c.low, c.close, c.volume])


def load_csv(path: Path) -> list[Candle]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        Candle(
            datetime.fromisoformat(r["day"]).replace(tzinfo=UTC),
            float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"]),
        )
        for r in rows
    ]
