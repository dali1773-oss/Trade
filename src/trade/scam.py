"""Scam Detection (Fase 3) — regole deterministiche con potere di veto.

Regola d'oro: si compra solo con verdetto PASS. FAIL e UNKNOWN bloccano.
Un dato mancante non è mai "ok": diventa UNKNOWN, quindi blocco (fail-closed).

Le informazioni on-chain (autorità di mint/freeze, estensioni Token-2022,
distribuzione degli holder) arriveranno dal client Helius; la prova di
rivendibilità dalle quotazioni Jupiter. Qui ci sono solo le regole, testabili
senza rete. Soglie iniziali da RISK_MANAGEMENT.md §4, modificabili solo con
approvazione di Danish.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from trade.models import PoolSnapshot


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Thresholds:
    min_liquidity_usd: Decimal = Decimal("20000")
    min_pool_age: timedelta = timedelta(minutes=10)
    max_top10_pct: Decimal = Decimal("30")
    max_creator_pct: Decimal = Decimal("5")
    max_sell_impact_pct: Decimal = Decimal("5")
    max_transfer_fee_bps: int = 0


@dataclass(frozen=True)
class TokenSecurityInfo:
    """Dati on-chain del token. None = non ancora verificato (=> UNKNOWN)."""

    mint_authority_active: bool | None = None
    freeze_authority_active: bool | None = None
    is_token_2022: bool | None = None
    transfer_fee_bps: int | None = None
    has_transfer_hook: bool | None = None
    has_permanent_delegate: bool | None = None
    top10_holders_pct: Decimal | None = None
    creator_holding_pct: Decimal | None = None
    sell_route_found: bool | None = None
    sell_price_impact_pct: Decimal | None = None


@dataclass(frozen=True)
class CheckResult:
    name: str
    verdict: Verdict
    reason: str


@dataclass(frozen=True)
class ScamVerdict:
    token: str
    verdict: Verdict
    checks: tuple[CheckResult, ...] = field(default_factory=tuple)

    @property
    def reasons(self) -> list[str]:
        return [f"{c.name}: {c.reason}" for c in self.checks if c.verdict is not Verdict.PASS]


def is_tradeable(verdict: ScamVerdict) -> bool:
    """L'unico modo per dire sì: PASS su tutto."""
    return verdict.verdict is Verdict.PASS


def _ok(name: str, reason: str = "ok") -> CheckResult:
    return CheckResult(name, Verdict.PASS, reason)


def _fail(name: str, reason: str) -> CheckResult:
    return CheckResult(name, Verdict.FAIL, reason)


def _unknown(name: str, reason: str = "dato mancante") -> CheckResult:
    return CheckResult(name, Verdict.UNKNOWN, reason)


# --- controlli sul pool ---------------------------------------------------

def check_liquidity(snap: PoolSnapshot, th: Thresholds) -> CheckResult:
    name = "liquidita"
    if snap.liquidity_usd is None:
        return _unknown(name, "liquidità non disponibile (es. ancora sulla curva di pump.fun)")
    if snap.liquidity_usd < th.min_liquidity_usd:
        return _fail(name, f"{snap.liquidity_usd} $ < minimo {th.min_liquidity_usd} $")
    return _ok(name)


def check_pool_age(snap: PoolSnapshot, th: Thresholds, now: datetime) -> CheckResult:
    name = "eta_pool"
    if snap.pool_created_at is None:
        return _unknown(name)
    age = now - snap.pool_created_at
    if age < th.min_pool_age:
        return _fail(name, f"pool troppo giovane ({int(age.total_seconds())} s)")
    return _ok(name)


# --- controlli on-chain ---------------------------------------------------

def _flag(name: str, value: bool | None, bad_reason: str) -> CheckResult:
    if value is None:
        return _unknown(name)
    return _fail(name, bad_reason) if value else _ok(name)


def check_onchain(info: TokenSecurityInfo, th: Thresholds) -> list[CheckResult]:
    results = [
        _flag("mint_authority", info.mint_authority_active, "si possono creare nuovi token"),
        _flag("freeze_authority", info.freeze_authority_active, "i token possono essere congelati"),
        _flag("transfer_hook", info.has_transfer_hook, "transfer hook presente (Token-2022)"),
        _flag("permanent_delegate", info.has_permanent_delegate, "delegato permanente (Token-2022)"),
    ]
    if info.transfer_fee_bps is None:
        results.append(_unknown("transfer_fee"))
    elif info.transfer_fee_bps > th.max_transfer_fee_bps:
        results.append(_fail("transfer_fee", f"tassa di trasferimento {info.transfer_fee_bps} bps"))
    else:
        results.append(_ok("transfer_fee"))

    if info.top10_holders_pct is None:
        results.append(_unknown("concentrazione_top10"))
    elif info.top10_holders_pct > th.max_top10_pct:
        results.append(_fail("concentrazione_top10", f"top 10 holder = {info.top10_holders_pct}%"))
    else:
        results.append(_ok("concentrazione_top10"))

    if info.creator_holding_pct is None:
        results.append(_unknown("quota_creatore"))
    elif info.creator_holding_pct > th.max_creator_pct:
        results.append(_fail("quota_creatore", f"creatore detiene {info.creator_holding_pct}%"))
    else:
        results.append(_ok("quota_creatore"))

    # Protezione honeypot: deve esistere una rotta di vendita con impatto accettabile.
    if info.sell_route_found is None:
        results.append(_unknown("vendibilita"))
    elif not info.sell_route_found:
        results.append(_fail("vendibilita", "nessuna rotta di vendita (possibile honeypot)"))
    elif info.sell_price_impact_pct is None:
        results.append(_unknown("vendibilita", "impatto di vendita sconosciuto"))
    elif info.sell_price_impact_pct > th.max_sell_impact_pct:
        results.append(_fail("vendibilita", f"impatto di vendita {info.sell_price_impact_pct}%"))
    else:
        results.append(_ok("vendibilita"))
    return results


# --- nomi imitati -----------------------------------------------------------

def _normalize(symbol: str) -> str:
    text = unicodedata.normalize("NFKD", symbol).encode("ascii", "ignore").decode()
    return "".join(ch for ch in text.upper() if ch.isalnum())


def _is_near_copy(a: str, b: str) -> bool:
    """Uguali dopo normalizzazione, oppure una sola modifica/scambio di lettere."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1 or min(len(a), len(b)) < 4:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        if len(diff) == 1:
            return True
        if len(diff) == 2 and diff[1] == diff[0] + 1:
            i, j = diff
            return a[i] == b[j] and a[j] == b[i]
        return False
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:k] + long_[k + 1:] == short for k in range(len(long_)))


def check_copycat(symbol: str | None, token: str, known: dict[str, str]) -> CheckResult:
    """`known` = simbolo normalizzato -> indirizzo del token già visto/noto."""
    name = "nome_imitato"
    if not symbol:
        return _unknown(name, "simbolo mancante")
    norm = _normalize(symbol)
    for other_sym, other_token in known.items():
        if other_token != token and _is_near_copy(norm, other_sym):
            return _fail(name, f"'{symbol}' somiglia a '{other_sym}' ({other_token[:6]}…)")
    return _ok(name)


# --- verdetto complessivo -------------------------------------------------

def evaluate(
    snap: PoolSnapshot,
    info: TokenSecurityInfo,
    *,
    now: datetime,
    known_symbols: dict[str, str] | None = None,
    thresholds: Thresholds | None = None,
) -> ScamVerdict:
    th = thresholds or Thresholds()
    checks = [check_liquidity(snap, th), check_pool_age(snap, th, now), *check_onchain(info, th)]
    if known_symbols is not None:
        checks.append(check_copycat(snap.base_symbol, snap.base_token, known_symbols))
    if any(c.verdict is Verdict.FAIL for c in checks):
        final = Verdict.FAIL
    elif any(c.verdict is Verdict.UNKNOWN for c in checks):
        final = Verdict.UNKNOWN
    else:
        final = Verdict.PASS
    return ScamVerdict(token=snap.base_token, verdict=final, checks=tuple(checks))
