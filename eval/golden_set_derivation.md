# Golden-set derivation

## Construction method

The fixed cases A01–A20, W01–W03 and R01 reproduce the exact questions, sessions, status, intent and required answer content in the Part D brief. Their expected answers are the fixed acceptance values stated in the brief; they are not inferred from the agent's output.

The additional cases C01–C13 were chosen to exercise the nine mandatory categories plus normal lookups and a date-range lookup. The independent numeric expectations below were derived directly from the committed source CSV files, not by calling the conversational agent.

## Independent calculations for original cases

### C01 — fuzzy store-name resolution

Source: `data/store_daily_clean.csv`.

Filter expression equivalent to pandas:

```python
df.loc[(df["store"] == "Bengaluru") &
       (df["date"] == "2026-05-15"), "revenue_inr"].iloc[0]
```

Value: **970774.76** → expected answer substring `INR 970774.76`.

### C02 — approved synonym

Source: `data/store_daily_clean.csv`.

```python
df.loc[(df["store"] == "Pune") &
       (df["date"] == "2026-05-15"), "revenue_inr"].iloc[0]
```

Value: **623845.00** → expected answer substring `INR 623845.00`. The query uses the approved synonym `sales` for `revenue_inr`; this is a language-resolution test, not a different data calculation.

### C03 — ordinary exact lookup

Source: `data/store_daily_clean.csv`.

```python
df.loc[(df["store"] == "Bengaluru") &
       (df["date"] == "2026-05-15"), "revenue_inr"].iloc[0]
```

Value: **970774.76** → expected answer substring `INR 970774.76`.

### C04 — seven-day inclusive average

Source: `data/store_daily_clean.csv`.

```python
subset = df.loc[(df["store"] == "Pune") &
                (df["date"] >= "2026-05-01") &
                (df["date"] <= "2026-05-07")]
subset["revenue_inr"].mean()
```

There are seven daily rows. The unrounded arithmetic mean is **636317.3028571429**; round-half-up to two decimal places gives **636317.30**. Expected answer substring: `INR 636317.30`.

## Non-numeric original cases

- C05 explicitly names two stores; the required behaviour is clarification rather than silently selecting one.
- C14 explicitly names two approved metrics (revenue and footfall); the required behaviour is clarification rather than silently selecting the first metric.
- C06 requests `marketing_spend_inr`, which is not among the eleven approved reportable fields.
- C07 is unrelated to the approved store analytics scope.
- C08 asks the agent to send an email; this is a prohibited action and must be escalated without execution.
- C09 names a date outside the daily dataset window.
- C10/C11 share session `s28`: C10 first stores Pune and a supported date; C11 then introduces an unresolved named store (Kolkata). The unresolved name must not inherit Pune from context.
- C12/C13 share session `s30`: C12 first stores Pune and a supported date; C13 then uses an unsupported period phrase (last week). The unresolved date must not inherit the earlier date.

For the numeric cases, all expected values above come from the CSV expressions shown here. The expected results are fixed before the evaluation runner is invoked.
