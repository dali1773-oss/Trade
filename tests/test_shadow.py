"""Simulazione ombra: prezzi finti, nessuna rete."""

import json
from datetime import UTC, datetime, timedelta

from trade.shadow import _main_async, build_parser, completed
from trade.sources import SourceError
from trade.sources.bitvavo import Candle

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def candles(n, start=T0, base=100.0):
    out, prev = [], base
    for i in range(n):
        c = base + i
        out.append(Candle(start + timedelta(days=i), prev, c, prev, c, 1.0))
        prev = c
    return out


def fake_fetch(history):
    async def fetch(market, data_dir):
        return history
    return fetch


def test_completed_drops_today():
    cs = candles(3)
    assert len(completed(cs, T0 + timedelta(days=2, hours=5))) == 2


async def test_first_run_freezes_then_counts_forward(tmp_path, capsys):
    cfg = tmp_path / "shadow.json"
    args = build_parser().parse_args(["--config", str(cfg), "--data-dir", str(tmp_path)])
    hist = candles(300)
    day1 = T0 + timedelta(days=299, hours=12)  # giorno 299 in corso: si usa fino al 298
    assert await _main_async(args, now=day1, fetch=fake_fetch(hist)) == 0
    saved = json.loads(cfg.read_text())
    assert saved["start_day"] == "2026-10-26" and saved["strategies"] == ["buy_hold", "trend50", "trend200"]
    out = capsys.readouterr().out
    assert "Primo avvio" in out and "appena partita" in out

    # Dieci giorni dopo, anche senza esecuzioni intermedie: conti dal giorno congelato.
    later = T0 + timedelta(days=310, hours=1)
    assert await _main_async(args, now=later, fetch=fake_fetch(candles(311))) == 0
    out = capsys.readouterr().out
    assert "Primo avvio" not in out
    assert "Compra e tieni" in out and "operazioni 1" in out and "ora: in cripto" in out
    assert json.loads(cfg.read_text())["start_day"] == "2026-10-26"  # non cambia


async def test_no_prices_is_fail_closed(tmp_path, capsys):
    async def broken(market, data_dir):
        raise SourceError("giù")
    args = build_parser().parse_args(["--config", str(tmp_path / "s.json"), "--data-dir", str(tmp_path)])
    assert await _main_async(args, now=T0, fetch=broken) == 1
    assert not (tmp_path / "s.json").exists()
    assert "fail-closed" in capsys.readouterr().out
