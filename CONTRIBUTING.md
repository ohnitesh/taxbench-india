# Contributing

The most useful contribution is a new case, or an upgrade of an existing case from `secondary` to `official`. You do not need to write Python for either.

## Add a case

1. Pick the folder under `cases/` that fits, or propose a new category in an issue.
2. Copy the template below into `cases/<category>/<id>.yaml`. The file name must equal the `id`.
3. Fill it in. Pin the question to a date so the answer cannot go out of date.
4. Run `taxbench validate` and `pytest`.
5. Open a pull request. Say in the description how you checked the answer.

```yaml
id: eway-validity-310-km
category: eway-bill
title: Validity for 310 km
question: >
  An e-way bill is generated on 5 November 2026 for ordinary (not over
  dimensional) cargo moved by road over 310 km. For how many days is it valid?
answer_keys:
  validity_days: number of days the e-way bill is valid, as a whole number
expected:
  validity_days: 2
stale_answer:            # optional: the answer under the rule that was replaced
  validity_days: 4
reference:               # optional: recompute the answer in CI
  fn: eway_validity_days
  args: {distance_km: 310, km_per_day: 200}
explanation: >
  One or two sentences on why this is the answer, naming the rule.
sources:
  - title: Who published it and what it is
    url: https://...
    type: official       # official or secondary
see_also: []             # optional: the official text, if you could not open it yourself
verification: secondary  # official, secondary or computed
as_of: 2026-11-10        # the day you checked the sources
law_effective_from: 2021-01-01
tags: [changed-rule]
```

## Rules for cases

- One question, one correct answer. If two readings are defensible, tighten the question until one is left, or drop the case.
- Answers are numbers, true or false, or short exact text. No free-form answers.
- List only sources you opened and read. Put links you could not open under `see_also`.
- `official` needs a government source: CBIC, the GST portal, the Income Tax Department, PIB, a gazette notification.
- `secondary` needs two independent sources that agree.
- `computed` needs a `reference` block, so CI recomputes the answer.
- `stale_answer` is only for the answer under a rule that has since changed. Explain the old rule in `explanation`. It is not for common mistakes in general.
- Use made-up names and identifiers. Do not put a real person's or business's GSTIN, PAN or invoice in a case.
- Give the rate in the question when the case is about arithmetic. Keep rate lookups in `gst-rates`.

## Cases we would like next

- GST registration thresholds, including the special category States
- Input tax credit: blocked credits, time limits, reversal on non-payment
- Place of supply for services and for bill-to ship-to sales
- Composition scheme limits and rates
- TDS: crossing the yearly limit partway through the year, GST shown separately on the invoice, payee without a PAN, purchase of goods
- Return due dates and late fees
- MSME payment timelines

## Code changes

- Keep the reference calculators free of built-in rates and thresholds. The case supplies every number and carries the source for it.
- Add or update tests for any behaviour change. `pytest` and `taxbench validate` must pass.

## AI assistance

Drafting cases or code with an AI assistant is fine. Say so in the pull request, and check every expected value against the source yourself before you submit. The person who opens the pull request is responsible for its accuracy.

## Review

A maintainer will open each cited source and confirm that it supports the expected answer. Expect questions if the source is ambiguous or out of date.
