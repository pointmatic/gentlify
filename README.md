# gentlify

[![CI](https://github.com/pointmatic/gentlify/actions/workflows/ci.yml/badge.svg)](https://github.com/pointmatic/gentlify/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/pointmatic/gentlify/graph/badge.svg)](https://codecov.io/gh/pointmatic/gentlify)
[![PyPI](https://img.shields.io/pypi/v/gentlify)](https://pypi.org/project/gentlify/)
[![Python](https://img.shields.io/pypi/pyversions/gentlify)](https://pypi.org/project/gentlify/)
[![License](https://img.shields.io/pypi/l/gentlify)](https://github.com/pointmatic/gentlify/blob/main/LICENSE)
[![Typed](https://img.shields.io/badge/typed-yes-blue)](https://peps.python.org/pep-0561/)

Adaptive async rate limiting for Python, closed-loop feedback control for API concurrency.

**Zero dependencies. Asyncio-native. Fully typed.**

Gentlify automatically adjusts concurrency and dispatch rate in response to failures, so your application backs off when an API is struggling and speeds up when it recovers — without manual tuning.

## Installation

```bash
pip install gentlify
```

Requires Python 3.11+.

## Quick Start

```python
import asyncio
from gentlify import Throttle

throttle = Throttle(max_concurrency=5)

async def main():
    for item in range(20):
        await throttle.execute(lambda slot: call_api(item))

asyncio.run(main())
```

If requests start failing, gentlify automatically halves concurrency, enters a cooling period, then gradually reaccelerates — all without any manual intervention.

## Execute API

`execute()` is the primary API — pass an async callable and get throttling, retry, and custom logic in one call:

```python
# Simple — just pass a callable
result = await throttle.execute(lambda slot: call_api(item))

# With custom logic — token recording, result inspection
async def my_task(slot):
    result = await call_llm(prompt)
    slot.record_tokens(result.usage.total_tokens)
    return result.text

text = await throttle.execute(my_task)
```

The callable receives a `Slot` with:
- `slot.record_tokens(count)` — report token consumption
- `slot.attempt` — zero-indexed attempt number (for idempotency keys)

## Decorator API

Wrap async functions directly — delegates to `execute()` internally:

```python
@throttle.wrap
async def call_api(item):
    return await httpx.post("/api", json=item)

# Each call is automatically throttled (with retry if configured)
await call_api(my_item)
```

The decorator preserves the function signature and return value. Failures are recorded automatically.

## Token Budget

Track and enforce token consumption within a rolling time window:

```python
from gentlify import Throttle, TokenBudget

throttle = Throttle(
    max_concurrency=10,
    token_budget=TokenBudget(max_tokens=100_000, window_seconds=60.0),
)

async def task(slot):
    result = await call_llm(prompt)
    slot.record_tokens(result.usage.total_tokens)
    return result

await throttle.execute(task)
```

When the budget is exhausted, `execute()` blocks until tokens expire from the rolling window.

## Circuit Breaker

Automatically stop sending requests when an API is down:

```python
from gentlify import Throttle, CircuitBreakerConfig

throttle = Throttle(
    max_concurrency=10,
    circuit_breaker=CircuitBreakerConfig(
        consecutive_failures=5,
        open_duration=30.0,
        half_open_max_calls=2,
    ),
)
```

After 5 consecutive failures the circuit opens, rejecting requests with `CircuitOpenError` for 30 seconds. It then enters half-open state, allowing 2 probe requests. If those succeed, the circuit closes; if they fail, it re-opens with a doubled delay (capped at 5x).

## Retry

Automatically retry failed requests with configurable backoff — no need for a separate retry library:

```python
from gentlify import Throttle, RetryConfig

throttle = Throttle(
    max_concurrency=5,
    retry=RetryConfig(
        max_attempts=3,
        backoff="exponential_jitter",
        base_delay=1.0,
        max_delay=60.0,
    ),
)

result = await throttle.execute(lambda slot: call_api(item))
```

Retries happen inside the throttled slot, so concurrency accounting stays correct. Only the final failure (after all retries are exhausted) triggers throttle deceleration — intermediate failures just trigger backoff sleep.

Backoff strategies:
- **`fixed`** — constant delay between retries
- **`exponential`** — delay doubles each attempt (`base_delay × 2^attempt`, capped at `max_delay`)
- **`exponential_jitter`** — exponential with random jitter (default, recommended)

You can also filter which exceptions are retryable:

```python
retry = RetryConfig(
    max_attempts=3,
    retryable=lambda exc: isinstance(exc, (TimeoutError, RateLimitError)),
)
```

Non-retryable exceptions propagate immediately without further attempts.

**Idempotency note:** When retry is configured, your callable may be invoked up to `max_attempts` times. Use `slot.attempt` to build idempotency keys if needed:

```python
async def safe_write(slot):
    return await post_api(item, idempotency_key=f"{item.id}-{slot.attempt}")

await throttle.execute(safe_write)
```

## Configuration

### From code

```python
throttle = Throttle(
    max_concurrency=10,
    initial_concurrency=3,
    min_dispatch_interval=0.2,
    failure_threshold=3,
    cooling_period=10.0,
    total_tasks=1000,
    on_progress=lambda snap: print(f"{snap.percentage:.0f}%"),
)
```

### From a dictionary

```python
throttle = Throttle.from_dict({
    "max_concurrency": 10,
    "token_budget": {"max_tokens": 50000, "window_seconds": 60.0},
})
```

### From environment variables

```python
# Set GENTLIFY_MAX_CONCURRENCY=10, GENTLIFY_MIN_DISPATCH_INTERVAL=0.5, etc.
throttle = Throttle.from_env()

# Or with a custom prefix:
throttle = Throttle.from_env(prefix="MYAPP")
```

## Callbacks

### State change events

```python
def on_change(event):
    print(f"[{event.kind}] {event.data}")

throttle = Throttle(
    max_concurrency=10,
    on_state_change=on_change,
)
# Prints: [decelerated] {'concurrency': (10, 5), ...}
# Prints: [reaccelerated] {'concurrency': (5, 6), ...}
```

### Progress milestones

```python
throttle = Throttle(
    max_concurrency=10,
    total_tasks=100,
    on_progress=lambda snap: print(
        f"{snap.percentage:.0f}% done, ETA {snap.eta_seconds:.0f}s"
    ),
)
```

## Advanced: Manual Control

For advanced use cases (middleware pipelines, conditional branching, batch operations), `acquire()` provides a low-level context manager. Retry does not apply — the body runs exactly once:

```python
async with throttle.acquire() as slot:
    result = await call_api(item)
    slot.record_tokens(result.usage.total_tokens)
```

For most use cases, prefer `execute()` or `@wrap`.

## Graceful Shutdown

```python
# Stop accepting new requests
throttle.close()

# Wait for in-flight requests to finish
await throttle.drain()
```

After `close()`, any new `execute()` or `acquire()` call raises `ThrottleClosed`. In-flight requests complete normally. `drain()` blocks until all in-flight requests finish.

## Snapshot

Inspect the throttle's current state at any time:

```python
snap = throttle.snapshot()
print(snap.concurrency)        # current concurrency limit
print(snap.dispatch_interval)  # current dispatch interval
print(snap.state)              # RUNNING, COOLING, CIRCUIT_OPEN, etc.
print(snap.tokens_remaining)   # remaining token budget (or None)
print(snap.eta_seconds)        # estimated time remaining (or None)
```

## Types

All public types are re-exported from the top-level package:

| Type | Description |
|------|-------------|
| `Throttle` | Main orchestrator |
| `ThrottleConfig` | Validated configuration dataclass |
| `TokenBudget` | Token budget configuration |
| `CircuitBreakerConfig` | Circuit breaker configuration |
| `RetryConfig` | Retry and backoff configuration |
| `ThrottleSnapshot` | Read-only state view |
| `ThrottleState` | Enum: `RUNNING`, `COOLING`, `CIRCUIT_OPEN`, `CLOSED`, `DRAINING` |
| `ThrottleEvent` | Structured event for state change callbacks |
| `GentlifyError` | Base exception |
| `CircuitOpenError` | Raised when circuit breaker is open |
| `ThrottleClosed` | Raised when throttle is closed |

## Development

```bash
pip install -e ".[dev]"
pytest
mypy --strict src/gentlify
ruff check src/ tests/
```

## Releasing

1. Bump the version in `src/gentlify/_version.py` and `pyproject.toml`
2. Update `CHANGELOG.md`
3. Commit and push to `main`
4. Tag the release and push:
   ```bash
   git tag v<version>
   git push --tags
   ```
5. The GitHub Action builds and publishes to PyPI automatically via trusted publishing (OIDC)

## License

Apache-2.0 — Copyright (c) 2026 Pointmatic
