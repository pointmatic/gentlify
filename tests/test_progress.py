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

from gentlify._progress import ProgressTracker

if TYPE_CHECKING:
    from conftest import FakeClock


class TestCompletionCounting:
    def test_initial_state(self, fake_clock: FakeClock) -> None:
        pt = ProgressTracker(total_tasks=100, clock=fake_clock)
        assert pt.completed == 0
        assert pt.percentage == 0.0

    def test_increments_completed(self, fake_clock: FakeClock) -> None:
        pt = ProgressTracker(total_tasks=10, clock=fake_clock)
        pt.record_completion(1.0)
        pt.record_completion(1.0)
        assert pt.completed == 2

    def test_single_task(self, fake_clock: FakeClock) -> None:
        pt = ProgressTracker(total_tasks=1, clock=fake_clock)
        pt.record_completion(0.5)
        assert pt.completed == 1
        assert pt.percentage == 100.0


class TestPercentage:
    def test_percentage_calculation(self, fake_clock: FakeClock) -> None:
        pt = ProgressTracker(total_tasks=10, clock=fake_clock)
        for _ in range(3):
            pt.record_completion(1.0)
        assert pt.percentage == 30.0

    def test_percentage_caps_at_100(self, fake_clock: FakeClock) -> None:
        pt = ProgressTracker(total_tasks=5, clock=fake_clock)
        for _ in range(7):
            pt.record_completion(1.0)
        assert pt.percentage == 100.0

    def test_zero_total_tasks(self, fake_clock: FakeClock) -> None:
        pt = ProgressTracker(total_tasks=0, clock=fake_clock)
        assert pt.percentage == 0.0


class TestMilestoneDetection:
    def test_milestone_at_10_percent(self, fake_clock: FakeClock) -> None:
        pt = ProgressTracker(total_tasks=100, clock=fake_clock)
        for i in range(10):
            result = pt.record_completion(1.0)
            if i < 9:
                assert not result
        assert result  # 10th completion crosses 10% milestone

    def test_milestones_at_each_10_percent(
        self, fake_clock: FakeClock
    ) -> None:
        pt = ProgressTracker(total_tasks=10, clock=fake_clock)
        milestones = []
        for _ in range(10):
            if pt.record_completion(1.0):
                milestones.append(pt.percentage)
        assert milestones == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]

    def test_no_milestones_with_zero_total(
        self, fake_clock: FakeClock
    ) -> None:
        pt = ProgressTracker(total_tasks=0, clock=fake_clock)
        assert not pt.record_completion(1.0)

    def test_custom_milestone_pct(self, fake_clock: FakeClock) -> None:
        pt = ProgressTracker(
            total_tasks=4, milestone_pct=25.0, clock=fake_clock
        )
        milestones = []
        for _ in range(4):
            if pt.record_completion(1.0):
                milestones.append(pt.percentage)
        assert milestones == [25.0, 50.0, 75.0, 100.0]


class TestEtaCalculation:
    def test_eta_with_known_durations(
        self, fake_clock: FakeClock
    ) -> None:
        pt = ProgressTracker(total_tasks=10, clock=fake_clock)
        for _ in range(5):
            pt.record_completion(2.0)
        # 5 remaining, avg duration = 2.0, ETA = 5 * 2.0 = 10.0
        assert pt.eta_seconds == 10.0

    def test_eta_none_when_no_completions(
        self, fake_clock: FakeClock
    ) -> None:
        pt = ProgressTracker(total_tasks=10, clock=fake_clock)
        assert pt.eta_seconds is None

    def test_eta_zero_when_all_done(self, fake_clock: FakeClock) -> None:
        pt = ProgressTracker(total_tasks=3, clock=fake_clock)
        for _ in range(3):
            pt.record_completion(1.0)
        assert pt.eta_seconds == 0.0

    def test_eta_with_varying_durations(
        self, fake_clock: FakeClock
    ) -> None:
        pt = ProgressTracker(total_tasks=10, clock=fake_clock)
        pt.record_completion(1.0)
        pt.record_completion(3.0)
        # avg = 2.0, remaining = 8, ETA = 16.0
        assert pt.eta_seconds == 16.0

    def test_eta_none_with_zero_total(
        self, fake_clock: FakeClock
    ) -> None:
        pt = ProgressTracker(total_tasks=0, clock=fake_clock)
        assert pt.eta_seconds is None
