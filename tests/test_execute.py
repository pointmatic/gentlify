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
    TokenBudget,
)


class TestExecuteBasicFlow:
    async def test_execute_calls_fn_and_returns_result(self) -> None:
        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)
        result = await t.execute(lambda slot: self._async_val(42))
        assert result == 42

    async def test_execute_records_success(self) -> None:
        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)
        await t.execute(lambda slot: self._async_val("ok"))
        snap = t.snapshot()
        assert snap.completed_tasks == 1

    async def test_execute_failure_propagates(self) -> None:
        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)

        async def failing(slot):  # type: ignore[no-untyped-def]
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await t.execute(failing)

    async def test_execute_failure_records_failure(self) -> None:
        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)

        async def failing(slot):  # type: ignore[no-untyped-def]
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await t.execute(failing)
        snap = t.snapshot()
        assert snap.failure_count == 1

    @staticmethod
    async def _async_val(val):  # type: ignore[no-untyped-def]
        return val


class TestExecuteTokenRecording:
    async def test_tokens_recorded_via_slot(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            token_budget=TokenBudget(max_tokens=1000, window_seconds=60.0),
        )

        async def task(slot):  # type: ignore[no-untyped-def]
            slot.record_tokens(50)
            return "done"

        await t.execute(task)
        snap = t.snapshot()
        assert snap.tokens_used == 50


class TestExecuteRetry:
    async def test_retry_succeeds_on_second_attempt(self) -> None:
        call_count = 0

        async def flaky(slot):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("transient")
            return "ok"

        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            retry=RetryConfig(max_attempts=3, backoff="fixed", base_delay=0.0),
        )
        result = await t.execute(flaky)
        assert result == "ok"
        assert call_count == 2

    async def test_retry_exhausted_propagates_final_exception(self) -> None:
        call_count = 0

        async def always_fails(slot):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            raise ValueError(f"fail-{call_count}")

        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            retry=RetryConfig(max_attempts=3, backoff="fixed", base_delay=0.0),
        )
        with pytest.raises(ValueError, match="fail-3"):
            await t.execute(always_fails)
        assert call_count == 3

    async def test_retry_exhausted_records_single_failure(self) -> None:
        async def always_fails(slot):  # type: ignore[no-untyped-def]
            raise ValueError("fail")

        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            retry=RetryConfig(max_attempts=3, backoff="fixed", base_delay=0.0),
        )
        with pytest.raises(ValueError):
            await t.execute(always_fails)
        # Only the final failure should trigger deceleration recording
        snap = t.snapshot()
        assert snap.failure_count == 1


class TestExecuteSlotAttempt:
    async def test_slot_attempt_starts_at_zero(self) -> None:
        recorded_attempt = -1

        async def task(slot):  # type: ignore[no-untyped-def]
            nonlocal recorded_attempt
            recorded_attempt = slot.attempt
            return "ok"

        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)
        await t.execute(task)
        assert recorded_attempt == 0

    async def test_slot_attempt_increments_on_retry(self) -> None:
        attempts: list[int] = []

        async def flaky(slot):  # type: ignore[no-untyped-def]
            attempts.append(slot.attempt)
            if len(attempts) < 3:
                raise ValueError("transient")
            return "ok"

        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            retry=RetryConfig(max_attempts=3, backoff="fixed", base_delay=0.0),
        )
        await t.execute(flaky)
        assert attempts == [0, 1, 2]

    async def test_slot_attempt_zero_without_retry(self) -> None:
        recorded_attempt = -1

        async def task(slot):  # type: ignore[no-untyped-def]
            nonlocal recorded_attempt
            recorded_attempt = slot.attempt
            return "ok"

        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)
        await t.execute(task)
        assert recorded_attempt == 0


class TestExecuteRetryPredicate:
    async def test_non_retryable_propagates_immediately(self) -> None:
        call_count = 0

        async def task(slot):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            raise TypeError("not retryable")

        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            retry=RetryConfig(
                max_attempts=3,
                backoff="fixed",
                base_delay=0.0,
                retryable=lambda exc: isinstance(exc, ValueError),
            ),
        )
        with pytest.raises(TypeError, match="not retryable"):
            await t.execute(task)
        assert call_count == 1


class TestExecuteRetryEvents:
    async def test_retry_emits_events(self) -> None:
        events: list[ThrottleEvent] = []
        call_count = 0

        async def flaky(slot):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient")
            return "ok"

        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            retry=RetryConfig(max_attempts=3, backoff="fixed", base_delay=0.0),
            on_state_change=events.append,
        )
        await t.execute(flaky)
        retry_events = [e for e in events if e.kind == "retry"]
        assert len(retry_events) == 2
        assert retry_events[0].data["attempt"] == 1
        assert retry_events[1].data["attempt"] == 2


class TestExecuteCircuitBreaker:
    async def test_circuit_opens_during_retry(self) -> None:
        call_count = 0

        async def always_fails(slot):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            retry=RetryConfig(max_attempts=5, backoff="fixed", base_delay=0.0),
            circuit_breaker=CircuitBreakerConfig(
                consecutive_failures=2,
                open_duration=30.0,
            ),
        )
        with pytest.raises(CircuitOpenError):
            await t.execute(always_fails)
        # Should have been called twice (initial + 1 retry), then circuit opened
        assert call_count == 2


class TestExecuteNoRetry:
    async def test_execute_without_retry_calls_once(self) -> None:
        call_count = 0

        async def task(slot):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            return "ok"

        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)
        result = await t.execute(task)
        assert result == "ok"
        assert call_count == 1


class TestExecuteCustomLogic:
    async def test_callback_with_custom_logic(self) -> None:
        t = Throttle(
            max_concurrency=5,
            min_dispatch_interval=0.0,
            token_budget=TokenBudget(max_tokens=1000, window_seconds=60.0),
        )

        async def task(slot):  # type: ignore[no-untyped-def]
            result = {"text": "hello", "tokens": 25}
            slot.record_tokens(result["tokens"])
            return result["text"].upper()

        result = await t.execute(task)
        assert result == "HELLO"
        snap = t.snapshot()
        assert snap.tokens_used == 25


class TestExecuteConcurrency:
    async def test_concurrent_execute_respects_limits(self) -> None:
        t = Throttle(
            max_concurrency=2,
            min_dispatch_interval=0.0,
            jitter_fraction=0.0,
        )
        max_concurrent = 0
        current = 0

        async def task(slot):  # type: ignore[no-untyped-def]
            nonlocal max_concurrent, current
            current += 1
            max_concurrent = max(max_concurrent, current)
            await asyncio.sleep(0.05)
            current -= 1

        await asyncio.gather(*[t.execute(task) for _ in range(6)])
        assert max_concurrent <= 2


class TestExecuteClosedThrottle:
    async def test_execute_raises_when_closed(self) -> None:
        t = Throttle(max_concurrency=5, min_dispatch_interval=0.0)
        t.close()
        with pytest.raises(ThrottleClosed):
            await t.execute(lambda slot: asyncio.sleep(0))
