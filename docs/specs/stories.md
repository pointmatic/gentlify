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
- [ ] Verify: coverage report appears on Codecov dashboard after push

### Story F.c: v1.3.0 Release Automation [Planned]

Automate PyPI publishing on tagged releases.

- [ ] Create `.github/workflows/publish.yml`
  - [ ] Trigger on push of version tags (`v*`)
  - [ ] Steps: checkout, setup-python, build (`python -m build`), publish to PyPI via `pypa/gh-action-pypi-publish@release/v1`
  - [ ] Use trusted publishing (OIDC) — no API token needed
- [ ] Add `build` to dev dependencies in `pyproject.toml`
- [ ] Document release process in `README.md` or `CONTRIBUTING.md`
  - [ ] Bump version in `_version.py` and `pyproject.toml`
  - [ ] Tag: `git tag v<version> && git push --tags`
  - [ ] GitHub Action builds and publishes automatically
- [ ] Verify: tag push triggers publish workflow
