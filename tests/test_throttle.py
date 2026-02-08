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
    CircuitOpenError,
    RetryConfig,
    Throttle,
    ThrottleClosed,
    ThrottleEvent,
    ThrottleSnapshot,
    ThrottleState,
    TokenBudget,
)


class TestBasicAcquireRelease:
    async def test_success_path(self) -> None:
        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)
        async with t.acquire() as slot:
            slot.record_tokens(10)
        snap = t.snapshot()
        assert snap.completed_tasks == 1

    async def test_multiple_acquires(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
        )
        for _ in range(5):
            async with t.acquire():
                pass
        assert t.snapshot().completed_tasks == 5

    async def test_slot_tokens_reported(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            token_budget=TokenBudget(max_tokens=10000, window_seconds=60.0),
        )
        async with t.acquire() as slot:
            slot.record_tokens(100)
            slot.record_tokens(50)
            assert slot.tokens_reported == 150
        assert t.snapshot().tokens_used == 150


class TestFailureDeceleration:
    async def test_failure_triggers_deceleration(self) -> None:
        t = Throttle(
            max_concurrency=10,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=1,
        )
        assert t.snapshot().concurrency == 10
        with pytest.raises(RuntimeError):
            async with t.acquire():
                raise RuntimeError("fail")
        # After 1 failure (threshold=1), should decelerate
        assert t.snapshot().concurrency == 5
        assert t.snapshot().state == ThrottleState.COOLING

    async def test_multiple_failures_before_threshold(self) -> None:
        t = Throttle(
            max_concurrency=10,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=3,
        )
        for _ in range(2):
            with pytest.raises(RuntimeError):
                async with t.acquire():
                    raise RuntimeError("fail")
        # Not yet at threshold
        assert t.snapshot().concurrency == 10
        # Third failure triggers deceleration
        with pytest.raises(RuntimeError):
            async with t.acquire():
                raise RuntimeError("fail")
        assert t.snapshot().concurrency == 5


class TestFailurePredicate:
    async def test_predicate_filters_exceptions(self) -> None:
        t = Throttle(
            max_concurrency=10,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=1,
            failure_predicate=lambda e: isinstance(e, ValueError),
        )
        # RuntimeError should be ignored by predicate
        with pytest.raises(RuntimeError):
            async with t.acquire():
                raise RuntimeError("not a throttle failure")
        assert t.snapshot().concurrency == 10  # no deceleration

        # ValueError should trigger deceleration
        with pytest.raises(ValueError):
            async with t.acquire():
                raise ValueError("throttle failure")
        assert t.snapshot().concurrency == 5


class TestSafeCeiling:
    async def test_safe_ceiling_set_on_deceleration(self) -> None:
        t = Throttle(
            max_concurrency=10,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=1,
        )
        with pytest.raises(RuntimeError):
            async with t.acquire():
                raise RuntimeError("fail")
        assert t.snapshot().safe_ceiling == 10
        assert t.snapshot().concurrency == 5


class TestSnapshot:
    async def test_snapshot_fields(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.2,
            total_tasks=10,
        )
        snap = t.snapshot()
        assert snap.max_concurrency == 5
        assert snap.concurrency == 5
        assert snap.dispatch_interval == 0.2
        assert snap.total_tasks == 10
        assert snap.completed_tasks == 0
        assert snap.state == ThrottleState.RUNNING
        assert snap.safe_ceiling == 5
        assert snap.tokens_used == 0
        assert snap.tokens_remaining is None

    async def test_snapshot_with_token_budget(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            token_budget=TokenBudget(max_tokens=1000, window_seconds=60.0),
        )
        snap = t.snapshot()
        assert snap.tokens_remaining == 1000
        assert snap.tokens_used == 0


class TestStateChangeCallback:
    async def test_fires_on_deceleration(self) -> None:
        events: list[ThrottleEvent] = []
        t = Throttle(
            max_concurrency=10,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=1,
            on_state_change=lambda e: events.append(e),
        )
        with pytest.raises(RuntimeError):
            async with t.acquire():
                raise RuntimeError("fail")
        kinds = [e.kind for e in events]
        assert "decelerated" in kinds
        assert "cooling_started" in kinds


class TestProgressCallback:
    async def test_fires_at_milestone(self) -> None:
        snapshots: list[ThrottleSnapshot] = []
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            total_tasks=10,
            on_progress=lambda s: snapshots.append(s),
        )
        for _ in range(10):
            async with t.acquire():
                pass
        # Should have fired at 10%, 20%, ..., 100%
        assert len(snapshots) == 10


class TestCircuitBreakerIntegration:
    async def test_raises_circuit_open_error(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            circuit_breaker=CircuitBreakerConfig(consecutive_failures=1, open_duration=10.0),
        )
        # Trip the circuit
        with pytest.raises(RuntimeError):
            async with t.acquire():
                raise RuntimeError("fail")
        # Next acquire should raise CircuitOpenError
        with pytest.raises(CircuitOpenError):
            async with t.acquire():
                pass


class TestTokenBudgetIntegration:
    async def test_token_recording(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            token_budget=TokenBudget(max_tokens=1000, window_seconds=60.0),
        )
        async with t.acquire() as slot:
            slot.record_tokens(200)
        assert t.snapshot().tokens_used == 200
        assert t.snapshot().tokens_remaining == 800


class TestManualRecordMethods:
    def test_record_success(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            total_tasks=10,
        )
        t.record_success(duration=1.0)
        assert t.snapshot().completed_tasks == 1

    def test_record_failure(self) -> None:
        t = Throttle(
            max_concurrency=10,
            min_dispatch_interval=0.0,
            failure_threshold=1,
        )
        t.record_failure()
        assert t.snapshot().concurrency == 5

    def test_record_tokens(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            token_budget=TokenBudget(max_tokens=1000, window_seconds=60.0),
        )
        t.record_tokens(300)
        assert t.snapshot().tokens_used == 300


class TestMultipleInstances:
    async def test_independent_throttles(self) -> None:
        t1 = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=1,
        )
        t2 = Throttle(
            max_concurrency=10,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
        )
        # Fail t1
        with pytest.raises(RuntimeError):
            async with t1.acquire():
                raise RuntimeError("fail")
        assert t1.snapshot().concurrency == 2  # 5 // 2
        # t2 should be unaffected
        assert t2.snapshot().concurrency == 10
        async with t2.acquire():
            pass
        assert t2.snapshot().completed_tasks == 1


class TestFromDict:
    def test_from_dict(self) -> None:
        t = Throttle.from_dict({"max_concurrency": 20})
        assert t.snapshot().max_concurrency == 20

    def test_from_dict_with_nested(self) -> None:
        t = Throttle.from_dict(
            {
                "max_concurrency": 10,
                "token_budget": {
                    "max_tokens": 5000,
                    "window_seconds": 60.0,
                },
            }
        )
        assert t.snapshot().tokens_remaining == 5000


class TestFromEnv:
    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GENTLIFY_MAX_CONCURRENCY", "15")
        t = Throttle.from_env()
        assert t.snapshot().max_concurrency == 15


class TestWrapDecorator:
    async def test_wrap_records_success(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            total_tasks=10,
        )

        @t.wrap
        async def my_fn(x: int) -> int:
            return x * 2

        result = await my_fn(5)
        assert result == 10
        assert t.snapshot().completed_tasks == 1

    async def test_wrap_records_failure(self) -> None:
        t = Throttle(
            max_concurrency=10,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=1,
        )

        @t.wrap
        async def failing_fn() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await failing_fn()
        assert t.snapshot().concurrency == 5

    async def test_wrap_preserves_function_name(self) -> None:
        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)

        @t.wrap
        async def my_special_fn() -> None:
            pass

        assert my_special_fn.__name__ == "my_special_fn"

    async def test_wrap_preserves_return_value(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
        )

        @t.wrap
        async def compute(a: int, b: int) -> dict[str, int]:
            return {"sum": a + b}

        result = await compute(3, 7)
        assert result == {"sum": 10}


class TestClose:
    async def test_close_rejects_new_acquires(self) -> None:
        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)
        t.close()
        with pytest.raises(ThrottleClosed):
            async with t.acquire():
                pass

    async def test_close_sets_state(self) -> None:
        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)
        t.close()
        assert t.snapshot().state == ThrottleState.CLOSED

    async def test_in_flight_completes_after_close(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
        )
        completed = False

        async def long_request() -> None:
            nonlocal completed
            async with t.acquire():
                await asyncio.sleep(0.1)
                completed = True

        task = asyncio.create_task(long_request())
        await asyncio.sleep(0.02)
        t.close()
        # In-flight request should still complete
        await task
        assert completed


class TestDrain:
    async def test_drain_waits_for_in_flight(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
        )
        completed = False

        async def long_request() -> None:
            nonlocal completed
            async with t.acquire():
                await asyncio.sleep(0.1)
                completed = True

        task = asyncio.create_task(long_request())
        await asyncio.sleep(0.02)
        await t.drain()
        assert completed
        assert t.snapshot().state == ThrottleState.CLOSED
        await task  # ensure no unhandled exceptions

    async def test_close_then_drain(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
        )
        completed = False

        async def long_request() -> None:
            nonlocal completed
            async with t.acquire():
                await asyncio.sleep(0.1)
                completed = True

        task = asyncio.create_task(long_request())
        await asyncio.sleep(0.02)
        t.close()
        await t.drain()
        assert completed
        assert t.snapshot().state == ThrottleState.CLOSED
        await task

    async def test_drain_immediate_when_no_in_flight(self) -> None:
        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)
        await t.drain()
        assert t.snapshot().state == ThrottleState.CLOSED


class TestRetryIntegration:
    async def test_wrap_retries_and_succeeds(self) -> None:
        """wrap() retries on failure and succeeds on second attempt."""
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
            if call_count < 2:
                raise RuntimeError("transient")
            return "ok"

        result = await flaky()
        assert result == "ok"
        assert call_count == 2
        # Success path — completed_tasks incremented
        assert t.snapshot().completed_tasks == 1

    async def test_wrap_exhausts_retries(self) -> None:
        """wrap() exhausts retries and records final failure."""
        call_count = 0
        t = Throttle(
            max_concurrency=10,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=1,
            retry=RetryConfig(
                max_attempts=3,
                backoff="fixed",
                base_delay=0.0,
            ),
        )

        @t.wrap
        async def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("permanent")

        with pytest.raises(RuntimeError, match="permanent"):
            await always_fail()
        assert call_count == 3
        # Final failure triggers deceleration
        assert t.snapshot().concurrency == 5

    async def test_retry_respects_retryable_predicate(self) -> None:
        """Non-retryable exception propagates immediately."""
        call_count = 0
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            retry=RetryConfig(
                max_attempts=3,
                backoff="fixed",
                base_delay=0.0,
                retryable=lambda e: isinstance(e, RuntimeError),
            ),
        )

        @t.wrap
        async def raises_value_error() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError, match="not retryable"):
            await raises_value_error()
        # Should not have retried
        assert call_count == 1

    async def test_retry_emits_events(self) -> None:
        """Retry emits 'retry' events via on_state_change."""
        events: list[ThrottleEvent] = []
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
            on_state_change=lambda e: events.append(e),
        )

        @t.wrap
        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient")
            return "ok"

        await flaky()
        retry_events = [e for e in events if e.kind == "retry"]
        assert len(retry_events) == 2
        assert retry_events[0].data["attempt"] == 1
        assert retry_events[1].data["attempt"] == 2

    async def test_retry_circuit_breaker_opens_during_retry(self) -> None:
        """Circuit opens during retry, CircuitOpenError propagates."""
        call_count = 0
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=100,  # high so throttle doesn't decelerate
            circuit_breaker=CircuitBreakerConfig(
                consecutive_failures=1,
                open_duration=10.0,
            ),
            retry=RetryConfig(
                max_attempts=5,
                backoff="fixed",
                base_delay=0.0,
            ),
        )

        @t.wrap
        async def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        with pytest.raises(CircuitOpenError):
            await always_fail()
        # First attempt fails, circuit trips (consecutive_failures=1),
        # retry checks circuit before attempt 2 -> CircuitOpenError
        assert call_count == 1

    async def test_retry_max_attempts_one_behaves_like_no_retry(self) -> None:
        """max_attempts=1 means no retries."""
        call_count = 0
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            retry=RetryConfig(
                max_attempts=1,
                backoff="fixed",
                base_delay=0.0,
            ),
        )

        @t.wrap
        async def fail_once() -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError, match="fail"):
            await fail_once()
        assert call_count == 1

    async def test_intermediate_failures_do_not_decelerate(self) -> None:
        """Only the final failure (after retries exhausted) triggers deceleration."""
        call_count = 0
        t = Throttle(
            max_concurrency=10,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
            failure_threshold=1,
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
            return "ok"

        result = await flaky()
        assert result == "ok"
        assert call_count == 3
        # Intermediate failures should NOT have triggered deceleration
        assert t.snapshot().concurrency == 10
        assert t.snapshot().state == ThrottleState.RUNNING
