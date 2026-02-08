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

from gentlify import CircuitBreakerConfig, Throttle, ThrottleConfig, TokenBudget

# --- TokenBudget ---


class TestTokenBudget:
    def test_construction(self) -> None:
        tb = TokenBudget(max_tokens=1000, window_seconds=60.0)
        assert tb.max_tokens == 1000
        assert tb.window_seconds == 60.0

    def test_max_tokens_too_low(self) -> None:
        with pytest.raises(ValueError, match="max_tokens"):
            TokenBudget(max_tokens=0, window_seconds=60.0)

    def test_window_seconds_zero(self) -> None:
        with pytest.raises(ValueError, match="window_seconds"):
            TokenBudget(max_tokens=100, window_seconds=0)

    def test_window_seconds_negative(self) -> None:
        with pytest.raises(ValueError, match="window_seconds"):
            TokenBudget(max_tokens=100, window_seconds=-1.0)


# --- CircuitBreakerConfig ---


class TestCircuitBreakerConfig:
    def test_defaults(self) -> None:
        cb = CircuitBreakerConfig()
        assert cb.consecutive_failures == 10
        assert cb.open_duration == 30.0
        assert cb.half_open_max_calls == 1

    def test_custom_values(self) -> None:
        cb = CircuitBreakerConfig(
            consecutive_failures=5, open_duration=10.0, half_open_max_calls=3
        )
        assert cb.consecutive_failures == 5
        assert cb.open_duration == 10.0
        assert cb.half_open_max_calls == 3

    def test_consecutive_failures_too_low(self) -> None:
        with pytest.raises(ValueError, match="consecutive_failures"):
            CircuitBreakerConfig(consecutive_failures=0)

    def test_open_duration_negative(self) -> None:
        with pytest.raises(ValueError, match="open_duration"):
            CircuitBreakerConfig(open_duration=-1.0)

    def test_open_duration_zero_allowed(self) -> None:
        cb = CircuitBreakerConfig(open_duration=0.0)
        assert cb.open_duration == 0.0

    def test_half_open_max_calls_too_low(self) -> None:
        with pytest.raises(ValueError, match="half_open_max_calls"):
            CircuitBreakerConfig(half_open_max_calls=0)


# --- ThrottleConfig defaults and validation ---


class TestThrottleConfigDefaults:
    def test_defaults(self) -> None:
        cfg = ThrottleConfig()
        assert cfg.max_concurrency == 5
        assert cfg.initial_concurrency is None
        assert cfg.min_dispatch_interval == 0.2
        assert cfg.max_dispatch_interval == 30.0
        assert cfg.failure_threshold == 3
        assert cfg.failure_window == 60.0
        assert cfg.cooling_period == 60.0
        assert cfg.safe_ceiling_decay_multiplier == 5.0
        assert cfg.jitter_fraction == 0.5
        assert cfg.total_tasks == 0
        assert cfg.failure_predicate is None
        assert cfg.token_budget is None
        assert cfg.circuit_breaker is None
        assert cfg.on_state_change is None
        assert cfg.on_progress is None


class TestThrottleConfigValidation:
    def test_max_concurrency_too_low(self) -> None:
        with pytest.raises(ValueError, match="max_concurrency"):
            ThrottleConfig(max_concurrency=0)

    def test_initial_concurrency_too_low(self) -> None:
        with pytest.raises(ValueError, match="initial_concurrency"):
            ThrottleConfig(initial_concurrency=0)

    def test_initial_concurrency_exceeds_max(self) -> None:
        with pytest.raises(ValueError, match="initial_concurrency"):
            ThrottleConfig(max_concurrency=5, initial_concurrency=6)

    def test_initial_concurrency_valid(self) -> None:
        cfg = ThrottleConfig(max_concurrency=10, initial_concurrency=3)
        assert cfg.initial_concurrency == 3

    def test_initial_concurrency_equals_max(self) -> None:
        cfg = ThrottleConfig(max_concurrency=5, initial_concurrency=5)
        assert cfg.initial_concurrency == 5

    def test_min_dispatch_interval_negative(self) -> None:
        with pytest.raises(ValueError, match="min_dispatch_interval"):
            ThrottleConfig(min_dispatch_interval=-0.1)

    def test_min_dispatch_interval_zero_allowed(self) -> None:
        cfg = ThrottleConfig(min_dispatch_interval=0.0)
        assert cfg.min_dispatch_interval == 0.0

    def test_max_dispatch_interval_below_min(self) -> None:
        with pytest.raises(ValueError, match="max_dispatch_interval"):
            ThrottleConfig(min_dispatch_interval=5.0, max_dispatch_interval=1.0)

    def test_failure_threshold_too_low(self) -> None:
        with pytest.raises(ValueError, match="failure_threshold"):
            ThrottleConfig(failure_threshold=0)

    def test_failure_window_zero(self) -> None:
        with pytest.raises(ValueError, match="failure_window"):
            ThrottleConfig(failure_window=0)

    def test_failure_window_negative(self) -> None:
        with pytest.raises(ValueError, match="failure_window"):
            ThrottleConfig(failure_window=-1.0)

    def test_cooling_period_zero(self) -> None:
        with pytest.raises(ValueError, match="cooling_period"):
            ThrottleConfig(cooling_period=0)

    def test_cooling_period_negative(self) -> None:
        with pytest.raises(ValueError, match="cooling_period"):
            ThrottleConfig(cooling_period=-1.0)

    def test_safe_ceiling_decay_multiplier_zero(self) -> None:
        with pytest.raises(ValueError, match="safe_ceiling_decay_multiplier"):
            ThrottleConfig(safe_ceiling_decay_multiplier=0)

    def test_safe_ceiling_decay_multiplier_negative(self) -> None:
        with pytest.raises(ValueError, match="safe_ceiling_decay_multiplier"):
            ThrottleConfig(safe_ceiling_decay_multiplier=-1.0)

    def test_jitter_fraction_below_zero(self) -> None:
        with pytest.raises(ValueError, match="jitter_fraction"):
            ThrottleConfig(jitter_fraction=-0.1)

    def test_jitter_fraction_above_one(self) -> None:
        with pytest.raises(ValueError, match="jitter_fraction"):
            ThrottleConfig(jitter_fraction=1.1)

    def test_jitter_fraction_boundaries(self) -> None:
        cfg_zero = ThrottleConfig(jitter_fraction=0.0)
        assert cfg_zero.jitter_fraction == 0.0
        cfg_one = ThrottleConfig(jitter_fraction=1.0)
        assert cfg_one.jitter_fraction == 1.0

    def test_total_tasks_negative(self) -> None:
        with pytest.raises(ValueError, match="total_tasks"):
            ThrottleConfig(total_tasks=-1)

    def test_total_tasks_zero_allowed(self) -> None:
        cfg = ThrottleConfig(total_tasks=0)
        assert cfg.total_tasks == 0


# --- ThrottleConfig.from_dict ---


class TestThrottleConfigFromDict:
    def test_empty_dict(self) -> None:
        cfg = ThrottleConfig.from_dict({})
        assert cfg == ThrottleConfig()

    def test_full_config(self) -> None:
        cfg = ThrottleConfig.from_dict(
            {
                "max_concurrency": 10,
                "initial_concurrency": 3,
                "min_dispatch_interval": 0.5,
                "max_dispatch_interval": 15.0,
                "failure_threshold": 5,
                "failure_window": 30.0,
                "cooling_period": 120.0,
                "safe_ceiling_decay_multiplier": 3.0,
                "jitter_fraction": 0.3,
                "total_tasks": 100,
                "token_budget": {"max_tokens": 5000, "window_seconds": 60.0},
                "circuit_breaker": {
                    "consecutive_failures": 5,
                    "open_duration": 10.0,
                    "half_open_max_calls": 2,
                },
            }
        )
        assert cfg.max_concurrency == 10
        assert cfg.initial_concurrency == 3
        assert cfg.min_dispatch_interval == 0.5
        assert cfg.max_dispatch_interval == 15.0
        assert cfg.failure_threshold == 5
        assert cfg.failure_window == 30.0
        assert cfg.cooling_period == 120.0
        assert cfg.safe_ceiling_decay_multiplier == 3.0
        assert cfg.jitter_fraction == 0.3
        assert cfg.total_tasks == 100
        assert cfg.token_budget == TokenBudget(max_tokens=5000, window_seconds=60.0)
        assert cfg.circuit_breaker == CircuitBreakerConfig(
            consecutive_failures=5, open_duration=10.0, half_open_max_calls=2
        )

    def test_partial_config(self) -> None:
        cfg = ThrottleConfig.from_dict({"max_concurrency": 20})
        assert cfg.max_concurrency == 20
        assert cfg.min_dispatch_interval == 0.2  # default

    def test_nested_token_budget_as_object(self) -> None:
        tb = TokenBudget(max_tokens=100, window_seconds=10.0)
        cfg = ThrottleConfig.from_dict({"token_budget": tb})
        assert cfg.token_budget is tb

    def test_nested_circuit_breaker_as_object(self) -> None:
        cb = CircuitBreakerConfig(consecutive_failures=3)
        cfg = ThrottleConfig.from_dict({"circuit_breaker": cb})
        assert cfg.circuit_breaker is cb

    def test_partial_circuit_breaker_dict(self) -> None:
        cfg = ThrottleConfig.from_dict(
            {
                "circuit_breaker": {"consecutive_failures": 20},
            }
        )
        assert cfg.circuit_breaker is not None
        assert cfg.circuit_breaker.consecutive_failures == 20
        assert cfg.circuit_breaker.open_duration == 30.0  # default
        assert cfg.circuit_breaker.half_open_max_calls == 1  # default

    def test_callable_passthrough(self) -> None:
        predicate = lambda e: True  # noqa: E731
        cfg = ThrottleConfig.from_dict({"failure_predicate": predicate})
        assert cfg.failure_predicate is predicate

    def test_string_values_coerced(self) -> None:
        cfg = ThrottleConfig.from_dict({"max_concurrency": "8"})
        assert cfg.max_concurrency == 8


# --- ThrottleConfig.from_env ---


class TestThrottleConfigFromEnv:
    def test_empty_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GENTLIFY_MAX_CONCURRENCY", raising=False)
        cfg = ThrottleConfig.from_env()
        assert cfg == ThrottleConfig()

    def test_simple_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GENTLIFY_MAX_CONCURRENCY", "20")
        monkeypatch.setenv("GENTLIFY_INITIAL_CONCURRENCY", "5")
        monkeypatch.setenv("GENTLIFY_MIN_DISPATCH_INTERVAL", "0.1")
        monkeypatch.setenv("GENTLIFY_MAX_DISPATCH_INTERVAL", "10.0")
        monkeypatch.setenv("GENTLIFY_FAILURE_THRESHOLD", "10")
        monkeypatch.setenv("GENTLIFY_FAILURE_WINDOW", "120.0")
        monkeypatch.setenv("GENTLIFY_COOLING_PERIOD", "30.0")
        monkeypatch.setenv("GENTLIFY_SAFE_CEILING_DECAY_MULTIPLIER", "2.0")
        monkeypatch.setenv("GENTLIFY_JITTER_FRACTION", "0.8")
        cfg = ThrottleConfig.from_env()
        assert cfg.max_concurrency == 20
        assert cfg.initial_concurrency == 5
        assert cfg.min_dispatch_interval == 0.1
        assert cfg.max_dispatch_interval == 10.0
        assert cfg.failure_threshold == 10
        assert cfg.failure_window == 120.0
        assert cfg.cooling_period == 30.0
        assert cfg.safe_ceiling_decay_multiplier == 2.0
        assert cfg.jitter_fraction == 0.8

    def test_token_budget_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GENTLIFY_TOKEN_BUDGET_MAX", "5000")
        monkeypatch.setenv("GENTLIFY_TOKEN_BUDGET_WINDOW", "60.0")
        cfg = ThrottleConfig.from_env()
        assert cfg.token_budget == TokenBudget(max_tokens=5000, window_seconds=60.0)

    def test_token_budget_partial_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GENTLIFY_TOKEN_BUDGET_MAX", "5000")
        monkeypatch.delenv("GENTLIFY_TOKEN_BUDGET_WINDOW", raising=False)
        cfg = ThrottleConfig.from_env()
        assert cfg.token_budget is None

    def test_circuit_breaker_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GENTLIFY_CIRCUIT_BREAKER_CONSECUTIVE_FAILURES", "5")
        monkeypatch.setenv("GENTLIFY_CIRCUIT_BREAKER_OPEN_DURATION", "15.0")
        monkeypatch.setenv("GENTLIFY_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS", "3")
        cfg = ThrottleConfig.from_env()
        assert cfg.circuit_breaker == CircuitBreakerConfig(
            consecutive_failures=5, open_duration=15.0, half_open_max_calls=3
        )

    def test_circuit_breaker_partial(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GENTLIFY_CIRCUIT_BREAKER_CONSECUTIVE_FAILURES", "20")
        monkeypatch.delenv("GENTLIFY_CIRCUIT_BREAKER_OPEN_DURATION", raising=False)
        monkeypatch.delenv("GENTLIFY_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS", raising=False)
        cfg = ThrottleConfig.from_env()
        assert cfg.circuit_breaker is not None
        assert cfg.circuit_breaker.consecutive_failures == 20
        assert cfg.circuit_breaker.open_duration == 30.0  # default

    def test_custom_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MYAPP_MAX_CONCURRENCY", "42")
        cfg = ThrottleConfig.from_env(prefix="MYAPP")
        assert cfg.max_concurrency == 42

    def test_missing_vars_use_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GENTLIFY_MAX_CONCURRENCY", "7")
        cfg = ThrottleConfig.from_env()
        assert cfg.max_concurrency == 7
        assert cfg.min_dispatch_interval == 0.2  # default
        assert cfg.failure_threshold == 3  # default


# --- Throttle Factory Methods ---


class TestThrottleFromDict:
    def test_produces_working_instance(self) -> None:
        t = Throttle.from_dict({"max_concurrency": 20})
        snap = t.snapshot()
        assert snap.max_concurrency == 20
        assert snap.concurrency == 20

    def test_with_token_budget(self) -> None:
        t = Throttle.from_dict(
            {
                "max_concurrency": 10,
                "token_budget": {
                    "max_tokens": 5000,
                    "window_seconds": 60.0,
                },
            }
        )
        assert t.snapshot().tokens_remaining == 5000

    def test_with_circuit_breaker(self) -> None:
        t = Throttle.from_dict(
            {
                "max_concurrency": 8,
                "circuit_breaker": {
                    "consecutive_failures": 5,
                    "open_duration": 20.0,
                },
            }
        )
        snap = t.snapshot()
        assert snap.max_concurrency == 8

    def test_round_trip_config_to_dict_to_throttle(self) -> None:
        """Config → dict → Throttle produces equivalent state."""
        import dataclasses

        original = ThrottleConfig(
            max_concurrency=12,
            initial_concurrency=4,
            min_dispatch_interval=0.5,
            failure_threshold=5,
            token_budget=TokenBudget(max_tokens=2000, window_seconds=30.0),
        )
        data: dict[str, object] = {}
        for f in dataclasses.fields(original):
            val = getattr(original, f.name)
            if val is not None and dataclasses.is_dataclass(val):
                data[f.name] = dataclasses.asdict(val)
            elif val is not None:
                data[f.name] = val

        t = Throttle.from_dict(data)
        snap = t.snapshot()
        assert snap.max_concurrency == 12
        assert snap.concurrency == 4
        assert snap.dispatch_interval == 0.5
        assert snap.tokens_remaining == 2000


class TestThrottleFromEnv:
    def test_produces_working_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GENTLIFY_MAX_CONCURRENCY", "15")
        t = Throttle.from_env()
        assert t.snapshot().max_concurrency == 15

    def test_custom_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MYAPP_MAX_CONCURRENCY", "25")
        t = Throttle.from_env(prefix="MYAPP")
        assert t.snapshot().max_concurrency == 25

    def test_with_token_budget_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GENTLIFY_MAX_CONCURRENCY", "10")
        monkeypatch.setenv("GENTLIFY_TOKEN_BUDGET_MAX", "3000")
        monkeypatch.setenv("GENTLIFY_TOKEN_BUDGET_WINDOW", "45.0")
        t = Throttle.from_env()
        assert t.snapshot().tokens_remaining == 3000
