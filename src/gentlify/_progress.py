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

_DEFAULT_ROLLING_SIZE = 50


class ProgressTracker:
    """Tracks task completion, computes ETA, and detects milestones."""

    def __init__(
        self,
        total_tasks: int,
        milestone_pct: float = 10.0,
        clock: Clock = time.monotonic,
    ) -> None:
        self._total_tasks = total_tasks
        self._milestone_pct = milestone_pct
        self._clock = clock
        self._completed = 0
        self._durations: deque[float] = deque(maxlen=_DEFAULT_ROLLING_SIZE)
        self._last_milestone: int = 0  # last milestone index crossed

    def record_completion(self, duration: float) -> bool:
        """Record a task completion. Returns True if a milestone was crossed."""
        self._completed += 1
        self._durations.append(duration)

        if self._total_tasks <= 0 or self._milestone_pct <= 0:
            return False

        current_milestone = int(self.percentage / self._milestone_pct)
        if current_milestone > self._last_milestone:
            self._last_milestone = current_milestone
            return True
        return False

    @property
    def completed(self) -> int:
        return self._completed

    @property
    def percentage(self) -> float:
        if self._total_tasks <= 0:
            return 0.0
        return min(100.0, (self._completed / self._total_tasks) * 100.0)

    @property
    def eta_seconds(self) -> float | None:
        """ETA based on rolling average of recent task durations. None if unknown."""
        if not self._durations or self._total_tasks <= 0:
            return None
        remaining = self._total_tasks - self._completed
        if remaining <= 0:
            return 0.0
        avg_duration = sum(self._durations) / len(self._durations)
        return avg_duration * remaining
