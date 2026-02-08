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

import pytest


class FakeClock:
    """Deterministic clock for testing. Starts at 0.0 and advances manually."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds

    @property
    def now(self) -> float:
        return self._now


def fixed_random(value: float = 0.5) -> callable:
    """Return a rand_fn that always returns a fixed value scaled to the range."""

    def _rand(lo: float, hi: float) -> float:
        return lo + (hi - lo) * value

    return _rand


@pytest.fixture()
def fake_clock() -> FakeClock:
    """Provide a FakeClock starting at 0.0."""
    return FakeClock()


@pytest.fixture()
def fixed_rand() -> callable:
    """Provide a fixed random function that returns the midpoint."""
    return fixed_random(0.5)
