"""Modelli dei dati normalizzati, comuni a tutte le fonti.

I valori numerici delle API arrivano come stringhe o numeri: qui diventano
Decimal (prezzi, importi) per non perdere precisione. Un campo mancante resta
None: chi legge deve trattarlo come "sconosciuto", mai come zero.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def to_decimal(value: Any) -> Decimal | None:
    """Converte stringhe/numeri in Decimal; None o valori non validi -> None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def to_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class TokenProfile(BaseModel):
    """Un token appena comparso o aggiornato (es. profili DexScreener)."""

    model_config = ConfigDict(frozen=True)

    source: str
    chain: str
    token_address: str
    url: str | None = None
    description: str | None = None
    links: tuple[str, ...] = ()
    observed_at: datetime


class PoolSnapshot(BaseModel):
    """Fotografia di un pool di liquidità in un istante."""

    model_config = ConfigDict(frozen=True)

    source: str
    chain: str
    dex: str | None = None
    pool_address: str
    base_token: str
    quote_token: str | None = None
    base_symbol: str | None = None
    price_usd: Decimal | None = None
    price_native: Decimal | None = None
    liquidity_usd: Decimal | None = None
    fdv_usd: Decimal | None = None
    volume_m5_usd: Decimal | None = None
    volume_h1_usd: Decimal | None = None
    volume_h24_usd: Decimal | None = None
    buys_m5: int | None = None
    sells_m5: int | None = None
    buys_h1: int | None = None
    sells_h1: int | None = None
    pool_created_at: datetime | None = None
    observed_at: datetime
    extra: dict[str, Any] = Field(default_factory=dict)
