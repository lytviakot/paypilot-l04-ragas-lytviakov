# L04 · RAGAS Diagnostic Report: PayPilot

Homework 3. A report on where the PayPilot agent breaks (before the model or in it), and 12 new retrieval cases added to the golden set.

The runner, the stand and the kit stay in `paypilot-l03-eval` and are not part of this repository.

## What is here

| File | What it is |
|---|---|
| `RAGAS_Diagnostic_Report.md` | the report, six sections and the last line |
| `golden.jsonl` | 43 cases: the 31 from homework 2 plus 12 retrieval cases (`RET-001` to `RET-012`) |
| `generate_retrieval.py` | builds the retrieval cases; each `reference` is copied from the corpus and the script checks it is really in the file |
| `generate_golden.py` | the generator from homework 2, unchanged |
| `measure_topk.py` | runs one question at `top_k` 4, 5 and 6, three times each (report section 5) |
| `measure_broken.py` | the same on the broken index `kb_broken` (report section 5) |
| `reports/` | raw run reports and measurement data |
| `lab/lab-report-l04.md` | notes from the four lab exercises |

## Run

Put `golden.jsonl` into `sets/` of the kit and run from the kit folder:

    docker compose run --rm eval --set golden --profile clean

`set_hash`: `ae84277bb205`. Agent model: `claude-haiku-5-5`. The judge is not used.

Regenerate the retrieval cases (needs the stand repo next to this one, or set `CORPUS_DIR`):

    python generate_retrieval.py > _retrieval.jsonl

## Results

| Run | Profile | Result | File |
|---|---|---|---|
| full set, daily gate | `clean` | 41 of 42 | `reports/1-full-set-clean.json` |
| retrieval cases only | `clean` | 11 of 12 | `reports/2-retrieval-only-clean.json` |
| retrieval cases only | `lesson-04` | 0 of 12 | `reports/3-retrieval-only-lesson-04.json` |

The one failing case on `clean` is `RET-007` (Tier 2 spread and daily limit in one question). It is a real retrieval problem, not a bad case: at the default `top_k` 4 the spread table falls out of the results. It is described in section 5 of the report. TON-001 is a release-gate case and is not in the daily run, which is why the full set shows 42 cases, not 43.

The first version of `RET-011` was a bad question (the agent took the word "threshold" for a confidential monitoring threshold and did not search), so it was rewritten before the runs above.

## Where the results differ from the lesson

- Lab exercise 1 on `lesson-04` returned `tariffs.md#b2` and not `#b3`. The failure point is the same, indexation.
- D05 never produced the wrong "EUR 15.00 fixed" answer. In 4 of 4 runs the agent did not search and refused to name a figure.
- Complaint C-13: the cut table reproduced, the wrong figure EUR 1,500 did not. Complaint C-14 did not reproduce on two real searches, because the codes and the windows sit in one chunk.
