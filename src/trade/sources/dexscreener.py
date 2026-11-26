"""DexScreener API (gratuita, senza chiave). Doc: https://docs.dexscreener.com/api/reference

Limiti documentati: 60 richieste/min per i profili. Per gli altri endpoint
usiamo comunque un intervallo prudente.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from trade.models import PoolSnapshot, TokenProfile, to_decimal, to_int
from trade.ratelimit import MinIntervalLimiter
from trade.sources import SourceError

BASE_URL = "https://api.dexscreener.com"
SOURCE = "dexscreener"


def _now() -> datetime:
    return datetime.now(UTC)


def parse_token_profiles(
    payload: Any, *, chain: str | None = "solana", observed_at: datetime | None = None
) -> list[TokenProfile]:
    if not isinstance(payload, list):
        raise SourceError("token-profiles: attesa una lista")
    observed_at = observed_at or _now()
    profiles: list[TokenProfile] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        item_chain = item.get("chainId")
        address = item.get("tokenAddress")
        if not item_chain or not address:
            continue
        if chain is not None and item_chain != chain:
            continue
        links = tuple(
            link["url"]
            for link in item.get("links") or []
            if isinstance(link, dict) and isinstance(link.get("url"), str)
        )
        profiles.append(
            TokenProfile(
                source=SOURCE,
                chain=item_chain,
                token_address=address,
                url=item.get("url"),
                description=item.get("description"),
                links=links,
                observed_at=observed_at,
            )
        )
    return profiles


def _nested(item: dict[str, Any], *keys: str) -> Any:
    current: Any = item
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def parse_pairs(payload: Any, *, observed_at: datetime | None = None) -> list[PoolSnapshot]:
    if not isinstance(payload, list):
        raise SourceError("token-pairs: attesa una lista")
    observed_at = observed_at or _now()
    snapshots: list[PoolSnapshot] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        pair = item.get("pairAddress")
        base = _nested(item, "baseToken", "address")
        if not pair or not base or not item.get("chainId"):
            continue
        created_ms = to_int(item.get("pairCreatedAt"))
        snapshots.append(
            PoolSnapshot(
                source=SOURCE,
                chain=item["chainId"],
                dex=item.get("dexId"),
                pool_address=pair,
                base_token=base,
                quote_token=_nested(item, "quoteToken", "address"),
                base_symbol=_nested(item, "baseToken", "symbol"),
                price_usd=to_decimal(item.get("priceUsd")),
                price_native=to_decimal(item.get("priceNative")),
                liquidity_usd=to_decimal(_nested(item, "liquidity", "usd")),
                fdv_usd=to_decimal(item.get("fdv")),
                volume_m5_usd=to_decimal(_nested(item, "volume", "m5")),
                volume_h1_usd=to_decimal(_nested(item, "volume", "h1")),
                volume_h24_usd=to_decimal(_nested(item, "volume", "h24")),
                buys_m5=to_int(_nested(item, "txns", "m5", "buys")),
                sells_m5=to_int(_nested(item, "txns", "m5", "sells")),
                buys_h1=to_int(_nested(item, "txns", "h1", "buys")),
                sells_h1=to_int(_nested(item, "txns", "h1", "sells")),
                pool_created_at=(
                    datetime.fromtimestamp(created_ms / 1000, UTC) if created_ms else None
                ),
                observed_at=observed_at,
                extra={
                    "labels": item.get("labels") or [],
                    # Quantità del token di quotazione (USDC, SOL…) nel pool: i "soldi veri".
                    "liquidity_quote": _nested(item, "liquidity", "quote"),
                },
            )
        )
    return snapshots


class DexScreenerClient:
    def __init__(
        self, client: httpx.AsyncClient, limiter: MinIntervalLimiter | None = None
    ) -> None:
        self._client = client
        # 60/min documentati -> 1 richiesta ogni 1,5 s per stare larghi.
        self._limiter = limiter or MinIntervalLimiter(1.5)

    async def _get(self, path: str) -> Any:
        await self._limiter.wait()
        try:
            response = await self._client.get(BASE_URL + path)
        except httpx.HTTPError as exc:
            raise SourceError(f"{SOURCE}: errore di rete su {path}: {exc}") from exc
        if response.status_code == 429:
            self._limiter.penalize(60)
            raise SourceError(f"{SOURCE}: limite di richieste superato (429) su {path}")
        if response.status_code != 200:
            raise SourceError(f"{SOURCE}: HTTP {response.status_code} su {path}")
        try:
            return response.json()
        except ValueError as exc:
            raise SourceError(f"{SOURCE}: risposta non JSON su {path}") from exc

    async def latest_token_profiles(self, chain: str = "solana") -> list[TokenProfile]:
        return parse_token_profiles(await self._get("/token-profiles/latest/v1"), chain=chain)

    async def token_pairs(self, token_address: str, chain: str = "solana") -> list[PoolSnapshot]:
        return parse_pairs(await self._get(f"/token-pairs/v1/{chain}/{token_address}"))
