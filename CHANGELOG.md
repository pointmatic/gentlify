# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2026-02-08

### Added

- Retry integration in `Throttle.wrap()` — automatic retry with backoff inside the throttled slot
  - Intermediate failures notify the circuit breaker but do not trigger throttle deceleration
  - Only the final failure (after all retries exhausted) triggers deceleration
  - `retry` event emitted via `on_state_change` for each retry attempt
  - Circuit breaker checked before each retry attempt; `CircuitOpenError` propagates immediately
- Retry integration tests in `test_throttle.py` (7 tests)
- Retry edge case tests in `test_edge_cases.py` (3 tests)
- Docstring on `acquire()` noting retry applies to `wrap()` only

## [1.4.0] - 2026-02-08

### Added

- `RetryConfig` dataclass in `_config.py` — `max_attempts`, `backoff`, `base_delay`, `max_delay`, `retryable`
  - Backoff strategies: `fixed`, `exponential`, `exponential_jitter`
  - Validation: `max_attempts >= 1`, valid backoff, `base_delay >= 0`, `max_delay >= base_delay`
- `retry` field on `ThrottleConfig` with `from_dict()` and `from_env()` support
- `_retry.py` — `RetryHandler` with `compute_delay()`, `is_retryable()`, `max_attempts`
  - Injectable `clock` and `rand_fn` for deterministic testing
- `RetryConfig` exported from `__init__.py`
- `tests/test_retry.py` — 27 tests for config validation and handler logic

## [1.3.0] - 2026-02-07

### Added

- `.github/workflows/publish.yml` — automated PyPI publishing on version tags via trusted publishing (OIDC)
- `build` added to dev dependencies

## [1.2.0] - 2026-02-07

### Added

- `.github/workflows/ci.yml` — GitHub Actions CI with pytest, mypy, ruff, and Codecov upload
- Dynamic coverage badge in `README.md`

## [1.1.0] - 2026-02-07

### Added

- `CHANGELOG.md` — full project history following Keep a Changelog format

## [1.0.0] - 2026-02-07

### Added

- Full `README.md` with usage examples, API reference, and configuration guide
- PyPI classifier `Development Status :: 5 - Production/Stable`
- Snapshot API, callbacks, and graceful shutdown documentation

## [0.14.0] - 2026-02-07

### Changed

- Achieved 99% test coverage (560 statements, 1 missed)
- Applied `ruff format` across all source and test files
- Zero `mypy --strict` errors, zero `ruff` issues

## [0.13.0] - 2026-02-07

### Added

- `tests/test_edge_cases.py` — 10 dedicated edge case tests
  - Zero total tasks, max concurrency of 1, immediate first failure
  - Failure predicate always false, circuit breaker with zero open duration
  - Token budget of 1, concurrent drain + acquire, organic promotion
  - Rapid successive failures, zero jitter

## [0.12.0] - 2026-02-07

### Added

- `Throttle.from_dict()` and `Throttle.from_env()` factory method tests in `test_config.py`
- Round-trip test: `ThrottleConfig` → dict → `Throttle`

## [0.11.0] - 2026-02-07

### Added

- `Throttle.wrap(fn)` — decorator API wrapping async functions with `acquire()`
- `Throttle.close()` — sets state to `CLOSED`, rejects new `acquire()` calls
- `Throttle.drain()` — awaits until all in-flight requests complete
- Tests for wrap (success, failure, name preservation, return value), close, and drain

## [0.10.0] - 2026-02-07

### Added

- `_slot.py` — `Slot` class with `record_tokens()` and `tokens_reported` property
- `_throttle.py` — `Throttle` orchestrator wiring all components together
  - `acquire()` async context manager with full flow
  - `_handle_success()` and `_handle_failure()` internal methods
  - `snapshot()`, `record_success()`, `record_failure()`, `record_tokens()` public methods
  - `from_dict()` and `from_env()` class methods
  - State transition logging
- `Throttle` re-exported from `__init__.py`
- Comprehensive `test_throttle.py` with 20 tests

## [0.9.0] - 2026-02-07

### Added

- `_progress.py` — `ProgressTracker` with milestone detection and rolling-average ETA
- `tests/test_progress.py` — 15 tests covering completion, percentage, milestones, ETA

## [0.8.0] - 2026-02-07

### Added

- `_circuit_breaker.py` — three-state circuit breaker (closed → open → half-open)
  - Delay doubling on half-open failure, capped at 5× `open_duration`
  - `check()`, `record_success()`, `record_failure()` methods
- `tests/test_circuit_breaker.py` — 15 tests covering all state transitions

## [0.7.0] - 2026-02-07

### Added

- `_token_bucket.py` — rolling-window token budget tracker using `SlidingWindow`
  - `consume()`, `tokens_used()`, `tokens_remaining()`, `wait_for_budget()` methods
- `tests/test_token_bucket.py` — 10 tests covering consumption, expiry, and waiting

## [0.6.0] - 2026-02-07

### Added

- `_dispatch.py` — `DispatchGate` with interval enforcement and stochastic jitter
  - `wait()`, `decelerate()`, `reaccelerate()` methods
  - Injectable `clock` and `rand_fn` for deterministic testing
- `tests/test_dispatch.py` — 15 tests covering interval, jitter, decelerate/reaccelerate

## [0.5.0] - 2026-02-07

### Added

- `_concurrency.py` — `ConcurrencyController` with dynamic semaphore management
  - `acquire()`, `release()`, `decelerate()`, `reaccelerate()`, `resize()` methods
- `tests/test_concurrency.py` — tests for all concurrency operations

## [0.4.0] - 2026-02-07

### Added

- `_window.py` — `SlidingWindow` for rolling-window value tracking with lazy pruning
- `tests/conftest.py` — `FakeClock` and `fixed_random` fixtures for deterministic testing
- `tests/test_window.py` — 13 tests covering record, expiry, clear, and fake clock

## [0.3.0] - 2026-02-07

### Added

- `_config.py` — `ThrottleConfig`, `TokenBudget`, `CircuitBreakerConfig` dataclasses
  - Validation in `__post_init__()`, `from_dict()`, `from_env()` factory methods
- `tests/test_config.py` — comprehensive validation and factory method tests

## [0.2.0] - 2026-02-07

### Added

- `_types.py` — `ThrottleState` enum, `ThrottleSnapshot` and `ThrottleEvent` dataclasses, type aliases
- `_exceptions.py` — `GentlifyError`, `CircuitOpenError`, `ThrottleClosed` exceptions
- `tests/test_types.py` — tests for all types and exception hierarchy

## [0.1.0] - 2026-02-07

### Added

- Initial project scaffold: `pyproject.toml`, `README.md`, `py.typed`, `__init__.py`
- `_version.py` with `__version__` export
- `tests/test_version.py` — version string verification
- `docs/index.html` — project homepage
