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

import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gentlify._config import RetryConfig
    from gentlify._types import Clock, RandFn


class RetryHandler:
    """Backoff computation and retryable predicate for the retry loop."""

    def __init__(
        self,
        config: RetryConfig,
        clock: Clock = time.monotonic,
        rand_fn: RandFn = random.uniform,
    ) -> None:
        self._config = config
        self._clock = clock
        self._rand_fn = rand_fn

    def compute_delay(self, attempt: int) -> float:
        """Compute backoff delay for the given attempt number (0-indexed).

        Args:
            attempt: Zero-indexed retry attempt number (0 = first retry).

        Returns:
            Delay in seconds before the next retry.
        """
        cfg = self._config
        if cfg.backoff == "fixed":
            return cfg.base_delay
        elif cfg.backoff == "exponential":
            delay: float = min(cfg.base_delay * (2.0**attempt), cfg.max_delay)
            return delay
        else:  # exponential_jitter
            exp_delay: float = min(cfg.base_delay * (2.0**attempt), cfg.max_delay)
            return self._rand_fn(0.0, exp_delay)

    def is_retryable(self, exc: BaseException) -> bool:
        """Check if the exception should be retried.

        Args:
            exc: The exception that was raised.

        Returns:
            True if the exception is retryable, False otherwise.
        """
        if self._config.retryable is None:
            return True
        return self._config.retryable(exc)

    @property
    def max_attempts(self) -> int:
        """Total attempts including the initial call."""
        return self._config.max_attempts
