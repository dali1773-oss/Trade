"""Etichettatura (Fase 3): i verdetti anti-truffa avevano ragione?

Per ogni token con un verdetto vecchio almeno `--horizon` ore, chiede a
DexScreener (gratis, senza chiave) com'è messo adesso e lo etichetta:

- MORTO: nessun pool, liquidità sotto 1.000 $, oppure prezzo crollato del 90% o più;
- VIVO: tutto il resto.

Poi stampa la tabella verdetto × esito:
- PASS ma MORTO  = falso negativo (avremmo comprato una truffa/un token morto) → il dato più importante;
- FAIL/UNKNOWN ma VIVO = possibile falso positivo (occasione persa, costa meno).

Uso:  uv run trade-label            (24 ore)
      uv run trade-label --horizon 168   (7 giorni)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections import Counter
from decimal import Decimal
from pathlib import Path

import httpx

from trade.models import to_decimal
from trade.sources import SourceError, make_client
from trade.sources.dexscreener import DexScreenerClient
from trade.store import Store

CHAIN = "solana"
DEAD_LIQUIDITY_USD = Decimal("1000")
DEAD_PRICE_RATIO = Decimal("0.10")


def classify(
    price_then: Decimal | None, price_now: Decimal | None, liquidity_now: Decimal | None, has_pool: bool
) -> tuple[str, Decimal | None, str]:
    if not has_pool:
        return "MORTO", None, "nessun pool"
    if liquidity_now is not None and liquidity_now < DEAD_LIQUIDITY_USD:
        return "MORTO", None, f"liquidità {liquidity_now} $"
    ratio = None
    if price_then and price_then > 0 and price_now is not None:
        ratio = (price_now / price_then).quantize(Decimal("0.0001"))
        if ratio <= DEAD_PRICE_RATIO:
            return "MORTO", ratio, f"prezzo x{ratio}"
    return "VIVO", ratio, "ok"


async def label_batch(
    store: Store, ds: DexScreenerClient, horizon_h: int, limit: int
) -> tuple[int, int]:
    done = errors = 0
    for row in store.checks_to_label(CHAIN, horizon_h, limit):
        token = row["token_address"]
        try:
            pairs = await ds.token_pairs(token, CHAIN)
        except SourceError:
            errors += 1
            continue
        same = [p for p in pairs if p.pool_address == row["pool_address"]]
        pool = same[0] if same else (max(pairs, key=lambda p: p.liquidity_usd or 0) if pairs else None)
        outcome, ratio, detail = classify(
            to_decimal(row["price_usd"]),
            pool.price_usd if pool else None,
            pool.liquidity_usd if pool else None,
            pool is not None,
        )
        store.add_label(CHAIN, token, horizon_h, outcome, price_ratio=ratio,
                        liquidity_usd=pool.liquidity_usd if pool else None, detail=detail)
        done += 1
    return done, errors


def format_matrix(matrix: dict[tuple[str, str], int], horizon_h: int) -> str:
    lines = [f"Esito dopo {horizon_h} ore      VIVO   MORTO"]
    for verdict in ("PASS", "FAIL", "UNKNOWN"):
        v, m = matrix.get((verdict, "VIVO"), 0), matrix.get((verdict, "MORTO"), 0)
        lines.append(f"  verdetto {verdict:<8} {v:>6} {m:>7}")
    fn = matrix.get(("PASS", "MORTO"), 0)
    lines.append(f"Falsi negativi (PASS ma MORTO): {fn}")
    return "\n".join(lines)


def check_name(reason: str) -> str:
    """'concentrazione_top10: top 10 holder = 45%' -> 'concentrazione_top10'."""
    return reason.split(":", 1)[0].strip()


def explain(rows) -> str:
    """Quali regole bloccano token che poi sopravvivono (possibili regole troppo severe).

    Per ogni regola: quante volte ha bloccato, quanti di quei token erano MORTI dopo
    l'orizzonte e quanti VIVI. Una regola con molti VIVI merita di essere studiata.
    "Unico blocco" = la regola era l'unico motivo: allentandola, quel token sarebbe passato.
    """
    fired: Counter = Counter()
    dead: Counter = Counter()
    sole_alive: Counter = Counter()
    survivors = []
    for r in rows:
        if r["verdict"] == "PASS":
            continue
        names = sorted({check_name(x) for x in json.loads(r["reasons"] or "[]")}) or ["(nessun motivo)"]
        for n in names:
            fired[n] += 1
            if r["outcome"] == "MORTO":
                dead[n] += 1
        if r["outcome"] == "VIVO":
            survivors.append((r["token_address"], r["verdict"], names, r["price_ratio"]))
            if len(names) == 1:
                sole_alive[names[0]] += 1
    lines = ["Regole che hanno bloccato (FAIL/UNKNOWN) e cosa è successo dopo:",
             f"  {'regola':<24}{'bloccati':>9}{'morti':>7}{'vivi':>6}{'% morti':>9}{'unico blocco e vivo':>21}"]
    for n, k in fired.most_common():
        lines.append(f"  {n:<24}{k:>9}{dead[n]:>7}{k - dead[n]:>6}{dead[n] * 100 / k:>8.0f}%{sole_alive[n]:>21}")
    lines.append(f"Token bloccati ma vivi: {len(survivors)}")
    for token, verdict, names, ratio in survivors:
        lines.append(f"  {token[:8]}… {verdict:<8} prezzo x{ratio or '?'}  motivi: {', '.join(names)}")
    return "\n".join(lines)


async def _main_async(args: argparse.Namespace, transport: httpx.AsyncBaseTransport | None = None) -> int:
    store = Store(args.db)
    async with make_client(transport) as client:
        done, errors = await label_batch(store, DexScreenerClient(client), args.horizon, args.limit)
    store.log_event("label", {"horizon_h": args.horizon, "labeled": done, "errors": errors})
    print(f"Etichettati ora: {done} (errori: {errors})")
    print(format_matrix(store.label_matrix(args.horizon), args.horizon))
    if args.explain:
        print()
        print(explain(store.labeled_checks(args.horizon)))
    store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Etichetta i verdetti anti-truffa (sola lettura, DexScreener).")
    p.add_argument("--db", type=Path, default=Path("data/recorder.sqlite"))
    p.add_argument("--horizon", type=int, default=24, help="ore dopo il verdetto (24 o 168)")
    p.add_argument("--limit", type=int, default=200, help="massimo token da etichettare in questa esecuzione")
    p.add_argument("--explain", action="store_true", help="mostra quali regole bloccano token che poi sopravvivono")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    return asyncio.run(_main_async(build_parser().parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
