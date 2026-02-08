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


class GentlifyError(Exception):
    """Base exception for all gentlify errors."""


class CircuitOpenError(GentlifyError):
    """Raised when the circuit breaker is open and rejecting requests."""

    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker is open. Retry after {retry_after:.1f}s.")


class ThrottleClosed(GentlifyError):  # noqa: N818
    """Raised when acquire() is called on a closed throttle."""

    def __init__(self) -> None:
        super().__init__("Throttle is closed and no longer accepting requests.")
