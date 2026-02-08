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

import pytest

from gentlify import (
    CircuitBreakerConfig,
    RetryConfig,
    Throttle,
    ThrottleClosed,
    ThrottleState,
    TokenBudget,
)


class TestZeroTotalTasks:
    async def test_progress_reports_no_eta(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            total_tasks=0,
        )
        async with t.acquire():
            pass
        snap = t.snapshot()
        assert snap.eta_seconds is None
        assert snap.completed_tasks == 1


class TestMaxConcurrencyOne:
    async def test_deceleration_stays_at_one(self) -> None:
        t = Throttle(
            max_concurrency=1,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=1,
        )
        with pytest.raises(RuntimeError):
            async with t.acquire():
                raise RuntimeError("fail")
        # Decelerate from 1: floor is 1
        assert t.snapshot().concurrency == 1
        assert t.snapshot().state == ThrottleState.COOLING


class TestImmediateFirstFailure:
    async def test_deceleration_on_first_request(self) -> None:
        t = Throttle(
            max_concurrency=10,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=1,
        )
        with pytest.raises(RuntimeError):
            async with t.acquire():
                raise RuntimeError("first request fails")
        assert t.snapshot().concurrency == 5
        assert t.snapshot().state == ThrottleState.COOLING


class TestFailurePredicateAlwaysFalse:
    async def test_no_deceleration_ever(self) -> None:
        t = Throttle(
            max_concurrency=10,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=1,
            failure_predicate=lambda _e: False,
        )
        for _ in range(5):
            with pytest.raises(RuntimeError):
                async with t.acquire():
                    raise RuntimeError("ignored")
        # No deceleration because predicate always returns False
        assert t.snapshot().concurrency == 10
        assert t.snapshot().state == ThrottleState.RUNNING


class TestCircuitBreakerZeroOpenDuration:
    async def test_immediately_half_open(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=100,  # high so throttle doesn't decelerate
            circuit_breaker=CircuitBreakerConfig(
                consecutive_failures=1,
                open_duration=0.0,
            ),
        )
        # Trip the circuit
        with pytest.raises(RuntimeError):
            async with t.acquire():
                raise RuntimeError("trip")
        # With open_duration=0, circuit should immediately be half-open
        # so acquire should succeed (probe allowed)
        async with t.acquire():
            pass


class TestTokenBudgetOfOne:
    async def test_single_token_budget(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            token_budget=TokenBudget(max_tokens=1, window_seconds=0.1),
        )
        # First request uses 1 token
        async with t.acquire() as slot:
            slot.record_tokens(1)
        assert t.snapshot().tokens_used == 1
        assert t.snapshot().tokens_remaining == 0

        # Wait for window to roll over
        await asyncio.sleep(0.15)
        assert t.snapshot().tokens_remaining == 1


class TestConcurrentDrainAndAcquire:
    async def test_drain_completes_acquire_raises(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
        )
        completed = False

        async def in_flight_request() -> None:
            nonlocal completed
            async with t.acquire():
                await asyncio.sleep(0.1)
                completed = True

        task = asyncio.create_task(in_flight_request())
        await asyncio.sleep(0.02)

        # Start drain (sets state to DRAINING)
        drain_task = asyncio.create_task(t.drain())
        await asyncio.sleep(0.01)

        # New acquire should raise ThrottleClosed
        with pytest.raises(ThrottleClosed):
            async with t.acquire():
                pass

        await drain_task
        assert completed
        assert t.snapshot().state == ThrottleState.CLOSED
        await task


class TestOrganicPromotion:
    async def test_initial_low_concurrency_reaccelerates(self) -> None:
        t = Throttle(
            max_concurrency=10,
            initial_concurrency=2,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=1,
            cooling_period=0.001,  # near-instant cooling
        )
        assert t.snapshot().concurrency == 2

        # Trigger deceleration: 2 -> 1
        with pytest.raises(RuntimeError):
            async with t.acquire():
                raise RuntimeError("fail")
        assert t.snapshot().concurrency == 1
        assert t.snapshot().state == ThrottleState.COOLING

        # Wait for cooling period to elapse, then success reaccelerates
        await asyncio.sleep(0.01)
        async with t.acquire():
            pass
        assert t.snapshot().state == ThrottleState.RUNNING
        # Reaccelerated from 1 toward safe_ceiling (2), so now 2
        assert t.snapshot().concurrency == 2


class TestRapidSuccessiveFailures:
    async def test_counter_cleared_after_deceleration(self) -> None:
        t = Throttle(
            max_concurrency=16,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=2,
        )
        # Two failures -> decelerate (16 -> 8), counter cleared
        for _ in range(2):
            with pytest.raises(RuntimeError):
                async with t.acquire():
                    raise RuntimeError("fail")
        assert t.snapshot().concurrency == 8

        # One more failure — not enough to trigger again (need 2)
        with pytest.raises(RuntimeError):
            async with t.acquire():
                raise RuntimeError("fail")
        assert t.snapshot().concurrency == 8

        # Second failure in new window -> decelerate (8 -> 4)
        with pytest.raises(RuntimeError):
            async with t.acquire():
                raise RuntimeError("fail")
        assert t.snapshot().concurrency == 4


class TestZeroJitter:
    async def test_deterministic_dispatch(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
        )
        # Multiple acquires should work without any jitter delay
        for _ in range(5):
            async with t.acquire():
                pass
        assert t.snapshot().completed_tasks == 5


class TestRetryWithNoRetryConfig:
    async def test_wrap_without_retry_behaves_normally(self) -> None:
        """wrap() without retry config calls function exactly once."""
        call_count = 0
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
        )

        @t.wrap
        async def fail() -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("no retry")

        with pytest.raises(RuntimeError, match="no retry"):
            await fail()
        assert call_count == 1


class TestRetryWithAcquire:
    async def test_acquire_does_not_retry(self) -> None:
        """acquire() context manager does not retry — user handles it."""
        call_count = 0
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            retry=RetryConfig(
                max_attempts=3,
                backoff="fixed",
                base_delay=0.0,
            ),
        )

        with pytest.raises(RuntimeError, match="manual"):
            async with t.acquire():
                call_count += 1
                raise RuntimeError("manual")
        # Body only executes once — retry doesn't apply to acquire()
        assert call_count == 1


class TestRetrySucceedsOnLastAttempt:
    async def test_succeeds_on_final_attempt(self) -> None:
        """Function succeeds on the very last allowed attempt."""
        call_count = 0
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            retry=RetryConfig(
                max_attempts=3,
                backoff="fixed",
                base_delay=0.0,
            ),
        )

        @t.wrap
        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient")
            return "finally"

        result = await flaky()
        assert result == "finally"
        assert call_count == 3
