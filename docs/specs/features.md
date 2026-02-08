# features.md — gentlify (Python)

Adaptive async rate limiting for Python: tame angry APIs, make them purr.

This document defines **what** gentlify does — its requirements, inputs, outputs, and expected behavior — without prescribing implementation details. It is the source of truth for project scope. For architecture and module design, see [`tech_spec.md`](tech_spec.md). For the implementation plan, see [`stories.md`](stories.md).

---

## Project Goal

gentlify is an adaptive rate-throttle library for Python asyncio applications that call external APIs. It provides closed-loop feedback control: when an API signals overload (rate limits, server errors, timeouts), gentlify automatically reduces request concurrency and dispatch rate; when pressure subsides, it cautiously recovers. Unlike static rate limiters, gentlify observes real-time failure signals and adjusts dynamically — preventing the burst-then-stall pattern common in concurrent API workloads.

gentlify is a **Python library** (no CLI) targeting **Python 3.11+** (developed on 3.14). It is designed to be embedded in applications that make concurrent async API calls — LLM pipelines, web scrapers, data ingestion tools, batch processors, etc.

### Core Requirements

1. **Adaptive concurrency control** — Maintain a dynamic concurrency limit (how many requests are in-flight simultaneously). Decelerate when failures accumulate; reaccelerate after a cooling period of sustained success.
2. **Dispatch interval gating** — Enforce a minimum time between consecutive request dispatches, independent of concurrency. This prevents bursts even when concurrency is high.
3. **Stochastic jitter** — Add random jitter to dispatch timing so concurrent slots don't fire at the same instant, avoiding the thundering-herd problem.
4. **Safe ceiling tracking** — Remember the concurrency level at which failures were last observed. Never reaccelerate past this ceiling until it is explicitly reset or decays over time.
5. **Failure signal abstraction** — Allow users to define what constitutes a "failure" — HTTP 429, HTTP 503, timeout, custom exceptions, or any callable predicate. The throttle does not hardcode provider-specific error handling.
6. **Token-aware budgeting** — Optionally track token (or unit) consumption per time window, not just request count. The term "token" is used because the primary audience is LLM APIs (e.g., Anthropic's 10,000 output tokens/minute, OpenAI's TPM limits), but the mechanism is generic — it can track any countable resource: API credits, bytes transferred, compute units, or weighted request costs. Many APIs enforce resource-consumption limits independently of request-count limits, and a small number of expensive requests can exhaust a resource budget long before the request limit is reached.
7. **Initial concurrency** — Allow the throttle to start at a concurrency level below the maximum and organically promote via the reacceleration mechanism. This supports conservative cold-start strategies.
8. **Progress reporting** — Expose task completion progress (percentage, ETA, current concurrency, current dispatch interval) via a typed snapshot object and optional callbacks.
9. **Built-in retry with backoff** — Optionally retry failed requests inside the throttled slot, with configurable max attempts, backoff strategy (fixed, exponential, exponential+jitter), and retryable predicate. Retries happen *inside* the acquired slot so concurrency accounting stays correct. Intermediate failures trigger backoff sleep but not throttle deceleration — only the final failure (after all retries exhausted) counts as a real failure for the throttle's adaptive logic. Retry is fully optional and disabled by default.

### Operational Requirements

1. **Error propagation** — gentlify must never swallow exceptions. If a user's function raises and retries are not configured (or are exhausted), the exception propagates to the caller. gentlify only intercepts failures for its own bookkeeping (recording that a failure occurred). When retry is enabled, intermediate failures are caught and retried transparently; only the final failure propagates.
2. **Logging** — Emit structured log events for key state transitions: deceleration, reacceleration, cooling start/end, circuit breaker trips. Use Python's standard `logging` module by default; allow users to plug in their own logger.
3. **Thread safety** — All state mutations must be safe for concurrent asyncio tasks. No global mutable state — each throttle instance is independent.
4. **Graceful shutdown** — Provide a mechanism to drain in-flight requests on cancellation rather than hard-stopping.

### Quality Requirements

1. **Zero runtime dependencies** — The core library depends only on the Python standard library (`asyncio`, `time`, `random`, `logging`, `dataclasses`). Optional integrations (httpx, aiohttp, litellm) are extras.
2. **Type-complete** — Ship with `py.typed` marker. Pass `mypy --strict` with zero errors.
3. **Deterministic under test** — All sources of randomness (jitter) and time (monotonic clock) must be injectable for deterministic testing.

### Usability Requirements

1. **Context manager API** — Primary usage is `async with throttle.acquire(): ...` for fine-grained control.
2. **Decorator API** — `@throttle.wrap` decorator for async functions that automatically acquires/releases and records success/failure.
3. **Configuration from code** — All parameters settable via constructor kwargs with sensible defaults.
4. **Configuration from dict/env** — Provide a `from_dict()` / `from_env()` factory for configuration without code changes.
5. **Multiple throttle instances** — Users can create independent throttle instances for different API providers in the same process.

### Non-goals

1. **HTTP client** — gentlify is transport-agnostic. It does not make HTTP requests itself. Optional integrations provide middleware for popular HTTP clients, but the core library has no network code.
2. **Persistent state** — Throttle state is in-memory only. It does not persist across process restarts.
3. **Distributed coordination** — gentlify operates within a single process. Cross-process or cross-machine rate coordination is out of scope.
4. **Sync support (v1)** — v1 is asyncio-only. A threading-based sync adapter may be added in a future version.
5. **CLI** — gentlify is a library; it has no command-line interface.

---

## Inputs

### Required

| Input | Description | Example |
|-------|-------------|---------|
| (none) | gentlify requires no mandatory inputs at construction time; all parameters have defaults | `Throttle()` creates a usable instance |

### Optional (Constructor Parameters)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_concurrency` | `int` | `5` | Maximum concurrent in-flight requests |
| `initial_concurrency` | `int \| None` | `None` (= max) | Starting concurrency; promotes to max organically |
| `min_dispatch_interval` | `float` | `0.2` | Minimum seconds between consecutive dispatches |
| `failure_threshold` | `int` | `3` | Failures in window before deceleration triggers |
| `failure_window` | `float` | `60.0` | Sliding window (seconds) for failure counting |
| `cooling_period` | `float` | `60.0` | Seconds of zero failures before reacceleration |
| `max_dispatch_interval` | `float` | `30.0` | Upper bound on dispatch interval after deceleration |
| `jitter_fraction` | `float` | `0.5` | Jitter as fraction of dispatch interval (0.0–1.0) |
| `total_tasks` | `int` | `0` | Total expected tasks (enables progress/ETA reporting) |
| `failure_predicate` | `Callable` | `None` | Custom callable to classify exceptions as failures |
| `token_budget` | `TokenBudget \| None` | `None` | Optional token-aware rate limiting configuration |
| `safe_ceiling_decay_multiplier` | `float` | `5.0` | After this many cooling periods with zero failures, the safe ceiling resets to `max_concurrency` |
| `circuit_breaker` | `CircuitBreakerConfig \| None` | `None` | Optional circuit breaker configuration |
| `on_state_change` | `Callable \| None` | `None` | Callback invoked on deceleration, reacceleration, circuit trips |
| `on_progress` | `Callable \| None` | `None` | Callback invoked at progress milestones (default: every 10%) |
| `retry` | `RetryConfig \| None` | `None` | Optional retry configuration (max attempts, backoff, retryable predicate) |

### Runtime Inputs

| Method | Description |
|--------|-------------|
| `record_success(duration, tokens_used)` | Report a successful request; may trigger reacceleration |
| `record_failure(exception)` | Report a failed request; may trigger deceleration |
| `record_tokens(count)` | Report token consumption against the token budget |

---

## Outputs

### Snapshot (State Inspection)

```python
@dataclass(frozen=True)
class ThrottleSnapshot:
    """Point-in-time view of throttle state."""
    concurrency: int              # Current concurrency limit
    max_concurrency: int          # Configured maximum
    dispatch_interval: float      # Current dispatch interval (seconds)
    completed_tasks: int          # Tasks completed so far
    total_tasks: int              # Total expected tasks (0 = unknown)
    failure_count: int            # Failures in current window
    state: ThrottleState          # RUNNING, COOLING, CIRCUIT_OPEN, CLOSED, DRAINING
    safe_ceiling: int             # Highest safe concurrency observed
    eta_seconds: float | None     # Estimated time remaining (None if unknown)
    tokens_used: int              # Tokens consumed in current window
    tokens_remaining: int | None  # Tokens remaining in budget (None if no budget)
```

### Callbacks / Events

gentlify emits structured events for observability. Users can register a callback to receive these:

| Event | When | Payload |
|-------|------|---------|
| `decelerated` | Failure threshold exceeded | old concurrency, new concurrency, old interval, new interval, trigger count |
| `reaccelerated` | Cooling period completed with zero failures | old concurrency, new concurrency |
| `cooling_started` | Deceleration triggered, cooling timer begins | cooling_period |
| `circuit_opened` | Circuit breaker tripped | consecutive failures, reopen delay |
| `circuit_closed` | Circuit breaker re-closed after delay | — |

Progress events are delivered via the separate `on_progress` callback:

| Event | When | Payload |
|-------|------|---------|
| `progress` | Task completed at a reporting milestone (default: every 10%) | snapshot |

---

## Functional Requirements

### FR-1: Adaptive Concurrency Control

The throttle maintains a dynamic concurrency limit controlling how many requests may be in-flight simultaneously. The limit is enforced via an asyncio semaphore.

- **Deceleration:** When the number of recorded failures within a sliding time window exceeds the failure threshold, the throttle halves the concurrency limit (minimum: 1) and doubles the dispatch interval (capped at `max_dispatch_interval`). The failure counter is cleared after each deceleration to prevent cascading.
- **Reacceleration:** After a cooling period with zero failures, the throttle increases concurrency by 1 and halves the dispatch interval. It never exceeds the safe ceiling — the concurrency level at which failures were last observed.
- **Safe ceiling decay:** If no failures occur for a configurable multiple of the cooling period (default: 5×), the safe ceiling resets to `max_concurrency`, allowing full recovery from transient incidents.

### FR-2: Dispatch Interval Gating

Each call to `acquire()` enforces a minimum time gap since the last dispatch. This prevents request bursts even when multiple concurrency slots are available. The interval is dynamically adjusted by deceleration/reacceleration.

### FR-3: Stochastic Jitter

When a dispatch must wait for the interval to elapse, a random jitter of `[0, interval × jitter_fraction]` is added. This ensures that concurrent tasks waiting on the same interval don't all fire at the same instant when the interval expires.

### FR-4: Failure Signal Abstraction

By default, any exception raised within an `acquire()` context or a `@wrap`-decorated function is recorded as a failure. Users can customize this by providing a `failure_predicate` — a callable that receives the exception and returns `True` if it should count as a rate-limit failure, `False` otherwise.

This allows users to distinguish between rate-limit errors (which should trigger deceleration) and application errors (which should not).

### FR-5: Token-Aware Budgeting

When a `TokenBudget` is configured, the throttle tracks token (or unit) consumption per time window in addition to request-based concurrency control. If the token budget is exhausted, `acquire()` blocks until the window rolls over, even if concurrency slots are available.

Despite the name, `TokenBudget` is not LLM-specific. "Tokens" are simply a countable unit — they could represent LLM tokens, API credits, bytes, compute units, or any resource where the API enforces a per-window consumption cap. This addresses the common scenario where two independent limits apply simultaneously: a request-count limit (handled by concurrency + dispatch interval) and a resource-consumption limit (handled by `TokenBudget`). For example, 3 large LLM requests consuming 4,000 tokens each can exhaust a 10,000 TPM budget even though the request-count limit allows 60 requests/minute.

Configuration:

| Field | Type | Description |
|-------|------|-------------|
| `max_tokens` | `int` | Maximum tokens per window |
| `window_seconds` | `float` | Rolling window duration (e.g., 60.0 for per-minute limits) |

Token consumption is reported via `record_success(tokens_used=N)` or `record_tokens(N)`.

### FR-6: Circuit Breaker

When configured, the circuit breaker provides a hard stop after sustained failures:

- **Open:** After N consecutive failures (configurable), the circuit opens and all `acquire()` calls raise `CircuitOpenError` immediately for a configurable delay period.
- **Half-open:** After the delay, up to `half_open_max_calls` (configurable, default: 1) `acquire()` calls are allowed through as probes. If all probes succeed, the circuit closes. If any probe fails, the circuit re-opens with an extended delay.
- **Closed:** Normal operation; failures are counted but requests are allowed.

The circuit breaker is independent of the adaptive concurrency control — it provides a safety net for catastrophic failure scenarios.

### FR-7: Progress Reporting

When `total_tasks` is set, the throttle tracks completion progress and computes an ETA based on the rolling average of task durations. Progress is available via:

- `throttle.snapshot()` — returns a `ThrottleSnapshot` at any time.
- `on_progress` callback — invoked at configurable milestones (default: every 10%).

### FR-8: Context Manager API

The primary usage pattern:

```python
async with throttle.acquire() as slot:
    result = await call_api(...)
    slot.record_tokens(result.usage.total_tokens)
# Success/failure is automatically recorded based on whether
# the block raised an exception.
```

The context manager:
1. Waits for a concurrency slot (semaphore).
2. Enforces the dispatch interval with jitter.
3. Checks the token budget (if configured).
4. Checks the circuit breaker (if configured).
5. Yields control to the user's code.
6. On exit, records success or failure and updates progress.

For users who need manual control (e.g., middleware pipelines, conditional success/failure, batch operations), `record_success(duration, tokens_used)` and `record_failure(exception)` are also available as public methods on the throttle instance directly.

### FR-9: Decorator API

For simpler use cases:

```python
@throttle.wrap
async def call_api(prompt: str) -> str:
    return await client.complete(prompt)

# Each call to call_api() automatically acquires/releases
# and records success/failure.
results = await asyncio.gather(*[call_api(p) for p in prompts])
```

The decorator wraps the function with `acquire()` and records the outcome. Token reporting requires the context manager API.

### FR-10: Multiple Throttle Instances

Users can create independent throttle instances for different providers:

```python
anthropic_throttle = Throttle(max_concurrency=3, token_budget=TokenBudget(10_000, 60))
openai_throttle = Throttle(max_concurrency=10)

async with anthropic_throttle.acquire():
    ...
async with openai_throttle.acquire():
    ...
```

Each instance maintains its own state (concurrency, interval, failure history, token budget). There is no global shared state.

### FR-12: Built-in Retry

When a `RetryConfig` is provided, failed requests are automatically retried inside the acquired slot:

- **Max attempts:** Total attempts including the initial call (default: 3). Setting to 1 disables retry.
- **Backoff strategy:** `fixed` (constant delay), `exponential` (delay doubles each attempt, starting from `base_delay`), or `exponential_jitter` (exponential with random jitter added). Default: `exponential_jitter`.
- **Base delay:** Initial delay between retries in seconds (default: 1.0).
- **Max delay:** Upper bound on backoff delay (default: 60.0).
- **Retryable predicate:** Optional callable `(BaseException) -> bool` that determines whether an exception is retryable. Defaults to retrying all exceptions. If the predicate returns `False`, the exception propagates immediately without further retries.

Key design decisions:
- Retries happen **inside** the acquired slot — the concurrency slot remains held during retries, so the throttle's concurrency accounting is always correct.
- Intermediate retry failures do **not** trigger throttle deceleration. Only the final failure (after all retries are exhausted) is recorded as a failure for the throttle's adaptive logic.
- The `on_state_change` callback emits a `retry` event for each retry attempt, including the attempt number, exception, and backoff delay.
- Retry is fully composable with all other features: token budget, circuit breaker, failure predicate, etc. The circuit breaker is checked before each retry attempt — if the circuit opens during retries, `CircuitOpenError` propagates immediately.

Configuration:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_attempts` | `int` | `3` | Total attempts (including initial). Must be ≥ 1. |
| `backoff` | `str` | `"exponential_jitter"` | `"fixed"`, `"exponential"`, or `"exponential_jitter"` |
| `base_delay` | `float` | `1.0` | Initial delay between retries (seconds) |
| `max_delay` | `float` | `60.0` | Maximum backoff delay (seconds) |
| `retryable` | `Callable \| None` | `None` | Predicate to filter retryable exceptions (None = retry all) |

Usage:

```python
from gentlify import Throttle, RetryConfig

throttle = Throttle(
    max_concurrency=5,
    retry=RetryConfig(max_attempts=3, backoff="exponential_jitter"),
)

async with throttle.acquire() as slot:
    result = await call_api(item)  # retried up to 3 times on failure
```

The decorator API also supports retry — retries are handled transparently inside the `acquire()` context.

### FR-11: Graceful Shutdown

`throttle.drain()` returns an awaitable that resolves when all in-flight requests complete. This allows clean shutdown:

```python
# Signal no more new requests
throttle.close()
# Wait for in-flight requests to finish
await throttle.drain()
```

After `close()`, new `acquire()` calls raise `ThrottleClosed`. In-flight requests are allowed to complete normally.

---

## Configuration

### From Code

```python
from gentlify import Throttle, TokenBudget, CircuitBreakerConfig

throttle = Throttle(
    max_concurrency=5,
    initial_concurrency=2,
    failure_threshold=3,
    cooling_period=60.0,
    token_budget=TokenBudget(max_tokens=10_000, window_seconds=60.0),
    circuit_breaker=CircuitBreakerConfig(
        consecutive_failures=10,
        open_duration=30.0,
        half_open_max_calls=1,
    ),
)
```

### From Dict

```python
throttle = Throttle.from_dict({
    "max_concurrency": 5,
    "initial_concurrency": 2,
    "token_budget": {"max_tokens": 10_000, "window_seconds": 60.0},
})
```

### From Environment Variables

```python
# Reads GENTLIFY_MAX_CONCURRENCY, GENTLIFY_INITIAL_CONCURRENCY, etc.
throttle = Throttle.from_env(prefix="GENTLIFY")
```

| Env Var | Maps to |
|---------|---------|
| `GENTLIFY_MAX_CONCURRENCY` | `max_concurrency` |
| `GENTLIFY_INITIAL_CONCURRENCY` | `initial_concurrency` |
| `GENTLIFY_MIN_DISPATCH_INTERVAL` | `min_dispatch_interval` |
| `GENTLIFY_FAILURE_THRESHOLD` | `failure_threshold` |
| `GENTLIFY_FAILURE_WINDOW` | `failure_window` |
| `GENTLIFY_COOLING_PERIOD` | `cooling_period` |
| `GENTLIFY_TOKEN_BUDGET_MAX` | `token_budget.max_tokens` |
| `GENTLIFY_TOKEN_BUDGET_WINDOW` | `token_budget.window_seconds` |
| `GENTLIFY_MAX_DISPATCH_INTERVAL` | `max_dispatch_interval` |
| `GENTLIFY_JITTER_FRACTION` | `jitter_fraction` |
| `GENTLIFY_SAFE_CEILING_DECAY_MULTIPLIER` | `safe_ceiling_decay_multiplier` |
| `GENTLIFY_CIRCUIT_BREAKER_CONSECUTIVE_FAILURES` | `circuit_breaker.consecutive_failures` |
| `GENTLIFY_CIRCUIT_BREAKER_OPEN_DURATION` | `circuit_breaker.open_duration` |
| `GENTLIFY_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS` | `circuit_breaker.half_open_max_calls` |

---

## Testing Requirements

1. **Unit tests** — Cover all state transitions: deceleration, reacceleration, safe ceiling tracking, ceiling decay, jitter bounds, token budget exhaustion/refill, circuit breaker open/half-open/close.
2. **Concurrency tests** — Verify that the semaphore correctly limits in-flight tasks under concurrent load.
3. **Timing tests** — Verify dispatch interval enforcement and jitter distribution using injected clocks.
4. **Integration tests** — Test the decorator API, context manager API, and `from_dict` / `from_env` factories.
5. **Edge cases** — Zero total tasks, single concurrency, immediate failure on first request, failure predicate that always returns False, circuit breaker with zero delay.
6. **Minimum coverage** — 95% line coverage. The library is small and critical; near-complete coverage is expected.

---

## Security and Compliance Notes

1. **No network access** — gentlify makes no network requests. It is purely a coordination primitive.
2. **No secrets handling** — gentlify does not accept, store, or log API keys or credentials.
3. **No telemetry** — No analytics, no phone-home, no data collection of any kind.
4. **License** — Apache-2.0. All source files carry the Pointmatic copyright header.

---

## Performance Notes

1. **Overhead** — The throttle's per-request overhead should be negligible (<1 ms) for the coordination logic (semaphore acquire, timestamp comparison, jitter computation). The dominant cost is the user's actual API call.
2. **Memory** — Failure timestamps are stored in a bounded deque (window-based). Token consumption uses a sliding window with bounded storage. Memory usage is O(failure_threshold + token_window_granularity), not O(total_requests).
3. **Scalability** — Each throttle instance is independent. An application can run hundreds of throttle instances (one per API provider) without interference.
4. **Clock resolution** — Uses `time.monotonic()` for all timing. Jitter uses `random.uniform()` (not cryptographic — `random` is sufficient for dispatch staggering).

---

## Acceptance Criteria

The project is considered complete when:

1. A user can `pip install gentlify` and use `Throttle()` with zero configuration to get adaptive rate limiting for any async workload.
2. Deceleration triggers reliably when failures accumulate, and reacceleration recovers throughput after sustained success.
3. Stochastic jitter measurably spreads dispatch times (no thundering herd under concurrent load).
4. Token-aware budgeting correctly blocks when the budget is exhausted and resumes when the window rolls over.
5. The circuit breaker trips on sustained failures and recovers via the half-open probe mechanism.
6. The decorator API and context manager API both work correctly and record success/failure automatically.
7. `from_dict()` and `from_env()` produce correctly configured instances.
8. `drain()` and `close()` enable graceful shutdown without dropping in-flight requests.
9. Built-in retry with configurable backoff retries failed requests inside the slot without disrupting throttle accounting.
10. All tests pass with ≥95% coverage.
11. `mypy --strict` passes with zero errors.
12. The library has zero runtime dependencies.
13. The `py.typed` marker is present and type stubs are complete.
