# Part D evaluation summary

## Evaluation configuration

- Evaluation date: 13 November 2026
- Golden-set size: 38 cases (24 fixed cases and 14 additional cases)
- Execution mode: `LLM_MODE=mock`, `WEATHER_MODE=stub`
- Data path: committed local CSV files and local SQLite
- Result file: `eval/eval_results.csv`
- Audit file: `eval/eval_runs.jsonl`

## Cost

The offline mock evaluation does not incur hosted-model API charges. Token estimates and tool calls are reported as execution-cost proxies.

- Mean estimated tokens per case: **20.89**
- Maximum estimated tokens in one case: **53**
- Total tool calls: **24**
- Budget breaches: **0**

## Latency

- Mean latency: **3.850 ms**
- 90th-percentile latency (linear): **8.221 ms**
- Maximum latency: **16.151 ms**

These are observed local evaluation timings, not production service-level guarantees.

## Quality

- Passed cases: **38 / 38**
- Overall pass rate: **100.00%**
- Intent matches: **38 / 38**
- Required-content matches: **38 / 38**
- Ungrounded numbers: **0**

The full-period R01 revenue comparison reconciles to the Part A pooled findings:

| Store | Average revenue (INR) |
|---|---:|
| Pune | 636358.55 |
| Ahmedabad | 782647.37 |
| Hyderabad | 893233.01 |
| Bengaluru | 931065.68 |
| Mumbai | 1064371.60 |

## Safety

- Mandatory release-gate category cases passed: **13 / 13**
- Injection, unsupported-metric and out-of-scope cases passed: **5 / 5**
- Non-answer replies containing INR figures: **0**
- Evaluation cases exceeding the configured budget: **0**
- `.gitignore` includes `.env`: **Yes**

The audit log contains **38 records**, **38 unique run IDs** and **29 unique sessions**. All records include the required audit fields. Clarification, safe-failure and escalation responses that did not execute a data query correctly have empty evidence and grounded-value arrays; the retry-exhaustion case is explicitly escalated without returning a result.

## Evaluation conclusion

All four Part D release-gate conditions are satisfied by this recorded evaluation. The result is a **GO for the capstone release gate**, subject to retaining the committed evaluation evidence and recognising the documented limitations: synthetic data, bounded rule-based language interpretation, local mock execution and stub weather values.
