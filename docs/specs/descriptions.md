# descriptions.md — gentlify (Python)

Canonical source of truth for all descriptive language used across the project. All consumer files (README.md, docs/index.html, pyproject.toml, features.md) should draw from these definitions.

---

## Name

- gentlify (GitHub)
- gentlify (PyPI)

## Tagline

Tame the angry APIs

## Long Tagline

Tame the angry APIs and make them purr.

## One-liner

Adaptive async rate limiting for Python

### Friendly Brief Description (with one-liner)

Closed-loop feedback control for API concurrency. When APIs push back, gentlify slows down. When pressure eases, it speeds up.

## Two-clause Technical Description

Adaptive async rate limiting for Python, closed-loop feedback control for API concurrency.

## Benefits

- Zero dependencies
- Asyncio-native
- Fully typed

## Technical Description

Gentlify automatically adjusts concurrency and dispatch rate in response to failures, so your application backs off when an API is struggling and speeds up when it recovers — without manual tuning.

## Keywords

`async`, `rate-limiting`, `concurrency`, `throttle`, `asyncio`, `retry`, `backoff`, `circuit-breaker`

---

## Feature Cards

Short blurbs for landing pages and feature grids. Each card has a title and a one-to-two sentence description.

| # | Title | Description |
|---|-------|-------------|
| 1 | Adaptive Concurrency | Dynamic concurrency limits that decelerate on failures and cautiously recover after a cooling period of sustained success. |
| 2 | Dispatch Interval + Jitter | Enforces minimum time gaps between requests with stochastic jitter to prevent thundering-herd bursts. |
| 3 | Token-Aware Budgeting | Track per-window resource consumption — LLM tokens, API credits, bytes — independently of request-count limits. |
| 4 | Circuit Breaker | Hard stop after sustained failures with automatic half-open probing for safe recovery. |
| 5 | Built-in Retry | Configurable retry with exponential backoff and jitter — retries happen inside the throttled slot so concurrency accounting stays correct. |
| 6 | Zero Dependencies | Pure Python standard library. No runtime dependencies. Ships with py.typed and passes mypy --strict. |
| 7 | Progress & Observability | Real-time snapshots with ETA, structured event callbacks, and standard logging integration. |
| 8 | Graceful Shutdown | Drain in-flight requests on shutdown — no dropped work, no hard stops. |

---

## Usage Notes

| File | Which descriptions to use |
|------|--------------------------|
| `pyproject.toml` `description` | Two-clause Technical Description |
| `pyproject.toml` `keywords` | Keywords |
| `README.md` line 10 | Two-clause Technical Description |
| `README.md` line 12 | Benefits (inline) |
| `README.md` line 14 | Technical Description |
| `docs/index.html` hero `<h1>` | One-liner |
| `docs/index.html` hero `<p>` | Friendly Brief Description |
| `docs/index.html` feature grid | Feature Cards |
| `docs/specs/features.md` line 1 | One-liner + Long Tagline |