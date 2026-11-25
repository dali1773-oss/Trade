"""Backtest delle grandi cripto su Bitvavo (spot, SENZA leva). Sola lettura.

Domanda a cui risponde: una regola semplice batte il "compra e tieni" dopo le
commissioni vere? Se no, non ha senso automatizzarla.

Regole oneste del motore:
- la decisione usa solo i prezzi fino alla chiusura del giorno i ed è eseguita
  all'apertura del giorno i+1 (niente "sbirciare il futuro");
- ogni operazione paga commissione + margine di slippage;
- ordini sotto il minimo di Bitvavo (5 €) non vengono eseguiti;
- tutte le strategie partono lo stesso giorno, così il confronto è alla pari;
- le tasse (33%) non sono incluse: si pagano solo sul guadagno a fine anno.

Uso:  uv run trade-backtest                 (scarica lo storico se manca)
      uv run trade-backtest --refresh       (riscarica lo storico)
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from trade.sources import SourceError, make_client
from trade.sources.bitvavo import BitvavoClient, Candle, load_csv, save_csv

DEFAULT_MARKETS = ("BTC-EUR", "ETH-EUR", "SOL-EUR")
DEFAULT_DATA_DIR = Path("data/candles")
TAKER_FEE = 0.0025  # Bitvavo, fascia base (<100.000 €/mese), ordine a mercato
SLIPPAGE = 0.001  # margine prudenziale oltre la commissione
MIN_ORDER_EUR = 5.0

# Target(chiusure fino a oggi incluso) -> quota del capitale da tenere in cripto (0..1)
Target = Callable[[Sequence[float]], float]


@dataclass(frozen=True)
class Strategy:
    name: str
    target: Target
    lookback: int = 1  # giorni di storia necessari prima della prima decisione
    band: float = 0.0  # si opera solo se la quota si allontana dal target più di così


def buy_and_hold() -> Strategy:
    return Strategy("Compra e tieni", lambda closes: 1.0)


def trend(days: int) -> Strategy:
    """In cripto se il prezzo è sopra la media degli ultimi `days` giorni, altrimenti in euro."""
    def target(closes: Sequence[float]) -> float:
        avg = sum(closes[-days:]) / days
        return 1.0 if closes[-1] > avg else 0.0
    return Strategy(f"Tendenza (media {days} g)", target, lookback=days, band=0.5)


def rebalance(share: float = 0.5, band: float = 0.10) -> Strategy:
    """Tiene sempre `share` in cripto, riequilibrando quando si sposta di oltre `band`."""
    return Strategy(f"Ribilanciamento {int(share * 100)}/{int(100 - share * 100)}",
                    lambda closes: share, band=band)


def default_strategies() -> list[Strategy]:
    return [buy_and_hold(), trend(50), trend(100), trend(200), rebalance()]


@dataclass
class Result:
    strategy: str
    start_value: float
    final_value: float
    max_drawdown_pct: float
    trades: int
    costs_eur: float
    days: int
    time_in_market_pct: float

    @property
    def return_pct(self) -> float:
        return (self.final_value / self.start_value - 1) * 100

    @property
    def cagr_pct(self) -> float:
        years = self.days / 365.25
        if years <= 0 or self.final_value <= 0:
            return 0.0
        return ((self.final_value / self.start_value) ** (1 / years) - 1) * 100


def simulate(
    candles: Sequence[Candle],
    strategy: Strategy,
    *,
    start: int,
    capital: float = 100.0,
    fee: float = TAKER_FEE,
    slippage: float = SLIPPAGE,
    min_order: float = MIN_ORDER_EUR,
) -> Result:
    if start < strategy.lookback - 1:
        raise ValueError("start precede la storia necessaria alla strategia")
    if start >= len(candles) - 1:
        raise ValueError("storico troppo corto")
    closes = [c.close for c in candles]
    cash, units = capital, 0.0
    trades, costs, in_market_days = 0, 0.0, 0
    peak, max_dd = capital, 0.0
    cost_rate = fee + slippage
    for i in range(start, len(candles) - 1):
        target = min(max(strategy.target(closes[: i + 1]), 0.0), 1.0)
        price = candles[i + 1].open
        value = cash + units * price
        current = units * price / value if value > 0 else 0.0
        wanted = target - current
        must_move = (target == 0.0 and units > 0) or (target > 0 and current == 0.0)
        if abs(wanted) > strategy.band or (must_move and abs(wanted) > 1e-9):
            amount = wanted * value
            if abs(amount) >= min_order:
                cost = abs(amount) * cost_rate
                if amount > 0:  # compra
                    cash -= amount
                    units += (amount - cost) / price
                else:  # vende
                    units -= -amount / price
                    cash += -amount - cost
                units = max(units, 0.0)
                trades += 1
                costs += cost
        if units > 0:
            in_market_days += 1
        equity = cash + units * candles[i + 1].close
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
    days = (candles[-1].day - candles[start].day).days
    return Result(
        strategy=strategy.name,
        start_value=capital,
        final_value=cash + units * candles[-1].close,
        max_drawdown_pct=max_dd * 100,
        trades=trades,
        costs_eur=costs,
        days=days,
        time_in_market_pct=in_market_days * 100 / max(len(candles) - 1 - start, 1),
    )


def run_all(candles: Sequence[Candle], strategies: Sequence[Strategy], *, capital: float = 100.0,
            fee: float = TAKER_FEE, from_index: int | None = None) -> list[Result]:
    """Tutte le strategie dallo stesso giorno (dopo la storia più lunga richiesta)."""
    warmup = max(s.lookback for s in strategies) - 1
    start = warmup if from_index is None else max(from_index, warmup)
    return [simulate(candles, s, start=start, capital=capital, fee=fee) for s in strategies]


def index_days_ago(candles: Sequence[Candle], days: int) -> int:
    cutoff = candles[-1].day - timedelta(days=days)
    for i, c in enumerate(candles):
        if c.day >= cutoff:
            return i
    return len(candles) - 1


def format_table(title: str, results: Sequence[Result]) -> str:
    first = results[0]
    lines = [
        title,
        f"  {'strategia':<26}{'finale €':>10}{'resa':>9}{'annua':>8}{'calo max':>10}{'operaz.':>9}{'costi €':>9}{'investito':>11}",
    ]
    for r in results:
        lines.append(
            f"  {r.strategy:<26}{r.final_value:>10.2f}{r.return_pct:>8.1f}%{r.cagr_pct:>7.1f}%"
            f"{-r.max_drawdown_pct:>9.1f}%{r.trades:>9}{r.costs_eur:>9.2f}{r.time_in_market_pct:>10.0f}%"
        )
    best = max(results, key=lambda r: r.final_value)
    verdict = ("nessuna regola batte il compra e tieni" if best is first
               else f"meglio del compra e tieni: {best.strategy}")
    lines.append(f"  → {verdict} (giorni: {first.days})")
    return "\n".join(lines)


async def load_history(market: str, data_dir: Path, refresh: bool) -> list[Candle]:
    path = data_dir / f"{market}_1d.csv"
    if path.exists() and not refresh:
        return load_csv(path)
    async with make_client() as client:
        candles = await BitvavoClient(client).daily_history(market)
    if not candles:
        raise SourceError(f"{market}: nessuna candela")
    save_csv(path, candles)
    return candles


async def _main_async(args: argparse.Namespace) -> int:
    print(f"Capitale simulato {args.capital:.0f} €, commissione {args.fee}% + slippage {SLIPPAGE * 100}%, "
          f"niente leva, tasse escluse.\n")
    status = 0
    for market in args.markets:
        try:
            candles = await load_history(market, args.data_dir, args.refresh)
        except SourceError as exc:
            print(f"{market}: dati non disponibili ({exc})\n")
            status = 1
            continue
        strategies = default_strategies()
        print(f"=== {market}: {len(candles)} giorni, dal {candles[0].day.date()} al {candles[-1].day.date()} ===")
        print(format_table("Tutto il periodo", run_all(candles, strategies, capital=args.capital,
                                                       fee=args.fee / 100)))
        recent = index_days_ago(candles, 365)
        print(format_table("Ultimi 365 giorni", run_all(candles, strategies, capital=args.capital,
                                                        fee=args.fee / 100, from_index=recent)))
        print()
    return status


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Backtest grandi cripto su Bitvavo (spot, senza leva, sola lettura).")
    p.add_argument("--markets", nargs="+", default=list(DEFAULT_MARKETS))
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--refresh", action="store_true", help="riscarica lo storico da Bitvavo")
    p.add_argument("--capital", type=float, default=100.0)
    p.add_argument("--fee", type=float, default=TAKER_FEE * 100, help="commissione per operazione in %%")
    return p


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main_async(build_parser().parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
