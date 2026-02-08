# tech_spec.md — gentlify (Python)

This document defines **how** gentlify is built — its architecture, module layout, dependencies, data models, API signatures, and cross-cutting concerns. It translates the requirements in [`features.md`](features.md) into a concrete design. For the implementation plan, see [`stories.md`](stories.md).

---

## Runtime & Tooling

| Concern | Choice |
|---------|--------|
| Language | Python 3.11+ (developed on 3.14.3) |
| Package manager | `pip` / `uv` with `pyproject.toml` (PEP 621) |
| Build backend | `hatchling` |
| Linter / formatter | `ruff` (lint + format) |
| Type checker | `mypy --strict` |
| Test runner | `pytest` with `pytest-asyncio` |
| Coverage | `pytest-cov` (target ≥ 95%) |
| Python env | `venv` via `.envrc` (already configured) |

---

## Dependencies

### Runtime Dependencies

None. gentlify uses only the Python standard library:

| Module | Purpose |
|--------|---------|
| `asyncio` | Semaphore, Event, sleep, task management |
| `time` | `monotonic()` for all timing |
| `random` | `uniform()` for jitter |
| `logging` | Structured log events |
| `dataclasses` | Data models (`ThrottleSnapshot`, `TokenBudget`, etc.) |
| `enum` | `ThrottleState` enum |
| `collections` | `deque` for bounded failure/token windows |
| `typing` | Type annotations |
| `os` | `environ` for `from_env()` factory |
| `math` | `ceil` for progress milestone calculation |
| `functools` | `wraps` for decorator API |

### Development Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | ≥ 8.0 | Test runner |
| `pytest-asyncio` | ≥ 0.24 | Async test support |
| `pytest-cov` | ≥ 6.0 | Coverage reporting |
| `mypy` | ≥ 1.13 | Static type checking |
| `ruff` | ≥ 0.8 | Linting and formatting |

---

## Package Structure

```
gentlify/
├── pyproject.toml                  # Package metadata, dependencies, tool config
├── LICENSE                         # Apache-2.0
├── README.md                       # Project overview, quick start, examples
├── .tool-versions                  # asdf/mise Python version pin
├── .gitignore                      # VCS ignores
├── .envrc                          # direnv venv activation
├── docs/
│   ├── guides/
│   │   └── project_guide.md        # LLM-assisted project creation guide
│   └── specs/
│       ├── features.md             # Requirements specification
│       ├── tech_spec.md            # This document
│       └── stories.md              # Implementation plan
├── src/
│   └── gentlify/
│       ├── __init__.py             # Public API re-exports
│       ├── py.typed                # PEP 561 marker
│       ├── _version.py             # Single-source version string
│       ├── _types.py               # Enums, dataclasses, type aliases
│       ├── _config.py              # ThrottleConfig, TokenBudget, CircuitBreakerConfig, from_dict, from_env
│       ├── _window.py              # SlidingWindow — bounded timestamp/value tracker
│       ├── _concurrency.py         # ConcurrencyController — semaphore + adaptive limit
│       ├── _dispatch.py            # DispatchGate — interval enforcement + jitter
│       ├── _token_bucket.py        # TokenBucket — rolling-window token budget
│       ├── _circuit_breaker.py     # CircuitBreaker — open/half-open/closed state machine
│       ├── _progress.py            # ProgressTracker — completion %, ETA, milestones
│       ├── _slot.py                # Slot — context manager yielded by acquire()
│       ├── _throttle.py            # Throttle — main orchestrator class
│       └── _exceptions.py          # CircuitOpenError, ThrottleClosed
└── tests/
    ├── conftest.py                 # Shared fixtures (FakeClock, FakeRandom)
    ├── test_window.py              # SlidingWindow unit tests
    ├── test_concurrency.py         # ConcurrencyController unit tests
    ├── test_dispatch.py            # DispatchGate unit tests
    ├── test_token_bucket.py        # TokenBucket unit tests
    ├── test_circuit_breaker.py     # CircuitBreaker unit tests
    ├── test_progress.py            # ProgressTracker unit tests
    ├── test_throttle.py            # Throttle integration tests (context manager, decorator)
    ├── test_config.py              # from_dict, from_env, validation tests
    └── test_edge_cases.py          # Edge case and stress tests
```

All internal modules use a leading underscore (`_`) to signal they are private. The public API is defined entirely in `__init__.py`.

---

## Key Component Design

### `_types.py` — Enums, Dataclasses, Type Aliases

```python
class ThrottleState(enum.Enum):
    RUNNING = "running"
    COOLING = "cooling"
    CIRCUIT_OPEN = "circuit_open"
    CLOSED = "closed"
    DRAINING = "draining"
```

```python
@dataclass(frozen=True)
class ThrottleSnapshot:
    """Point-in-time view of throttle state."""
    concurrency: int
    max_concurrency: int
    dispatch_interval: float
    completed_tasks: int
    total_tasks: int
    failure_count: int
    state: ThrottleState
    safe_ceiling: int
    eta_seconds: float | None
    tokens_used: int
    tokens_remaining: int | None
```

```python
@dataclass(frozen=True)
class ThrottleEvent:
    """Structured event emitted on state transitions."""
    kind: str                       # "decelerated", "reaccelerated", etc.
    timestamp: float                # monotonic time
    data: dict[str, Any]            # event-specific payload
```

Type aliases:

```python
FailurePredicate = Callable[[BaseException], bool]
StateChangeCallback = Callable[[ThrottleEvent], Any]
ProgressCallback = Callable[[ThrottleSnapshot], Any]
Clock = Callable[[], float]         # injectable time source
RandFn = Callable[[float, float], float]  # injectable random source
```

### `_config.py` — Configuration

```python
@dataclass(frozen=True)
class TokenBudget:
    max_tokens: int
    window_seconds: float

@dataclass(frozen=True)
class CircuitBreakerConfig:
    consecutive_failures: int = 10
    open_duration: float = 30.0
    half_open_max_calls: int = 1

@dataclass(frozen=True)
class ThrottleConfig:
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
```

Factory methods:

```python
@staticmethod
def from_dict(data: dict[str, Any]) -> ThrottleConfig:
    """Build config from a plain dict. Nested dicts for token_budget and circuit_breaker."""

@staticmethod
def from_env(prefix: str = "GENTLIFY") -> ThrottleConfig:
    """Build config from environment variables. See features.md for env var mapping."""
```

Validation (called in `__post_init__`):
- `max_concurrency >= 1`
- `initial_concurrency` is `None` or `1 <= initial_concurrency <= max_concurrency`
- `min_dispatch_interval >= 0`
- `max_dispatch_interval >= min_dispatch_interval`
- `failure_threshold >= 1`
- `failure_window > 0`
- `cooling_period > 0`
- `safe_ceiling_decay_multiplier > 0`
- `0.0 <= jitter_fraction <= 1.0`
- `total_tasks >= 0`
- `TokenBudget.max_tokens >= 1`, `TokenBudget.window_seconds > 0`
- `CircuitBreakerConfig.consecutive_failures >= 1`, `open_duration >= 0`, `half_open_max_calls >= 1`

Raises `ValueError` with a descriptive message on invalid input.

### `_window.py` — SlidingWindow

A generic bounded sliding-window tracker used by both failure counting and token budgeting.

```python
class SlidingWindow:
    def __init__(
        self,
        window_seconds: float,
        clock: Clock = time.monotonic,
    ) -> None: ...

    def record(self, value: float = 1.0) -> None:
        """Record a value at the current time."""

    def total(self) -> float:
        """Sum of values within the window, after pruning expired entries."""

    def count(self) -> int:
        """Number of entries within the window."""

    def clear(self) -> None:
        """Remove all entries."""
```

Internally uses a `deque` of `(timestamp, value)` tuples. `total()` and `count()` prune expired entries lazily on access.

### `_concurrency.py` — ConcurrencyController

Manages the dynamic concurrency limit via an asyncio semaphore.

```python
class ConcurrencyController:
    def __init__(
        self,
        max_concurrency: int,
        initial_concurrency: int | None = None,
    ) -> None: ...

    @property
    def current_limit(self) -> int:
        """Current concurrency limit."""

    @property
    def in_flight(self) -> int:
        """Number of currently acquired slots."""

    async def acquire(self) -> None:
        """Wait for a concurrency slot."""

    def release(self) -> None:
        """Release a concurrency slot."""

    def decelerate(self) -> tuple[int, int]:
        """Halve the concurrency limit (min 1). Returns (old, new)."""

    def reaccelerate(self, safe_ceiling: int) -> tuple[int, int]:
        """Increase concurrency by 1, capped at safe_ceiling. Returns (old, new)."""

    def resize(self, new_limit: int) -> None:
        """Set the concurrency limit to an exact value. Used during ceiling decay reset."""
```

The semaphore is rebuilt when the limit changes. Pending waiters are handled by draining the old semaphore and creating a new one, or by using a counter-based approach that adjusts available permits.

### `_dispatch.py` — DispatchGate

Enforces the minimum time gap between consecutive dispatches with jitter.

```python
class DispatchGate:
    def __init__(
        self,
        interval: float,
        jitter_fraction: float = 0.5,
        clock: Clock = time.monotonic,
        rand_fn: RandFn = random.uniform,
    ) -> None: ...

    @property
    def interval(self) -> float:
        """Current dispatch interval."""

    async def wait(self) -> None:
        """Wait until the next dispatch is allowed, with jitter."""

    def decelerate(self, max_interval: float) -> tuple[float, float]:
        """Double the interval (capped at max_interval). Returns (old, new)."""

    def reaccelerate(self, min_interval: float) -> tuple[float, float]:
        """Halve the interval (floored at min_interval). Returns (old, new)."""
```

`wait()` computes `elapsed = clock() - last_dispatch`, then sleeps for `max(0, interval - elapsed) + jitter`. Updates `last_dispatch` after the sleep.

### `_token_bucket.py` — TokenBucket

Rolling-window token budget tracker.

```python
class TokenBucket:
    def __init__(
        self,
        budget: TokenBudget,
        clock: Clock = time.monotonic,
    ) -> None: ...

    def consume(self, tokens: int) -> None:
        """Record token consumption."""

    def tokens_used(self) -> int:
        """Tokens consumed in the current window."""

    def tokens_remaining(self) -> int:
        """Tokens remaining in the current window."""

    async def wait_for_budget(self, tokens: int = 1) -> None:
        """Block until at least `tokens` are available in the budget window."""
```

Uses `SlidingWindow` internally. `wait_for_budget()` computes the time until enough tokens expire from the window and sleeps accordingly.

### `_circuit_breaker.py` — CircuitBreaker

Three-state machine: closed → open → half-open → closed/open.

```python
class CircuitBreaker:
    def __init__(
        self,
        config: CircuitBreakerConfig,
        clock: Clock = time.monotonic,
    ) -> None: ...

    @property
    def state(self) -> str:
        """Current state: 'closed', 'open', 'half_open'."""

    def check(self) -> None:
        """Raise CircuitOpenError if the circuit is open. Allow probes if half-open."""

    def record_success(self) -> None:
        """Record a success. Closes the circuit if half-open and probe threshold met."""

    def record_failure(self) -> None:
        """Record a failure. Opens the circuit if consecutive threshold exceeded."""

    @property
    def consecutive_failures(self) -> int: ...

    @property
    def half_open_successes(self) -> int: ...
```

State transitions:
- **Closed → Open:** `consecutive_failures >= config.consecutive_failures`
- **Open → Half-open:** `clock() - opened_at >= config.open_duration`
- **Half-open → Closed:** `half_open_successes >= config.half_open_max_calls`
- **Half-open → Open:** any failure during half-open (delay doubles, capped at 5× `open_duration`)

### `_progress.py` — ProgressTracker

Tracks task completion and computes ETA.

```python
class ProgressTracker:
    def __init__(
        self,
        total_tasks: int,
        milestone_pct: float = 10.0,
        clock: Clock = time.monotonic,
    ) -> None: ...

    def record_completion(self, duration: float) -> bool:
        """Record a task completion. Returns True if a milestone was crossed."""

    @property
    def completed(self) -> int: ...

    @property
    def percentage(self) -> float: ...

    @property
    def eta_seconds(self) -> float | None:
        """ETA based on rolling average of recent task durations. None if unknown."""
```

ETA uses a rolling average of the last 50 task durations (configurable) multiplied by remaining tasks, adjusted by current concurrency.

### `_slot.py` — Slot

The object yielded by the `acquire()` context manager.

```python
class Slot:
    def __init__(self, throttle: Throttle) -> None: ...

    def record_tokens(self, count: int) -> None:
        """Report token consumption for this request."""

    @property
    def tokens_reported(self) -> int:
        """Tokens reported via record_tokens() during this slot's lifetime."""
```

`Slot` is a lightweight handle. Token counts reported via `record_tokens()` are forwarded to the throttle's `TokenBucket` on context exit.

### `_throttle.py` — Throttle (Main Orchestrator)

```python
class Throttle:
    def __init__(self, **kwargs: Any) -> None:
        """Accept all ThrottleConfig fields as kwargs."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Throttle: ...

    @classmethod
    def from_env(cls, prefix: str = "GENTLIFY") -> Throttle: ...

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[Slot]:
        """Primary API: acquire a throttled slot."""

    def wrap(self, fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """Decorator API: wrap an async function with acquire()."""

    def record_success(self, duration: float = 0.0, tokens_used: int = 0) -> None:
        """Manually record a successful request."""

    def record_failure(self, exception: BaseException | None = None) -> None:
        """Manually record a failed request."""

    def record_tokens(self, count: int) -> None:
        """Manually record token consumption."""

    def snapshot(self) -> ThrottleSnapshot:
        """Return a point-in-time snapshot of throttle state."""

    def close(self) -> None:
        """Signal that no new requests should be accepted."""

    async def drain(self) -> None:
        """Wait for all in-flight requests to complete."""
```

#### `acquire()` flow:

1. Check state — raise `ThrottleClosed` if closed/draining.
2. `circuit_breaker.check()` — raise `CircuitOpenError` if open.
3. `concurrency_controller.acquire()` — wait for semaphore slot.
4. `dispatch_gate.wait()` — enforce interval + jitter.
5. `token_bucket.wait_for_budget()` — wait for token budget (if configured).
6. Yield `Slot` to user code.
7. On `__aexit__`:
   - If no exception: call `_handle_success(duration, slot.tokens_reported)`.
   - If exception: call `_handle_failure(exception)`.
   - Always: `concurrency_controller.release()`, update progress.

#### `_handle_success()`:

1. `circuit_breaker.record_success()` (if configured).
2. `failure_window` — no action (success doesn't clear individual failures; they expire naturally).
3. Check cooling: if in COOLING state and `clock() - cooling_start >= cooling_period`, trigger reacceleration.
4. Check safe ceiling decay: if `clock() - last_failure >= cooling_period × safe_ceiling_decay_multiplier`, reset `safe_ceiling` to `max_concurrency`.
5. Record token consumption in `TokenBucket` (if configured and tokens > 0).
6. Update `ProgressTracker` and fire `on_progress` if milestone crossed.

#### `_handle_failure(exception)`:

1. If `failure_predicate` is set and returns `False` for this exception, skip throttle bookkeeping (but still re-raise).
2. `failure_window.record()`.
3. `circuit_breaker.record_failure()` (if configured).
4. If `failure_window.count() >= failure_threshold`:
   - `concurrency_controller.decelerate()`.
   - `dispatch_gate.decelerate()`.
   - Set `safe_ceiling = old_concurrency`.
   - `failure_window.clear()`.
   - Enter COOLING state, record `cooling_start`.
   - Emit `decelerated` event, then `cooling_started` event.
5. Re-raise the original exception (gentlify never swallows).

### `_exceptions.py` — Custom Exceptions

```python
class GentlifyError(Exception):
    """Base exception for all gentlify errors."""

class CircuitOpenError(GentlifyError):
    """Raised when acquire() is called while the circuit breaker is open."""
    retry_after: float  # seconds until the circuit may transition to half-open

class ThrottleClosed(GentlifyError):
    """Raised when acquire() is called after close()."""
```

---

## Data Models

All data models are frozen dataclasses for immutability and hashability.

| Model | Module | Fields | Purpose |
|-------|--------|--------|---------|
| `ThrottleConfig` | `_config` | See [Configuration](#_configpy--configuration) | Validated configuration |
| `TokenBudget` | `_config` | `max_tokens: int`, `window_seconds: float` | Token budget config |
| `CircuitBreakerConfig` | `_config` | `consecutive_failures: int`, `open_duration: float`, `half_open_max_calls: int` | Circuit breaker config |
| `ThrottleSnapshot` | `_types` | See [Enums, Dataclasses](#_typespy--enums-dataclasses-type-aliases) | Read-only state view |
| `ThrottleEvent` | `_types` | `kind: str`, `timestamp: float`, `data: dict` | Structured event |

---

## Configuration

### Precedence

1. **Constructor kwargs** (highest priority)
2. **`from_dict()` values**
3. **`from_env()` values**
4. **Defaults in `ThrottleConfig`** (lowest priority)

`from_dict()` and `from_env()` both produce a `ThrottleConfig` which is passed to the `Throttle` constructor. Users cannot mix sources in a single call — they pick one factory method or use kwargs directly.

### Validation

All validation happens in `ThrottleConfig.__post_init__()`. Invalid values raise `ValueError` with a message identifying the field and constraint. This ensures that a `Throttle` instance is always in a valid state from construction.

---

## Library API

### Public Exports (`__init__.py`)

```python
from gentlify._throttle import Throttle
from gentlify._config import ThrottleConfig, TokenBudget, CircuitBreakerConfig
from gentlify._types import ThrottleSnapshot, ThrottleState, ThrottleEvent
from gentlify._exceptions import GentlifyError, CircuitOpenError, ThrottleClosed
from gentlify._version import __version__

__all__ = [
    "Throttle",
    "ThrottleConfig",
    "TokenBudget",
    "CircuitBreakerConfig",
    "ThrottleSnapshot",
    "ThrottleState",
    "ThrottleEvent",
    "GentlifyError",
    "CircuitOpenError",
    "ThrottleClosed",
    "__version__",
]
```

### Usage Examples

#### Minimal

```python
from gentlify import Throttle

throttle = Throttle()

async def process(items):
    for item in items:
        async with throttle.acquire():
            await call_api(item)
```

#### With token budget and circuit breaker

```python
from gentlify import Throttle, TokenBudget, CircuitBreakerConfig

throttle = Throttle(
    max_concurrency=5,
    initial_concurrency=2,
    token_budget=TokenBudget(max_tokens=10_000, window_seconds=60.0),
    circuit_breaker=CircuitBreakerConfig(consecutive_failures=10),
    on_state_change=lambda event: print(f"[{event.kind}] {event.data}"),
    on_progress=lambda snap: print(f"{snap.percentage:.0f}% done, ETA {snap.eta_seconds:.0f}s"),
    total_tasks=100,
)

async def process(prompts):
    async with asyncio.TaskGroup() as tg:
        for prompt in prompts:
            tg.create_task(call_one(prompt))

async def call_one(prompt):
    async with throttle.acquire() as slot:
        result = await llm_client.complete(prompt)
        slot.record_tokens(result.usage.total_tokens)
```

#### Decorator API

```python
from gentlify import Throttle

throttle = Throttle(max_concurrency=3)

@throttle.wrap
async def call_api(prompt: str) -> str:
    return await client.complete(prompt)

results = await asyncio.gather(*[call_api(p) for p in prompts])
```

#### Graceful shutdown

```python
throttle.close()
await throttle.drain()
```

---

## Cross-Cutting Concerns

### Logging

- Logger name: `"gentlify"`
- Log levels:
  - `INFO` — deceleration, reacceleration, circuit state changes
  - `DEBUG` — dispatch wait times, token budget status, cooling timer progress
  - `WARNING` — circuit breaker opened
- Users can configure via `logging.getLogger("gentlify")` as usual.
- No log output by default (follows Python logging convention — no handlers attached).

### Deterministic Testing

All components accept injectable dependencies:

| Dependency | Default | Test Replacement |
|------------|---------|------------------|
| `clock` | `time.monotonic` | `FakeClock` — manually advanceable |
| `rand_fn` | `random.uniform` | `lambda a, b: (a + b) / 2` or fixed value |

`FakeClock` is a simple class with an `advance(seconds)` method that increments an internal counter. It is defined in `tests/conftest.py`.

### Atomic State Transitions

All state mutations (deceleration, reacceleration, circuit breaker transitions) are performed as atomic sequences within a single asyncio task turn (no `await` between read-check-write). Since asyncio is single-threaded cooperative, this guarantees consistency without locks for the state machine logic. The only lock-like primitive is the semaphore in `ConcurrencyController`, which is inherently safe.

### Error Propagation

gentlify **never** catches and suppresses user exceptions. The `acquire()` context manager uses a `try/finally` pattern:

```python
try:
    yield slot
except BaseException as exc:
    self._handle_failure(exc)
    raise
else:
    self._handle_success(duration, slot.tokens_reported)
finally:
    self._concurrency.release()
```

The exception is always re-raised after bookkeeping.

---

## Testing Strategy

### Unit Tests

Each internal module has a dedicated test file. Tests use `FakeClock` and deterministic random functions to eliminate timing flakiness.

| Test File | Covers |
|-----------|--------|
| `test_window.py` | SlidingWindow: record, total, count, expiry, clear |
| `test_concurrency.py` | ConcurrencyController: acquire/release, decelerate/reaccelerate, resize, in_flight count |
| `test_dispatch.py` | DispatchGate: interval enforcement, jitter bounds, decelerate/reaccelerate |
| `test_token_bucket.py` | TokenBucket: consume, wait_for_budget, window rollover |
| `test_circuit_breaker.py` | CircuitBreaker: closed→open→half-open→closed, half_open_max_calls, delay doubling |
| `test_progress.py` | ProgressTracker: completion, milestones, ETA calculation |
| `test_config.py` | ThrottleConfig validation, from_dict, from_env |

### Integration Tests

| Test File | Covers |
|-----------|--------|
| `test_throttle.py` | Full Throttle lifecycle: acquire, success/failure recording, deceleration/reacceleration, context manager, decorator, close/drain, snapshot, callbacks, multiple instances |

### Edge Case Tests

| Test File | Covers |
|-----------|--------|
| `test_edge_cases.py` | Zero total_tasks, single concurrency, immediate first-request failure, failure_predicate always False, circuit breaker with zero delay, max_concurrency=1 with deceleration, token budget of 1, concurrent drain + acquire |

### Test Fixtures (`conftest.py`)

```python
class FakeClock:
    """Manually advanceable clock for deterministic tests."""
    def __init__(self, start: float = 0.0) -> None: ...
    def __call__(self) -> float: ...
    def advance(self, seconds: float) -> None: ...

@pytest.fixture
def fake_clock() -> FakeClock: ...

@pytest.fixture
def fixed_random() -> Callable[[float, float], float]:
    """Returns midpoint of range for deterministic jitter."""
    return lambda a, b: (a + b) / 2
```
