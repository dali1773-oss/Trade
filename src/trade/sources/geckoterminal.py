"""GeckoTerminal API pubblica. Doc: https://docs.coingecko.com/docs/keyless-public-api

Senza chiave il limite è circa 5 chiamate/min (dinamico) e la stessa doc dice che
non è adatta alla produzione: qui la usiamo con un intervallo minimo di 20 s.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from trade.models import PoolSnapshot, to_decimal, to_int
from trade.ratelimit import MinIntervalLimiter
from trade.sources import SourceError

BASE_URL = "https://api.geckoterminal.com/api/v2"
SOURCE = "geckoterminal"


def _strip_prefix(gt_id: Any, network: str) -> str | None:
    if not isinstance(gt_id, str):
        return None
    prefix = f"{network}_"
    return gt_id[len(prefix):] if gt_id.startswith(prefix) else gt_id


def _rel_id(item: dict[str, Any], name: str) -> Any:
    rel = (item.get("relationships") or {}).get(name) or {}
    return (rel.get("data") or {}).get("id")


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_pools(
    payload: Any, *, network: str = "solana", observed_at: datetime | None = None
) -> list[PoolSnapshot]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise SourceError("new_pools: atteso un oggetto con 'data' lista")
    observed_at = observed_at or datetime.now(UTC)
    snapshots: list[PoolSnapshot] = []
    for item in payload["data"]:
        if not isinstance(item, dict):
            continue
        attrs = item.get("attributes") or {}
        pool = attrs.get("address") or _strip_prefix(item.get("id"), network)
        base = _strip_prefix(_rel_id(item, "base_token"), network)
        if not pool or not base:
            continue
        volume = attrs.get("volume_usd") or {}
        tx = attrs.get("transactions") or {}
        name = attrs.get("name")
        snapshots.append(
            PoolSnapshot(
                source=SOURCE,
                chain=network,
                dex=_rel_id(item, "dex"),
                pool_address=pool,
                base_token=base,
                quote_token=_strip_prefix(_rel_id(item, "quote_token"), network),
                base_symbol=name.split(" / ")[0] if isinstance(name, str) else None,
                price_usd=to_decimal(attrs.get("base_token_price_usd")),
                price_native=to_decimal(attrs.get("base_token_price_native_currency")),
                liquidity_usd=to_decimal(attrs.get("reserve_in_usd")),
                fdv_usd=to_decimal(attrs.get("fdv_usd")),
                volume_m5_usd=to_decimal(volume.get("m5")),
                volume_h1_usd=to_decimal(volume.get("h1")),
                volume_h24_usd=to_decimal(volume.get("h24")),
                buys_m5=to_int((tx.get("m5") or {}).get("buys")),
                sells_m5=to_int((tx.get("m5") or {}).get("sells")),
                buys_h1=to_int((tx.get("h1") or {}).get("buys")),
                sells_h1=to_int((tx.get("h1") or {}).get("sells")),
                pool_created_at=_parse_time(attrs.get("pool_created_at")),
                observed_at=observed_at,
                extra={"unique_traders_h1": to_int((tx.get("h1") or {}).get("unique_traders"))},
            )
        )
    return snapshots


class GeckoTerminalClient:
    def __init__(
        self, client: httpx.AsyncClient, limiter: MinIntervalLimiter | None = None
    ) -> None:
        self._client = client
        self._limiter = limiter or MinIntervalLimiter(20.0)

    async def new_pools(self, network: str = "solana") -> list[PoolSnapshot]:
        path = f"/networks/{network}/new_pools"
        await self._limiter.wait()
        try:
            response = await self._client.get(BASE_URL + path)
        except httpx.HTTPError as exc:
            raise SourceError(f"{SOURCE}: errore di rete su {path}: {exc}") from exc
        if response.status_code == 429:
            self._limiter.penalize(120)
            raise SourceError(f"{SOURCE}: limite di richieste superato (429)")
        if response.status_code != 200:
            raise SourceError(f"{SOURCE}: HTTP {response.status_code} su {path}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError(f"{SOURCE}: risposta non JSON") from exc
        return parse_pools(payload, network=network)
