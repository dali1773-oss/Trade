"""Client delle fonti dati (sola lettura)."""

from __future__ import annotations

import httpx

USER_AGENT = "trade-recorder/0.0.1"
DEFAULT_TIMEOUT_S = 15.0


class SourceError(Exception):
    """Errore di una fonte dati: la richiesta non ha prodotto dati validi."""


def make_client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=DEFAULT_TIMEOUT_S,
        transport=transport,
    )
