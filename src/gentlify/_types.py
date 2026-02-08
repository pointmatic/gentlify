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

import enum
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ThrottleState(enum.Enum):
    RUNNING = "running"
    COOLING = "cooling"
    CIRCUIT_OPEN = "circuit_open"
    CLOSED = "closed"
    DRAINING = "draining"


@dataclass(frozen=True)
class ThrottleSnapshot:
    """Point-in-time view of throttle state."""

    concurrency: int
    max_concurrency: int
    dispatch_interval: float
    completed_tasks: int
    total_tasks: int
    failure_count: int
    state: ThrottleState
    safe_ceiling: int
    eta_seconds: float | None
    tokens_used: int
    tokens_remaining: int | None


@dataclass(frozen=True)
class ThrottleEvent:
    """Structured event emitted on state transitions."""

    kind: str
    timestamp: float
    data: dict[str, Any]


FailurePredicate = Callable[[BaseException], bool]
StateChangeCallback = Callable[[ThrottleEvent], Any]
ProgressCallback = Callable[[ThrottleSnapshot], Any]
Clock = Callable[[], float]
RandFn = Callable[[float, float], float]
