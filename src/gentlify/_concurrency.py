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


class ConcurrencyController:
    """Dynamic concurrency limit via asyncio semaphore with decelerate/reaccelerate."""

    def __init__(
        self,
        max_concurrency: int,
        initial_concurrency: int | None = None,
    ) -> None:
        self._max_concurrency = max_concurrency
        self._limit = initial_concurrency if initial_concurrency is not None else max_concurrency
        self._semaphore = asyncio.Semaphore(self._limit)
        self._in_flight = 0

    @property
    def current_limit(self) -> int:
        """Current concurrency limit."""
        return self._limit

    @property
    def in_flight(self) -> int:
        """Number of currently acquired slots."""
        return self._in_flight

    async def acquire(self) -> None:
        """Wait for a concurrency slot."""
        await self._semaphore.acquire()
        self._in_flight += 1

    def release(self) -> None:
        """Release a concurrency slot."""
        self._in_flight -= 1
        self._semaphore.release()

    def decelerate(self) -> tuple[int, int]:
        """Halve the concurrency limit (min 1). Returns (old, new)."""
        old = self._limit
        new = max(1, old // 2)
        self._resize_semaphore(new)
        return (old, new)

    def reaccelerate(self, safe_ceiling: int) -> tuple[int, int]:
        """Increase concurrency by 1, capped at safe_ceiling. Returns (old, new)."""
        old = self._limit
        new = min(old + 1, safe_ceiling)
        self._resize_semaphore(new)
        return (old, new)

    def resize(self, new_limit: int) -> None:
        """Set the concurrency limit to an exact value. Used during ceiling decay reset."""
        self._resize_semaphore(new_limit)

    def _resize_semaphore(self, new_limit: int) -> None:
        """Adjust the semaphore to reflect a new concurrency limit."""
        old_limit = self._limit
        self._limit = new_limit

        diff = new_limit - old_limit
        if diff > 0:
            for _ in range(diff):
                self._semaphore.release()
        elif diff < 0:
            # Reduce available permits. We can't "un-release" a semaphore,
            # so we acquire permits to remove them. This is synchronous —
            # we only drain permits that are currently available (not in-flight).
            for _ in range(-diff):
                if self._semaphore._value > 0:  # noqa: SLF001
                    self._semaphore._value -= 1  # noqa: SLF001
