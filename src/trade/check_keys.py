"""Controlla che le chiavi API salvate funzionino, SENZA mai mostrarle.

Uso:  uv run trade-check-keys

Fa solo richieste di lettura (Helius getHealth, Jupiter quotazione SOL->USDC). Stampa OK o il tipo di errore.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import httpx

from trade.config import DEFAULT_FILE, load_settings, redact
from trade.sources import make_client

HELIUS_RPC = "https://mainnet.helius-rpc.com/"
JUPITER_QUOTE = "https://api.jup.ag/swap/v1/quote"
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWvd5wAvzSyT3hDtFGgEWTLkVqQKmSHjCvG5UpUCZ"


async def check_helius(client: httpx.AsyncClient, key: str | None) -> str:
    if not key:
        return "MANCANTE (HELIUS_API_KEY non impostata)"
    try:
        r = await client.post(
            HELIUS_RPC,
            params={"api-key": key},
            json={"jsonrpc": "2.0", "id": 1, "method": "getHealth"},
        )
    except httpx.HTTPError as exc:
        # Il messaggio di httpx può contenere l'URL con la chiave: lo copriamo.
        return "ERRORE DI RETE (" + redact(type(exc).__name__, [key]) + ")"
    if r.status_code in (401, 403):
        return f"CHIAVE NON VALIDA (HTTP {r.status_code})"
    if r.status_code == 429:
        return "LIMITE RICHIESTE RAGGIUNTO (HTTP 429), riprova tra poco"
    if r.status_code != 200:
        return f"ERRORE HTTP {r.status_code}"
    try:
        result = r.json().get("result")
    except ValueError:
        return "RISPOSTA NON VALIDA"
    return "OK" if result == "ok" else "RISPOSTA INATTESA"


async def check_jupiter(client: httpx.AsyncClient, key: str | None) -> str:
    if not key:
        return "MANCANTE (JUPITER_API_KEY non impostata)"
    try:
        r = await client.get(
            JUPITER_QUOTE,
            headers={"x-api-key": key},
            params={"inputMint": SOL_MINT, "outputMint": USDC_MINT, "amount": "1000000", "slippageBps": "50"},
        )
    except httpx.HTTPError as exc:
        return "ERRORE DI RETE (" + redact(type(exc).__name__, [key]) + ")"
    if r.status_code in (401, 403):
        return f"CHIAVE NON VALIDA (HTTP {r.status_code})"
    if r.status_code == 429:
        return "LIMITE RICHIESTE RAGGIUNTO (HTTP 429), riprova tra poco"
    if r.status_code != 200:
        return f"ERRORE HTTP {r.status_code}"
    try:
        out = r.json().get("outAmount")
    except ValueError:
        return "RISPOSTA NON VALIDA"
    return "OK" if out else "RISPOSTA INATTESA"


async def run(path: Path, transport: httpx.AsyncBaseTransport | None = None) -> dict[str, str]:
    settings = load_settings(path)
    async with make_client(transport) as client:
        return {
            "Helius": await check_helius(client, settings.get("HELIUS_API_KEY")),
            "Jupiter": await check_jupiter(client, settings.get("JUPITER_API_KEY")),
        }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Controlla le chiavi API senza mostrarle.")
    p.add_argument("--file", type=Path, default=DEFAULT_FILE)
    p.add_argument("--only", choices=["helius", "jupiter"], help="codice di uscita solo per questa fonte")
    args = p.parse_args(argv)
    results = asyncio.run(run(args.file))
    for name, status in results.items():
        print(f"{name}: {status}")
    only = args.only
    checked = {k: v for k, v in results.items() if only is None or k.lower() == only.lower()}
    return 0 if all(s == "OK" for s in checked.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
