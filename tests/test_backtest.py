"""Backtest e client Bitvavo: dati finti, nessuna rete."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from trade.backtest import (
    Strategy, buy_and_hold, format_table, index_days_ago, rebalance, run_all, simulate, trend,
)
from trade.ratelimit import MinIntervalLimiter
from trade.sources import SourceError, make_client
from trade.sources.bitvavo import DAY_MS, BitvavoClient, Candle, load_csv, parse_candles, save_csv

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def series(closes):
    """Candele in cui l'apertura di oggi = chiusura di ieri."""
    out, prev = [], closes[0]
    for i, c in enumerate(closes):
        out.append(Candle(T0 + timedelta(days=i), prev, max(prev, c), min(prev, c), c, 1.0))
        prev = c
    return out


def test_buy_and_hold_pays_fee_once():
    candles = series([100, 100, 200])
    r = simulate(candles, buy_and_hold(), start=0, capital=100, fee=0.0025, slippage=0.001)
    assert r.trades == 1
    assert r.final_value == pytest.approx(100 * (1 - 0.0035) * 2)
    assert r.costs_eur == pytest.approx(0.35)


def test_decision_uses_only_past_prices():
    # Il prezzo raddoppia il giorno 2: chi decide alla chiusura del giorno 1
    # compra all'apertura del giorno 2 (=100), non prima.
    seen = []

    def spy(closes):
        seen.append(len(closes))
        return 1.0

    simulate(series([100, 100, 200, 200]), Strategy("spia", spy), start=0, capital=100, fee=0, slippage=0)
    assert seen == [1, 2, 3]  # mai la chiusura del giorno in cui esegue


def test_trend_exits_in_crash_and_skips_tiny_orders():
    up, down = [100 + i for i in range(10)], [109 - 10 * i for i in range(1, 10)]
    candles = series(up + down)
    r = simulate(candles, trend(3), start=2, capital=100, fee=0, slippage=0)
    bh = simulate(candles, buy_and_hold(), start=2, capital=100, fee=0, slippage=0)
    assert r.final_value > bh.final_value
    assert r.trades == 2  # entra e poi esce
    tiny = simulate(candles, trend(3), start=2, capital=4, fee=0, slippage=0)
    assert tiny.trades == 0 and tiny.final_value == 4  # sotto i 5 € di Bitvavo


def test_rebalance_respects_band_and_drawdown():
    candles = series([100, 100, 105, 160, 160])
    r = simulate(candles, rebalance(0.5, 0.10), start=0, capital=100, fee=0, slippage=0)
    assert r.trades == 2  # acquisto iniziale + un riequilibrio dopo il +60%
    crash = simulate(series([100, 100, 50, 50]), buy_and_hold(), start=0, capital=100, fee=0, slippage=0)
    assert crash.max_drawdown_pct == pytest.approx(50)


def test_run_all_uses_same_start_and_table():
    candles = series([100 + (i % 7) for i in range(60)])
    results = run_all(candles, [buy_and_hold(), trend(20)], capital=100)
    assert {r.days for r in results} == {40}
    assert "Compra e tieni" in format_table("x", results)
    assert index_days_ago(candles, 10) == 49
    with pytest.raises(ValueError):
        simulate(candles, trend(20), start=5)


def test_out_of_sample_and_stress():
    from trade.backtest import format_out_of_sample, format_stress, out_of_sample

    # Prima metà: sale e crolla (vince la tendenza); seconda metà: sale sempre (vince compra e tieni).
    closes = [100 + i for i in range(30)] + [129 - 4 * i for i in range(1, 20)] + [53 + i for i in range(50)]
    candles = series(closes)
    strategies = [buy_and_hold(), trend(5)]
    o = out_of_sample(candles, strategies, capital=100, fee=0)
    assert o.chosen == "Tendenza (media 5 g)"
    assert "NON regge" in format_out_of_sample(o)
    assert "1%" in format_stress(candles, strategies, capital=100, fee=0.01)


def test_parse_candles_sorts_and_drops_bad_rows():
    payload = [
        [2 * DAY_MS, "2", "3", "1", "2.5", "10"],
        [1 * DAY_MS, "1", "2", "0.5", "1.5", "5"],
        ["x"], [3 * DAY_MS, "0", "1", "0", "1", "1"],
    ]
    out = parse_candles(payload)
    assert [c.close for c in out] == [1.5, 2.5]
    with pytest.raises(SourceError):
        parse_candles({"error": "x"})


async def test_daily_history_pages_backwards(tmp_path):
    days = list(range(2000))
    calls = []

    def handler(request):
        assert request.url.path == "/v2/BTC-EUR/candles"
        assert "x-api-key" not in request.headers and "bitvavo-access-key" not in request.headers
        end = request.url.params.get("end")
        calls.append(end)
        last = len(days) - 1 if end is None else int(end) // DAY_MS
        page = [d for d in days if d <= last][-1440:]
        return httpx.Response(200, json=[[d * DAY_MS, "1", "1", "1", str(d + 1), "1"] for d in reversed(page)])

    async with make_client(httpx.MockTransport(handler)) as client:
        hist = await BitvavoClient(client, MinIntervalLimiter(0)).daily_history("BTC-EUR")
    assert len(hist) == 2000 and len(calls) == 2
    assert hist[0].close == 1 and hist[-1].close == 2000

    path = tmp_path / "c.csv"
    save_csv(path, hist[:3])
    assert [c.close for c in load_csv(path)] == [1, 2, 3]


async def test_http_error_is_source_error():
    async with make_client(httpx.MockTransport(lambda r: httpx.Response(429))) as client:
        with pytest.raises(SourceError):
            await BitvavoClient(client, MinIntervalLimiter(0)).candles("BTC-EUR")
