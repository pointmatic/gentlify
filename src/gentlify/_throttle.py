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
import functools
import logging
import random
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from gentlify._circuit_breaker import CircuitBreaker
from gentlify._concurrency import ConcurrencyController
from gentlify._config import ThrottleConfig
from gentlify._dispatch import DispatchGate
from gentlify._exceptions import ThrottleClosed
from gentlify._progress import ProgressTracker
from gentlify._slot import Slot
from gentlify._token_bucket import TokenBucket
from gentlify._types import (
    ThrottleEvent,
    ThrottleSnapshot,
    ThrottleState,
)
from gentlify._window import SlidingWindow

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_log = logging.getLogger("gentlify")


class Throttle:
    """Main orchestrator — wires all components together."""

    def __init__(self, **kwargs: Any) -> None:
        """Accept all ThrottleConfig fields as kwargs."""
        self._config = ThrottleConfig(**kwargs)
        self._clock = time.monotonic
        self._rand_fn = random.uniform

        self._concurrency = ConcurrencyController(
            max_concurrency=self._config.max_concurrency,
            initial_concurrency=self._config.initial_concurrency,
        )
        self._dispatch = DispatchGate(
            interval=self._config.min_dispatch_interval,
            jitter_fraction=self._config.jitter_fraction,
            clock=self._clock,
            rand_fn=self._rand_fn,
        )
        self._failure_window = SlidingWindow(
            window_seconds=self._config.failure_window,
            clock=self._clock,
        )
        self._progress = ProgressTracker(
            total_tasks=self._config.total_tasks,
            clock=self._clock,
        )

        self._token_bucket: TokenBucket | None = None
        if self._config.token_budget is not None:
            self._token_bucket = TokenBucket(
                budget=self._config.token_budget,
                clock=self._clock,
            )

        self._circuit_breaker: CircuitBreaker | None = None
        if self._config.circuit_breaker is not None:
            self._circuit_breaker = CircuitBreaker(
                config=self._config.circuit_breaker,
                clock=self._clock,
            )

        self._state = ThrottleState.RUNNING
        self._safe_ceiling = self._config.max_concurrency
        self._cooling_start: float | None = None
        self._last_failure_time: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Throttle:
        """Build a Throttle from a plain dict."""
        config = ThrottleConfig.from_dict(data)
        return cls(**{
            f.name: getattr(config, f.name)
            for f in config.__dataclass_fields__.values()
        })

    @classmethod
    def from_env(cls, prefix: str = "GENTLIFY") -> Throttle:
        """Build a Throttle from environment variables."""
        config = ThrottleConfig.from_env(prefix)
        return cls(**{
            f.name: getattr(config, f.name)
            for f in config.__dataclass_fields__.values()
        })

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[Slot]:
        """Primary API: acquire a throttled slot."""
        # 1. Check state
        if self._state in (ThrottleState.CLOSED, ThrottleState.DRAINING):
            raise ThrottleClosed()

        # 2. Circuit breaker check
        if self._circuit_breaker is not None:
            self._circuit_breaker.check()

        # 3. Acquire concurrency slot
        await self._concurrency.acquire()

        start = self._clock()
        slot = Slot()
        exc_occurred: BaseException | None = None

        try:
            # 4. Dispatch gate
            await self._dispatch.wait()

            # 5. Token budget
            if self._token_bucket is not None:
                await self._token_bucket.wait_for_budget()

            # 6. Yield slot
            yield slot

        except BaseException as exc:
            exc_occurred = exc
            raise

        finally:
            duration = self._clock() - start

            if exc_occurred is not None:
                self._handle_failure(exc_occurred)
            else:
                self._handle_success(duration, slot.tokens_reported)

            # Always release
            self._concurrency.release()

    def _handle_success(self, duration: float, tokens: int) -> None:
        """Process a successful request completion."""
        # 1. Circuit breaker
        if self._circuit_breaker is not None:
            self._circuit_breaker.record_success()

        # 2. Check cooling -> reaccelerate
        if (
            self._state == ThrottleState.COOLING
            and self._cooling_start is not None
        ):
            elapsed = self._clock() - self._cooling_start
            if elapsed >= self._config.cooling_period:
                old_c, new_c = self._concurrency.reaccelerate(
                    self._safe_ceiling
                )
                old_i, new_i = self._dispatch.reaccelerate(
                    self._config.min_dispatch_interval
                )
                self._state = ThrottleState.RUNNING
                self._cooling_start = None
                _log.info(
                    "Reaccelerated: concurrency %d->%d, interval %.3f->%.3f",
                    old_c, new_c, old_i, new_i,
                )
                self._emit_event("reaccelerated", {
                    "concurrency": (old_c, new_c),
                    "interval": (old_i, new_i),
                })

        # 3. Safe ceiling decay
        if self._last_failure_time is not None:
            decay_threshold = (
                self._config.cooling_period
                * self._config.safe_ceiling_decay_multiplier
            )
            elapsed = self._clock() - self._last_failure_time
            if elapsed >= decay_threshold:
                old_ceiling = self._safe_ceiling
                self._safe_ceiling = self._config.max_concurrency
                self._last_failure_time = None
                if old_ceiling != self._safe_ceiling:
                    _log.info(
                        "Safe ceiling decayed: %d -> %d",
                        old_ceiling, self._safe_ceiling,
                    )

        # 4. Token recording
        if self._token_bucket is not None and tokens > 0:
            self._token_bucket.consume(tokens)

        # 5. Progress tracking
        is_milestone = self._progress.record_completion(duration)
        if is_milestone and self._config.on_progress is not None:
            self._config.on_progress(self.snapshot())

    def _handle_failure(self, exception: BaseException) -> None:
        """Process a failed request."""
        # 1. Failure predicate filtering
        if (
            self._config.failure_predicate is not None
            and not self._config.failure_predicate(exception)
        ):
            return

        # 2. Record in failure window
        self._failure_window.record()
        self._last_failure_time = self._clock()

        # 3. Circuit breaker
        if self._circuit_breaker is not None:
            self._circuit_breaker.record_failure()

        # 4. Check threshold -> decelerate
        if self._failure_window.count() >= self._config.failure_threshold:
            old_c, new_c = self._concurrency.decelerate()
            old_i, new_i = self._dispatch.decelerate(
                self._config.max_dispatch_interval
            )
            self._safe_ceiling = old_c
            self._failure_window.clear()
            self._state = ThrottleState.COOLING
            self._cooling_start = self._clock()

            _log.info(
                "Decelerated: concurrency %d->%d, interval %.3f->%.3f",
                old_c, new_c, old_i, new_i,
            )
            self._emit_event("decelerated", {
                "concurrency": (old_c, new_c),
                "interval": (old_i, new_i),
                "safe_ceiling": self._safe_ceiling,
            })
            self._emit_event("cooling_started", {
                "cooling_period": self._config.cooling_period,
            })

    def _emit_event(self, kind: str, data: dict[str, Any]) -> None:
        """Emit a ThrottleEvent to the on_state_change callback."""
        if self._config.on_state_change is not None:
            event = ThrottleEvent(
                kind=kind,
                timestamp=self._clock(),
                data=data,
            )
            self._config.on_state_change(event)

    def snapshot(self) -> ThrottleSnapshot:
        """Return a point-in-time snapshot of throttle state."""
        tokens_used = 0
        tokens_remaining: int | None = None
        if self._token_bucket is not None:
            tokens_used = self._token_bucket.tokens_used()
            tokens_remaining = self._token_bucket.tokens_remaining()

        return ThrottleSnapshot(
            concurrency=self._concurrency.current_limit,
            max_concurrency=self._config.max_concurrency,
            dispatch_interval=self._dispatch.interval,
            completed_tasks=self._progress.completed,
            total_tasks=self._config.total_tasks,
            failure_count=self._failure_window.count(),
            state=self._state,
            safe_ceiling=self._safe_ceiling,
            eta_seconds=self._progress.eta_seconds,
            tokens_used=tokens_used,
            tokens_remaining=tokens_remaining,
        )

    def record_success(
        self, duration: float = 0.0, tokens_used: int = 0
    ) -> None:
        """Manually record a successful request."""
        self._handle_success(duration, tokens_used)

    def record_failure(
        self, exception: BaseException | None = None
    ) -> None:
        """Manually record a failed request."""
        exc = exception if exception is not None else Exception("manual failure")
        self._handle_failure(exc)

    def record_tokens(self, count: int) -> None:
        """Manually record token consumption."""
        if self._token_bucket is not None:
            self._token_bucket.consume(count)

    def wrap(
        self,
        fn: Any,
    ) -> Any:
        """Decorator API: wrap an async function with acquire()."""

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with self.acquire():
                return await fn(*args, **kwargs)

        return wrapper

    def close(self) -> None:
        """Signal that no new requests should be accepted."""
        self._state = ThrottleState.CLOSED
        _log.info("Throttle closed — no new requests accepted")
        self._emit_event("closed", {})

    async def drain(self) -> None:
        """Wait for all in-flight requests to complete."""
        self._state = ThrottleState.DRAINING
        _log.info("Draining — waiting for %d in-flight requests",
                   self._concurrency.in_flight)
        self._emit_event("draining", {
            "in_flight": self._concurrency.in_flight,
        })

        while self._concurrency.in_flight > 0:
            await asyncio.sleep(0.05)

        self._state = ThrottleState.CLOSED
        _log.info("Drain complete — throttle closed")
        self._emit_event("drained", {})
