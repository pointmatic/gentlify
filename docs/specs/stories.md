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

### Story B.b: v0.6.0 DispatchGate [Planned]

Dispatch interval enforcement with stochastic jitter.

- [ ] Create `src/gentlify/_dispatch.py` with copyright header
  - [ ] `DispatchGate` class with injectable `clock` and `rand_fn`
  - [ ] `interval` property
  - [ ] `wait()` — enforces interval + jitter, updates `last_dispatch`
  - [ ] `decelerate(max_interval)` — doubles interval, capped
  - [ ] `reaccelerate(min_interval)` — halves interval, floored
- [ ] Create `tests/test_dispatch.py`
  - [ ] Test wait enforces minimum interval (with FakeClock)
  - [ ] Test jitter is within expected bounds
  - [ ] Test decelerate doubles, caps at max
  - [ ] Test reaccelerate halves, floors at min
  - [ ] Test rapid sequential waits respect interval
- [ ] Verify: `pytest` passes
- [ ] Verify: `mypy --strict` passes
- [ ] Bump version to `0.6.0`

### Story B.c: v0.7.0 TokenBucket [Planned]

Rolling-window token budget tracker.

- [ ] Create `src/gentlify/_token_bucket.py` with copyright header
  - [ ] `TokenBucket` class with injectable `clock`
  - [ ] `consume(tokens)` — records consumption
  - [ ] `tokens_used()` — current window usage
  - [ ] `tokens_remaining()` — budget minus used
  - [ ] `wait_for_budget(tokens)` — blocks until budget available
- [ ] Create `tests/test_token_bucket.py`
  - [ ] Test consume and tokens_used within window
  - [ ] Test tokens_remaining calculation
  - [ ] Test window rollover — old tokens expire
  - [ ] Test wait_for_budget blocks and resumes (with FakeClock)
  - [ ] Test budget exhaustion then refill
- [ ] Verify: `pytest` passes
- [ ] Verify: `mypy --strict` passes
- [ ] Bump version to `0.7.0`

### Story B.d: v0.8.0 CircuitBreaker [Planned]

Three-state circuit breaker: closed → open → half-open → closed/open.

- [ ] Create `src/gentlify/_circuit_breaker.py` with copyright header
  - [ ] `CircuitBreaker` class with injectable `clock`
  - [ ] `state` property
  - [ ] `check()` — raises `CircuitOpenError` if open, allows probes if half-open
  - [ ] `record_success()` — closes circuit if half-open threshold met
  - [ ] `record_failure()` — opens circuit if consecutive threshold exceeded
  - [ ] `consecutive_failures` and `half_open_successes` properties
  - [ ] Delay doubling on half-open → open, capped at 5× `open_duration`
- [ ] Create `tests/test_circuit_breaker.py`
  - [ ] Test closed → open after N consecutive failures
  - [ ] Test open → half-open after delay expires
  - [ ] Test half-open → closed after `half_open_max_calls` successes
  - [ ] Test half-open → open on failure (delay doubles)
  - [ ] Test delay cap at 5× open_duration
  - [ ] Test `check()` raises `CircuitOpenError` with correct `retry_after`
  - [ ] Test success resets consecutive failure count
- [ ] Verify: `pytest` passes
- [ ] Verify: `mypy --strict` passes
- [ ] Bump version to `0.8.0`

### Story B.e: v0.9.0 ProgressTracker [Planned]

Task completion tracking with ETA and milestone detection.

- [ ] Create `src/gentlify/_progress.py` with copyright header
  - [ ] `ProgressTracker` class with injectable `clock`
  - [ ] `record_completion(duration)` — returns `True` if milestone crossed
  - [ ] `completed`, `percentage`, `eta_seconds` properties
  - [ ] Rolling average of last 50 durations for ETA
- [ ] Create `tests/test_progress.py`
  - [ ] Test completion counting
  - [ ] Test percentage calculation
  - [ ] Test milestone detection at 10% intervals
  - [ ] Test ETA calculation with known durations
  - [ ] Test zero total_tasks (percentage = 0, ETA = None)
  - [ ] Test single task completion
- [ ] Verify: `pytest` passes
- [ ] Verify: `mypy --strict` passes
- [ ] Bump version to `0.9.0`

---

## Phase C: Pipeline & Orchestration

### Story C.a: v0.10.0 Slot and Throttle Core [Planned]

Wire all components together into the `Throttle` orchestrator with `acquire()` context manager.

- [ ] Create `src/gentlify/_slot.py` with copyright header
  - [ ] `Slot` class with `record_tokens(count)` and `tokens_reported` property
- [ ] Create `src/gentlify/_throttle.py` with copyright header
  - [ ] `Throttle.__init__(**kwargs)` — builds `ThrottleConfig`, instantiates all sub-components
  - [ ] `acquire()` async context manager — full flow (check state, circuit breaker, semaphore, dispatch gate, token budget, yield slot, handle success/failure, release)
  - [ ] `_handle_success()` — circuit breaker, cooling check, ceiling decay, token recording, progress
  - [ ] `_handle_failure()` — failure predicate, window record, circuit breaker, deceleration logic
  - [ ] `snapshot()` — assembles `ThrottleSnapshot` from sub-components
  - [ ] `record_success()`, `record_failure()`, `record_tokens()` — public manual methods
  - [ ] Logging for state transitions
- [ ] Update `src/gentlify/__init__.py` to re-export `Throttle`
- [ ] Create `tests/test_throttle.py`
  - [ ] Test basic acquire/release cycle (success path)
  - [ ] Test failure recording triggers deceleration
  - [ ] Test reacceleration after cooling period
  - [ ] Test safe ceiling enforcement
  - [ ] Test safe ceiling decay
  - [ ] Test snapshot returns correct state
  - [ ] Test failure_predicate filtering
  - [ ] Test on_state_change callback fires on deceleration/reacceleration
  - [ ] Test on_progress callback fires at milestones
  - [ ] Test token budget integration (acquire blocks when exhausted)
  - [ ] Test circuit breaker integration (acquire raises CircuitOpenError)
  - [ ] Test multiple independent throttle instances
- [ ] Verify: `pytest` passes
- [ ] Verify: `mypy --strict` passes
- [ ] Bump version to `0.10.0`

### Story C.b: v0.11.0 Decorator API and Graceful Shutdown [Planned]

Add `@throttle.wrap` decorator and `close()`/`drain()` lifecycle methods.

- [ ] Add `wrap(fn)` to `Throttle` — decorator that wraps async function with `acquire()`
- [ ] Add `close()` to `Throttle` — sets state to `CLOSED`, rejects new `acquire()` calls
- [ ] Add `drain()` to `Throttle` — awaits until `in_flight == 0`, sets state to `DRAINING` then back to `CLOSED`
- [ ] Add tests to `tests/test_throttle.py`
  - [ ] Test `@wrap` decorator records success/failure automatically
  - [ ] Test `@wrap` preserves function signature and return value
  - [ ] Test `close()` causes `acquire()` to raise `ThrottleClosed`
  - [ ] Test `drain()` waits for in-flight requests
  - [ ] Test `close()` + `drain()` sequence
  - [ ] Test in-flight requests complete normally after `close()`
- [ ] Verify: `pytest` passes
- [ ] Verify: `mypy --strict` passes
- [ ] Bump version to `0.11.0`

### Story C.c: v0.12.0 Factory Methods on Throttle [Planned]

Add `Throttle.from_dict()` and `Throttle.from_env()` class methods.

- [ ] Add `from_dict(data)` classmethod to `Throttle` — delegates to `ThrottleConfig.from_dict()`
- [ ] Add `from_env(prefix)` classmethod to `Throttle` — delegates to `ThrottleConfig.from_env()`
- [ ] Add tests to `tests/test_config.py`
  - [ ] Test `Throttle.from_dict()` produces working instance
  - [ ] Test `Throttle.from_env()` produces working instance
  - [ ] Test round-trip: config → dict → Throttle works
- [ ] Verify: `pytest` passes
- [ ] Verify: `mypy --strict` passes
- [ ] Bump version to `0.12.0`

---

## Phase D: Testing & Quality

### Story D.a: v0.13.0 Edge Case Tests [Planned]

Dedicated edge case and stress tests.

- [ ] Create `tests/test_edge_cases.py`
  - [ ] Zero `total_tasks` — progress reports no ETA
  - [ ] `max_concurrency=1` — deceleration stays at 1
  - [ ] Immediate failure on first request — deceleration triggers correctly
  - [ ] `failure_predicate` always returns `False` — no deceleration ever
  - [ ] Circuit breaker with `open_duration=0` — immediately transitions to half-open
  - [ ] Token budget of 1 — every request waits for window rollover
  - [ ] Concurrent `drain()` + `acquire()` — drain completes, acquire raises
  - [ ] `initial_concurrency=1`, `max_concurrency=10` — organic promotion via reacceleration
  - [ ] Rapid successive failures — deceleration cascading prevention (counter cleared)
  - [ ] `jitter_fraction=0.0` — no jitter, deterministic dispatch timing
- [ ] Verify: `pytest` passes
- [ ] Verify: `mypy --strict` passes
- [ ] Bump version to `0.13.0`

### Story D.b: v0.14.0 Coverage and Type Checking Polish [Planned]

Achieve ≥95% coverage and zero mypy errors.

- [ ] Run `pytest --cov=gentlify --cov-report=term-missing` and identify uncovered lines
- [ ] Add tests to cover any gaps
- [ ] Run `mypy --strict src/gentlify` and fix any errors
- [ ] Run `ruff check src/ tests/` and fix any issues
- [ ] Run `ruff format --check src/ tests/` and fix any formatting issues
- [ ] Verify: coverage ≥ 95%
- [ ] Verify: `mypy --strict` passes with zero errors
- [ ] Verify: `ruff` passes with zero issues
- [ ] Bump version to `0.14.0`

---

## Phase E: Documentation & Release

### Story E.a: v1.0.0 README and Release Polish [Planned]

Complete documentation and prepare for PyPI release.

- [ ] Write full `README.md`
  - [ ] Project description and motivation
  - [ ] Installation (`pip install gentlify`)
  - [ ] Quick start example (minimal usage)
  - [ ] Context manager API example
  - [ ] Decorator API example
  - [ ] Token budget example
  - [ ] Circuit breaker example
  - [ ] Configuration (code, dict, env vars)
  - [ ] Graceful shutdown example
  - [ ] API reference summary (link to types)
  - [ ] License
- [ ] Verify all copyright headers present on every source file
- [ ] Verify `py.typed` marker is present
- [ ] Verify `pyproject.toml` has correct metadata (description, classifiers, urls, keywords)
- [ ] Add PyPI classifiers: `Framework :: AsyncIO`, `Typing :: Typed`, `License :: OSI Approved :: Apache Software License`, etc.
- [ ] Final full test run: `pytest --cov=gentlify`
- [ ] Final `mypy --strict src/gentlify`
- [ ] Final `ruff check src/ tests/`
- [ ] Bump version to `1.0.0`

### Story E.b: CHANGELOG [Planned]

Create a changelog summarizing all changes.

- [ ] Create `CHANGELOG.md` with entries for v0.1.0 through v1.0.0
- [ ] Follow Keep a Changelog format
