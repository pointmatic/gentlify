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

from gentlify._config import TokenBudget
from gentlify._token_bucket import TokenBucket

if TYPE_CHECKING:
    from conftest import FakeClock


class TestTokenBucketConsumeAndUsed:
    def test_initial_state(self, fake_clock: FakeClock) -> None:
        budget = TokenBudget(max_tokens=1000, window_seconds=60.0)
        tb = TokenBucket(budget=budget, clock=fake_clock)
        assert tb.tokens_used() == 0
        assert tb.tokens_remaining() == 1000

    def test_consume_tracks_usage(self, fake_clock: FakeClock) -> None:
        budget = TokenBudget(max_tokens=1000, window_seconds=60.0)
        tb = TokenBucket(budget=budget, clock=fake_clock)
        tb.consume(100)
        assert tb.tokens_used() == 100
        assert tb.tokens_remaining() == 900

    def test_multiple_consumes(self, fake_clock: FakeClock) -> None:
        budget = TokenBudget(max_tokens=1000, window_seconds=60.0)
        tb = TokenBucket(budget=budget, clock=fake_clock)
        tb.consume(200)
        tb.consume(300)
        tb.consume(100)
        assert tb.tokens_used() == 600
        assert tb.tokens_remaining() == 400


class TestTokenBucketRemaining:
    def test_remaining_floors_at_zero(self, fake_clock: FakeClock) -> None:
        tb = TokenBucket(budget=TokenBudget(max_tokens=100, window_seconds=60.0), clock=fake_clock)
        tb.consume(150)
        assert tb.tokens_remaining() == 0
        assert tb.tokens_used() == 150


class TestTokenBucketWindowRollover:
    def test_tokens_expire_after_window(self, fake_clock: FakeClock) -> None:
        budget = TokenBudget(max_tokens=1000, window_seconds=10.0)
        tb = TokenBucket(budget=budget, clock=fake_clock)
        tb.consume(500)
        fake_clock.advance(5.0)
        tb.consume(300)
        fake_clock.advance(6.0)  # first consume is now 11s old
        assert tb.tokens_used() == 300
        assert tb.tokens_remaining() == 700

    def test_all_tokens_expire(self, fake_clock: FakeClock) -> None:
        budget = TokenBudget(max_tokens=1000, window_seconds=10.0)
        tb = TokenBucket(budget=budget, clock=fake_clock)
        tb.consume(800)
        fake_clock.advance(11.0)
        assert tb.tokens_used() == 0
        assert tb.tokens_remaining() == 1000


class TestTokenBucketWaitForBudget:
    async def test_no_wait_when_budget_available(self, fake_clock: FakeClock) -> None:
        tb = TokenBucket(budget=TokenBudget(max_tokens=100, window_seconds=10.0), clock=fake_clock)
        tb.consume(50)
        with patch("gentlify._token_bucket.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await tb.wait_for_budget(10)
            mock_sleep.assert_not_called()

    async def test_waits_when_budget_exhausted(self, fake_clock: FakeClock) -> None:
        tb = TokenBucket(budget=TokenBudget(max_tokens=100, window_seconds=10.0), clock=fake_clock)
        tb.consume(100)  # fully exhausted at t=0

        async def advance_on_sleep(delay: float) -> None:
            fake_clock.advance(delay)

        with patch(
            "gentlify._token_bucket.asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=advance_on_sleep,
        ):
            await tb.wait_for_budget(1)

        # After waiting, tokens should have expired
        assert tb.tokens_remaining() >= 1

    async def test_waits_for_partial_refill(self, fake_clock: FakeClock) -> None:
        tb = TokenBucket(budget=TokenBudget(max_tokens=100, window_seconds=10.0), clock=fake_clock)
        tb.consume(60)  # t=0, 60 used
        fake_clock.advance(3.0)
        tb.consume(30)  # t=3, 90 used total, 10 remaining

        async def advance_on_sleep(delay: float) -> None:
            fake_clock.advance(delay)

        with patch(
            "gentlify._token_bucket.asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=advance_on_sleep,
        ):
            await tb.wait_for_budget(50)

        # After the first batch (60 tokens at t=0) expires at t=10,
        # we should have enough budget
        assert tb.tokens_remaining() >= 50


class TestTokenBucketSingleToken:
    def test_budget_of_one(self, fake_clock: FakeClock) -> None:
        tb = TokenBucket(budget=TokenBudget(max_tokens=1, window_seconds=5.0), clock=fake_clock)
        tb.consume(1)
        assert tb.tokens_remaining() == 0
        fake_clock.advance(6.0)
        assert tb.tokens_remaining() == 1
