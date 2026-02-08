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
import time
from typing import TYPE_CHECKING

from gentlify._window import SlidingWindow

if TYPE_CHECKING:
    from gentlify._config import TokenBudget
    from gentlify._types import Clock


class TokenBucket:
    """Rolling-window token budget tracker.

    Uses a SlidingWindow internally to track token consumption over time.
    """

    def __init__(
        self,
        budget: TokenBudget,
        clock: Clock = time.monotonic,
    ) -> None:
        self._budget = budget
        self._clock = clock
        self._window = SlidingWindow(
            window_seconds=budget.window_seconds,
            clock=clock,
        )

    def consume(self, tokens: int) -> None:
        """Record token consumption."""
        self._window.record(float(tokens))

    def tokens_used(self) -> int:
        """Tokens consumed in the current window."""
        return int(self._window.total())

    def tokens_remaining(self) -> int:
        """Tokens remaining in the current window."""
        return max(0, self._budget.max_tokens - self.tokens_used())

    async def wait_for_budget(self, tokens: int = 1) -> None:
        """Block until at least ``tokens`` are available in the budget window.

        Computes the time until enough tokens expire from the window and
        sleeps accordingly.
        """
        while self.tokens_remaining() < tokens:
            # Find the oldest entry — that's the one that will expire first.
            # Sleep until it falls out of the window, then re-check.
            if self._window._entries:  # noqa: SLF001
                oldest_ts = self._window._entries[0][0]  # noqa: SLF001
                expires_at = oldest_ts + self._budget.window_seconds
                sleep_time = max(0.0, expires_at - self._clock())
                await asyncio.sleep(sleep_time + 0.001)
            else:
                # No entries but still over budget shouldn't happen,
                # but guard against infinite loop.
                break
