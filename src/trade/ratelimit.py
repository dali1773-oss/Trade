"""Limitatore di frequenza semplice: un intervallo minimo tra due richieste.

Prudente per scelta: rispettiamo i limiti documentati con margine e non
proviamo mai ad aggirarli (niente rotazione di chiavi o di indirizzi).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class MinIntervalLimiter:
    def __init__(
        self,
        min_interval_s: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if min_interval_s < 0:
            raise ValueError("min_interval_s deve essere >= 0")
        self.min_interval_s = min_interval_s
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = self._clock()
            if self._last is not None:
                delay = self._last + self.min_interval_s - now
                if delay > 0:
                    await self._sleep(delay)
                    now = self._clock()
            self._last = now

    def penalize(self, seconds: float) -> None:
        """Dopo un 429 sposta in avanti la prossima richiesta permessa."""
        base = self._last if self._last is not None else self._clock()
        self._last = max(base, self._clock()) + seconds
