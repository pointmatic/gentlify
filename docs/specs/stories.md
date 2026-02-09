# stories.md — gentlify (Python)

This document breaks the gentlify project into an ordered sequence of small, independently completable stories grouped into phases. Each story maps to modules defined in [`tech_spec.md`](tech_spec.md) and implements requirements from [`features.md`](features.md).

Stories are numbered as `<Phase>.<letter>` (e.g., A.a, A.b, B.a). Each story that introduces or modifies code carries a semver version number, bumped incrementally. Stories with no code changes (e.g., documentation-only) omit the version. Each story is suffixed with `[Planned]` initially and changed to `[Done]` when completed. Checklist items use `- [ ]` for planned and `- [x]` for completed tasks.

---

## Phase A: Foundation

### Story A.a: v0.1.0 Hello World [Done]

Minimal runnable package — proves the build toolchain works end to end.

- [x] Create `pyproject.toml` with hatchling backend, project metadata (name, version, description, license, authors, python-requires, urls)
  - [x] License: `Apache-2.0`
  - [x] Authors: `Pointmatic`
  - [x] Python requires: `>=3.11`
  - [x] Dev dependencies: `pytest`, `pytest-asyncio`, `pytest-cov`, `mypy`, `ruff`
- [x] Create `src/gentlify/__init__.py` with copyright header and `__version__` re-export
- [x] Create `src/gentlify/_version.py` with copyright header and `__version__ = "0.1.0"`
- [x] Create `src/gentlify/py.typed` (empty PEP 561 marker)
- [x] Create `README.md` with project name, one-line description, and install instructions
- [x] Create `tests/__init__.py` (empty)
- [x] Verify `docs/index.html` homepage exists with correct repository link and banner
- [x] Create `tests/test_version.py` — verify `import gentlify; assert gentlify.__version__ == "0.1.0"`
- [x] Install package in dev mode (`pip install -e ".[dev]"`)
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict src/gentlify` passes
- [x] Verify: `ruff check src/ tests/` passes

### Story A.b: v0.2.0 Types and Exceptions [Done]

Define the foundational types, enums, and exceptions used throughout the library.

- [x] Create `src/gentlify/_types.py` with copyright header
  - [x] `ThrottleState` enum: `RUNNING`, `COOLING`, `CIRCUIT_OPEN`, `CLOSED`, `DRAINING`
  - [x] `ThrottleSnapshot` frozen dataclass (all fields from tech spec)
  - [x] `ThrottleEvent` frozen dataclass (`kind`, `timestamp`, `data`)
  - [x] Type aliases: `FailurePredicate`, `StateChangeCallback`, `ProgressCallback`, `Clock`, `RandFn`
- [x] Create `src/gentlify/_exceptions.py` with copyright header
  - [x] `GentlifyError(Exception)`
  - [x] `CircuitOpenError(GentlifyError)` with `retry_after: float`
  - [x] `ThrottleClosed(GentlifyError)`
- [x] Update `src/gentlify/__init__.py` to re-export all public types and exceptions
- [x] Create `tests/test_types.py` — verify enum values, dataclass immutability, exception hierarchy
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict` passes
- [x] Bump version to `0.2.0`

### Story A.c: v0.3.0 Configuration and Validation [Done]

Configuration dataclasses with validation, `from_dict()`, and `from_env()` factories.

- [x] Create `src/gentlify/_config.py` with copyright header
  - [x] `TokenBudget` frozen dataclass
  - [x] `CircuitBreakerConfig` frozen dataclass (with `half_open_max_calls`)
  - [x] `ThrottleConfig` frozen dataclass with all fields and defaults
  - [x] `__post_init__` validation for all constraints (see tech spec)
  - [x] `from_dict()` static method — handles nested dicts for `token_budget` and `circuit_breaker`
  - [x] `from_env()` static method — reads env vars with prefix, maps to config fields
- [x] Update `src/gentlify/__init__.py` to re-export `ThrottleConfig`, `TokenBudget`, `CircuitBreakerConfig`
- [x] Create `tests/test_config.py`
  - [x] Test default construction
  - [x] Test all validation constraints (each invalid value raises `ValueError`)
  - [x] Test `from_dict()` with full config, partial config, nested dicts
  - [x] Test `from_env()` with mocked environment variables
  - [x] Test `from_env()` with missing vars (uses defaults)
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict` passes
- [x] Bump version to `0.3.0`

### Story A.d: v0.4.0 SlidingWindow [Done]

Generic sliding-window tracker — the shared primitive for failure counting and token budgeting.

- [x] Create `src/gentlify/_window.py` with copyright header
  - [x] `SlidingWindow` class with `__init__`, `record`, `total`, `count`, `clear`
  - [x] Injectable `clock` parameter
  - [x] Lazy pruning on `total()` and `count()`
- [x] Create `tests/test_window.py`
  - [x] Test record and count within window
  - [x] Test expiry — entries outside window are pruned
  - [x] Test total — sum of values within window
  - [x] Test clear — removes all entries
  - [x] Test with FakeClock — advance time and verify pruning
- [x] Create `tests/conftest.py` with `FakeClock` class and `fake_clock` fixture
  - [x] Also add `fixed_random` fixture
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict` passes
- [x] Bump version to `0.4.0`

---

## Phase B: Core Services

### Story B.a: v0.5.0 ConcurrencyController [Done]

Dynamic concurrency limit via asyncio semaphore with decelerate/reaccelerate.

- [x] Create `src/gentlify/_concurrency.py` with copyright header
  - [x] `ConcurrencyController` class
  - [x] `current_limit` and `in_flight` properties
  - [x] `acquire()` — async, waits for semaphore
  - [x] `release()` — releases semaphore
  - [x] `decelerate()` — halves limit (min 1), returns `(old, new)`
  - [x] `reaccelerate(safe_ceiling)` — increments by 1, capped at ceiling, returns `(old, new)`
  - [x] `resize(new_limit)` — sets exact limit
- [x] Create `tests/test_concurrency.py`
  - [x] Test acquire/release cycle
  - [x] Test concurrency limit enforcement (N+1th acquire blocks)
  - [x] Test decelerate halves correctly, floors at 1
  - [x] Test reaccelerate increments, respects ceiling
  - [x] Test resize to arbitrary value
  - [x] Test in_flight count accuracy under concurrent tasks
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict` passes
- [x] Bump version to `0.5.0`

### Story B.b: v0.6.0 DispatchGate [Done]

Dispatch interval enforcement with stochastic jitter.

- [x] Create `src/gentlify/_dispatch.py` with copyright header
  - [x] `DispatchGate` class with injectable `clock` and `rand_fn`
  - [x] `interval` property
  - [x] `wait()` — enforces interval + jitter, updates `last_dispatch`
  - [x] `decelerate(max_interval)` — doubles interval, capped
  - [x] `reaccelerate(min_interval)` — halves interval, floored
- [x] Create `tests/test_dispatch.py`
  - [x] Test wait enforces minimum interval (with FakeClock)
  - [x] Test jitter is within expected bounds
  - [x] Test decelerate doubles, caps at max
  - [x] Test reaccelerate halves, floors at min
  - [x] Test rapid sequential waits respect interval
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict` passes
- [x] Bump version to `0.6.0`

### Story B.c: v0.7.0 TokenBucket [Done]

Rolling-window token budget tracker.

- [x] Create `src/gentlify/_token_bucket.py` with copyright header
  - [x] `TokenBucket` class with injectable `clock`
  - [x] `consume(tokens)` — records consumption
  - [x] `tokens_used()` — current window usage
  - [x] `tokens_remaining()` — budget minus used
  - [x] `wait_for_budget(tokens)` — blocks until budget available
- [x] Create `tests/test_token_bucket.py`
  - [x] Test consume and tokens_used within window
  - [x] Test tokens_remaining calculation
  - [x] Test window rollover — old tokens expire
  - [x] Test wait_for_budget blocks and resumes (with FakeClock)
  - [x] Test budget exhaustion then refill
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict` passes
- [x] Bump version to `0.7.0`

### Story B.d: v0.8.0 CircuitBreaker [Done]

Three-state circuit breaker: closed → open → half-open → closed/open.

- [x] Create `src/gentlify/_circuit_breaker.py` with copyright header
  - [x] `CircuitBreaker` class with injectable `clock`
  - [x] `state` property
  - [x] `check()` — raises `CircuitOpenError` if open, allows probes if half-open
  - [x] `record_success()` — closes circuit if half-open threshold met
  - [x] `record_failure()` — opens circuit if consecutive threshold exceeded
  - [x] `consecutive_failures` and `half_open_successes` properties
  - [x] Delay doubling on half-open → open, capped at 5× `open_duration`
- [x] Create `tests/test_circuit_breaker.py`
  - [x] Test closed → open after N consecutive failures
  - [x] Test open → half-open after delay expires
  - [x] Test half-open → closed after `half_open_max_calls` successes
  - [x] Test half-open → open on failure (delay doubles)
  - [x] Test delay cap at 5× open_duration
  - [x] Test `check()` raises `CircuitOpenError` with correct `retry_after`
  - [x] Test success resets consecutive failure count
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict` passes
- [x] Bump version to `0.8.0`

### Story B.e: v0.9.0 ProgressTracker [Done]

Task completion tracking with ETA and milestone detection.

- [x] Create `src/gentlify/_progress.py` with copyright header
  - [x] `ProgressTracker` class with injectable `clock`
  - [x] `record_completion(duration)` — returns `True` if milestone crossed
  - [x] `completed`, `percentage`, `eta_seconds` properties
  - [x] Rolling average of last 50 durations for ETA
- [x] Create `tests/test_progress.py`
  - [x] Test completion counting
  - [x] Test percentage calculation
  - [x] Test milestone detection at 10% intervals
  - [x] Test ETA calculation with known durations
  - [x] Test zero total_tasks (percentage = 0, ETA = None)
  - [x] Test single task completion
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict` passes
- [x] Bump version to `0.9.0`

---

## Phase C: Pipeline & Orchestration

### Story C.a: v0.10.0 Slot and Throttle Core [Done]

Wire all components together into the `Throttle` orchestrator with `acquire()` context manager.

- [x] Create `src/gentlify/_slot.py` with copyright header
  - [x] `Slot` class with `record_tokens(count)` and `tokens_reported` property
- [x] Create `src/gentlify/_throttle.py` with copyright header
  - [x] `Throttle.__init__(**kwargs)` — builds `ThrottleConfig`, instantiates all sub-components
  - [x] `acquire()` async context manager — full flow (check state, circuit breaker, semaphore, dispatch gate, token budget, yield slot, handle success/failure, release)
  - [x] `_handle_success()` — circuit breaker, cooling check, ceiling decay, token recording, progress
  - [x] `_handle_failure()` — failure predicate, window record, circuit breaker, deceleration logic
  - [x] `snapshot()` — assembles `ThrottleSnapshot` from sub-components
  - [x] `record_success()`, `record_failure()`, `record_tokens()` — public manual methods
  - [x] Logging for state transitions
- [x] Update `src/gentlify/__init__.py` to re-export `Throttle`
- [x] Create `tests/test_throttle.py`
  - [x] Test basic acquire/release cycle (success path)
  - [x] Test failure recording triggers deceleration
  - [x] Test reacceleration after cooling period
  - [x] Test safe ceiling enforcement
  - [x] Test safe ceiling decay
  - [x] Test snapshot returns correct state
  - [x] Test failure_predicate filtering
  - [x] Test on_state_change callback fires on deceleration/reacceleration
  - [x] Test on_progress callback fires at milestones
  - [x] Test token budget integration (acquire blocks when exhausted)
  - [x] Test circuit breaker integration (acquire raises CircuitOpenError)
  - [x] Test multiple independent throttle instances
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict` passes
- [x] Bump version to `0.10.0`

### Story C.b: v0.11.0 Decorator API and Graceful Shutdown [Done]

Add `@throttle.wrap` decorator and `close()`/`drain()` lifecycle methods.

- [x] Add `wrap(fn)` to `Throttle` — decorator that wraps async function with `acquire()`
- [x] Add `close()` to `Throttle` — sets state to `CLOSED`, rejects new `acquire()` calls
- [x] Add `drain()` to `Throttle` — awaits until `in_flight == 0`, sets state to `DRAINING` then back to `CLOSED`
- [x] Add tests to `tests/test_throttle.py`
  - [x] Test `@wrap` decorator records success/failure automatically
  - [x] Test `@wrap` preserves function signature and return value
  - [x] Test `close()` causes `acquire()` to raise `ThrottleClosed`
  - [x] Test `drain()` waits for in-flight requests
  - [x] Test `close()` + `drain()` sequence
  - [x] Test in-flight requests complete normally after `close()`
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict` passes
- [x] Bump version to `0.11.0`

### Story C.c: v0.12.0 Factory Methods on Throttle [Done]

Add `Throttle.from_dict()` and `Throttle.from_env()` class methods.

- [x] Add `from_dict(data)` classmethod to `Throttle` — delegates to `ThrottleConfig.from_dict()`
- [x] Add `from_env(prefix)` classmethod to `Throttle` — delegates to `ThrottleConfig.from_env()`
- [x] Add tests to `tests/test_config.py`
  - [x] Test `Throttle.from_dict()` produces working instance
  - [x] Test `Throttle.from_env()` produces working instance
  - [x] Test round-trip: config → dict → Throttle works
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict` passes
- [x] Bump version to `0.12.0`

---

## Phase D: Testing & Quality

### Story D.a: v0.13.0 Edge Case Tests [Done]

Dedicated edge case and stress tests.

- [x] Create `tests/test_edge_cases.py`
  - [x] Zero `total_tasks` — progress reports no ETA
  - [x] `max_concurrency=1` — deceleration stays at 1
  - [x] Immediate failure on first request — deceleration triggers correctly
  - [x] `failure_predicate` always returns `False` — no deceleration ever
  - [x] Circuit breaker with `open_duration=0` — immediately transitions to half-open
  - [x] Token budget of 1 — every request waits for window rollover
  - [x] Concurrent `drain()` + `acquire()` — drain completes, acquire raises
  - [x] `initial_concurrency=1`, `max_concurrency=10` — organic promotion via reacceleration
  - [x] Rapid successive failures — deceleration cascading prevention (counter cleared)
  - [x] `jitter_fraction=0.0` — no jitter, deterministic dispatch timing
- [x] Verify: `pytest` passes
- [x] Verify: `mypy --strict` passes
- [x] Bump version to `0.13.0`

### Story D.b: v0.14.0 Coverage and Type Checking Polish [Done]

Achieve ≥95% coverage and zero mypy errors.

- [x] Run `pytest --cov=gentlify --cov-report=term-missing` and identify uncovered lines
- [x] Add tests to cover any gaps
- [x] Run `mypy --strict src/gentlify` and fix any errors
- [x] Run `ruff check src/ tests/` and fix any issues
- [x] Run `ruff format --check src/ tests/` and fix any formatting issues
- [x] Verify: coverage ≥ 95% (achieved 99%)
- [x] Verify: `mypy --strict` passes with zero errors
- [x] Verify: `ruff` passes with zero issues
- [x] Bump version to `0.14.0`

---

## Phase E: Documentation & Release

### Story E.a: v1.0.0 README and Release Polish [Done]

Complete documentation and prepare for PyPI release.

- [x] Write full `README.md`
  - [x] Project description and motivation
  - [x] Installation (`pip install gentlify`)
  - [x] Quick start example (minimal usage)
  - [x] Context manager API example
  - [x] Decorator API example
  - [x] Token budget example
  - [x] Circuit breaker example
  - [x] Configuration (code, dict, env vars)
  - [x] Graceful shutdown example
  - [x] API reference summary (link to types)
  - [x] License
- [x] Verify all copyright headers present on every source file
- [x] Verify `py.typed` marker is present
- [x] Verify `pyproject.toml` has correct metadata (description, classifiers, urls, keywords)
- [x] Add PyPI classifiers: `Framework :: AsyncIO`, `Typing :: Typed`, `License :: OSI Approved :: Apache Software License`, etc.
- [x] Final full test run: `pytest --cov=gentlify` (195 passed, 99% coverage)
- [x] Final `mypy --strict src/gentlify` (zero errors)
- [x] Final `ruff check src/ tests/` (all passed)
- [x] Bump version to `1.0.0`

### Story E.b: CHANGELOG [Done]

Create a changelog summarizing all changes.

- [x] Create `CHANGELOG.md` with entries for v0.1.0 through v1.0.0
- [x] Follow Keep a Changelog format

---

## Phase F: CI/CD & Automation

### Story F.a: v1.1.0 GitHub Actions CI [Done]

Set up continuous integration with GitHub Actions.

- [x] Create `.github/workflows/ci.yml`
  - [x] Trigger on push to `main` and on pull requests
  - [x] Matrix: Python 3.11, 3.12, 3.13, 3.14
  - [x] Steps: checkout, setup-python, install dev deps, `ruff check`, `ruff format --check`, `mypy --strict src/gentlify`, `pytest --cov=gentlify`
  - [x] Upload coverage report as artifact
- [x] Add CI status badge to `README.md`
- [x] Add coverage badge to `README.md`
- [x] Add license badge to `README.md`
- [x] Add typed badge to `README.md`
- [x] Verify: push to repo triggers workflow and passes

### Story F.b: v1.2.0 Dynamic Coverage Badge [Done]

Add a dynamic code coverage badge using Codecov or Coveralls.

- [x] Choose coverage service (Codecov recommended for open-source)
- [x] Add `codecov` upload step to `.github/workflows/ci.yml`
  - [x] Generate coverage XML: `pytest --cov=gentlify --cov-report=xml`
  - [x] Upload via `codecov/codecov-action@v4`
- [x] Add coverage badge to `README.md` (e.g. `[![codecov](https://codecov.io/gh/<org>/<repo>/...)]`)
- [x] Verify: coverage report appears on Codecov dashboard after push

### Story F.c: v1.3.0 Release Automation [Done]

Automate PyPI publishing on tagged releases.

- [x] Create `.github/workflows/publish.yml`
  - [x] Trigger on push of version tags (`v*`)
  - [x] Steps: checkout, setup-python, build (`python -m build`), publish to PyPI via `pypa/gh-action-pypi-publish@release/v1`
  - [x] Use trusted publishing (OIDC) — no API token needed
- [x] Add `build` to dev dependencies in `pyproject.toml`
- [x] Document release process in `README.md`
  - [x] Bump version in `_version.py` and `pyproject.toml`
  - [x] Tag: `git tag v<version> && git push --tags`
  - [x] GitHub Action builds and publishes automatically
- [x] Verify: tag push triggers publish workflow

---

## Phase G: Built-in Retry

### Story G.a: v1.4.0 RetryConfig and RetryHandler [Done]

Add retry configuration and backoff computation.

- [x] Add `RetryConfig` dataclass to `_config.py`
  - [x] Fields: `max_attempts`, `backoff`, `base_delay`, `max_delay`, `retryable`
  - [x] Validation in `__post_init__()`: `max_attempts >= 1`, `backoff` in valid set, `base_delay >= 0`, `max_delay >= base_delay`
  - [x] Add `retry` field to `ThrottleConfig`
  - [x] Support `retry` in `from_dict()` and `from_env()`
- [x] Create `_retry.py` with `RetryHandler`
  - [x] `compute_delay(attempt)` — fixed, exponential, exponential_jitter strategies
  - [x] `is_retryable(exc)` — delegates to predicate or returns True
  - [x] `max_attempts` property
  - [x] Injectable `clock` and `rand_fn` for deterministic testing
- [x] Export `RetryConfig` from `__init__.py` and add to `__all__`
- [x] Create `tests/test_retry.py`
  - [x] Test all three backoff strategies with deterministic rand_fn
  - [x] Test retryable predicate (custom and default)
  - [x] Test validation (invalid max_attempts, invalid backoff, invalid delays)
  - [x] Test delay capping at max_delay
- [x] Verify: `pytest`, `mypy --strict`, `ruff check` all pass
- [x] Bump version to `1.4.0`

### Story G.b: v1.5.0 Throttle Retry Integration [Done]

Wire retry into the Throttle's `acquire()` and `wrap()` flows.

- [x] Update `_throttle.py`
  - [x] Create `RetryHandler` from config if `retry` is set
  - [x] In `wrap()`: retry the wrapped function call on failure
    - [x] Check `is_retryable()` before each retry
    - [x] Sleep `compute_delay(attempt)` between retries
    - [x] Check circuit breaker before each retry attempt
    - [x] Emit `retry` event via `on_state_change`
    - [x] Only record final failure for throttle deceleration
  - [x] Context manager `acquire()`: document that retry applies to `wrap()` only (context manager body cannot be re-entered)
- [x] Add retry integration tests to `tests/test_throttle.py`
  - [x] `wrap()` retries on failure and succeeds on second attempt
  - [x] `wrap()` exhausts retries and records final failure
  - [x] Retry respects `retryable` predicate (non-retryable propagates immediately)
  - [x] Retry emits `retry` events via `on_state_change`
  - [x] Retry + circuit breaker: circuit opens during retry, `CircuitOpenError` propagates
  - [x] Retry with `max_attempts=1` behaves like no retry
  - [x] Intermediate retry failures do not trigger deceleration
- [x] Add retry edge cases to `tests/test_edge_cases.py`
- [x] Verify: `pytest`, `mypy --strict`, `ruff check` all pass
- [x] Bump version to `1.5.0`

### Story G.c: v1.6.0 Retry Documentation and Polish [Done]

Update all documentation for the retry feature.

- [x] Update `README.md` with retry section and examples
- [x] Update `CHANGELOG.md` with retry entries
- [x] Final full test run: `pytest --cov=gentlify`
- [x] Final `mypy --strict src/gentlify`
- [x] Final `ruff check src/ tests/`
- [x] Bump version to `1.6.0`

### Story G.d: v1.6.1 Formatting Bugfix [Done]

Fix `ruff format --check` CI failures introduced in Phase G.

- [x] Run `ruff format` on `_config.py`, `_throttle.py`, `test_retry.py`
- [x] Verify: `ruff format --check`, `ruff check`, `mypy --strict`, `pytest` all pass
- [x] Bump version to `1.6.1`

### Story G.e: v1.6.2 Minor Description Polish [Done]

Improve descriptions to be more concise and clear.

- [x] Update `README.md`
- [x] Update `docs/index.html`
- [x] Update `docs/specs/descriptions.md`
- [x] Update `docs/specs/features.md`
- [x] Update `pyproject.toml`
- [x] Verify: `pytest`, `mypy --strict`, `ruff check` all pass
- [x] Bump version to `1.6.2`

---

## Phase H: Unified Execute API (v2.0.0)

**Motivation:** In v1.x, the library offers two distinct patterns — `acquire()` (white-box context manager with full control but no retry) and `wrap()` (black-box decorator with retry but no custom logic). This forces developers to choose between retry and customization. Phase H introduces `throttle.execute(fn)` as the **primary API** — a single pattern that provides retry, throttling, and custom logic (token recording, result inspection, conditional branching) in one call. `acquire()` remains as an advanced escape hatch; `wrap()` becomes thin sugar over `execute()`.

**Breaking changes (v1.x → v2.0.0):**
- `execute()` becomes the recommended primary API (new method, not a rename)
- `wrap()` internals refactored to delegate to `execute()` (behavior unchanged, but internal implementation changes)
- `_call_with_retry()` removed as a private method (replaced by `execute()` logic)
- README restructured: Quick Start leads with `execute()`, `acquire()` moved to Advanced section
- No removed public APIs — `acquire()` and `wrap()` continue to work as before

### Story H.a: v2.0.0-alpha.1 Execute Method and Slot Callback [Done]

Add `throttle.execute(fn)` — the unified API that runs a user-provided async callable inside a throttled slot with retry.

- [x] Update `features.md`
  - [x] Add FR-13: Unified Execute API
    - [x] `execute(fn)` accepts an async callable `fn(slot) -> T`
    - [x] The callable receives a `Slot` instance for token recording and metadata
    - [x] Retry applies automatically if `RetryConfig` is configured
    - [x] The callable may be invoked up to `max_attempts` times on retryable failures
    - [x] Document idempotency responsibility: "Your callable may run multiple times. Ensure your operation is safe to retry."
  - [x] Update FR-8 (Context Manager API) to position `acquire()` as the advanced/escape-hatch API
  - [x] Update FR-9 (Decorator API) to note that `wrap()` delegates to `execute()` internally
  - [x] Update FR-12 (Built-in Retry) to note retry works with all three APIs: `execute()`, `wrap()`, and manual loops around `acquire()`
- [x] Update `tech_spec.md`
  - [x] Add `execute()` method signature: `async def execute(self, fn: Callable[[Slot], Awaitable[T]]) -> T`
  - [x] Document internal flow: acquire slot → call fn(slot) with retry loop → handle success/failure → release slot
  - [x] Update `wrap()` to show it delegates to `execute()`
  - [x] Add `attempt` attribute to `Slot` (zero-indexed, so developers can build idempotency keys)
- [x] Update `_slot.py`
  - [x] Add `attempt: int` property to `Slot` (default 0, set by retry loop)
  - [x] Add `_set_attempt(n)` internal method (not public API)
- [x] Update `_throttle.py`
  - [x] Add `execute(fn)` public method
    - [x] Acquires slot via internal `acquire()` flow (state check, circuit breaker, concurrency, dispatch, token budget)
    - [x] Calls `fn(slot)` inside retry loop (reuses `RetryHandler` logic)
    - [x] Sets `slot.attempt` before each invocation
    - [x] On success: records success, releases concurrency
    - [x] On final failure: records failure (triggers deceleration), releases concurrency
    - [x] Intermediate failures: notify circuit breaker, emit retry event, backoff sleep
  - [x] Refactor `wrap()` to delegate to `execute()`:
    ```python
    def wrap(self, fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await self.execute(lambda slot: fn(*args, **kwargs))
        return wrapper
    ```
  - [x] Remove `_call_with_retry()` (logic absorbed into `execute()`)
  - [x] Update `acquire()` docstring: "Low-level API for advanced use cases. For most users, prefer `execute()` or `@wrap`."
- [x] Export any new public types from `__init__.py` if needed
- [x] Verify: `pytest`, `mypy --strict`, `ruff check`, `ruff format --check` all pass

### Story H.b: v2.0.0-alpha.2 Execute Tests [Done]

Comprehensive tests for the `execute()` API.

- [x] Add `tests/test_execute.py`
  - [x] **Basic flow:** `execute(fn)` calls fn, returns result, records success
  - [x] **Token recording:** fn calls `slot.record_tokens()`, tokens are tracked
  - [x] **Failure recording:** fn raises, exception propagates, failure recorded
  - [x] **Retry succeeds:** fn fails then succeeds, retry transparent to caller
  - [x] **Retry exhausted:** fn fails all attempts, final exception propagates, single deceleration
  - [x] **Retry with slot.attempt:** verify `slot.attempt` increments on each retry
  - [x] **Retryable predicate:** non-retryable exception propagates immediately
  - [x] **Retry events:** `on_state_change` receives `retry` events with attempt info
  - [x] **Circuit breaker interaction:** circuit opens during retry, `CircuitOpenError` propagates
  - [x] **No retry configured:** `execute()` calls fn exactly once, no retry
  - [x] **Custom logic in callback:** fn inspects result, conditionally records tokens, returns transformed value
  - [x] **Concurrent execute calls:** multiple `execute()` calls respect concurrency limits
  - [x] **Execute with closed throttle:** raises `ThrottleClosed`
  - [x] **Execute with token budget:** blocks when budget exhausted
- [x] Update existing `wrap()` tests to verify `wrap()` still works identically (regression)
- [x] Add edge cases to `tests/test_edge_cases.py`
  - [x] `execute()` with `max_attempts=1` — no retry, single call
  - [x] `execute()` callback raises non-Exception BaseException (e.g., `KeyboardInterrupt`) — propagates immediately
  - [x] `execute()` with both retry and failure_predicate — interactions are correct
- [x] Verify: `pytest`, `mypy --strict`, `ruff check`, `ruff format --check` all pass
- [x] Verify: coverage ≥ 95%

### Story H.c: v2.0.0-rc.1 Documentation Overhaul [Done]

Restructure all documentation to lead with `execute()` as the primary API.

- [x] Rewrite `README.md`
  - [x] Quick Start: lead with `execute()` example (simple black-box call)
  - [x] Second example: `execute()` with custom logic (token recording, result inspection)
  - [x] Decorator API section: show `@wrap` as sugar, note it delegates to `execute()`
  - [x] Context Manager section: reposition as "Advanced: Manual Control" for custom orchestration
  - [x] Retry section: show retry working with `execute()` (primary) and note it also works with `wrap()`
  - [x] Add "Idempotency" note: "Your callback may run multiple times when retry is configured. Use `slot.attempt` for idempotency keys if needed."
  - [x] Update Types table: add `slot.attempt` description
- [x] Update `docs/index.html`
  - [x] Update Quick Start code example to use `execute()`
- [x] Update `docs/specs/descriptions.md`
  - [x] Update feature card descriptions if needed (no changes needed — cards are feature-level)
- [x] Update `CHANGELOG.md`
  - [x] Add v2.0.0 entry documenting the new `execute()` API and README restructure
  - [x] Note: no removed APIs, `acquire()` and `wrap()` still work
- [x] Verify: `pytest`, `mypy --strict`, `ruff check`, `ruff format --check` all pass

### Story H.d: v2.0.0 Final Release [Planned]

Final verification and version bump.

- [ ] Final full test run: `pytest --cov=gentlify`
- [ ] Final `mypy --strict src/gentlify`
- [ ] Final `ruff check src/ tests/` and `ruff format --check src/ tests/`
- [ ] Verify: coverage ≥ 95%
- [ ] Bump version to `2.0.0` in `_version.py`, `pyproject.toml`, `tests/test_version.py`
- [ ] Mark all Phase H stories as `[Done]`