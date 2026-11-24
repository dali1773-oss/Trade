"""Parser delle fonti, verificati con risposte reali registrate il 24/11/2026."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from trade.models import to_decimal
from trade.sources import SourceError
from trade.sources.dexscreener import parse_pairs, parse_token_profiles
from trade.sources.geckoterminal import parse_pools

FIX = Path(__file__).parent / "fixtures"
T0 = datetime(2026, 11, 24, 18, 0, tzinfo=UTC)


def load(name):
    return json.loads((FIX / name).read_text())


def test_token_profiles_filters_chain_and_handles_missing_fields():
    profiles = parse_token_profiles(load("dexscreener_token_profiles.json"), observed_at=T0)
    assert [p.token_address for p in profiles] == [
        "3hiM6twGsV6Lcf8sh68A5DqfTmU84jeM4kNPy2DVpump",
        "Az7dYDicMc4G9hwnkeQYwHi6Fop1711C7hABcrWzpump",
    ]
    assert profiles[1].description is None
    assert "https://t.me/smokingchickenfishs" in profiles[1].links


def test_pairs_parsing_types():
    pairs = parse_pairs(load("dexscreener_token_pairs.json"), observed_at=T0)
    sol = pairs[0]
    assert sol.price_usd == Decimal("69.59")
    assert sol.liquidity_usd == Decimal("17094669.54")
    assert sol.buys_m5 == 113 and sol.sells_h1 == 2067
    assert sol.pool_created_at == datetime.fromtimestamp(1688106058, UTC)


def test_pairs_missing_values_stay_unknown_not_zero():
    pair = parse_pairs(load("dexscreener_token_pairs.json"), observed_at=T0)[1]
    assert pair.liquidity_usd is None
    assert pair.price_usd is None
    assert pair.sells_m5 == 0
    assert pair.buys_h1 is None


def test_geckoterminal_pools():
    pools = parse_pools(load("geckoterminal_new_pools.json"), observed_at=T0)
    assert len(pools) == 1
    p = pools[0]
    assert p.pool_address == "6ZVQtXdBzX1CA642Xrg4LLY8WXEWVEBSTehumfqRLZ8Q"
    assert p.base_token == "BgyM82KTzsVAVET3Sm86dwaEnmYN1AtAgrkRap45u47j"
    assert p.quote_token == "So11111111111111111111111111111111111111112"
    assert p.dex == "pump-fun"
    assert p.base_symbol == "AC"
    assert p.liquidity_usd == Decimal("1555.8911")
    assert p.price_usd is not None and p.price_usd > 0
    assert p.pool_created_at == datetime(2026, 11, 24, 18, 20, 13, tzinfo=UTC)


@pytest.mark.parametrize("bad", [None, {}, "x", 3])
def test_bad_payloads_raise(bad):
    with pytest.raises(SourceError):
        parse_token_profiles(bad)
    with pytest.raises(SourceError):
        parse_pairs(bad)
    with pytest.raises(SourceError):
        parse_pools(bad if bad != {} else [])


@pytest.mark.parametrize("value", [None, True, "abc", "nan", "inf"])
def test_to_decimal_rejects_invalid(value):
    assert to_decimal(value) is None
