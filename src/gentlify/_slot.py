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


class Slot:
    """Lightweight handle yielded by ``Throttle.acquire()``.

    Users call ``record_tokens()`` to report token consumption for this request.
    The throttle reads ``tokens_reported`` on context exit.
    """

    def __init__(self) -> None:
        self._tokens_reported = 0
        self._attempt = 0

    def record_tokens(self, count: int) -> None:
        """Report token consumption for this request."""
        self._tokens_reported += count

    @property
    def tokens_reported(self) -> int:
        """Tokens reported via record_tokens() during this slot's lifetime."""
        return self._tokens_reported

    @property
    def attempt(self) -> int:
        """Zero-indexed attempt number. 0 on first call, increments on retry."""
        return self._attempt

    def _set_attempt(self, n: int) -> None:
        """Internal: set the attempt number. Not part of the public API."""
        self._attempt = n
