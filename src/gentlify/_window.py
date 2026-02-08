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

import time
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gentlify._types import Clock


class SlidingWindow:
    """Bounded sliding-window tracker for timestamps and values.

    Used by both failure counting (value=1.0) and token budgeting (value=tokens).
    Entries older than ``window_seconds`` are lazily pruned on access.
    """

    def __init__(
        self,
        window_seconds: float,
        clock: Clock = time.monotonic,
    ) -> None:
        self._window_seconds = window_seconds
        self._clock = clock
        self._entries: deque[tuple[float, float]] = deque()

    def record(self, value: float = 1.0) -> None:
        """Record a value at the current time."""
        self._entries.append((self._clock(), value))

    def _prune(self) -> None:
        """Remove entries older than the window."""
        cutoff = self._clock() - self._window_seconds
        while self._entries and self._entries[0][0] < cutoff:
            self._entries.popleft()

    def total(self) -> float:
        """Sum of values within the window, after pruning expired entries."""
        self._prune()
        return sum(v for _, v in self._entries)

    def count(self) -> int:
        """Number of entries within the window."""
        self._prune()
        return len(self._entries)

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()
