"""Verdetti salvati dal registratore ed etichettatura: tutto finto, nessuna rete."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx

from trade.label import _main_async as label_main, build_parser as label_parser, classify
from trade.ratelimit import MinIntervalLimiter
from trade.recorder import Recorder
from trade.scam import ScamVerdict, TokenSecurityInfo, Verdict
from trade.security import ScanResult, SecurityReport
from trade.sources import make_client
from trade.sources.dexscreener import DexScreenerClient
from trade.sources.geckoterminal import GeckoTerminalClient
from trade.store import Store

NOW = datetime.now(UTC)


class FakeScanner:
    def __init__(self):
        self.calls = []

    async def check(self, mint):
        self.calls.append(mint)
        from trade.models import PoolSnapshot

        pool = PoolSnapshot(source="t", chain="solana", pool_address="P-" + mint, base_token=mint,
                            price_usd=Decimal("0.001"), liquidity_usd=Decimal("30000"), observed_at=NOW)
        v = ScamVerdict(token=mint, verdict=Verdict.PASS)
        return ScanResult(v, SecurityReport(TokenSecurityInfo(top10_holders_pct=Decimal("12"))), pool, "ok")


def empty_api():
    def handler(request):
        if "new_pools" in request.url.path:
            return httpx.Response(200, json={"data": [], "included": []})
        return httpx.Response(200, json=[])
    return httpx.MockTransport(handler)


async def test_recorder_scans_only_tokens_old_enough_once():
    store = Store(":memory:")
    store.ensure_token("solana", "OLD", "test", NOW - timedelta(minutes=20))
    store.ensure_token("solana", "YOUNG", "test", NOW - timedelta(minutes=2))
    store.ensure_token("solana", "STALE", "test", NOW - timedelta(hours=5))
    scanner = FakeScanner()
    async with make_client(empty_api()) as client:
        rec = Recorder(store, DexScreenerClient(client, MinIntervalLimiter(0)),
                       GeckoTerminalClient(client, MinIntervalLimiter(0)), scanner=scanner)
        s1 = await rec.run_cycle()
        s2 = await rec.run_cycle()
    assert scanner.calls == ["OLD"]
    assert s1.scans == 1 and s2.scans == 0
    row = store.conn.execute("SELECT verdict, price_usd, info FROM scam_checks").fetchone()
    assert row["verdict"] == "PASS" and row["price_usd"] == "0.001"
    assert '"top10_holders_pct": "12"' in row["info"]


def test_classify():
    assert classify(Decimal("1"), Decimal("0.05"), Decimal("5000"), True)[0] == "MORTO"
    assert classify(Decimal("1"), Decimal("0.5"), Decimal("500"), True)[0] == "MORTO"
    assert classify(None, None, None, False)[0] == "MORTO"
    assert classify(Decimal("1"), Decimal("2"), Decimal("50000"), True)[0] == "VIVO"
    assert classify(None, Decimal("2"), None, True)[0] == "VIVO"  # dati scarsi: non lo diamo per morto


async def test_label_and_matrix(tmp_path, capsys):
    db = tmp_path / "r.sqlite"
    store = Store(db)
    old = NOW - timedelta(hours=30)
    store.add_scam_check("solana", "RUG", verdict="PASS", reasons=[], info={}, notes=[],
                         pool_address="P1", price_usd=Decimal("1"), checked_at=old)
    store.add_scam_check("solana", "GOOD", verdict="FAIL", reasons=["x"], info={}, notes=[],
                         pool_address="P2", price_usd=Decimal("1"), checked_at=old)
    store.add_scam_check("solana", "NEW", verdict="PASS", reasons=[], info={}, notes=[],
                         pool_address="P3", price_usd=Decimal("1"), checked_at=NOW)
    store.close()

    def handler(request):
        token = request.url.path.rsplit("/", 1)[-1]
        assert token != "NEW"  # troppo recente per l'etichetta a 24 h
        price = "0.01" if token == "RUG" else "3"
        return httpx.Response(200, json=[{"chainId": "solana", "pairAddress": "P1" if token == "RUG" else "P2",
                                          "baseToken": {"address": token}, "priceUsd": price,
                                          "liquidity": {"usd": 20000}}])

    args = label_parser().parse_args(["--db", str(db)])
    assert await label_main(args, transport=httpx.MockTransport(handler)) == 0
    out = capsys.readouterr().out
    assert "Etichettati ora: 2" in out
    assert "Falsi negativi (PASS ma MORTO): 1" in out
    # Seconda esecuzione: niente da rifare.
    assert await label_main(args, transport=httpx.MockTransport(handler)) == 0
    assert "Etichettati ora: 0" in capsys.readouterr().out


def test_refresh_priority_scanned_then_young_then_oldest():
    store = Store(":memory:")
    now = NOW
    store.ensure_token("solana", "OLD_STALE", "t", now - timedelta(days=2))
    store.ensure_token("solana", "OLD_NEVER", "t", now - timedelta(days=1))
    store.ensure_token("solana", "YOUNG", "t", now - timedelta(hours=1))
    store.ensure_token("solana", "YOUNG_FRESH", "t", now - timedelta(hours=1))
    store.ensure_token("solana", "SCANNED", "t", now - timedelta(days=3))
    store.ensure_token("solana", "ANCIENT", "t", now - timedelta(days=30))
    store.mark_snapshot("solana", "OLD_STALE", now - timedelta(hours=3))
    store.mark_snapshot("solana", "YOUNG", now - timedelta(minutes=30))
    store.mark_snapshot("solana", "YOUNG_FRESH", now - timedelta(minutes=2))
    store.mark_snapshot("solana", "SCANNED", now - timedelta(hours=1))
    store.add_scam_check("solana", "SCANNED", verdict="FAIL", reasons=[], info={}, notes=[])
    order = store.tokens_to_refresh("solana", 10, now=now)
    assert order[:2] == ["SCANNED", "YOUNG"]
    assert "ANCIENT" not in order  # oltre 7 giorni
    assert order.index("OLD_NEVER") < order.index("OLD_STALE") < order.index("YOUNG_FRESH")
    # Appena fotografato, il token controllato torna in coda.
    store.mark_snapshot("solana", "SCANNED", now)
    assert store.tokens_to_refresh("solana", 1, now=now) == ["YOUNG"]
