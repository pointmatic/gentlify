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

from gentlify._window import SlidingWindow

if TYPE_CHECKING:
    from conftest import FakeClock


class TestSlidingWindowRecordAndCount:
    def test_empty_window(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=10.0, clock=fake_clock)
        assert w.count() == 0
        assert w.total() == 0.0

    def test_record_increments_count(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=10.0, clock=fake_clock)
        w.record()
        w.record()
        w.record()
        assert w.count() == 3

    def test_record_default_value(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=10.0, clock=fake_clock)
        w.record()
        w.record()
        assert w.total() == 2.0

    def test_record_custom_values(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=10.0, clock=fake_clock)
        w.record(5.0)
        w.record(3.0)
        w.record(7.0)
        assert w.total() == 15.0
        assert w.count() == 3


class TestSlidingWindowExpiry:
    def test_entries_expire_after_window(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=10.0, clock=fake_clock)
        w.record(1.0)
        fake_clock.advance(5.0)
        w.record(2.0)
        fake_clock.advance(6.0)  # first entry is now 11s old
        assert w.count() == 1
        assert w.total() == 2.0

    def test_all_entries_expire(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=5.0, clock=fake_clock)
        w.record(10.0)
        w.record(20.0)
        fake_clock.advance(6.0)
        assert w.count() == 0
        assert w.total() == 0.0

    def test_entries_at_exact_boundary_are_pruned(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=10.0, clock=fake_clock)
        w.record(1.0)  # recorded at t=0
        fake_clock.advance(10.0)  # cutoff = 10 - 10 = 0, entry at 0 < 0 is false
        # Entry at exactly the cutoff boundary (0 < 0 is false) should be kept
        assert w.count() == 1

    def test_entries_just_past_boundary_are_pruned(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=10.0, clock=fake_clock)
        w.record(1.0)  # recorded at t=0
        fake_clock.advance(10.01)  # cutoff = 10.01 - 10 = 0.01, entry at 0 < 0.01
        assert w.count() == 0

    def test_mixed_expiry(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=10.0, clock=fake_clock)
        w.record(1.0)  # t=0
        fake_clock.advance(3.0)
        w.record(2.0)  # t=3
        fake_clock.advance(3.0)
        w.record(3.0)  # t=6
        fake_clock.advance(5.0)  # t=11, cutoff=1 -> entry at 0 pruned
        assert w.count() == 2
        assert w.total() == 5.0


class TestSlidingWindowClear:
    def test_clear_removes_all(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=10.0, clock=fake_clock)
        w.record(1.0)
        w.record(2.0)
        w.record(3.0)
        w.clear()
        assert w.count() == 0
        assert w.total() == 0.0

    def test_record_after_clear(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=10.0, clock=fake_clock)
        w.record(10.0)
        w.clear()
        w.record(5.0)
        assert w.count() == 1
        assert w.total() == 5.0


class TestSlidingWindowWithFakeClock:
    def test_advance_and_verify_pruning(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=5.0, clock=fake_clock)
        for i in range(5):
            w.record(float(i + 1))
            fake_clock.advance(1.0)
        # t=5, entries at t=0,1,2,3,4 -> cutoff=-0 -> all within window
        assert w.count() == 5
        assert w.total() == 15.0

        fake_clock.advance(2.0)  # t=7, cutoff=2 -> entries at 0,1 pruned
        assert w.count() == 3
        assert w.total() == 12.0  # 3+4+5

    def test_rapid_records_same_timestamp(self, fake_clock: FakeClock) -> None:
        w = SlidingWindow(window_seconds=10.0, clock=fake_clock)
        for _ in range(100):
            w.record(1.0)
        assert w.count() == 100
        assert w.total() == 100.0
