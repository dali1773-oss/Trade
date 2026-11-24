from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trade.models import PoolSnapshot
from trade.scam import (
    TokenSecurityInfo,
    Verdict,
    check_copycat,
    evaluate,
    is_tradeable,
)

NOW = datetime(2026, 11, 24, 19, 0, tzinfo=UTC)

SAFE_INFO = TokenSecurityInfo(
    mint_authority_active=False,
    freeze_authority_active=False,
    is_token_2022=False,
    transfer_fee_bps=0,
    has_transfer_hook=False,
    has_permanent_delegate=False,
    top10_holders_pct=Decimal("18"),
    creator_holding_pct=Decimal("1"),
    sell_route_found=True,
    sell_price_impact_pct=Decimal("1.2"),
)


def snap(**kw):
    base = dict(
        source="test",
        chain="solana",
        dex="pumpswap",
        pool_address="POOL",
        base_token="TOKEN",
        base_symbol="GOOD",
        liquidity_usd=Decimal("50000"),
        pool_created_at=NOW - timedelta(hours=2),
        observed_at=NOW,
    )
    base.update(kw)
    return PoolSnapshot(**base)


def test_all_good_passes():
    v = evaluate(snap(), SAFE_INFO, now=NOW)
    assert v.verdict is Verdict.PASS
    assert is_tradeable(v)


def test_missing_onchain_data_blocks():
    v = evaluate(snap(), TokenSecurityInfo(), now=NOW)
    assert v.verdict is Verdict.UNKNOWN
    assert not is_tradeable(v)


def test_missing_liquidity_blocks():
    v = evaluate(snap(liquidity_usd=None), SAFE_INFO, now=NOW)
    assert v.verdict is Verdict.UNKNOWN
    assert not is_tradeable(v)


@pytest.mark.parametrize(
    "change",
    [
        {"mint_authority_active": True},
        {"freeze_authority_active": True},
        {"transfer_fee_bps": 100},
        {"has_transfer_hook": True},
        {"has_permanent_delegate": True},
        {"top10_holders_pct": Decimal("55")},
        {"creator_holding_pct": Decimal("20")},
        {"sell_route_found": False},
        {"sell_price_impact_pct": Decimal("12")},
    ],
)
def test_each_red_flag_fails(change):
    info = TokenSecurityInfo(**{**SAFE_INFO.__dict__, **change})
    v = evaluate(snap(), info, now=NOW)
    assert v.verdict is Verdict.FAIL
    assert not is_tradeable(v)
    assert v.reasons


def test_fail_wins_over_unknown():
    info = TokenSecurityInfo(mint_authority_active=True)
    assert evaluate(snap(), info, now=NOW).verdict is Verdict.FAIL


def test_low_liquidity_and_young_pool_fail():
    assert evaluate(snap(liquidity_usd=Decimal("1555")), SAFE_INFO, now=NOW).verdict is Verdict.FAIL
    young = snap(pool_created_at=NOW - timedelta(minutes=3))
    assert evaluate(young, SAFE_INFO, now=NOW).verdict is Verdict.FAIL


def test_copycat_seen_on_mac():
    known = {"CHRISTMAS": "ORIGINAL"}
    assert check_copycat("CHIRSTMAS", "COPY", known).verdict is Verdict.FAIL
    assert check_copycat("ChristMas", "COPY", known).verdict is Verdict.FAIL
    assert check_copycat("CHRISTMASS", "COPY", known).verdict is Verdict.FAIL
    assert check_copycat("CHRISTMAS", "ORIGINAL", known).verdict is Verdict.PASS
    assert check_copycat("BONK", "OTHER", known).verdict is Verdict.PASS
    assert check_copycat(None, "X", known).verdict is Verdict.UNKNOWN


def test_short_symbols_not_overmatched():
    known = {"SOL": "WSOL"}
    assert check_copycat("SOX", "OTHER", known).verdict is Verdict.PASS


def test_copycat_included_in_evaluate():
    v = evaluate(snap(base_symbol="CHIRSTMAS"), SAFE_INFO, now=NOW, known_symbols={"CHRISTMAS": "ORIG"})
    assert v.verdict is Verdict.FAIL
