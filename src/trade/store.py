"""Archivio SQLite del registratore (ARCHITECTURE.md §7).

- `events`: registro append-only (un trigger impedisce modifiche e cancellazioni).
- `tokens`: token osservati, con prima/ultima osservazione.
- `pool_snapshots`: fotografie dei pool nel tempo (base per backtest ed etichettatura).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from trade.models import PoolSnapshot, TokenProfile

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    source TEXT,
    payload TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'events e'' append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'events e'' append-only'); END;

CREATE TABLE IF NOT EXISTS tokens (
    chain TEXT NOT NULL,
    token_address TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    first_source TEXT NOT NULL,
    url TEXT,
    description TEXT,
    links TEXT,
    last_snapshot_at TEXT,
    PRIMARY KEY (chain, token_address)
);

CREATE TABLE IF NOT EXISTS pool_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    source TEXT NOT NULL,
    chain TEXT NOT NULL,
    dex TEXT,
    pool_address TEXT NOT NULL,
    base_token TEXT NOT NULL,
    quote_token TEXT,
    base_symbol TEXT,
    price_usd TEXT,
    price_native TEXT,
    liquidity_usd TEXT,
    fdv_usd TEXT,
    volume_m5_usd TEXT,
    volume_h1_usd TEXT,
    volume_h24_usd TEXT,
    buys_m5 INTEGER,
    sells_m5 INTEGER,
    buys_h1 INTEGER,
    sells_h1 INTEGER,
    pool_created_at TEXT,
    extra TEXT
);
CREATE INDEX IF NOT EXISTS idx_snap_token ON pool_snapshots(chain, base_token, observed_at);
CREATE INDEX IF NOT EXISTS idx_snap_pool ON pool_snapshots(chain, pool_address, observed_at);

-- Verdetti anti-truffa (Fase 3): uno per token, dato quando il token ha almeno 15 minuti.
CREATE TABLE IF NOT EXISTS scam_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TEXT NOT NULL,
    chain TEXT NOT NULL,
    token_address TEXT NOT NULL,
    pool_address TEXT,
    verdict TEXT NOT NULL,
    reasons TEXT NOT NULL,
    info TEXT NOT NULL,
    notes TEXT NOT NULL,
    price_usd TEXT,
    liquidity_usd TEXT,
    UNIQUE (chain, token_address)
);

-- Esito a distanza di tempo (24 h, 7 giorni): serve a misurare falsi positivi/negativi.
CREATE TABLE IF NOT EXISTS scam_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    labeled_at TEXT NOT NULL,
    chain TEXT NOT NULL,
    token_address TEXT NOT NULL,
    horizon_h INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    price_ratio TEXT,
    liquidity_usd TEXT,
    detail TEXT,
    UNIQUE (chain, token_address, horizon_h)
);
"""


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat() if dt else None


def _dec(value: Decimal | None) -> str | None:
    # I prezzi restano testo per non perdere precisione.
    return str(value) if value is not None else None


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return _iso(value)
    raise TypeError(type(value).__name__)


class Store:
    def __init__(self, path: str | Path) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # --- eventi -----------------------------------------------------------
    def log_event(self, kind: str, payload: dict[str, Any], source: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO events (ts, kind, source, payload) VALUES (?, ?, ?, ?)",
            (_iso(datetime.now(UTC)), kind, source, json.dumps(payload, default=_json_default)),
        )
        self.conn.commit()

    # --- token ------------------------------------------------------------
    def upsert_token(self, profile: TokenProfile) -> bool:
        """Registra un token. Restituisce True se è la prima volta che lo vediamo."""
        now = _iso(profile.observed_at)
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO tokens (chain, token_address, first_seen, last_seen, "
            "first_source, url, description, links) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                profile.chain,
                profile.token_address,
                now,
                now,
                profile.source,
                profile.url,
                profile.description,
                json.dumps(list(profile.links)),
            ),
        )
        is_new = cur.rowcount == 1
        if not is_new:
            self.conn.execute(
                "UPDATE tokens SET last_seen = ? WHERE chain = ? AND token_address = ?",
                (now, profile.chain, profile.token_address),
            )
        self.conn.commit()
        return is_new

    def ensure_token(self, chain: str, token_address: str, source: str, seen_at: datetime) -> bool:
        return self.upsert_token(
            TokenProfile(source=source, chain=chain, token_address=token_address, observed_at=seen_at)
        )

    def tokens_to_refresh(
        self,
        chain: str,
        limit: int,
        *,
        max_age: timedelta = timedelta(days=7),
        young: timedelta = timedelta(hours=6),
        young_every: timedelta = timedelta(minutes=10),
        scanned_every: timedelta = timedelta(minutes=15),
        now: datetime | None = None,
    ) -> list[str]:
        """Token da aggiornare, in ordine di priorità.

        1. token con un verdetto anti-truffa, se l'ultima foto ha più di `scanned_every`
           (servono serie di prezzi fitte per capire se il verdetto era giusto);
        2. token nati da meno di `young`, se l'ultima foto ha più di `young_every`
           (è quando succede quasi tutto: lancio, pump, rug);
        3. tutti gli altri visti negli ultimi `max_age`, prima i fotografati da più tempo.
        """
        now = now or datetime.now(UTC)
        rows = self.conn.execute(
            """
            SELECT t.token_address,
                   CASE
                     WHEN EXISTS (SELECT 1 FROM scam_checks c
                                  WHERE c.chain = t.chain AND c.token_address = t.token_address)
                          AND COALESCE(t.last_snapshot_at, '') < :scanned_cut THEN 0
                     WHEN t.first_seen >= :young_cut
                          AND COALESCE(t.last_snapshot_at, '') < :young_every_cut THEN 1
                     ELSE 2
                   END AS prio
            FROM tokens t
            WHERE t.chain = :chain AND t.first_seen >= :cutoff
            ORDER BY prio ASC, COALESCE(t.last_snapshot_at, '') ASC, t.first_seen ASC
            LIMIT :limit
            """,
            {
                "chain": chain,
                "cutoff": _iso(now - max_age),
                "young_cut": _iso(now - young),
                "young_every_cut": _iso(now - young_every),
                "scanned_cut": _iso(now - scanned_every),
                "limit": limit,
            },
        ).fetchall()
        return [row["token_address"] for row in rows]

    def mark_snapshot(self, chain: str, token_address: str, at: datetime) -> None:
        self.conn.execute(
            "UPDATE tokens SET last_snapshot_at = ? WHERE chain = ? AND token_address = ?",
            (_iso(at), chain, token_address),
        )
        self.conn.commit()

    # --- snapshot ---------------------------------------------------------
    def add_snapshots(self, snapshots: list[PoolSnapshot]) -> int:
        rows = [
            (
                _iso(s.observed_at),
                s.source,
                s.chain,
                s.dex,
                s.pool_address,
                s.base_token,
                s.quote_token,
                s.base_symbol,
                _dec(s.price_usd),
                _dec(s.price_native),
                _dec(s.liquidity_usd),
                _dec(s.fdv_usd),
                _dec(s.volume_m5_usd),
                _dec(s.volume_h1_usd),
                _dec(s.volume_h24_usd),
                s.buys_m5,
                s.sells_m5,
                s.buys_h1,
                s.sells_h1,
                _iso(s.pool_created_at),
                json.dumps(s.extra, default=_json_default),
            )
            for s in snapshots
        ]
        self.conn.executemany(
            "INSERT INTO pool_snapshots (observed_at, source, chain, dex, pool_address, base_token, "
            "quote_token, base_symbol, price_usd, price_native, liquidity_usd, fdv_usd, "
            "volume_m5_usd, volume_h1_usd, volume_h24_usd, buys_m5, sells_m5, buys_h1, sells_h1, "
            "pool_created_at, extra) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        self.conn.commit()
        return len(rows)

    # --- verdetti anti-truffa -----------------------------------------------
    def tokens_to_scan(
        self, chain: str, limit: int, *, now: datetime | None = None,
        min_age: timedelta = timedelta(minutes=15), max_age: timedelta = timedelta(hours=2),
    ) -> list[str]:
        """Token visti da almeno `min_age` (e non più di `max_age`) senza ancora un verdetto."""
        now = now or datetime.now(UTC)
        rows = self.conn.execute(
            "SELECT t.token_address FROM tokens t WHERE t.chain = ? AND t.first_seen <= ? "
            "AND t.first_seen >= ? AND NOT EXISTS (SELECT 1 FROM scam_checks c "
            "WHERE c.chain = t.chain AND c.token_address = t.token_address) "
            "ORDER BY t.first_seen ASC LIMIT ?",
            (chain, _iso(now - min_age), _iso(now - max_age), limit),
        ).fetchall()
        return [row["token_address"] for row in rows]

    def add_scam_check(
        self, chain: str, token_address: str, *, verdict: str, reasons: list[str],
        info: dict[str, Any], notes: list[str], pool_address: str | None = None,
        price_usd: Decimal | None = None, liquidity_usd: Decimal | None = None,
        checked_at: datetime | None = None,
    ) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO scam_checks (checked_at, chain, token_address, pool_address, verdict, "
            "reasons, info, notes, price_usd, liquidity_usd) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                _iso(checked_at or datetime.now(UTC)), chain, token_address, pool_address, verdict,
                json.dumps(reasons), json.dumps(info, default=_json_default), json.dumps(notes),
                _dec(price_usd), _dec(liquidity_usd),
            ),
        )
        self.conn.commit()

    def checks_to_label(
        self, chain: str, horizon_h: int, limit: int, *, now: datetime | None = None
    ) -> list[sqlite3.Row]:
        now = now or datetime.now(UTC)
        return self.conn.execute(
            "SELECT * FROM scam_checks c WHERE c.chain = ? AND c.checked_at <= ? AND NOT EXISTS "
            "(SELECT 1 FROM scam_labels l WHERE l.chain = c.chain AND l.token_address = c.token_address "
            "AND l.horizon_h = ?) ORDER BY c.checked_at ASC LIMIT ?",
            (chain, _iso(now - timedelta(hours=horizon_h)), horizon_h, limit),
        ).fetchall()

    def add_label(
        self, chain: str, token_address: str, horizon_h: int, outcome: str, *,
        price_ratio: Decimal | None, liquidity_usd: Decimal | None, detail: str,
    ) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO scam_labels (labeled_at, chain, token_address, horizon_h, outcome, "
            "price_ratio, liquidity_usd, detail) VALUES (?,?,?,?,?,?,?,?)",
            (_iso(datetime.now(UTC)), chain, token_address, horizon_h, outcome,
             _dec(price_ratio), _dec(liquidity_usd), detail),
        )
        self.conn.commit()

    def label_matrix(self, horizon_h: int) -> dict[tuple[str, str], int]:
        rows = self.conn.execute(
            "SELECT c.verdict, l.outcome, COUNT(*) n FROM scam_checks c JOIN scam_labels l "
            "ON l.chain = c.chain AND l.token_address = c.token_address WHERE l.horizon_h = ? "
            "GROUP BY c.verdict, l.outcome",
            (horizon_h,),
        ).fetchall()
        return {(r["verdict"], r["outcome"]): r["n"] for r in rows}

    def counts(self) -> dict[str, int]:
        return {
            table: self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("events", "tokens", "pool_snapshots", "scam_checks", "scam_labels")
        }
