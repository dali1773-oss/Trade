"""Data Recorder (Fase 2): registra nuovi token e pool su Solana. SOLA LETTURA.

Non usa chiavi, non tocca wallet, non invia ordini. Ogni ciclo:
1. GeckoTerminal: nuovi pool su Solana -> snapshot + token da seguire.
2. DexScreener: ultimi profili token su Solana -> token da seguire.
3. DexScreener: aggiorna i pool dei token seguiti (prima i più "vecchi").

Uso:  uv run trade-record --once
      uv run trade-record --interval 60
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from trade.modes import Mode
from trade.sources import SourceError, make_client
from trade.sources.dexscreener import SOURCE as DS, DexScreenerClient
from trade.sources.geckoterminal import SOURCE as GT, GeckoTerminalClient
from trade.store import Store

log = logging.getLogger("trade.recorder")

CHAIN = "solana"
DEFAULT_DB = Path("data/recorder.sqlite")


@dataclass
class CycleStats:
    new_tokens: int = 0
    snapshots: int = 0
    errors: int = 0
    scans: int = 0


class Recorder:
    def __init__(
        self,
        store: Store,
        dexscreener: DexScreenerClient,
        geckoterminal: GeckoTerminalClient,
        *,
        refresh_per_cycle: int = 20,
        scanner: Any = None,
        scans_per_cycle: int = 3,
    ) -> None:
        self.store = store
        self.ds = dexscreener
        self.gt = geckoterminal
        self.refresh_per_cycle = refresh_per_cycle
        self.mode = Mode.RECORD
        # Facoltativo (--scan): verdetto anti-truffa sui token nuovi. Sola lettura.
        self.scanner = scanner
        self.scans_per_cycle = scans_per_cycle

    def _error(self, stats: CycleStats, source: str, exc: Exception) -> None:
        stats.errors += 1
        log.warning("errore fonte %s: %s", source, exc)
        self.store.log_event("source_error", {"error": str(exc)}, source=source)

    async def _scan(self, stats: CycleStats, token: str) -> None:
        try:
            res = await self.scanner.check(token)
        except Exception as exc:  # un errore non deve fermare il registratore
            self._error(stats, "scan", exc)
            return
        stats.scans += 1
        if res.verdict is None:
            self.store.add_scam_check(CHAIN, token, verdict="UNKNOWN", reasons=[res.message], info={}, notes=[])
            return
        self.store.add_scam_check(
            CHAIN, token,
            verdict=res.verdict.verdict.value,
            reasons=res.verdict.reasons,
            info=dict(res.report.info.__dict__),
            notes=res.report.notes,
            pool_address=res.main_pool.pool_address,
            price_usd=res.main_pool.price_usd,
            liquidity_usd=res.main_pool.liquidity_usd,
        )

    async def run_cycle(self) -> CycleStats:
        stats = CycleStats()

        try:
            pools = await self.gt.new_pools(CHAIN)
            stats.snapshots += self.store.add_snapshots(pools)
            for pool in pools:
                if self.store.ensure_token(CHAIN, pool.base_token, GT, pool.observed_at):
                    stats.new_tokens += 1
        except SourceError as exc:
            self._error(stats, GT, exc)

        try:
            for profile in await self.ds.latest_token_profiles(CHAIN):
                if self.store.upsert_token(profile):
                    stats.new_tokens += 1
        except SourceError as exc:
            self._error(stats, DS, exc)

        for token in self.store.tokens_to_refresh(CHAIN, self.refresh_per_cycle):
            try:
                pairs = await self.ds.token_pairs(token, CHAIN)
            except SourceError as exc:
                self._error(stats, DS, exc)
                continue
            stats.snapshots += self.store.add_snapshots(pairs)
            self.store.mark_snapshot(CHAIN, token, datetime.now(UTC))

        if self.scanner is not None:
            for token in self.store.tokens_to_scan(CHAIN, self.scans_per_cycle):
                await self._scan(stats, token)

        self.store.log_event(
            "cycle",
            {"new_tokens": stats.new_tokens, "snapshots": stats.snapshots, "errors": stats.errors,
             "scans": stats.scans},
        )
        return stats


async def _main_async(args: argparse.Namespace, transport: httpx.AsyncBaseTransport | None = None) -> int:
    store = Store(args.db)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass

    log.info("modalità %s, database %s (sola lettura, nessun ordine)", Mode.RECORD.value, args.db)
    store.log_event("recorder_start", {"mode": Mode.RECORD.value, "interval_s": args.interval, "scan": bool(getattr(args, "scan", False))})
    cycles = 0
    async with make_client(transport) as client:
        ds = DexScreenerClient(client)
        scanner = None
        if getattr(args, "scan", False):
            from trade.config import load_settings
            from trade.security import Scanner, keys_from
            from trade.sources.helius import HeliusClient
            from trade.sources.jupiter import JupiterClient

            keys = keys_from(load_settings(args.settings))
            if keys is None:
                log.error("--scan richiede le chiavi Helius e Jupiter (vedi trade-check-keys)")
                store.log_event("recorder_stop", {"cycles": 0, "error": "chiavi mancanti"})
                store.close()
                return 2
            scanner = Scanner(ds, HeliusClient(client, keys[0]), JupiterClient(client, keys[1]))
        recorder = Recorder(
            store,
            ds,
            GeckoTerminalClient(client),
            refresh_per_cycle=args.refresh,
            scanner=scanner,
        )
        while not stop.is_set():
            # Ctrl+C interrompe subito anche un ciclo in corso: ogni snapshot già
            # salvato resta nel database, il ciclo a metà viene semplicemente scartato.
            cycle = asyncio.ensure_future(recorder.run_cycle())
            stopper = asyncio.ensure_future(stop.wait())
            done, _ = await asyncio.wait({cycle, stopper}, return_when=asyncio.FIRST_COMPLETED)
            if cycle not in done:
                cycle.cancel()
                try:
                    await cycle
                except asyncio.CancelledError:
                    pass
                break
            stopper.cancel()
            stats = cycle.result()
            cycles += 1
            totals = store.counts()
            log.info(
                "ciclo %d: nuovi token %d, snapshot %d, verdetti %d, errori %d | totale token %d, snapshot %d, verdetti %d",
                cycles, stats.new_tokens, stats.snapshots, stats.scans, stats.errors,
                totals["tokens"], totals["pool_snapshots"], totals["scam_checks"],
            )
            if args.once or (args.max_cycles and cycles >= args.max_cycles):
                break
            try:
                await asyncio.wait_for(stop.wait(), timeout=args.interval)
            except TimeoutError:
                pass
    store.log_event("recorder_stop", {"cycles": cycles})
    store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Registratore dati Trade (sola lettura)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="file SQLite")
    parser.add_argument("--once", action="store_true", help="esegue un solo ciclo")
    parser.add_argument("--interval", type=float, default=60.0, help="secondi tra i cicli (min 30)")
    parser.add_argument("--max-cycles", type=int, default=0, help="0 = senza limite")
    parser.add_argument("--refresh", type=int, default=20, help="token da aggiornare per ciclo")
    parser.add_argument("--scan", action="store_true",
                        help="verdetto anti-truffa sui token nuovi (usa le chiavi Helius/Jupiter, sola lettura)")
    parser.add_argument("--settings", type=Path, default=Path(".env"), help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.interval = max(args.interval, 30.0)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Una riga per ogni richiesta HTTP riempirebbe il disco: solo avvisi ed errori.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
