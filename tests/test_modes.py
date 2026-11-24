import pytest

from trade.modes import DEFAULT_MODE, Mode, ModeChangeRefused, change_mode, uses_real_money


def test_default_is_off():
    assert DEFAULT_MODE is Mode.OFF


@pytest.mark.parametrize("mode", list(Mode))
def test_kill_switch_always_allowed(mode):
    assert change_mode(mode, Mode.OFF) is Mode.OFF


@pytest.mark.parametrize("target", [Mode.LIVE_PILOT, Mode.LIVE])
def test_real_money_requires_human_approval(target):
    with pytest.raises(ModeChangeRefused):
        change_mode(Mode.SHADOW, target)


def test_pilot_with_approval():
    assert change_mode(Mode.SHADOW, Mode.LIVE_PILOT, human_approved=True) is Mode.LIVE_PILOT


def test_live_cannot_skip_pilot():
    with pytest.raises(ModeChangeRefused):
        change_mode(Mode.SHADOW, Mode.LIVE, human_approved=True)


def test_simulation_modes_do_not_use_money():
    for mode in (Mode.OFF, Mode.RECORD, Mode.BACKTEST, Mode.SHADOW, Mode.DEVNET):
        assert not uses_real_money(mode)
