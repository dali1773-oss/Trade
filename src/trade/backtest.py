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
from dataclasses import dataclass, field
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
    equity: list[float] = field(default_factory=list, repr=False)  # valore a fine di ogni giorno

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
    curve: list[float] = []
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
        curve.append(equity)
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
        equity=curve,
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


def align(histories: dict[str, Sequence[Candle]]) -> dict[str, list[Candle]]:
    """Tiene solo i giorni presenti in tutte le monete (il mix parte quando c'è l'ultima arrivata)."""
    common = set.intersection(*(set(c.day for c in h) for h in histories.values()))
    return {m: [c for c in h if c.day in common] for m, h in histories.items()}


def max_drawdown_pct(curve: Sequence[float], start: float) -> float:
    peak, dd = start, 0.0
    for v in curve:
        peak = max(peak, v)
        dd = max(dd, (peak - v) / peak)
    return dd * 100


def portfolio_results(histories: dict[str, Sequence[Candle]], strategies: Sequence[Strategy], *,
                      capital: float = 100.0, fee: float = TAKER_FEE,
                      from_index: int | None = None) -> list[Result]:
    """Mix a quote uguali: ogni moneta riceve capital/n all'inizio e segue la stessa regola."""
    aligned = align(histories)
    n = len(aligned)
    per_market = {m: run_all(c, strategies, capital=capital / n, fee=fee, from_index=from_index)
                  for m, c in aligned.items()}
    out = []
    for k, s in enumerate(strategies):
        parts = [per_market[m][k] for m in aligned]
        curve = [sum(vals) for vals in zip(*(p.equity for p in parts))]
        out.append(Result(
            strategy=s.name, start_value=capital, final_value=sum(p.final_value for p in parts),
            max_drawdown_pct=max_drawdown_pct(curve, capital), trades=sum(p.trades for p in parts),
            costs_eur=sum(p.costs_eur for p in parts), days=parts[0].days,
            time_in_market_pct=sum(p.time_in_market_pct for p in parts) / n, equity=curve,
        ))
    return out


STRESS_FEE = 0.01  # 1% per operazione: costi molto peggiori del previsto


@dataclass
class OutOfSample:
    split_day: str
    chosen: str
    chosen_in_sample_pct: float
    chosen_after: Result
    buy_hold_after: Result


def out_of_sample(candles: Sequence[Candle], strategies: Sequence[Strategy], *, capital: float = 100.0,
                  fee: float = TAKER_FEE) -> OutOfSample:
    """Sceglie la strategia migliore sulla prima metà e la giudica sulla seconda, mai vista."""
    mid = len(candles) // 2
    first = run_all(candles[: mid + 1], strategies, capital=capital, fee=fee)
    best = max(range(len(strategies)), key=lambda k: first[k].final_value)
    second = run_all(candles, strategies, capital=capital, fee=fee, from_index=mid)
    bh = next(k for k, s in enumerate(strategies) if s.name == buy_and_hold().name)
    return OutOfSample(str(candles[mid].day.date()), strategies[best].name, first[best].return_pct,
                       second[best], second[bh])


def format_out_of_sample(o: OutOfSample) -> str:
    if o.chosen == buy_and_hold().name:
        verdict = "sulla prima metà vinceva già il compra e tieni: nessuna regola da usare"
    elif o.chosen_after.final_value > o.buy_hold_after.final_value:
        verdict = "regge anche sui dati mai visti" + (" (ma perde comunque soldi)" if o.chosen_after.return_pct < 0 else "")
    else:
        verdict = "NON regge sui dati mai visti"
    return (
        f"Prova fuori campione (scelta prima del {o.split_day}, verifica dopo)\n"
        f"  scelta: {o.chosen} (prima metà {o.chosen_in_sample_pct:+.1f}%)\n"
        f"  seconda metà: {o.chosen_after.return_pct:+.1f}% (calo max {-o.chosen_after.max_drawdown_pct:.1f}%)"
        f" contro compra e tieni {o.buy_hold_after.return_pct:+.1f}% (calo max {-o.buy_hold_after.max_drawdown_pct:.1f}%)\n"
        f"  → {verdict}"
    )


def format_stress(candles: Sequence[Candle], strategies: Sequence[Strategy], *, capital: float,
                  fee: float) -> str:
    rs = run_all(candles, strategies, capital=capital, fee=fee)
    cells = ", ".join(f"{r.strategy} {r.return_pct:+.0f}%" for r in rs)
    return f"Con costi all'{fee * 100:.0f}% per operazione: {cells}"


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
    loaded: dict[str, list[Candle]] = {}
    strategies = default_strategies()
    for market in args.markets:
        try:
            candles = await load_history(market, args.data_dir, args.refresh)
        except SourceError as exc:
            print(f"{market}: dati non disponibili ({exc})\n")
            status = 1
            continue
        loaded[market] = candles
        print(f"=== {market}: {len(candles)} giorni, dal {candles[0].day.date()} al {candles[-1].day.date()} ===")
        print(format_table("Tutto il periodo", run_all(candles, strategies, capital=args.capital,
                                                       fee=args.fee / 100)))
        recent = index_days_ago(candles, 365)
        print(format_table("Ultimi 365 giorni", run_all(candles, strategies, capital=args.capital,
                                                        fee=args.fee / 100, from_index=recent)))
        print(format_out_of_sample(out_of_sample(candles, strategies, capital=args.capital, fee=args.fee / 100)))
        print(format_stress(candles, strategies, capital=args.capital, fee=STRESS_FEE))
        print()
    for mix in mixes(list(loaded)):
        print_mix(mix, {m: loaded[m] for m in mix}, strategies, args)
    return status


def mixes(markets: list[str]) -> list[list[str]]:
    """Il mix di tutte le monete e, se c'è SOL (storia più corta), anche quello senza SOL."""
    out = [markets] if len(markets) >= 2 else []
    without_sol = [m for m in markets if not m.startswith("SOL-")]
    if len(without_sol) >= 2 and without_sol != markets:
        out.append(without_sol)
    return out


def print_mix(mix: list[str], histories: dict[str, list[Candle]], strategies: Sequence[Strategy],
              args: argparse.Namespace) -> None:
    aligned = align(histories)
    days = next(iter(aligned.values()))
    if len(days) < max(s.lookback for s in strategies) + 2:
        print(f"=== Mix {' + '.join(mix)}: storia comune troppo corta ===\n")
        return
    fee = args.fee / 100
    print(f"=== Mix a quote uguali {' + '.join(mix)}: dal {days[0].day.date()} al {days[-1].day.date()} ===")
    print(format_table("Tutto il periodo", portfolio_results(aligned, strategies, capital=args.capital, fee=fee)))
    recent = index_days_ago(days, 365)
    print(format_table("Ultimi 365 giorni", portfolio_results(aligned, strategies, capital=args.capital,
                                                              fee=fee, from_index=recent)))
    stress = portfolio_results(aligned, strategies, capital=args.capital, fee=STRESS_FEE)
    print(f"Con costi all'{STRESS_FEE * 100:.0f}% per operazione: "
          + ", ".join(f"{r.strategy} {r.return_pct:+.0f}%" for r in stress))
    print()


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
