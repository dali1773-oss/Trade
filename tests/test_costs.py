from decimal import Decimal

import pytest

from trade.costs import CostModel, sol_to_lamports


def test_network_cost_small_position_is_significant():
    m = CostModel()
    # 0,03 SOL: due transazioni da 55.000 lamport = 0,00011 SOL ≈ 0,37% della posizione
    cost = m.roundtrip_cost_pct(sol_to_lamports(Decimal("0.03")), Decimal("2.00"))
    assert cost == Decimal("3.37")


def test_not_closing_token_account_adds_rent():
    open_ = CostModel(close_token_account=False)
    closed = CostModel()
    pos = sol_to_lamports(Decimal("0.03"))
    assert open_.roundtrip_cost_pct(pos, Decimal("2")) - closed.roundtrip_cost_pct(pos, Decimal("2")) > Decimal("6")


def test_edge_rule_and_tax():
    m = CostModel()
    assert m.worth_trading(Decimal("8"), Decimal("4"))
    assert not m.worth_trading(Decimal("7.99"), Decimal("4"))
    assert m.net_after_tax_pct(Decimal("10"), Decimal("4")) == Decimal("4.02")
    assert m.net_after_tax_pct(Decimal("2"), Decimal("4")) == Decimal("-2.00")  # le perdite non sono tassate


def test_rejects_zero_position():
    with pytest.raises(ValueError):
        CostModel().roundtrip_cost_pct(0, Decimal("1"))
