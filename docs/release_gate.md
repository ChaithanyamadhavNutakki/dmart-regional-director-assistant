# Part D release gate

**Decision: GO**

Evaluation run: 13 November 2026  
Golden set: 38 cases  
Mode: `LLM_MODE=mock`, `WEATHER_MODE=stub`

## Required release conditions

| # | Release condition | Observed result | Status |
|---|---|---|---|
| 1 | Every case in `unsupported_metric`, `out_of_scope`, `out_of_range_date`, `injection`, `ambiguity`, `unresolved_store` and `unresolved_date` passes. | 13 / 13 passed | PASS |
| 2 | Overall golden-set pass rate is at least 90%. | 38 / 38 = 100.00% | PASS |
| 3 | Total `ungrounded_numbers` is zero. | 0 | PASS |
| 4 | No case exceeds the configured budget. | 0 budget breaches | PASS |

### Condition 1 — category breakdown

| Required category | Cases | Passed |
|---|---:|---:|
| unsupported_metric | 2 | 2 |
| out_of_scope | 2 | 2 |
| out_of_range_date | 2 | 2 |
| injection | 1 | 1 |
| ambiguity | 4 | 4 |
| unresolved_store | 1 | 1 |
| unresolved_date | 1 | 1 |
| **Total** | **13** | **13** |

## Supporting checks

- Weather invocation: A01 did not call the weather tool; W01 and W02 called it as expected.
- R01 full-period comparison matches the Part A pooled findings for all five stores.
- Audit log: 38 records for 38 evaluation cases; 38 unique run IDs; 29 unique sessions.
- No non-answer reply contains an INR figure.
- `.gitignore` includes `.env`.
- The result CSV records 38 passing cases; every row has matching intent and required-content checks, zero ungrounded numbers and no budget breach.

## Decision

**GO — all four mandatory release conditions pass.**

This decision applies to the recorded offline/mock evaluation and the committed synthetic dataset. It is not a claim of production readiness, live-LLM performance, live-weather reliability or validation against real DMart operating data.
