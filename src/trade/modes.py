"""Modalità operative globali (ARCHITECTURE.md §2).

Regola: il sistema parte sempre in OFF e non può passare da solo a una
modalità che usa denaro reale. Le modalità reali richiedono un'approvazione
esplicita di Danish, rappresentata qui da `human_approved=True` passato da un
comando locale, mai da un agente.
"""

from enum import Enum


class Mode(str, Enum):
    OFF = "OFF"
    RECORD = "RECORD"
    BACKTEST = "BACKTEST"
    SHADOW = "SHADOW"
    DEVNET = "DEVNET"
    LIVE_PILOT = "LIVE_PILOT"
    LIVE = "LIVE"


DEFAULT_MODE = Mode.OFF

REAL_MONEY_MODES = frozenset({Mode.LIVE_PILOT, Mode.LIVE})


class ModeChangeRefused(Exception):
    """Cambio di modalità non consentito."""


def uses_real_money(mode: Mode) -> bool:
    return mode in REAL_MONEY_MODES


def change_mode(current: Mode, target: Mode, *, human_approved: bool = False) -> Mode:
    """Restituisce la nuova modalità oppure solleva ModeChangeRefused.

    - Tornare a OFF (kill switch) è sempre permesso.
    - Entrare in una modalità con denaro reale richiede human_approved=True.
    - LIVE si raggiunge solo da LIVE_PILOT (mai saltando il pilota).
    """
    if target is Mode.OFF:
        return Mode.OFF
    if uses_real_money(target):
        if not human_approved:
            raise ModeChangeRefused(
                f"{target.value} richiede l'approvazione esplicita di Danish"
            )
        if target is Mode.LIVE and current is not Mode.LIVE_PILOT:
            raise ModeChangeRefused("LIVE è raggiungibile solo da LIVE_PILOT")
    return target
