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

from gentlify import RetryConfig
from gentlify._retry import RetryHandler

# --- RetryConfig validation ---


class TestRetryConfigValidation:
    def test_defaults(self) -> None:
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.backoff == "exponential_jitter"
        assert cfg.base_delay == 1.0
        assert cfg.max_delay == 60.0
        assert cfg.retryable is None

    def test_custom_values(self) -> None:
        pred = lambda e: isinstance(e, ValueError)  # noqa: E731
        cfg = RetryConfig(
            max_attempts=5,
            backoff="fixed",
            base_delay=0.5,
            max_delay=10.0,
            retryable=pred,
        )
        assert cfg.max_attempts == 5
        assert cfg.backoff == "fixed"
        assert cfg.base_delay == 0.5
        assert cfg.max_delay == 10.0
        assert cfg.retryable is pred

    def test_max_attempts_zero(self) -> None:
        with pytest.raises(ValueError, match="max_attempts"):
            RetryConfig(max_attempts=0)

    def test_max_attempts_negative(self) -> None:
        with pytest.raises(ValueError, match="max_attempts"):
            RetryConfig(max_attempts=-1)

    def test_max_attempts_one_allowed(self) -> None:
        cfg = RetryConfig(max_attempts=1)
        assert cfg.max_attempts == 1

    def test_invalid_backoff(self) -> None:
        with pytest.raises(ValueError, match="backoff"):
            RetryConfig(backoff="linear")

    def test_valid_backoff_fixed(self) -> None:
        cfg = RetryConfig(backoff="fixed")
        assert cfg.backoff == "fixed"

    def test_valid_backoff_exponential(self) -> None:
        cfg = RetryConfig(backoff="exponential")
        assert cfg.backoff == "exponential"

    def test_valid_backoff_exponential_jitter(self) -> None:
        cfg = RetryConfig(backoff="exponential_jitter")
        assert cfg.backoff == "exponential_jitter"

    def test_base_delay_negative(self) -> None:
        with pytest.raises(ValueError, match="base_delay"):
            RetryConfig(base_delay=-0.1)

    def test_base_delay_zero_allowed(self) -> None:
        cfg = RetryConfig(base_delay=0.0)
        assert cfg.base_delay == 0.0

    def test_max_delay_below_base_delay(self) -> None:
        with pytest.raises(ValueError, match="max_delay"):
            RetryConfig(base_delay=5.0, max_delay=2.0)

    def test_max_delay_equals_base_delay(self) -> None:
        cfg = RetryConfig(base_delay=5.0, max_delay=5.0)
        assert cfg.max_delay == 5.0


# --- RetryHandler backoff strategies ---


class TestRetryHandlerFixedBackoff:
    def test_constant_delay(self) -> None:
        handler = RetryHandler(RetryConfig(backoff="fixed", base_delay=2.0))
        assert handler.compute_delay(0) == 2.0
        assert handler.compute_delay(1) == 2.0
        assert handler.compute_delay(5) == 2.0
        assert handler.compute_delay(100) == 2.0

    def test_zero_base_delay(self) -> None:
        handler = RetryHandler(RetryConfig(backoff="fixed", base_delay=0.0, max_delay=0.0))
        assert handler.compute_delay(0) == 0.0


class TestRetryHandlerExponentialBackoff:
    def test_doubles_each_attempt(self) -> None:
        handler = RetryHandler(RetryConfig(backoff="exponential", base_delay=1.0, max_delay=60.0))
        assert handler.compute_delay(0) == 1.0  # 1.0 * 2^0
        assert handler.compute_delay(1) == 2.0  # 1.0 * 2^1
        assert handler.compute_delay(2) == 4.0  # 1.0 * 2^2
        assert handler.compute_delay(3) == 8.0  # 1.0 * 2^3
        assert handler.compute_delay(4) == 16.0  # 1.0 * 2^4

    def test_capped_at_max_delay(self) -> None:
        handler = RetryHandler(RetryConfig(backoff="exponential", base_delay=1.0, max_delay=10.0))
        assert handler.compute_delay(0) == 1.0
        assert handler.compute_delay(3) == 8.0
        assert handler.compute_delay(4) == 10.0  # capped
        assert handler.compute_delay(10) == 10.0  # still capped

    def test_custom_base_delay(self) -> None:
        handler = RetryHandler(RetryConfig(backoff="exponential", base_delay=0.5, max_delay=60.0))
        assert handler.compute_delay(0) == 0.5
        assert handler.compute_delay(1) == 1.0
        assert handler.compute_delay(2) == 2.0


class TestRetryHandlerExponentialJitterBackoff:
    @staticmethod
    def _fixed_random(value: float) -> object:
        def _rand(lo: float, hi: float) -> float:
            return lo + (hi - lo) * value

        return _rand

    def test_jitter_at_midpoint(self) -> None:
        rand_fn = self._fixed_random(0.5)
        handler = RetryHandler(
            RetryConfig(backoff="exponential_jitter", base_delay=1.0, max_delay=60.0),
            rand_fn=rand_fn,
        )
        # uniform(0, 1.0 * 2^0) = uniform(0, 1.0) → midpoint = 0.5
        assert handler.compute_delay(0) == 0.5
        # uniform(0, 1.0 * 2^1) = uniform(0, 2.0) → midpoint = 1.0
        assert handler.compute_delay(1) == 1.0
        # uniform(0, 1.0 * 2^2) = uniform(0, 4.0) → midpoint = 2.0
        assert handler.compute_delay(2) == 2.0

    def test_jitter_at_zero(self) -> None:
        rand_fn = self._fixed_random(0.0)
        handler = RetryHandler(
            RetryConfig(backoff="exponential_jitter", base_delay=1.0, max_delay=60.0),
            rand_fn=rand_fn,
        )
        assert handler.compute_delay(0) == 0.0
        assert handler.compute_delay(5) == 0.0

    def test_jitter_at_one(self) -> None:
        rand_fn = self._fixed_random(1.0)
        handler = RetryHandler(
            RetryConfig(backoff="exponential_jitter", base_delay=1.0, max_delay=60.0),
            rand_fn=rand_fn,
        )
        # uniform(0, 1.0) → max = 1.0
        assert handler.compute_delay(0) == 1.0
        # uniform(0, 2.0) → max = 2.0
        assert handler.compute_delay(1) == 2.0

    def test_jitter_capped_at_max_delay(self) -> None:
        rand_fn = self._fixed_random(1.0)
        handler = RetryHandler(
            RetryConfig(backoff="exponential_jitter", base_delay=1.0, max_delay=5.0),
            rand_fn=rand_fn,
        )
        # uniform(0, min(1.0 * 2^10, 5.0)) = uniform(0, 5.0) → 5.0
        assert handler.compute_delay(10) == 5.0


# --- RetryHandler retryable predicate ---


class TestRetryHandlerRetryable:
    def test_default_retries_all(self) -> None:
        handler = RetryHandler(RetryConfig())
        assert handler.is_retryable(ValueError("test")) is True
        assert handler.is_retryable(RuntimeError("test")) is True
        assert handler.is_retryable(KeyboardInterrupt()) is True

    def test_custom_predicate(self) -> None:
        handler = RetryHandler(
            RetryConfig(retryable=lambda e: isinstance(e, (ValueError, TimeoutError)))
        )
        assert handler.is_retryable(ValueError("test")) is True
        assert handler.is_retryable(TimeoutError("test")) is True
        assert handler.is_retryable(RuntimeError("test")) is False
        assert handler.is_retryable(KeyError("test")) is False

    def test_predicate_always_false(self) -> None:
        handler = RetryHandler(RetryConfig(retryable=lambda e: False))
        assert handler.is_retryable(ValueError("test")) is False


# --- RetryHandler max_attempts property ---


class TestRetryHandlerMaxAttempts:
    def test_returns_config_value(self) -> None:
        handler = RetryHandler(RetryConfig(max_attempts=5))
        assert handler.max_attempts == 5

    def test_single_attempt(self) -> None:
        handler = RetryHandler(RetryConfig(max_attempts=1))
        assert handler.max_attempts == 1
