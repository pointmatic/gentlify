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
from unittest.mock import AsyncMock, patch

from gentlify._dispatch import DispatchGate

if TYPE_CHECKING:
    from conftest import FakeClock


class TestDispatchGateWait:
    async def test_first_wait_no_base_delay(self, fake_clock: FakeClock) -> None:
        """First wait should have no base delay, only jitter."""
        zero_rand = lambda lo, hi: 0.0  # noqa: E731
        gate = DispatchGate(
            interval=1.0, jitter_fraction=0.5, clock=fake_clock, rand_fn=zero_rand
        )
        with patch("gentlify._dispatch.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await gate.wait()
            mock_sleep.assert_called_once_with(0.0)

    async def test_wait_enforces_interval(self, fake_clock: FakeClock) -> None:
        """Second wait should enforce the interval minus elapsed time."""
        zero_rand = lambda lo, hi: 0.0  # noqa: E731
        gate = DispatchGate(
            interval=1.0, jitter_fraction=0.5, clock=fake_clock, rand_fn=zero_rand
        )
        with patch("gentlify._dispatch.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await gate.wait()  # first call, sets last_dispatch=0
            fake_clock.advance(0.3)  # only 0.3s elapsed
            await gate.wait()  # should sleep for 0.7 (1.0 - 0.3)
            assert mock_sleep.call_count == 2
            # Second call should have delay = remaining (0.7) + jitter (0.0) = 0.7
            actual_delay = mock_sleep.call_args_list[1][0][0]
            assert abs(actual_delay - 0.7) < 1e-9

    async def test_wait_no_delay_if_interval_elapsed(self, fake_clock: FakeClock) -> None:
        """If enough time has passed, no base delay needed."""
        zero_rand = lambda lo, hi: 0.0  # noqa: E731
        gate = DispatchGate(
            interval=1.0, jitter_fraction=0.5, clock=fake_clock, rand_fn=zero_rand
        )
        with patch("gentlify._dispatch.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await gate.wait()
            fake_clock.advance(2.0)  # more than interval
            await gate.wait()
            actual_delay = mock_sleep.call_args_list[1][0][0]
            assert actual_delay == 0.0


class TestDispatchGateJitter:
    async def test_jitter_within_bounds(self, fake_clock: FakeClock) -> None:
        """Jitter should be between 0 and interval * jitter_fraction."""
        # rand_fn returns the max of the range
        max_rand = lambda lo, hi: hi  # noqa: E731
        gate = DispatchGate(
            interval=1.0, jitter_fraction=0.5, clock=fake_clock, rand_fn=max_rand
        )
        with patch("gentlify._dispatch.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await gate.wait()
            # First wait: remaining=0, jitter=0.5 (1.0 * 0.5)
            actual_delay = mock_sleep.call_args_list[0][0][0]
            assert abs(actual_delay - 0.5) < 1e-9

    async def test_zero_jitter_fraction(self, fake_clock: FakeClock) -> None:
        """With jitter_fraction=0, jitter should always be 0."""
        # Even if rand returns hi, jitter should be 0 because range is [0, 0]
        max_rand = lambda lo, hi: hi  # noqa: E731
        gate = DispatchGate(
            interval=1.0, jitter_fraction=0.0, clock=fake_clock, rand_fn=max_rand
        )
        with patch("gentlify._dispatch.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await gate.wait()
            actual_delay = mock_sleep.call_args_list[0][0][0]
            assert actual_delay == 0.0

    async def test_jitter_adds_to_remaining(self, fake_clock: FakeClock) -> None:
        """Jitter is added on top of the remaining interval delay."""
        fixed_rand = lambda lo, hi: 0.2  # noqa: E731
        gate = DispatchGate(
            interval=1.0, jitter_fraction=0.5, clock=fake_clock, rand_fn=fixed_rand
        )
        with patch("gentlify._dispatch.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await gate.wait()  # sets last_dispatch
            fake_clock.advance(0.5)  # 0.5s elapsed
            await gate.wait()
            # remaining = 0.5, jitter = 0.2, total = 0.7
            actual_delay = mock_sleep.call_args_list[1][0][0]
            assert abs(actual_delay - 0.7) < 1e-9


class TestDispatchGateDecelerate:
    def test_doubles_interval(self) -> None:
        gate = DispatchGate(interval=1.0)
        old, new = gate.decelerate(max_interval=10.0)
        assert old == 1.0
        assert new == 2.0
        assert gate.interval == 2.0

    def test_caps_at_max(self) -> None:
        gate = DispatchGate(interval=8.0)
        old, new = gate.decelerate(max_interval=10.0)
        assert old == 8.0
        assert new == 10.0

    def test_already_at_max(self) -> None:
        gate = DispatchGate(interval=10.0)
        old, new = gate.decelerate(max_interval=10.0)
        assert old == 10.0
        assert new == 10.0

    def test_successive_decelerations(self) -> None:
        gate = DispatchGate(interval=1.0)
        gate.decelerate(max_interval=100.0)  # 1 -> 2
        gate.decelerate(max_interval=100.0)  # 2 -> 4
        old, new = gate.decelerate(max_interval=100.0)  # 4 -> 8
        assert old == 4.0
        assert new == 8.0


class TestDispatchGateReaccelerate:
    def test_halves_interval(self) -> None:
        gate = DispatchGate(interval=4.0)
        old, new = gate.reaccelerate(min_interval=0.1)
        assert old == 4.0
        assert new == 2.0
        assert gate.interval == 2.0

    def test_floors_at_min(self) -> None:
        gate = DispatchGate(interval=0.3)
        old, new = gate.reaccelerate(min_interval=0.2)
        assert old == 0.3
        assert new == 0.2

    def test_already_at_min(self) -> None:
        gate = DispatchGate(interval=0.2)
        old, new = gate.reaccelerate(min_interval=0.2)
        assert old == 0.2
        assert new == 0.2

    def test_successive_reaccelerations(self) -> None:
        gate = DispatchGate(interval=8.0)
        gate.reaccelerate(min_interval=0.5)  # 8 -> 4
        gate.reaccelerate(min_interval=0.5)  # 4 -> 2
        old, new = gate.reaccelerate(min_interval=0.5)  # 2 -> 1
        assert old == 2.0
        assert new == 1.0


class TestDispatchGateSequentialWaits:
    async def test_rapid_waits_respect_interval(self, fake_clock: FakeClock) -> None:
        """Multiple rapid waits should each enforce the interval."""
        zero_rand = lambda lo, hi: 0.0  # noqa: E731
        gate = DispatchGate(
            interval=1.0, jitter_fraction=0.0, clock=fake_clock, rand_fn=zero_rand
        )
        delays: list[float] = []
        with patch("gentlify._dispatch.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            for _ in range(3):
                await gate.wait()
            delays = [call[0][0] for call in mock_sleep.call_args_list]

        # First wait: 0 delay. Second and third: full interval (1.0) since
        # FakeClock doesn't advance during asyncio.sleep mock
        assert delays[0] == 0.0
        assert delays[1] == 1.0
        assert delays[2] == 1.0
