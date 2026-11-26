"""Simulazione ombra (shadow) delle grandi cripto su Bitvavo. SENZA SOLDI, sola lettura.

Le regole e i parametri vengono congelati al primo avvio (file `data/shadow.json`).
Da quel giorno in poi, ad ogni esecuzione, il comando riscarica i prezzi pubblici e
rifà i conti dal giorno di partenza: decisione alla chiusura di un giorno,
esecuzione all'apertura del successivo, con commissioni e slippage.

Siccome i conti partono sempre dal giorno di partenza, non importa se il comando
salta qualche giorno (Mac spento, ecc.): il risultato è lo stesso che si avrebbe
eseguendolo ogni giorno. La candela del giorno in corso non viene mai usata,
perché il suo prezzo di chiusura non è ancora definitivo.

Nessuna chiave dell'exchange, nessun ordine: è solo un quaderno di prova.

Uso:  uv run trade-shadow
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from trade.backtest import TAKER_FEE, Result, Strategy, buy_and_hold, simulate, trend
from trade.sources import SourceError, make_client
from trade.sources.bitvavo import BitvavoClient, Candle, save_csv

DEFAULT_CONFIG = Path("data/shadow.json")
DEFAULT_DATA_DIR = Path("data/candles")
DEFAULT_MARKETS = ("BTC-EUR", "ETH-EUR", "SOL-EUR")
STRATEGY_FACTORIES = {
    "buy_hold": buy_and_hold,
    "trend50": lambda: trend(50),
    "trend200": lambda: trend(200),
}


def completed(candles: Sequence[Candle], now: datetime) -> list[Candle]:
    """Solo le candele di giorni già chiusi (in UTC)."""
    return [c for c in candles if c.day + timedelta(days=1) <= now]


def new_config(last_closed: date, *, capital: float = 100.0, markets: Sequence[str] = DEFAULT_MARKETS,
               now: datetime | None = None) -> dict:
    return {
        "start_day": last_closed.isoformat(),  # prima decisione alla chiusura di questo giorno
        "capital_eur": capital,
        "fee": TAKER_FEE,
        "markets": list(markets),
        "strategies": list(STRATEGY_FACTORIES),
        "frozen_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "note": "Parametri congelati: non modificare senza nuovo backtest e approvazione di Danish.",
    }


def load_or_create_config(path: Path, last_closed: date, now: datetime) -> tuple[dict, bool]:
    if path.exists():
        return json.loads(path.read_text()), False
    cfg = new_config(last_closed, now=now)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    return cfg, True


def strategies_from(cfg: dict) -> list[Strategy]:
    unknown = [s for s in cfg["strategies"] if s not in STRATEGY_FACTORIES]
    if unknown:
        raise ValueError(f"strategie sconosciute nel file shadow: {unknown}")
    return [STRATEGY_FACTORIES[s]() for s in cfg["strategies"]]


def start_index(candles: Sequence[Candle], start_day: date) -> int | None:
    for i, c in enumerate(candles):
        if c.day.date() == start_day:
            return i
    return None


def signal(candles: Sequence[Candle], strategy: Strategy) -> str:
    target = strategy.target([c.close for c in candles])
    return "in cripto" if target >= 0.5 else "in euro"


def market_report(market: str, candles: Sequence[Candle], cfg: dict) -> str:
    strategies = strategies_from(cfg)
    start_day = date.fromisoformat(cfg["start_day"])
    idx = start_index(candles, start_day)
    lines = [f"=== {market} (ultimo giorno chiuso {candles[-1].day.date()}, prezzo {candles[-1].close:,.2f} €) ==="]
    if idx is None:
        lines.append(f"  giorno di partenza {start_day} non trovato nello storico: nessun conto (fail-closed)")
        return "\n".join(lines)
    for s in strategies:
        sig = signal(candles, s)
        if idx >= len(candles) - 1:
            lines.append(f"  {s.name:<26} appena partita, prossima mossa: {sig}")
            continue
        r: Result = simulate(candles, s, start=idx, capital=cfg["capital_eur"], fee=cfg["fee"])
        lines.append(
            f"  {s.name:<26} {r.final_value:>8.2f} € ({r.return_pct:+.1f}%), calo max {-r.max_drawdown_pct:.1f}%, "
            f"operazioni {r.trades}, ora: {sig}"
        )
    return "\n".join(lines)


async def fetch_recent(market: str, data_dir: Path) -> list[Candle]:
    async with make_client() as client:
        candles = await BitvavoClient(client).daily_history(market, max_pages=1)
    if candles:
        save_csv(data_dir / f"{market}_1d.csv", candles)
    return candles


async def _main_async(args: argparse.Namespace, now: datetime | None = None, fetch=fetch_recent) -> int:
    now = now or datetime.now(UTC)
    histories: dict[str, list[Candle]] = {}
    status = 0
    markets = list(DEFAULT_MARKETS)
    if args.config.exists():
        markets = json.loads(args.config.read_text())["markets"]
    for market in markets:
        try:
            histories[market] = completed(await fetch(market, args.data_dir), now)
        except SourceError as exc:
            print(f"{market}: prezzi non disponibili ({exc}), salto")
            status = 1
    if not histories or not any(histories.values()):
        print("Nessun prezzo disponibile: nessun calcolo (fail-closed).")
        return 1
    last_closed = max(h[-1].day.date() for h in histories.values() if h)
    cfg, created = load_or_create_config(args.config, last_closed, now)
    print("Simulazione ombra: soldi finti, nessun ordine. Capitale finto "
          f"{cfg['capital_eur']:.0f} € per ogni strategia e moneta, partenza {cfg['start_day']}.")
    if created:
        print(f"Primo avvio: regole congelate in {args.config}.")
    print()
    for market, candles in histories.items():
        if not candles:
            continue
        print(market_report(market, candles, cfg))
    return status


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Simulazione ombra grandi cripto (soldi finti, sola lettura).")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    return p


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main_async(build_parser().parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
