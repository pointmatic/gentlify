# better_features.md — gentlify (Python)

Working document for v2.x / v3.x improvements. Captures competitive analysis, differentiation gaps, documentation shortcomings, and candidate features. This is a planning artifact — nothing here is committed to implementation yet.

---

## Competitive Landscape

### Direct competitors

| Library | PyPI | What it does | Approach |
|---------|------|-------------|----------|
| **aiolimiter** | ~800★ | Leaky bucket rate limiter | Fixed rate (N per T seconds). No concurrency control, no retry, no feedback. |
| **aiometer** | ~300★ | Concurrency scheduler | `max_at_once` + `max_per_second`. Batch-oriented (`run_all`, `amap`). No failure response, no retry. |
| **pyrate-limiter** | ~600★ | Multi-backend rate limiter | Leaky bucket with Redis/SQLite backends. Sync+async. No concurrency adaptation, no retry. |
| **tenacity** | ~6k★ | Retry library | Retry with backoff/jitter. No rate limiting, no concurrency control, no token budgets. |
| **backoff** | ~2k★ | Retry library | Decorator-based retry. Same gap as tenacity — no throttling. |
| **aiobreaker** | ~100★ | Circuit breaker | Circuit breaker only. No rate limiting, no retry, no concurrency. |

### What developers do today

To get what gentlify provides in a single `Throttle`, developers currently glue together 3–4 libraries:

```
tenacity (retry) + aiolimiter (rate limit) + aiobreaker (circuit breaker) + custom token tracking
```

Each library has its own configuration, its own decorator/context manager, and they don't share state. Retry releases the rate limit slot and re-acquires it, distorting concurrency counts. Circuit breaker state is invisible to the rate limiter. Token budgets are entirely DIY.

---

## What's unique about gentlify (v2.0)

1. **Closed-loop adaptive feedback** — Decelerate on failures, cool, reaccelerate on success. No other Python library does this. Every competitor enforces static limits that never change.

2. **Unified primitives** — Rate limiting + concurrency control + retry + circuit breaker + token budgeting in one object. Replaces tenacity + aiolimiter + aiobreaker + custom token tracking.

3. **Token-aware budgeting** — Purpose-built for LLM APIs where the constraint is tokens-per-minute, not requests-per-second. No competitor has this.

4. **Retry-aware concurrency accounting** — Retries happen *inside* the throttled slot. The concurrency slot stays held during retry, so accounting is always correct. With tenacity + aiolimiter, a retry releases and re-acquires the slot, distorting counts.

5. **Single-call API** — `execute(fn)` gives throttling + retry + custom logic in one call. No decorator stacking, no context manager nesting.

6. **Zero dependencies** — Pure Python standard library. Ships with `py.typed`, passes `mypy --strict`.

---

## Documentation gaps (README + index.html)

### README problems

| Problem | Detail |
|---------|--------|
| **Opening line is generic** | "Adaptive async rate limiting for Python, closed-loop feedback control for API concurrency" reads like a dictionary definition. Doesn't land the punch of *why you'd pick this over aiolimiter*. |
| **No "Why gentlify?" section** | A developer scanning the README has no idea this is different from aiolimiter or that it replaces tenacity + aiolimiter + aiobreaker. The competitive advantage is invisible. |
| **Quick Start doesn't show adaptation** | `execute(lambda slot: call_api(item))` looks identical to what aiolimiter does. The magic (automatic deceleration/reacceleration) is mentioned in a sentence but not *shown*. |
| **Feature sections are flat** | Token Budget, Circuit Breaker, Retry are listed as peers. The narrative should build: core loop → retry inside it → circuit breaker interaction → token budgeting on top. The *integration* is the differentiator, not the individual features. |
| **No comparison table** | Developers evaluating libraries want a quick "what does this replace?" answer. |

### index.html problems

| Problem | Detail |
|---------|--------|
| **Feature cards are generic** | "Adaptive Concurrency" could be any library's tagline. Cards don't convey the *closed-loop* differentiator. |
| **No before/after** | A "Without gentlify / With gentlify" code comparison would immediately show value. |
| **Quick Start doesn't show feedback loop** | The landing page should show the thing no one else does — adaptation. |

### Recommended fixes

1. Add a **"Why gentlify?"** section right after Installation:

   > Most rate limiters enforce a fixed limit you configure upfront. Gentlify is different — it **adapts**. When your API starts returning errors, gentlify automatically reduces concurrency and slows dispatch. When the pressure eases, it cautiously speeds back up. No manual tuning, no retry library, no separate circuit breaker — one object handles it all.

2. Add a **comparison table**:

   | Capability | aiolimiter | tenacity | aiometer | gentlify |
   |---|---|---|---|---|
   | Rate limiting | ✅ static | ❌ | ✅ static | ✅ adaptive |
   | Retry + backoff | ❌ | ✅ | ❌ | ✅ built-in |
   | Circuit breaker | ❌ | ❌ | ❌ | ✅ built-in |
   | Token budgeting | ❌ | ❌ | ❌ | ✅ built-in |
   | Concurrency control | ❌ | ✅ static | ✅ static | ✅ adaptive |
   | Feedback loop | ❌ | ❌ | ❌ | ✅ closed-loop |
   | Zero dependencies | ✅ | ❌ | ❌ | ✅ |

3. Rewrite Quick Start to **show the feedback loop** — not just a static call, but a hint of what happens when things go wrong.

4. On index.html, add a **before/after code comparison** or a short "What happens when the API pushes back?" narrative section.

---

## Candidate features for v2.x / v3.x

Features that would strengthen gentlify's position while staying within the "adaptive throttling" mission. Ordered by estimated impact.

### 1. Response-header-driven adaptation

**Impact: High** — This is the natural evolution of "closed-loop."

Many APIs return rate limit headers (`Retry-After`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`). A hook that feeds these signals back into the throttle would make gentlify truly closed-loop against the *server's* state, not just inferred from failures.

Possible API:

```python
async def task(slot):
    response = await call_api(item)
    slot.report_headers(response.headers)  # or slot.report_rate_limit(remaining=5, reset_at=...)
    return response
```

This would let gentlify proactively slow down *before* hitting 429s, rather than reacting after the fact. No competitor does this.

### 2. Per-endpoint / multi-key throttling

**Impact: High** — Addresses a real pain point for multi-endpoint APIs.

A single `Throttle` per endpoint works, but many apps hit multiple endpoints with different limits (e.g., OpenAI `/chat/completions` vs `/embeddings`). A `ThrottleGroup` or keyed throttle that shares a global budget but tracks per-key limits would be a killer feature.

Possible API:

```python
group = ThrottleGroup(
    global_budget=TokenBudget(max_tokens=100_000, window_seconds=60.0),
    keys={
        "chat": ThrottleConfig(max_concurrency=5),
        "embeddings": ThrottleConfig(max_concurrency=20),
    },
)

await group.execute("chat", lambda slot: call_chat(prompt))
await group.execute("embeddings", lambda slot: call_embed(text))
```

### 3. Metrics / OpenTelemetry integration

**Impact: Medium** — Makes gentlify production-ready for teams with dashboards.

A lightweight `on_metrics` callback or OTel span integration for observability of the throttle itself. Stays focused — it's not adding a metrics library, just emitting structured data that plugs into existing infrastructure.

Possible API:

```python
throttle = Throttle(
    on_metrics=lambda m: otel_meter.record(m),  # or a protocol/interface
)
```

### 4. Adaptive backoff from response latency

**Impact: Medium** — Latency is often the first signal of overload, before errors appear.

Track rolling p50/p95 latency and proactively decelerate when latency spikes, even if requests are still succeeding. This catches the "API is degrading but not yet failing" scenario.

### 5. Cooperative multi-process / distributed throttling

**Impact: Low-Medium** — Niche but valuable for scaled deployments.

Share throttle state across processes via Redis or shared memory. pyrate-limiter has Redis backends, but without the adaptive feedback loop. This would be gentlify's adaptive loop + distributed state.

**Note:** This is a significant scope increase and may warrant a separate package (`gentlify-redis`).

---

## AI / LLM positioning

Gentlify has a strong AI/LLM angle that is currently underplayed in the docs. The library is purpose-built for the exact problem LLM application developers face.

### Why gentlify is an AI-native library

1. **Token budgeting is an LLM-native concept.** No other rate limiting library has it. `TokenBudget` exists because LLM APIs charge per token and enforce tokens-per-minute limits, not just requests-per-second. This is gentlify's most differentiated feature for AI developers, and it's currently buried as a mid-page section.

2. **LLM APIs are the poster child for adaptive throttling.** OpenAI, Anthropic, Google, etc. all have dynamic rate limits that change based on usage tier, time of day, and load. Static rate limiters force you to guess the limit. Gentlify's feedback loop *discovers* the right rate by reacting to 429s and backing off.

3. **`execute()` with `slot` was designed for LLM workflows.** The callback pattern — call the API, inspect the response, record tokens, return a transformed result — is exactly what every LLM app does. `slot.attempt` for idempotency keys matters because LLM calls are expensive and non-idempotent by default.

4. **The future features are AI-first.** Response-header adaptation (`X-RateLimit-Remaining`), per-endpoint throttling (chat vs embeddings vs fine-tuning), and latency-based adaptation are all driven by LLM API patterns.

### What's missing in the docs (AI angle)

**README:**
- The tagline says "API concurrency" — generic. It should signal "built for LLM and AI APIs" without excluding general use.
- The Quick Start uses `call_api(item)` — could be anything. An LLM example (`call_llm(prompt)`) would immediately resonate with the target audience.
- Token Budget is section 4. For AI developers, it should be much more prominent — it's the reason they'd pick gentlify over aiolimiter.

**index.html:**
- The hero says "Adaptive async rate limiting for Python" — no AI signal at all.
- The feature cards mention "Token-Aware Budgeting" but describe it generically ("LLM tokens, API credits, bytes"). It should lead with the LLM use case.
- No mention of OpenAI, Anthropic, or any LLM provider. Developers searching for "Python OpenAI rate limiting" won't find this.

### Recommended positioning: "AI-first, not AI-only"

**Hero/tagline:**
> "Adaptive rate limiting for Python — built for LLM APIs, works with any async service."

**Sub-tagline:**
> "Token budgets, automatic backoff, circuit breakers, and retry — one object replaces four libraries."

**Quick Start should use an LLM example:**

```python
throttle = Throttle(
    max_concurrency=5,
    token_budget=TokenBudget(max_tokens=100_000, window_seconds=60.0),
    retry=RetryConfig(max_attempts=3, backoff="exponential_jitter"),
)

async def summarize(slot):
    result = await openai.chat.completions.create(model="gpt-4", messages=[...])
    slot.record_tokens(result.usage.total_tokens)
    return result.choices[0].message.content

text = await throttle.execute(summarize)
```

This immediately shows: concurrency control + token budget + retry + custom logic — all in one call, all relevant to what AI developers actually do.

### SEO / discoverability

The docs and PyPI metadata (`pyproject.toml` keywords) should include terms like: `openai`, `llm`, `ai`, `rate-limit`, `token-budget`, `anthropic`. Developers searching for "python openai rate limit" or "llm token rate limiting python" should find gentlify.

---

## Complementary relationship with LiteLLM

LiteLLM (~20k★) is a widely-used LLM API abstraction layer and gateway. Gentlify and LiteLLM are **not competitors — they're complementary**, operating at different layers.

### What LiteLLM does

- **Unified interface** — Call 100+ LLM providers (OpenAI, Anthropic, Azure, Bedrock, etc.) through one API
- **Router** — Load balance across deployments, fallback between providers
- **Proxy server** — Centralized gateway with auth, budgets, logging
- **Basic reliability** — `num_retries`, `cooldown_time`, `max_parallel_requests` per deployment, `allowed_fails`

### What LiteLLM does NOT do

LiteLLM's rate limiting is **static and per-deployment**:
- `max_parallel_requests` is a fixed semaphore — no adaptation
- Cooldowns are binary (on/off after N fails) — no gradual deceleration or reacceleration
- No client-side token-per-minute budget enforcement (their TPM/RPM rate limiting is an enterprise proxy feature)
- No feedback loop — if the API is struggling but not yet failing, LiteLLM doesn't slow down
- Retry is simple (`num_retries` + optional `retry_after`) — no exponential jitter, no retryable predicates

### Where gentlify fits

**Gentlify wraps the LiteLLM call itself.** LiteLLM picks *which* provider to call; gentlify controls *how fast and how many* calls go out, adapting in real time.

```python
import litellm
from gentlify import Throttle, TokenBudget, RetryConfig

throttle = Throttle(
    max_concurrency=10,
    token_budget=TokenBudget(max_tokens=100_000, window_seconds=60.0),
    retry=RetryConfig(max_attempts=3, backoff="exponential_jitter"),
)

async def summarize(slot):
    # LiteLLM handles provider routing
    response = await litellm.acompletion(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
    )
    # Gentlify handles adaptive throttling + token tracking
    slot.record_tokens(response.usage.total_tokens)
    return response.choices[0].message.content

text = await throttle.execute(summarize)
```

### Comparison table

| Concern | LiteLLM | gentlify | Together |
|---------|---------|----------|----------|
| Which provider to call | ✅ Router + fallback | ❌ | LiteLLM picks the provider |
| How fast to call | ❌ Static limits | ✅ Adaptive | gentlify adapts the rate |
| Token budget enforcement | ⚠️ Enterprise proxy only | ✅ Client-side | gentlify enforces locally |
| Retry with backoff/jitter | ⚠️ Basic | ✅ Full | gentlify handles retry |
| Circuit breaker | ⚠️ Binary cooldown | ✅ Half-open probing | gentlify provides safe recovery |
| Feedback loop | ❌ | ✅ Closed-loop | gentlify decelerates/reaccelerates |

### The one-liner

> *LiteLLM is your universal LLM remote control. Gentlify is the speed governor that keeps you from burning it out.*

### Documentation recommendation

A "Works with LiteLLM" example in the README would:
1. Immediately resonate with the large LiteLLM user base
2. Clarify the relationship — not a replacement, a complement
3. Show token budget + adaptive throttling in a context developers already understand
4. Differentiate from LiteLLM's built-in rate limiting — which is static and basic

---

## Priority assessment

| Feature | Impact | Complexity | Stays focused? | Target |
|---------|--------|-----------|----------------|--------|
| Documentation rewrite | High | Low | Yes | v2.0.0 |
| Response-header adaptation | High | Medium | Yes — extends feedback loop | v2.1 |
| Per-endpoint throttling | High | Medium-High | Yes — natural extension | v2.2 or v3.0 |
| Metrics / OTel | Medium | Low | Yes — observability | v2.1 |
| Latency-based adaptation | Medium | Medium | Yes — extends feedback loop | v2.2 |
| Distributed throttling | Low-Medium | High | Borderline — separate package? | v3.0+ |
