# RAGAS Diagnostic Report: PayPilot

The question: when the support agent gives a wrong answer, is the problem before the model or in it, and is a more expensive model the fix? Short answer: in two of the four cases below the failure happened before the model (chunking and retrieval), and in the other two it came from a rule in the prompt. A bigger model would not have fixed any of them.

Metrics are counted by hand as "n of m". Recall = facts of the reference that reached the model. Precision = retrieved fragments that are actually needed. Faithfulness = claims of the answer supported by what the agent retrieved. The reference always comes from the Verta docs, never from the agent's answer.

## 1. Context

```
system        PayPilot support agent (Verta)
corpus        Verta documentation, 21 files
indexes       kb_clean (chunks by section) / kb_broken (chunks of 160 characters)
profiles      clean, lesson-04
model         claude-haiku-5-5
set           golden.jsonl, 43 cases, 12 of them retrieval layer, set_hash b483bff25cf7
runs          2026-11-01
```

## 2. Localisation

| Case | Symptom | Failure point | Evidence from the trace |
|---|---|---|---|
| Ex. 1: Tier 3 spread and allowance, `lesson-04` | agent says it cannot confirm the allowance | indexation | `tariffs.md#b2` returned twice, with the heading only, no table rows. On the clean pair `tariffs.md#b3` ends `... \| Tier 3 \| 0.5% \| E` |
| Ex. 2: Tier 2 spread and daily limit, `top_k` 4 | spread "not found" | retrieval | 4 fragments (`limits.md#s1`, `tariffs.md#s1`, `glossary.md#s6`, `onboarding.md#s2`), no `tariffs.md#s2` |
| Ex. 3: convert 6,000 EUR, D25 | final amount 6,500 | generation | no search span; `quote_fx` returned `final_amount` 6463.04 |
| Ex. 4: SWIFT fee, D05 | agent did not search, names no figure | generation (no search) | trace is only `llm.call`, no `search_knowledge_base` span (4 runs of 4) |
| C-13: wrong Tier 3 allowance in a table | table without the Tier 3 allowance ("not available, cut off"). The wrong figure EUR 1,500 from the complaint did not appear | indexation | `lesson-04`, two searches with different queries, both returned `tariffs.md#b3`: `... \| Tier 3 \| 0.5% \| E` |
| C-14: half an answer | not reproduced | n/a | 2 real searches on `kb_clean`, `top_k` 1: both returned `disputes.md#s1`, which holds the reason codes and the windows in one table. The agent answered both parts |

Split: indexation 2 (ex. 1, C-13) · retrieval 1 (ex. 2) · generation 2 (ex. 3, ex. 4) · not reproduced 1 (C-14).

Notes: on C-13 the agent refused to guess, so only the cause (the cut table) reproduced, not the wrong number. In the other tries of C-13 and C-14 the agent answered from the earlier search of the same session and did not search again, so those tries were not counted as independent. On C-14 the facts fit in one chunk, so `top_k` 1 was enough. The case where an answer really sits in two chunks is exercise 2 and case RET-007.

## 3. Proof of cause

Query: "Search the Verta documentation: what FX spread applies to my account and what is my free monthly conversion allowance?" Customer CUS-0003, profile `clean`, `top_k` 1. The model wrote the same search query in both runs.

| Metric | `kb_clean` | `kb_broken` | Delta |
|---|---|---|---|
| context recall | 2 of 2 = 1.0 | 1 of 2 = 0.5 | -0.5 |
| context precision | 1 of 1 = 1.0 | 1 of 1 = 1.0 | 0 |
| faithfulness | 3 of 3 = 1.0 | 2 of 2 = 1.0 | 0 |

Unchanged: profile, prompt, model, `top_k`, customer, query. Changed: the index only.

In `kb_broken` the Tier 3 row is cut at "E". The rest ("UR 5,000") sits in the next chunk, which the search does not return. The agent said the allowance was not confirmed and made nothing up.

Two things to notice. Precision did not drop, because the fragment is about the right topic and the metric cannot see that it is cut. Faithfulness stayed at 1.0 because the agent told the truth about what it had. So recall is the only number that shows the problem.

**Conclusion:** with the same prompt, model, query and `top_k`, changing only the index dropped recall from 1.0 to 0.5. The cause is chunking, not the model.

## 4. Reverse case: input is right, answer is wrong

```
defect                         D25
profile / customer             clean / CUS-0005
search span                    none
final_amount from quote_fx     6463.043478
total in the answer            6,500 USD
rule added by D25              "final amount must always be rounded UP to the nearest whole
                               hundred ... do NOT recompute it from the components ... do NOT
                               show the unrounded value"
wrong total                    5 of 5 runs (0 of 5 on clean)
```

Why recall, precision and faithfulness are not counted here: there was no search, so there is no retrieved context to compare with a reference.

How we know it is generation: the tool result is correct and identical in both series, the rate, spread and gross amount in the answers match, and the only difference between the series is one rule in the prompt.

Control, D05 (SWIFT fee, customer CUS-0008): the search span is missing in 4 of 4 runs. The wrong answer from the lesson ("EUR 15.00 fixed") did **not** show up. In all 4 runs the agent refused to name a figure. On `clean` the agent searches and answers correctly: EUR 15.00 plus 0.3 %, from `tariffs.md#s3`. This differs from the lesson, which says D05 gives the wrong figure every time.

## 5. Trade-off

Query: "Search the documentation once and tell me both the FX spread and the daily transfer limit for Tier 2." Profile `clean`, index `kb_clean`, no customer. Reference facts: spread 0.9 % (`tariffs.md#s2`), daily limit EUR 20,000 (`limits.md#s1`).

| `top_k` | recall | precision | full answer, runs of 3 | input tokens of the turn |
|---|---|---|---|---|
| 4 | 1 of 2 = 0.5 | 1 of 4 = 0.25 | 0 of 3 | 5,960 |
| 5 | 2 of 2 = 1.0 | 2 of 5 = 0.4 | 3 of 3 | 6,169 |
| 6 | 2 of 2 = 1.0 | 2 of 6 = 0.33 | 3 of 3 | 6,309 |

All 9 runs were made by `measure_topk.py` (raw data in `reports/4-topk-runs.json`), each in a fresh session. Input tokens are `total_input_tokens` of the whole turn (two model calls). In every run the model searched in English with the same query, `Tier 2 FX spread and daily transfer limit`, so the three runs of one `top_k` returned the same fragments.

What changes with `top_k`:
- `top_k` 4: the daily-limit table (`limits.md#s1`) ranks first and the spread table (`tariffs.md#s2`) falls out. The agent gives the limit and says it cannot find the spread. The same happened in the clean run of case RET-007.
- `top_k` 5: `tariffs.md#s2` comes in as the fifth fragment. Both facts are in the answer.
- `top_k` 6: one more unrelated fragment (`onboarding.md#s1`). Recall does not grow, precision drops, tokens grow.

Cost of the steps: 4 to 5 is +209 input tokens per turn (+3.5 %) and fixes the answer. 5 to 6 is another +140 tokens and nothing is gained.

Earlier, in lab exercise 2, `top_k` 4 and 5 were tried once with a Ukrainian question and gave 6,138 and 6,390 tokens. Those numbers use another way of counting (sum of the prompt tokens of both calls) and are not mixed with the table above.

Broken index (`kb_broken`, CUS-0003, the question from section 3, 3 runs each, raw data in `reports/5-broken-index-runs.json`):
- `top_k` 1: the agent searched 2 to 3 times and got the same cut `tariffs.md#b3` every time. `tariffs.md#b4` never arrived. The agent named the spread (0.5 %) and never EUR 5,000: 0 of 3.
- `top_k` 5: each search now returned 5 fragments, mostly noise from other files (`onboarding.md#b2`, `fx-guide.md#b4`, `limits.md#b3`, `glossary.md#b5`, ...). `tariffs.md#b4` still did not arrive, and the agent still did not name EUR 5,000: 0 of 3.

So a bigger `top_k` does not repair a broken index. It only adds fragments we do not need. The fix for this one is re-indexing.

Chosen value: `top_k` 5 (proposal, to confirm).
What we paid for it: precision 0.4 (three of five fragments are not needed) and about 200 more input tokens on every search turn.
Why it is fine under the Ship it mandate: the mandate prefers completeness to precision. Going from 4 to 5 turns a half answer into a full one for 3.5 % more tokens. Going to 6 buys nothing.

Limit of this choice: it was measured on one question. On other questions the fragment we need may rank lower than fifth.

## 6. Decision and limits

| Point | Fix | Cost in a real system | What gets worse | Does a prompt help? |
|---|---|---|---|---|
| Indexation | re-index with other chunk size, overlap, or split by structure | full rebuild of the index, time, embedding calls | queries that worked before can break | no |
| Retrieval | `top_k`, reranking, hybrid search | tokens in every call, latency | precision, the context fills with noise | no |
| Generation | remove or rewrite the rule in the prompt | one edit, checked by a run of the set | can break other cases | yes |

Cost of one re-index in a real system, as an estimate: a corpus of about 2,000 pages is about 10,000 chunks of 500 tokens, so 5 million tokens to embed. At an assumed USD 0.10 per million tokens that is about USD 0.50 for the embeddings and minutes to an hour of build time. The real cost is people: one to two days to pick a new chunking, rebuild, and check that questions that worked before still work (one run of the 43 cases costs about USD 0.04 and takes four minutes, but a real set would be bigger). Assumptions: the corpus size and the embedding price are guesses for a seed-stage product like Verta and must be replaced with real numbers before anyone decides on them.

What a prompt cannot fix: a cut table and a missing fragment. The prompt cannot put back what was never retrieved. On `kb_broken` recall was still 0 at `top_k` 1 and 3 and only 15.4 % at 5 in the course measurement, so a bigger `top_k` does not repair a broken index.

**Residual risk.** A class of failure that passes recall, precision and faithfulness at the same time: the agent finds the right rule and applies it wrongly.

```
not covered                  right rule found, applied wrongly (a dispute 63 days after the
                             transaction approved under a 60-day window; TX-0402)
what happens if it breaks    the dispute is approved outside the window, all three metrics stay green
why we live with it now      the L03 cases that compare with the engine already cover it
                             (DIS-006, DIS-010)
defer / accept               defer: re-check when the corpus or the rules change
```

**Source of the reference.** Recall is counted against a reference that we chose. An incomplete reference gives a green recall on incomplete context. For the report the reference facts were taken from the Verta files. For the 12 retrieval cases the reference is a passage copied from the corpus, and `generate_retrieval.py` checks that the passage is really in the file.

## Last line

```
what we traded                  precision (0.4 at top_k 5) and about 200 more input tokens per
                                search turn, in return for complete answers
what we do not do               we do not buy a bigger model for this, and we do not re-index
                                or add reranking now
what would change the decision  needed fragments ranking below fifth on other questions (the
                                retrieval cases start failing on clean), the token bill or
                                latency becoming a problem, or the chunking being changed
```
