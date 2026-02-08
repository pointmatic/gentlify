# design_decisions.md — gentlify (Python)

This document captures design decisions, rationale, and context that informed `features.md` and `tech_spec.md` but don't belong in either. It serves as a reference for future contributors (and future LLM sessions) to understand *why* things are the way they are.

---

## Python Version

- **Target:** Python 3.11+. **Developed on:** 3.14.3.
- **Rationale:** 3.11 introduced `TaskGroup` and `ExceptionGroup`, which are useful for concurrent workloads. Supporting 3.11+ covers the vast majority of active Python developers while still allowing modern stdlib features. No 3.12+ or 3.14+ features are required by the design.

## Build Backend

- **Choice:** `hatchling` with PEP 621 `pyproject.toml`.
- **Alternatives considered:** `setuptools`, `flit`.
- **Rationale:** `hatchling` is lightweight, has good defaults for src-layout projects, and requires minimal configuration. `setuptools` carries legacy baggage; `flit` is simpler but less flexible for extras/optional deps if needed later.

## Package Layout

- **Choice:** `src/gentlify/` layout with all internal modules prefixed by `_`.
- **Rationale:** The `src/` layout prevents accidental imports of the local package during development (a common pitfall with flat layouts). Leading underscores on internal modules make the public/private boundary explicit — the public API is defined entirely in `__init__.py`.

## Separate `on_state_change` and `on_progress` Callbacks

- **Choice:** Two separate callbacks instead of a single overloaded one.
- **Rationale:** Overloading a single callback forces users who only care about progress to filter out state-change events (and vice versa). Separate callbacks are cleaner — users subscribe only to what they need. There is no practical advantage to a single callback.

## `record_success` / `record_failure` as Public API

- **Choice:** These methods are public on the `Throttle` instance, in addition to automatic recording via the context manager.
- **Rationale:** Several common patterns require manual control:
  - **Middleware pipelines** — gentlify is integrated into an existing request pipeline where `acquire()`/`release()` are called at different layers.
  - **Conditional success/failure** — the HTTP request succeeds (no exception) but the response body indicates a logical failure the user wants to count as a rate-limit signal.
  - **Batch operations** — a single `acquire()` covers multiple sub-requests, and the user wants to record each individually.

## `ThrottleState` Enum Values

- **Choice:** `RUNNING`, `COOLING`, `CIRCUIT_OPEN`, `CLOSED`, `DRAINING`.
- **Rationale:** `CLOSED` and `DRAINING` were added beyond the original three to accurately represent the shutdown lifecycle. After `throttle.close()`, the state is `CLOSED` (no new requests accepted). After `close()` with in-flight requests still running, the state is `DRAINING` until `drain()` completes. This gives users and observability tools a clear picture of the throttle's lifecycle phase.

## Circuit Breaker `half_open_max_calls`

- **Choice:** Configurable number of probe requests in half-open state (default: 1).
- **Rationale:** A single probe is the simplest model, but some APIs recover gradually — allowing N probes before deciding gives more confidence that the service is truly healthy. Default of 1 keeps the simple case simple.

## Circuit Breaker Delay Cap

- **Choice:** When half-open → open re-triggers, the delay doubles, capped at 5× the original `open_duration`.
- **Rationale:** Prevents unbounded exponential backoff. 5× is a reasonable ceiling — e.g., if `open_duration` is 30s, the max delay is 150s (2.5 minutes). This avoids scenarios where a flapping service causes the circuit to stay open for hours.

## Safe Ceiling Decay

- **Choice:** `safe_ceiling_decay_multiplier` (default: 5.0) — after `cooling_period × multiplier` seconds with zero failures, the safe ceiling resets to `max_concurrency`.
- **Rationale:** Without decay, a single transient failure permanently caps concurrency below max. The multiplier provides a conservative recovery path — 5× the cooling period (default: 5 minutes) is long enough to be confident the incident is over, short enough to recover within a reasonable timeframe.

## Semaphore Resize Strategy

- **Decision deferred to implementation.** Two approaches:
  1. **Rebuild:** Create a new semaphore with the new limit, drain pending waiters from the old one.
  2. **Counter-based:** Track permits manually and adjust the semaphore's internal counter.
- **Rationale for deferral:** Both approaches are valid. The rebuild approach is simpler to reason about; the counter approach avoids waking/re-queuing waiters. The right choice depends on implementation details that are easier to evaluate with code in hand.

## ETA Rolling Window

- **Choice:** Rolling average of the last 50 task durations.
- **Rationale:** 50 is large enough to smooth out variance from individual slow/fast requests, small enough to be responsive to changing conditions (e.g., if the API slows down). The window size is an internal constant, not user-configurable — it's an implementation detail that doesn't need to be part of the public API.

## Atomic State Transitions (No Locks)

- **Choice:** State machine transitions (decelerate, reaccelerate, circuit breaker) are performed without explicit locks.
- **Rationale:** asyncio is single-threaded cooperative multitasking. As long as there is no `await` between the read-check-write steps of a state transition, consistency is guaranteed. The only lock-like primitive is the semaphore in `ConcurrencyController`, which is inherently safe. This avoids the complexity and potential deadlocks of explicit locking.

## Error Propagation Philosophy

- **Choice:** gentlify **never** catches and suppresses user exceptions. `try/finally` pattern only.
- **Rationale:** Rate limiters that swallow exceptions are a debugging nightmare. gentlify's job is coordination, not error handling. The exception is intercepted solely for bookkeeping (recording that a failure occurred), then immediately re-raised. Users pair gentlify with retry libraries (e.g., `tenacity`) for retry logic.

## Deterministic Testing via Injection

- **Choice:** All time-sensitive components accept `clock` and `rand_fn` parameters.
- **Rationale:** Tests that depend on `time.monotonic()` and `random.uniform()` are inherently flaky. By injecting a `FakeClock` and a deterministic random function, tests are fast, repeatable, and can simulate arbitrary time progressions without `asyncio.sleep()`. This is a standard pattern for testing async coordination primitives.

## Linting and Formatting

- **Choice:** `ruff` for both linting and formatting.
- **Rationale:** Single tool for both concerns, fast (Rust-based), compatible with `mypy --strict`. Replaces the need for `black`, `isort`, `flake8`, and `pylint` with a single dependency.
