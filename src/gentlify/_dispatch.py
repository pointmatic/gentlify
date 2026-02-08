# Copyright (c) 2026 Pointmatic
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import asyncio
import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gentlify._types import Clock, RandFn


class DispatchGate:
    """Enforces minimum time gap between consecutive dispatches with jitter."""

    def __init__(
        self,
        interval: float,
        jitter_fraction: float = 0.5,
        clock: Clock = time.monotonic,
        rand_fn: RandFn = random.uniform,
    ) -> None:
        self._interval = interval
        self._jitter_fraction = jitter_fraction
        self._clock = clock
        self._rand_fn = rand_fn
        self._last_dispatch: float | None = None

    @property
    def interval(self) -> float:
        """Current dispatch interval."""
        return self._interval

    async def wait(self) -> None:
        """Wait until the next dispatch is allowed, with jitter."""
        now = self._clock()

        if self._last_dispatch is not None:
            elapsed = now - self._last_dispatch
            remaining = max(0.0, self._interval - elapsed)
        else:
            remaining = 0.0

        jitter = self._rand_fn(0.0, self._interval * self._jitter_fraction)
        delay = remaining + jitter

        await asyncio.sleep(delay)

        self._last_dispatch = self._clock()

    def decelerate(self, max_interval: float) -> tuple[float, float]:
        """Double the interval (capped at max_interval). Returns (old, new)."""
        old = self._interval
        self._interval = min(old * 2, max_interval)
        return (old, self._interval)

    def reaccelerate(self, min_interval: float) -> tuple[float, float]:
        """Halve the interval (floored at min_interval). Returns (old, new)."""
        old = self._interval
        self._interval = max(old / 2, min_interval)
        return (old, self._interval)
