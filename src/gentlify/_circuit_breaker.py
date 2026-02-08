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
from typing import TYPE_CHECKING

from gentlify._exceptions import CircuitOpenError

if TYPE_CHECKING:
    from gentlify._config import CircuitBreakerConfig
    from gentlify._types import Clock

_STATE_CLOSED = "closed"
_STATE_OPEN = "open"
_STATE_HALF_OPEN = "half_open"


class CircuitBreaker:
    """Three-state circuit breaker: closed -> open -> half-open -> closed/open."""

    def __init__(
        self,
        config: CircuitBreakerConfig,
        clock: Clock = time.monotonic,
    ) -> None:
        self._config = config
        self._clock = clock
        self._state = _STATE_CLOSED
        self._consecutive_failures = 0
        self._half_open_successes = 0
        self._opened_at = 0.0
        self._current_open_duration = config.open_duration
        self._half_open_probes = 0

    @property
    def state(self) -> str:
        """Current state: 'closed', 'open', 'half_open'."""
        self._maybe_transition_to_half_open()
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def half_open_successes(self) -> int:
        return self._half_open_successes

    def check(self) -> None:
        """Raise CircuitOpenError if open. Allow probes if half-open."""
        self._maybe_transition_to_half_open()

        if self._state == _STATE_OPEN:
            retry_after = max(
                0.0,
                self._current_open_duration - (self._clock() - self._opened_at),
            )
            raise CircuitOpenError(retry_after=retry_after)

        if self._state == _STATE_HALF_OPEN:
            if self._half_open_probes >= self._config.half_open_max_calls:
                retry_after = max(
                    0.0,
                    self._current_open_duration - (self._clock() - self._opened_at),
                )
                raise CircuitOpenError(retry_after=retry_after)
            self._half_open_probes += 1

    def record_success(self) -> None:
        """Record a success. Closes circuit if half-open threshold met."""
        self._consecutive_failures = 0

        if self._state == _STATE_HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self._config.half_open_max_calls:
                self._state = _STATE_CLOSED
                self._current_open_duration = self._config.open_duration
                self._half_open_successes = 0
                self._half_open_probes = 0

    def record_failure(self) -> None:
        """Record a failure. Opens circuit if consecutive threshold exceeded."""
        self._consecutive_failures += 1

        if self._state == _STATE_HALF_OPEN:
            # Half-open failure: re-open with doubled delay
            self._current_open_duration = min(
                self._current_open_duration * 2,
                self._config.open_duration * 5,
            )
            self._open_circuit()
        elif self._consecutive_failures >= self._config.consecutive_failures:
            self._open_circuit()

    def _open_circuit(self) -> None:
        """Transition to open state."""
        self._state = _STATE_OPEN
        self._opened_at = self._clock()
        self._half_open_successes = 0
        self._half_open_probes = 0

    def _maybe_transition_to_half_open(self) -> None:
        """Check if open duration has elapsed and transition to half-open."""
        if self._state == _STATE_OPEN:
            elapsed = self._clock() - self._opened_at
            if elapsed >= self._current_open_duration:
                self._state = _STATE_HALF_OPEN
                self._half_open_successes = 0
                self._half_open_probes = 0
