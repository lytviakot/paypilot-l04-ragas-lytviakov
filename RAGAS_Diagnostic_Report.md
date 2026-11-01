# RAGAS Diagnostic Report: PayPilot

When the support agent gives a wrong answer, where did it break: before the model or in it? And is a more expensive model the fix?

Short answer: in two of the four cases below it broke before the model (chunking, retrieval). In the other two a rule in the prompt caused it. A bigger model would not have fixed any of them.

Metrics are counted by hand as "n of m". Recall: how many facts of the reference reached the model. Precision: how many retrieved fragments are needed. Faithfulness: how many claims in the answer are backed by what the agent retrieved. The reference always comes from the Verta docs.

## 1. Context

```
system        PayPilot support agent (Verta)
corpus        Verta documentation, 21 files
indexes       kb_clean (chunks by section) / kb_broken (chunks of 160 characters)
profiles      clean, lesson-04
model         claude-haiku-5-5
set           golden.jsonl, 43 cases, 12 of them retrieval, set_hash b483bff25cf7
runs          2026-11-01
```

## 2. Localisation

| Case | Symptom | Failure point | Evidence from the trace |
|---|---|---|---|
| Ex. 1: Tier 3 spread and allowance, `lesson-04` | agent cannot confirm the allowance | indexation | `tariffs.md#b2` twice: heading only, no table rows |
| Ex. 2: Tier 2 spread and daily limit, `top_k` 4 | spread "not found" | retrieval | 4 fragments, no `tariffs.md#s2` |
| Ex. 3: convert 6,000 EUR, D25 | final amount 6,500 | generation | no search; `quote_fx` returned `final_amount` 6463.04 |
| Ex. 4: SWIFT fee, D05 | agent did not search, gave no figure | generation (no search) | trace has only `llm.call`, no `search_knowledge_base` span, 4 runs of 4 |
| C-13: wrong Tier 3 allowance in a table | table without the Tier 3 allowance ("cut off"); the wrong EUR 1,500 did not appear | indexation | `tariffs.md#b3` in two searches: `... \| Tier 3 \| 0.5% \| E` |
| C-14: half an answer | not reproduced | n/a | `disputes.md#s1` holds the codes and the windows in one table, so `top_k` 1 was enough; both parts answered in 2 of 2 searches |

Split: indexation 2 · retrieval 1 · generation 2 · not reproduced 1.

On C-13 the agent refused to guess, so only the cause (the cut table) reproduced, not the wrong number. In the repeated tries inside one session the agent reused its first search, so those were not counted as independent.

## 3. Proof of cause

Question: "Search the Verta documentation: what FX spread applies to my account and what is my free monthly conversion allowance?" Customer CUS-0003, profile `clean`, `top_k` 1. The model used the same search query in both runs.

| Metric | `kb_clean` | `kb_broken` | Delta |
|---|---|---|---|
| context recall | 2 of 2 = 1.0 | 1 of 2 = 0.5 | -0.5 |
| context precision | 1 of 1 = 1.0 | 1 of 1 = 1.0 | 0 |
| faithfulness | 3 of 3 = 1.0 | 2 of 2 = 1.0 | 0 |

Unchanged: profile, prompt, model, `top_k`, customer, question. Changed: the index only.

In `kb_broken` the Tier 3 row is cut at "E". The rest ("UR 5,000") is in the next chunk, which search does not return. The agent said the allowance was not confirmed and made nothing up. That is why precision and faithfulness stay at 1.0: the fragment is on topic and the answer is honest. Only recall shows the problem.

**Conclusion:** same prompt, model, question and `top_k`; only the index changed, and recall fell from 1.0 to 0.5. The cause is chunking, not the model.

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

Recall, precision and faithfulness are not counted: there was no search, so there is no retrieved context to compare with.

Why it is generation: the tool result is correct and the same in both series, the rate, spread and gross amount in the answers match, and the only difference is one rule in the prompt.

Control, D05 (SWIFT fee, CUS-0008): no search span in 4 of 4 runs, but the wrong "EUR 15.00 fixed" answer from the lesson never appeared. The agent refused to name a figure each time. On `clean` it searches and answers correctly (EUR 15.00 plus 0.3 %, `tariffs.md#s3`).

## 5. Trade-off

Question: "Search the documentation once and tell me both the FX spread and the daily transfer limit for Tier 2." Profile `clean`, index `kb_clean`, no customer. Reference: spread 0.9 % (`tariffs.md#s2`), daily limit EUR 20,000 (`limits.md#s1`).

| `top_k` | recall | precision | full answer, runs of 3 | input tokens of the turn |
|---|---|---|---|---|
| 4 | 1 of 2 = 0.5 | 1 of 4 = 0.25 | 0 of 3 | 5,960 |
| 5 | 2 of 2 = 1.0 | 2 of 5 = 0.4 | 3 of 3 | 6,169 |
| 6 | 2 of 2 = 1.0 | 2 of 6 = 0.33 | 3 of 3 | 6,309 |

All 9 runs come from `measure_topk.py` (data in `reports/4-topk-runs.json`), each in a fresh session. The model searched in English with the same query every time, so runs with the same `top_k` returned the same fragments. At `top_k` 4 the limit table ranks first and the spread table falls out; at 5 it comes in as the fifth fragment; at 6 only an unrelated fragment is added.

4 to 5 costs +209 input tokens per turn (+3.5 %) and fixes the answer. 5 to 6 costs another +140 and gains nothing.

Broken index (`kb_broken`, CUS-0003, question from section 3, 3 runs each, `reports/5-broken-index-runs.json`): at `top_k` 1 and at `top_k` 5 the missing chunk `tariffs.md#b4` never arrived, and the agent never named EUR 5,000 (0 of 3 both times). At 5 the search only added fragments from other files. A bigger `top_k` does not repair a broken index; only re-indexing does.

**Chosen value: `top_k` 5.** Price: precision 0.4 (three of five fragments are not needed) and about 200 more input tokens per search turn. Under the Ship it mandate completeness comes first, and the extra cost is small. Limit: this was measured on one question; on other questions the needed fragment may rank below fifth.

## 6. Decision and limits

| Failure point | Fix | Cost | Time to ship | What gets worse | Can a prompt fix it? |
|---|---|---|---|---|---|
| Indexation | re-chunk by section or table row, rebuild the index | about USD 160 to 320, almost all of it people (formula below) | 1 to 2 days | answers that worked before may change | no: a cut row cannot be rebuilt from text |
| Retrieval | `top_k` 5 now; reranking later | about USD 0.02 per 1,000 search turns, plus about USD 10 of work (formula below) | `top_k`: half a day. Reranking: 3 to 5 days, not planned | precision 0.4 | no: the prompt cannot add a fragment that was not returned |
| Generation | delete the rounding rule from the prompt | about USD 10 of work (formula below) | half a day, including a run of the set | other cases can change | yes, this is the only one |

How the costs are counted. Prices of the agent model, `claude-haiku-5-5`, are the published ones: USD 0.10 per million input tokens and USD 0.50 per million output tokens (prompts up to 100K tokens). The engineer rate of USD 20 per hour is an assumption. The hours are my estimates, not measurements.

```
re-index    documents x tokens per document x embedding price + hours x rate
            21 x ~230 x 0 + (8 to 16) x 20
            = USD 0 + USD 160 to 320
retrieval   extra tokens x search turns x input price + hours x rate
            209 x 1,000 x 0.10 / 1,000,000 + 0.5 x 20
            = USD 0.02 per 1,000 turns + USD 10 (top_k 5 only; reranking would be 24 to 40 hours, USD 480 to 800)
generation  hours x rate + one run of the set
            0.5 x 20 + 0.03 = USD 10
```

Embedding price. The stand has no embeddings: `retriever.py` splits the files into chunks and matches words in memory when the stand starts. So the embedding term is 0 here. With a real embedding model the term is documents x tokens x price. This corpus is 21 files, about 19,000 characters, about 4,800 tokens (characters divided by 4), so even at USD 0.10 per million it would be under a cent.

Where the 8 to 16 hours of re-indexing come from: choose the chunking and change the chunker, 2 to 3 hours; rebuild the index (21 files, seconds); run the 43 cases on both indexes and compare, 1 hour; look at what changed and fix the cases that broke, 3 to 6 hours; review and release, 1 to 2 hours. That adds up to 7 to 12 hours; with a buffer for surprises I take 8 to 16, one to two working days. One run of the 43 cases costs about USD 0.03 (about 6,000 input tokens per case) and takes under 4 minutes.

**Residual risk.** A class of failure that passes recall, precision and faithfulness together: the agent finds the right rule and applies it wrongly.

```
not covered                  right rule found, applied wrongly (a dispute 63 days after the
                             transaction approved under a 60-day window, TX-0402)
what happens if it breaks    the dispute is approved outside the window; all three metrics stay green
why we live with it now      cases that compare with the engine already cover it (DIS-006, DIS-010)
defer / accept               defer: re-check when the corpus or the rules change
```

**Source of the reference.** Recall is only as good as the reference. An incomplete reference gives green recall on incomplete context. For this report the reference facts come from the Verta files. For the 12 retrieval cases the reference is a passage copied from the corpus, and `generate_retrieval.py` checks the passage is really in the file.

## Last line

```
what we traded                  precision (0.4 at top_k 5) and about 200 tokens per search turn,
                                for complete answers
what we do not do               we do not buy a bigger model, and we do not add reranking yet;
                                we re-index only if chunks are cut like in kb_broken
what would change the decision  needed fragments ranking below fifth on other questions (the
                                retrieval cases start failing on clean), or the token bill
                                or latency becoming a problem
```
