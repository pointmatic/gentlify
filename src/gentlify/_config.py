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

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gentlify._types import (
        FailurePredicate,
        ProgressCallback,
        StateChangeCallback,
    )


@dataclass(frozen=True)
class TokenBudget:
    """Rolling-window token budget configuration."""

    max_tokens: int
    window_seconds: float

    def __post_init__(self) -> None:
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1, got {self.max_tokens}")
        if self.window_seconds <= 0:
            raise ValueError(f"window_seconds must be > 0, got {self.window_seconds}")


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    consecutive_failures: int = 10
    open_duration: float = 30.0
    half_open_max_calls: int = 1

    def __post_init__(self) -> None:
        if self.consecutive_failures < 1:
            raise ValueError(
                f"consecutive_failures must be >= 1, got {self.consecutive_failures}"
            )
        if self.open_duration < 0:
            raise ValueError(f"open_duration must be >= 0, got {self.open_duration}")
        if self.half_open_max_calls < 1:
            raise ValueError(
                f"half_open_max_calls must be >= 1, got {self.half_open_max_calls}"
            )


@dataclass(frozen=True)
class ThrottleConfig:
    """Complete throttle configuration with validation."""

    max_concurrency: int = 5
    initial_concurrency: int | None = None
    min_dispatch_interval: float = 0.2
    max_dispatch_interval: float = 30.0
    failure_threshold: int = 3
    failure_window: float = 60.0
    cooling_period: float = 60.0
    safe_ceiling_decay_multiplier: float = 5.0
    jitter_fraction: float = 0.5
    total_tasks: int = 0
    failure_predicate: FailurePredicate | None = None
    token_budget: TokenBudget | None = None
    circuit_breaker: CircuitBreakerConfig | None = None
    on_state_change: StateChangeCallback | None = None
    on_progress: ProgressCallback | None = None

    def __post_init__(self) -> None:
        if self.max_concurrency < 1:
            raise ValueError(f"max_concurrency must be >= 1, got {self.max_concurrency}")
        if self.initial_concurrency is not None and not (
            1 <= self.initial_concurrency <= self.max_concurrency
        ):
            raise ValueError(
                f"initial_concurrency must be between 1 and max_concurrency "
                f"({self.max_concurrency}), got {self.initial_concurrency}"
            )
        if self.min_dispatch_interval < 0:
            raise ValueError(
                f"min_dispatch_interval must be >= 0, got {self.min_dispatch_interval}"
            )
        if self.max_dispatch_interval < self.min_dispatch_interval:
            raise ValueError(
                f"max_dispatch_interval ({self.max_dispatch_interval}) must be >= "
                f"min_dispatch_interval ({self.min_dispatch_interval})"
            )
        if self.failure_threshold < 1:
            raise ValueError(f"failure_threshold must be >= 1, got {self.failure_threshold}")
        if self.failure_window <= 0:
            raise ValueError(f"failure_window must be > 0, got {self.failure_window}")
        if self.cooling_period <= 0:
            raise ValueError(f"cooling_period must be > 0, got {self.cooling_period}")
        if self.safe_ceiling_decay_multiplier <= 0:
            raise ValueError(
                f"safe_ceiling_decay_multiplier must be > 0, "
                f"got {self.safe_ceiling_decay_multiplier}"
            )
        if not (0.0 <= self.jitter_fraction <= 1.0):
            raise ValueError(
                f"jitter_fraction must be between 0.0 and 1.0, got {self.jitter_fraction}"
            )
        if self.total_tasks < 0:
            raise ValueError(f"total_tasks must be >= 0, got {self.total_tasks}")

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ThrottleConfig:
        """Build config from a plain dict. Nested dicts for token_budget and circuit_breaker."""
        kwargs: dict[str, Any] = {}

        simple_fields: dict[str, type] = {
            "max_concurrency": int,
            "initial_concurrency": int,
            "min_dispatch_interval": float,
            "max_dispatch_interval": float,
            "failure_threshold": int,
            "failure_window": float,
            "cooling_period": float,
            "safe_ceiling_decay_multiplier": float,
            "jitter_fraction": float,
            "total_tasks": int,
        }

        for field, typ in simple_fields.items():
            if field in data:
                kwargs[field] = typ(data[field])

        for passthrough in ("failure_predicate", "on_state_change", "on_progress"):
            if passthrough in data:
                kwargs[passthrough] = data[passthrough]

        if "token_budget" in data:
            tb = data["token_budget"]
            if isinstance(tb, TokenBudget):
                kwargs["token_budget"] = tb
            elif isinstance(tb, dict):
                kwargs["token_budget"] = TokenBudget(
                    max_tokens=int(tb["max_tokens"]),
                    window_seconds=float(tb["window_seconds"]),
                )

        if "circuit_breaker" in data:
            cb = data["circuit_breaker"]
            if isinstance(cb, CircuitBreakerConfig):
                kwargs["circuit_breaker"] = cb
            elif isinstance(cb, dict):
                cb_kwargs: dict[str, Any] = {}
                if "consecutive_failures" in cb:
                    cb_kwargs["consecutive_failures"] = int(cb["consecutive_failures"])
                if "open_duration" in cb:
                    cb_kwargs["open_duration"] = float(cb["open_duration"])
                if "half_open_max_calls" in cb:
                    cb_kwargs["half_open_max_calls"] = int(cb["half_open_max_calls"])
                kwargs["circuit_breaker"] = CircuitBreakerConfig(**cb_kwargs)

        return ThrottleConfig(**kwargs)

    @staticmethod
    def from_env(prefix: str = "GENTLIFY") -> ThrottleConfig:
        """Build config from environment variables. See features.md for env var mapping."""
        kwargs: dict[str, Any] = {}

        int_fields = {
            "MAX_CONCURRENCY": "max_concurrency",
            "INITIAL_CONCURRENCY": "initial_concurrency",
            "FAILURE_THRESHOLD": "failure_threshold",
            "TOTAL_TASKS": "total_tasks",
        }
        float_fields = {
            "MIN_DISPATCH_INTERVAL": "min_dispatch_interval",
            "MAX_DISPATCH_INTERVAL": "max_dispatch_interval",
            "FAILURE_WINDOW": "failure_window",
            "COOLING_PERIOD": "cooling_period",
            "SAFE_CEILING_DECAY_MULTIPLIER": "safe_ceiling_decay_multiplier",
            "JITTER_FRACTION": "jitter_fraction",
        }

        for env_suffix, field in int_fields.items():
            val = os.environ.get(f"{prefix}_{env_suffix}")
            if val is not None:
                kwargs[field] = int(val)

        for env_suffix, field in float_fields.items():
            val = os.environ.get(f"{prefix}_{env_suffix}")
            if val is not None:
                kwargs[field] = float(val)

        # Token budget (both fields required if either is set)
        tb_max = os.environ.get(f"{prefix}_TOKEN_BUDGET_MAX")
        tb_window = os.environ.get(f"{prefix}_TOKEN_BUDGET_WINDOW")
        if tb_max is not None and tb_window is not None:
            kwargs["token_budget"] = TokenBudget(
                max_tokens=int(tb_max),
                window_seconds=float(tb_window),
            )

        # Circuit breaker (any field triggers creation with defaults for the rest)
        cb_failures = os.environ.get(f"{prefix}_CIRCUIT_BREAKER_CONSECUTIVE_FAILURES")
        cb_duration = os.environ.get(f"{prefix}_CIRCUIT_BREAKER_OPEN_DURATION")
        cb_half_open = os.environ.get(f"{prefix}_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS")
        if any(v is not None for v in (cb_failures, cb_duration, cb_half_open)):
            cb_kwargs: dict[str, Any] = {}
            if cb_failures is not None:
                cb_kwargs["consecutive_failures"] = int(cb_failures)
            if cb_duration is not None:
                cb_kwargs["open_duration"] = float(cb_duration)
            if cb_half_open is not None:
                cb_kwargs["half_open_max_calls"] = int(cb_half_open)
            kwargs["circuit_breaker"] = CircuitBreakerConfig(**cb_kwargs)

        return ThrottleConfig(**kwargs)
