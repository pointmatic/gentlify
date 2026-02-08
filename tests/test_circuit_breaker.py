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

from typing import TYPE_CHECKING

import pytest

from gentlify._circuit_breaker import CircuitBreaker
from gentlify._config import CircuitBreakerConfig
from gentlify._exceptions import CircuitOpenError

if TYPE_CHECKING:
    from conftest import FakeClock


class TestClosedToOpen:
    def test_opens_after_consecutive_failures(
        self, fake_clock: FakeClock
    ) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(consecutive_failures=3),
            clock=fake_clock,
        )
        assert cb.state == "closed"
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "open"

    def test_consecutive_failures_count(
        self, fake_clock: FakeClock
    ) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(consecutive_failures=5),
            clock=fake_clock,
        )
        for _ in range(4):
            cb.record_failure()
        assert cb.consecutive_failures == 4
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.consecutive_failures == 5
        assert cb.state == "open"


class TestOpenToHalfOpen:
    def test_transitions_after_delay(self, fake_clock: FakeClock) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(
                consecutive_failures=1, open_duration=10.0
            ),
            clock=fake_clock,
        )
        cb.record_failure()
        assert cb.state == "open"
        fake_clock.advance(10.0)
        assert cb.state == "half_open"

    def test_stays_open_before_delay(self, fake_clock: FakeClock) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(
                consecutive_failures=1, open_duration=10.0
            ),
            clock=fake_clock,
        )
        cb.record_failure()
        fake_clock.advance(9.9)
        assert cb.state == "open"


class TestHalfOpenToClosed:
    def test_closes_after_enough_successes(
        self, fake_clock: FakeClock
    ) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(
                consecutive_failures=1,
                open_duration=5.0,
                half_open_max_calls=1,
            ),
            clock=fake_clock,
        )
        cb.record_failure()
        fake_clock.advance(5.0)
        assert cb.state == "half_open"
        cb.check()  # allow probe
        cb.record_success()
        assert cb.state == "closed"

    def test_closes_after_multiple_successes(
        self, fake_clock: FakeClock
    ) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(
                consecutive_failures=1,
                open_duration=5.0,
                half_open_max_calls=3,
            ),
            clock=fake_clock,
        )
        cb.record_failure()
        fake_clock.advance(5.0)
        assert cb.state == "half_open"
        for _i in range(3):
            cb.check()
            cb.record_success()
        assert cb.state == "closed"
        assert cb.half_open_successes == 0  # reset after close


class TestHalfOpenToOpen:
    def test_reopens_on_failure(self, fake_clock: FakeClock) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(
                consecutive_failures=1, open_duration=5.0
            ),
            clock=fake_clock,
        )
        cb.record_failure()
        fake_clock.advance(5.0)
        assert cb.state == "half_open"
        cb.record_failure()
        assert cb.state == "open"

    def test_delay_doubles_on_reopen(self, fake_clock: FakeClock) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(
                consecutive_failures=1, open_duration=5.0
            ),
            clock=fake_clock,
        )
        # First trip
        cb.record_failure()
        fake_clock.advance(5.0)
        assert cb.state == "half_open"

        # Fail in half-open -> delay doubles to 10
        cb.record_failure()
        assert cb.state == "open"
        fake_clock.advance(9.9)
        assert cb.state == "open"
        fake_clock.advance(0.1)
        assert cb.state == "half_open"


class TestDelayCapAt5x:
    def test_delay_caps_at_five_times_open_duration(
        self, fake_clock: FakeClock
    ) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(
                consecutive_failures=1, open_duration=10.0
            ),
            clock=fake_clock,
        )
        # Trip 1: open_duration=10
        cb.record_failure()
        assert cb.state == "open"
        fake_clock.advance(10.0)
        assert cb.state == "half_open"

        # Half-open fail -> delay doubles to 20
        cb.record_failure()
        assert cb.state == "open"
        fake_clock.advance(20.0)
        assert cb.state == "half_open"

        # Half-open fail -> delay doubles to 40
        cb.record_failure()
        assert cb.state == "open"
        fake_clock.advance(40.0)
        assert cb.state == "half_open"

        # Half-open fail -> delay would be 80, capped at 50 (5×10)
        cb.record_failure()
        assert cb.state == "open"
        fake_clock.advance(49.9)
        assert cb.state == "open"
        fake_clock.advance(0.1)
        assert cb.state == "half_open"

        # Half-open fail -> delay stays at 50 (already capped)
        cb.record_failure()
        assert cb.state == "open"
        fake_clock.advance(49.9)
        assert cb.state == "open"
        fake_clock.advance(0.1)
        assert cb.state == "half_open"


class TestCheckRaisesCircuitOpenError:
    def test_raises_when_open(self, fake_clock: FakeClock) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(
                consecutive_failures=1, open_duration=10.0
            ),
            clock=fake_clock,
        )
        cb.record_failure()
        with pytest.raises(CircuitOpenError) as exc_info:
            cb.check()
        assert exc_info.value.retry_after == pytest.approx(10.0)

    def test_retry_after_decreases(self, fake_clock: FakeClock) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(
                consecutive_failures=1, open_duration=10.0
            ),
            clock=fake_clock,
        )
        cb.record_failure()
        fake_clock.advance(3.0)
        with pytest.raises(CircuitOpenError) as exc_info:
            cb.check()
        assert exc_info.value.retry_after == pytest.approx(7.0)

    def test_no_raise_when_closed(self, fake_clock: FakeClock) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(consecutive_failures=5),
            clock=fake_clock,
        )
        cb.check()  # should not raise

    def test_allows_probes_in_half_open(
        self, fake_clock: FakeClock
    ) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(
                consecutive_failures=1,
                open_duration=5.0,
                half_open_max_calls=2,
            ),
            clock=fake_clock,
        )
        cb.record_failure()
        fake_clock.advance(5.0)
        cb.check()  # probe 1 — should not raise
        cb.check()  # probe 2 — should not raise
        with pytest.raises(CircuitOpenError):
            cb.check()  # probe 3 — exceeds max, should raise


class TestSuccessResetsFailureCount:
    def test_success_resets_consecutive_failures(
        self, fake_clock: FakeClock
    ) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(consecutive_failures=3),
            clock=fake_clock,
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.consecutive_failures == 2
        cb.record_success()
        assert cb.consecutive_failures == 0
        # Need 3 more failures to trip
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "open"


class TestZeroOpenDuration:
    def test_immediately_half_open(self, fake_clock: FakeClock) -> None:
        cb = CircuitBreaker(
            config=CircuitBreakerConfig(
                consecutive_failures=1, open_duration=0.0
            ),
            clock=fake_clock,
        )
        cb.record_failure()
        # With open_duration=0, should immediately transition to half_open
        assert cb.state == "half_open"
