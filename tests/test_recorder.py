"""Registratore e archivio: tutto con HTTP finto, nessuna rete."""

import json
import sqlite3
from pathlib import Path

import httpx
import pytest

from trade.ratelimit import MinIntervalLimiter
from trade.recorder import Recorder, _main_async, build_parser
from trade.sources import make_client
from trade.sources.dexscreener import DexScreenerClient
from trade.sources.geckoterminal import GeckoTerminalClient
from trade.store import Store

FIX = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIX / name).read_text())


def fake_api(fail_gecko=False, seen=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request.url.path)
        assert request.method == "GET"  # il registratore non scrive mai
        path = request.url.path
        if "new_pools" in path:
            if fail_gecko:
                return httpx.Response(429)
            return httpx.Response(200, json=fixture("geckoterminal_new_pools.json"))
        if path == "/token-profiles/latest/v1":
            return httpx.Response(200, json=fixture("dexscreener_token_profiles.json"))
        if path.startswith("/token-pairs/v1/solana/"):
            return httpx.Response(200, json=fixture("dexscreener_token_pairs.json"))
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def no_wait():
    return MinIntervalLimiter(0)


async def make_recorder(store, transport):
    client = make_client(transport)
    rec = Recorder(
        store,
        DexScreenerClient(client, no_wait()),
        GeckoTerminalClient(client, no_wait()),
        refresh_per_cycle=5,
    )
    return rec, client


async def test_cycle_records_tokens_and_snapshots():
    store = Store(":memory:")
    rec, client = await make_recorder(store, fake_api())
    async with client:
        stats = await rec.run_cycle()
    # 1 token da GeckoTerminal + 2 profili Solana (quello su Base è escluso)
    assert stats.new_tokens == 3
    assert stats.errors == 0
    counts = store.counts()
    assert counts["tokens"] == 3
    # 1 pool GT + 3 token aggiornati x 2 coppie ciascuno
    assert counts["pool_snapshots"] == 1 + 3 * 2


async def test_second_cycle_does_not_duplicate_tokens():
    store = Store(":memory:")
    rec, client = await make_recorder(store, fake_api())
    async with client:
        await rec.run_cycle()
        stats = await rec.run_cycle()
    assert stats.new_tokens == 0
    assert store.counts()["tokens"] == 3


async def test_source_failure_is_logged_and_cycle_continues():
    store = Store(":memory:")
    rec, client = await make_recorder(store, fake_api(fail_gecko=True))
    async with client:
        stats = await rec.run_cycle()
    assert stats.errors == 1
    assert stats.new_tokens == 2  # DexScreener funziona ancora
    kinds = [r[0] for r in store.conn.execute("SELECT kind FROM events")]
    assert "source_error" in kinds


def test_events_are_append_only():
    store = Store(":memory:")
    store.log_event("test", {"a": 1})
    with pytest.raises(sqlite3.DatabaseError):
        store.conn.execute("UPDATE events SET kind = 'x'")
    with pytest.raises(sqlite3.DatabaseError):
        store.conn.execute("DELETE FROM events")


async def test_cli_once_writes_database(tmp_path):
    db = tmp_path / "rec.sqlite"
    args = build_parser().parse_args(["--once", "--db", str(db), "--refresh", "2"])
    seen = []
    assert await _main_async(args, transport=fake_api(seen=seen)) == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM tokens").fetchone()[0] == 3
    kinds = {r[0] for r in conn.execute("SELECT kind FROM events")}
    assert {"recorder_start", "cycle", "recorder_stop"} <= kinds
    assert all(not p.startswith("/swap") for p in seen)


async def test_limiter_spaces_requests():
    t = [0.0]
    slept = []

    async def fake_sleep(s):
        slept.append(s)
        t[0] += s

    lim = MinIntervalLimiter(1.5, clock=lambda: t[0], sleep=fake_sleep)
    await lim.wait()
    await lim.wait()
    assert slept == [1.5]
    lim.penalize(60)
    await lim.wait()
    assert slept[-1] == pytest.approx(61.5)


async def test_ctrl_c_stops_immediately_mid_cycle(tmp_path):
    import asyncio
    import os
    import signal
    import time

    async def slow(request):
        await asyncio.sleep(30)
        return httpx.Response(200, json={})

    class SlowTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return await slow(request)

    args = build_parser().parse_args(["--db", str(tmp_path / "r.sqlite"), "--interval", "60"])
    loop = asyncio.get_running_loop()
    loop.call_later(0.3, os.kill, os.getpid(), signal.SIGINT)
    t0 = time.monotonic()
    assert await _main_async(args, transport=SlowTransport()) == 0
    assert time.monotonic() - t0 < 5
    conn = sqlite3.connect(tmp_path / "r.sqlite")
    kinds = [r[0] for r in conn.execute("SELECT kind FROM events")]
    assert kinds[-1] == "recorder_stop"
