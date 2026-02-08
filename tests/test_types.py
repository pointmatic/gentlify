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

import dataclasses

import pytest

import gentlify
from gentlify import (
    CircuitOpenError,
    GentlifyError,
    ThrottleClosed,
    ThrottleEvent,
    ThrottleSnapshot,
    ThrottleState,
)

# --- ThrottleState enum ---


class TestThrottleState:
    def test_members(self) -> None:
        assert ThrottleState.RUNNING.value == "running"
        assert ThrottleState.COOLING.value == "cooling"
        assert ThrottleState.CIRCUIT_OPEN.value == "circuit_open"
        assert ThrottleState.CLOSED.value == "closed"
        assert ThrottleState.DRAINING.value == "draining"

    def test_member_count(self) -> None:
        assert len(ThrottleState) == 5

    def test_accessible_from_package(self) -> None:
        assert gentlify.ThrottleState is ThrottleState


# --- ThrottleSnapshot frozen dataclass ---


class TestThrottleSnapshot:
    def test_construction(self) -> None:
        snap = ThrottleSnapshot(
            concurrency=3,
            max_concurrency=10,
            dispatch_interval=0.5,
            completed_tasks=42,
            total_tasks=100,
            failure_count=2,
            state=ThrottleState.RUNNING,
            safe_ceiling=8,
            eta_seconds=12.5,
            tokens_used=500,
            tokens_remaining=1500,
        )
        assert snap.concurrency == 3
        assert snap.max_concurrency == 10
        assert snap.dispatch_interval == 0.5
        assert snap.completed_tasks == 42
        assert snap.total_tasks == 100
        assert snap.failure_count == 2
        assert snap.state is ThrottleState.RUNNING
        assert snap.safe_ceiling == 8
        assert snap.eta_seconds == 12.5
        assert snap.tokens_used == 500
        assert snap.tokens_remaining == 1500

    def test_frozen(self) -> None:
        snap = ThrottleSnapshot(
            concurrency=3,
            max_concurrency=10,
            dispatch_interval=0.5,
            completed_tasks=0,
            total_tasks=0,
            failure_count=0,
            state=ThrottleState.RUNNING,
            safe_ceiling=10,
            eta_seconds=None,
            tokens_used=0,
            tokens_remaining=None,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.concurrency = 5  # type: ignore[misc]

    def test_nullable_fields(self) -> None:
        snap = ThrottleSnapshot(
            concurrency=1,
            max_concurrency=1,
            dispatch_interval=0.0,
            completed_tasks=0,
            total_tasks=0,
            failure_count=0,
            state=ThrottleState.CLOSED,
            safe_ceiling=1,
            eta_seconds=None,
            tokens_used=0,
            tokens_remaining=None,
        )
        assert snap.eta_seconds is None
        assert snap.tokens_remaining is None


# --- ThrottleEvent frozen dataclass ---


class TestThrottleEvent:
    def test_construction(self) -> None:
        event = ThrottleEvent(kind="decelerated", timestamp=1234.5, data={"old": 10, "new": 5})
        assert event.kind == "decelerated"
        assert event.timestamp == 1234.5
        assert event.data == {"old": 10, "new": 5}

    def test_frozen(self) -> None:
        event = ThrottleEvent(kind="test", timestamp=0.0, data={})
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.kind = "changed"  # type: ignore[misc]


# --- Exception hierarchy ---


class TestExceptions:
    def test_gentlify_error_is_exception(self) -> None:
        assert issubclass(GentlifyError, Exception)

    def test_circuit_open_error_hierarchy(self) -> None:
        assert issubclass(CircuitOpenError, GentlifyError)
        assert issubclass(CircuitOpenError, Exception)

    def test_circuit_open_error_retry_after(self) -> None:
        err = CircuitOpenError(retry_after=15.0)
        assert err.retry_after == 15.0
        assert "15.0" in str(err)

    def test_circuit_open_error_is_catchable_as_gentlify_error(self) -> None:
        with pytest.raises(GentlifyError):
            raise CircuitOpenError(retry_after=5.0)

    def test_throttle_closed_hierarchy(self) -> None:
        assert issubclass(ThrottleClosed, GentlifyError)
        assert issubclass(ThrottleClosed, Exception)

    def test_throttle_closed_message(self) -> None:
        err = ThrottleClosed()
        assert "closed" in str(err).lower()

    def test_throttle_closed_is_catchable_as_gentlify_error(self) -> None:
        with pytest.raises(GentlifyError):
            raise ThrottleClosed()

    def test_accessible_from_package(self) -> None:
        assert gentlify.GentlifyError is GentlifyError
        assert gentlify.CircuitOpenError is CircuitOpenError
        assert gentlify.ThrottleClosed is ThrottleClosed
