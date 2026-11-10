# taxbench-india

A test suite for AI agents and agent skills that answer Indian tax questions. Every case has one correct answer, a link to the source it was checked against, and the date it was checked.

## Why this exists

Several open source skill packs now teach agents Indian GST and TDS. By their own READMEs, their rules have not been verified, and there is no shared way to check them. Meanwhile the rules keep moving:

| Change | In force from | What a model on old rules gets wrong |
|---|---|---|
| GST rates rationalised to 5%, 18% and 40% | 22 September 2025 | Quotes 12% for tractors, 28% for cement and televisions |
| Income-tax Act, 2025 replaces the 1961 Act | 1 April 2026 | Cites section 194C instead of section 393 |
| TDS thresholds raised (rent, professional fees) | 1 April 2025 | Deducts tax on payments that are now under the limit |
| E-way bill validity, 200 km a day | 1 January 2021 | Gives 4 days for 310 km instead of 2 |
| E-invoicing limit lowered to Rs 5 crore | 1 August 2023 | Says a Rs 6 crore business is not covered |

taxbench-india turns each of these into a question with a checkable answer. It also records the outdated answer, so a run tells you how often a model fails and how often it fails because it is quoting old law.

## What is in it

| Category | Cases | What it tests |
|---|---|---|
| `gst-rates` | 12 | Rates after the September 2025 change, including boundary and date traps |
| `tds` | 9 | Rates, thresholds and section numbers under the Income-tax Act, 2025 |
| `eway-bill` | 7 | Validity by distance, and the Rs 50,000 test on value including tax |
| `gst-split` | 6 | CGST, SGST or UTGST, and IGST, on exclusive and inclusive prices |
| `einvoice` | 5 | Who must generate an e-invoice and who is exempt |
| `gstin` | 4 | Length, structure and check digit |

43 cases in this first release. The aim is depth per topic before breadth.

## How cases are verified

Each case states its level in the `verification` field.

| Level | Meaning | Cases |
|---|---|---|
| `official` | Checked against a government source that a maintainer opened and read | 18 |
| `secondary` | Two independent professional sources agree; the official text is linked under `see_also` | 15 |
| `computed` | Arithmetic or an algorithm, recomputed in CI by the reference calculators | 10 |

Things to know before you rely on this:

- No chartered accountant has reviewed these cases. They are checked against published sources, which is weaker.
- `secondary` cases exist because some official sites could not be read by the tools used to build this release. Upgrading them to `official` is a welcome contribution.
- Questions are pinned to a date. If the law changes later, the case stays correct for its date and a new case is added for the new rule.
- This is a test suite. It is not tax advice and should not be used to file returns or make payments.

## Quick start

```bash
pip install -e ".[dev]"
taxbench validate        # check every case file
taxbench list            # see the cases
pytest                   # run the unit tests
```

Run the suite against a model served over an OpenAI-compatible API:

```bash
export TAXBENCH_API_KEY=...
taxbench run --model <model-name> --base-url https://api.example.com/v1 --out results.json
```

Test whether a skill helps. This runs every case twice, without the skill and with it:

```bash
taxbench run --model <model-name> --base-url https://api.example.com/v1 \
  --skill path/to/SKILL.md --out results.json
```

Check the pipeline without calling any model:

```bash
taxbench run --provider oracle   # answers with the expected values, should score 100%
taxbench run --provider stale    # answers with the outdated values where a case has them
```

## Reading the results

```
Baseline (no skill)
category        passed  total  pass %  stale  errors
einvoice             4      5    80.0      1       0
...
```

- `passed`: every key in the answer matched the expected value.
- `stale`: the answer was wrong and matched the outdated rule recorded in the case.
- `errors`: the reply had no JSON object, or the request failed.

Grading is deterministic. Numbers must match within 0.01, booleans and text must match exactly. There is no judge model.

## Limits of this release

- One request per case. The runner does not execute tools, scripts or a multi-step agent loop, so a skill that depends on helper scripts is tested on its instructions only.
- The skill is added to the system prompt in full. That measures whether the content helps, not whether an agent would choose to load it.
- 43 cases is a small sample. Treat differences of one or two cases as noise.

## Results

No model or skill results are published yet. They will be added here with the exact command, model name and date for each run.

## Contributing

One case is one small YAML file, so a first contribution takes a few minutes. See [CONTRIBUTING.md](CONTRIBUTING.md). Cases from accountants are as welcome as code from developers.

## Licence

MIT. See [LICENSE](LICENSE).
