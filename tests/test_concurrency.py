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

from gentlify._concurrency import ConcurrencyController


class TestAcquireRelease:
    async def test_basic_acquire_release(self) -> None:
        cc = ConcurrencyController(max_concurrency=5)
        await cc.acquire()
        assert cc.in_flight == 1
        cc.release()
        assert cc.in_flight == 0

    async def test_multiple_acquire_release(self) -> None:
        cc = ConcurrencyController(max_concurrency=3)
        await cc.acquire()
        await cc.acquire()
        await cc.acquire()
        assert cc.in_flight == 3
        cc.release()
        cc.release()
        cc.release()
        assert cc.in_flight == 0


class TestConcurrencyLimitEnforcement:
    async def test_blocks_at_limit(self) -> None:
        cc = ConcurrencyController(max_concurrency=2)
        await cc.acquire()
        await cc.acquire()
        assert cc.in_flight == 2

        acquired = False

        async def try_acquire() -> None:
            nonlocal acquired
            await cc.acquire()
            acquired = True

        task = asyncio.create_task(try_acquire())
        await asyncio.sleep(0.05)
        assert not acquired  # should be blocked

        cc.release()
        await asyncio.sleep(0.05)
        assert acquired  # now unblocked
        assert cc.in_flight == 2  # 1 original + 1 new

        cc.release()
        cc.release()
        await task

    async def test_initial_concurrency(self) -> None:
        cc = ConcurrencyController(max_concurrency=10, initial_concurrency=2)
        assert cc.current_limit == 2
        await cc.acquire()
        await cc.acquire()

        acquired = False

        async def try_acquire() -> None:
            nonlocal acquired
            await cc.acquire()
            acquired = True

        task = asyncio.create_task(try_acquire())
        await asyncio.sleep(0.05)
        assert not acquired  # blocked at limit=2

        cc.release()
        await asyncio.sleep(0.05)
        assert acquired

        cc.release()
        cc.release()
        await task


class TestDecelerate:
    def test_halves_limit(self) -> None:
        cc = ConcurrencyController(max_concurrency=10)
        old, new = cc.decelerate()
        assert old == 10
        assert new == 5
        assert cc.current_limit == 5

    def test_halves_again(self) -> None:
        cc = ConcurrencyController(max_concurrency=10)
        cc.decelerate()  # 10 -> 5
        old, new = cc.decelerate()  # 5 -> 2
        assert old == 5
        assert new == 2

    def test_floors_at_one(self) -> None:
        cc = ConcurrencyController(max_concurrency=2)
        cc.decelerate()  # 2 -> 1
        old, new = cc.decelerate()  # 1 -> 1
        assert old == 1
        assert new == 1
        assert cc.current_limit == 1

    def test_from_one(self) -> None:
        cc = ConcurrencyController(max_concurrency=1)
        old, new = cc.decelerate()
        assert old == 1
        assert new == 1


class TestReaccelerate:
    def test_increments_by_one(self) -> None:
        cc = ConcurrencyController(max_concurrency=10, initial_concurrency=3)
        old, new = cc.reaccelerate(safe_ceiling=10)
        assert old == 3
        assert new == 4

    def test_respects_ceiling(self) -> None:
        cc = ConcurrencyController(max_concurrency=10, initial_concurrency=5)
        old, new = cc.reaccelerate(safe_ceiling=5)
        assert old == 5
        assert new == 5  # capped

    def test_increments_up_to_ceiling(self) -> None:
        cc = ConcurrencyController(max_concurrency=10, initial_concurrency=4)
        cc.reaccelerate(safe_ceiling=6)  # 4 -> 5
        old, new = cc.reaccelerate(safe_ceiling=6)  # 5 -> 6
        assert old == 5
        assert new == 6


class TestResize:
    def test_resize_up(self) -> None:
        cc = ConcurrencyController(max_concurrency=10, initial_concurrency=3)
        cc.resize(7)
        assert cc.current_limit == 7

    def test_resize_down(self) -> None:
        cc = ConcurrencyController(max_concurrency=10)
        cc.resize(2)
        assert cc.current_limit == 2

    async def test_resize_up_unblocks(self) -> None:
        cc = ConcurrencyController(max_concurrency=10, initial_concurrency=1)
        await cc.acquire()

        acquired = False

        async def try_acquire() -> None:
            nonlocal acquired
            await cc.acquire()
            acquired = True

        task = asyncio.create_task(try_acquire())
        await asyncio.sleep(0.05)
        assert not acquired

        cc.resize(2)  # should free up a permit
        await asyncio.sleep(0.05)
        assert acquired

        cc.release()
        cc.release()
        await task


class TestInFlightAccuracy:
    async def test_concurrent_tasks(self) -> None:
        cc = ConcurrencyController(max_concurrency=3)
        max_observed = 0

        async def worker() -> None:
            nonlocal max_observed
            await cc.acquire()
            if cc.in_flight > max_observed:
                max_observed = cc.in_flight
            await asyncio.sleep(0.02)
            cc.release()

        tasks = [asyncio.create_task(worker()) for _ in range(10)]
        await asyncio.gather(*tasks)

        assert cc.in_flight == 0
        assert max_observed <= 3
