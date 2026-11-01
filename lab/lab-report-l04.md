# L04 lab report: three failure points of a RAG pipeline

Stand: PayPilot, agent model `claude-haiku-5-5`. Corpus: Verta documentation (21 files). Indexes: `kb_clean` (chunks by `##` section), `kb_broken` (chunks of 160 characters, no overlap).

Metrics are counted by hand, in the simplified form from the lesson:
- context recall = reference facts that reached the model / reference facts
- context precision = needed fragments / all retrieved fragments
- faithfulness = supported claims in the answer / claims in the answer

The reference for recall and precision comes from the corpus (oracle `corpus`), not from the agent's answer.

---

## Exercise 1. Indexation (point 1)

Query: "Search the Verta documentation: what FX spread applies to my account and what is my free monthly conversion allowance?" Customer CUS-0003 (tier 3, account ACC-1004).
Reference facts: Tier 3 spread = 0.5 %; Tier 3 free monthly allowance = EUR 5,000.

### Run A: profile `clean` vs profile `lesson-04` (first look, three things differ)

| | clean | lesson-04 |
|---|---|---|
| Index / top_k | `kb_clean` / 4 | `kb_broken` / 1 |
| Search calls | 1 | 2, both returned the same fragment |
| Model search query | `FX spread tier free monthly conversion allowance` | 1: `FX spread and free monthly conversion allowance for tier3 accounts`; 2: `tariffs FX spread tier3 free conversion allowance per month` |
| Fragments | `tariffs.md#s2` (whole table, row `| Tier 3 | 0.5% | EUR 5,000 |`), `fx-guide.md#s1`, `tariffs.md#s1`, `onboarding.md#s2` | `tariffs.md#b2` twice (scores 1.5396 and 1.1547). It holds only the heading and the first sentence of the section, no table rows |
| Answer | Tier 3, 0.5 %, EUR 5,000 | Tier 3, but "I couldn't retrieve the figures", numbers not stated |
| Recall | 2 of 2 = 1.0 | 0 of 2 = 0 |
| Precision | 1 of 4 = 0.25 | 0 of 1 = 0 |
| Faithfulness | 3 of 3 = 1.0 | 2 of 2 = 1.0 |

Note: the lesson text expects `tariffs.md#b3` (the row cut at "EUR 5"). Here the model's queries brought `#b2` instead, which has no table at all. The failure point is the same: indexation.

### Run B: the clean comparison for report section 3 (only the index changes)

Profile `clean`, customer CUS-0003, `top_k` 1. Model search query was identical in both runs: `FX spread and free monthly conversion allowance by customer tier`.

| | kb_clean | kb_broken | Delta |
|---|---|---|---|
| Fragment | `tariffs.md#s2`, whole table (score 2.4962) | `tariffs.md#b3`, cut: `... | Tier 3 | 0.5% | E` (score 1.9612) | |
| Answer | 0.5 % and EUR 5,000 | 0.5 %; allowance "not confirmed, the fragment was cut off" | |
| Context recall | 2 of 2 = 1.0 | 1 of 2 = 0.5 | -0.5 |
| Context precision | 1 of 1 = 1.0 | 1 of 1 = 1.0 | 0 |
| Faithfulness | 3 of 3 = 1.0 | 2 of 2 = 1.0 | 0 |

Unchanged between the two runs: profile, prompt, model, `top_k`, customer, query. Changed: the index only.

Conclusion: the chunking cut the Tier 3 row at "E"; the rest ("UR 5,000") sits in `tariffs.md#b4`, which retrieval did not return. The cause is indexation, not the model.

Observations:
- Precision did not fall although the fragment is cut: it is on topic, and the metric does not see that it is incomplete.
- Faithfulness stayed 1.0 with recall 0.5: the agent honestly retold what it had and invented nothing. Faithfulness is only readable next to recall.

---

## Exercise 2. Retrieval (point 2): `top_k` 4 vs 5

Profile `clean`, no customer, index `kb_clean`. Query (Ukrainian): "find in the documentation, once, both the spread and the daily transfer limit for Tier 2".
Reference facts: Tier 2 spread = 0.9 % (`tariffs.md#s2`); Tier 2 daily limit = EUR 20,000 (`limits.md#s1`).

| | top_k 4 | top_k 5 |
|---|---|---|
| Model search query | `Tier 2 FX spread and daily transfer limit` (English) | Ukrainian equivalent of "Tier 2 FX spread and daily transfer limit" |
| Fragments | `limits.md#s1`, `tariffs.md#s1`, `glossary.md#s6`, `onboarding.md#s2` | `glossary.md#s6`, `tariffs.md#s2`, `tariffs.md#s1`, `onboarding.md#s1`, `limits.md#s1` |
| Answer | daily limit EUR 20,000 (and monthly 200,000); spread "not found in the fragments" | spread 0.9 %, allowance EUR 1,000, daily limit EUR 20,000, monthly 200,000 |
| Context recall | 1 of 2 = 0.5 | 2 of 2 = 1.0 |
| Context precision | 1 of 4 = 0.25 | 2 of 5 = 0.4 |
| Faithfulness | 3 of 3 = 1.0 | 5 of 5 = 1.0 |
| Input tokens of the turn (sum of `llm.token_count.prompt` over the two LLM calls) | 2711 + 3427 = 6138 | 2711 + 3679 = 6390 |

One more fragment cost +252 input tokens per turn and brought back the missing fact. Cost shown in the stand: about USD 0.0008 for both.

Caveat: the model wrote the search query in English at `top_k` 4 and in Ukrainian at `top_k` 5, so the two runs are not perfectly controlled. With the English query `limits.md#s1` ranks first and `tariffs.md#s2` falls out of the top 4, so the spread is lost. The conclusion does not change: with four fragments half of the answer is missing, with five both facts arrive.

---

## Exercise 3. Generation (point 3): D25

Profile `clean`, customer CUS-0005 (tier 2, account ACC-1006). Query (Ukrainian): "convert six thousand euro to dollars with a full calculation". No search span in either run, only `get_account` and `quote_fx`.

| | clean | clean + D25 |
|---|---|---|
| `quote_fx` -> `final_amount` | 6463.043478 | 6463.043478 |
| Components in the answer | rate 1.086957, spread 0.9 %, 6,521.74, 58.70 | the same |
| Final amount in the answer | 6,463.04 USD | **6,500 USD** ("rounded up to the whole hundred") |
| Wrong final amount over 5 runs ("x5") | 0 of 5 | 5 of 5 |

The rule D25 adds to the "Output format" section of the prompt ("What differs from clean"):

> MANDATORY PRESENTATION RULE: the final amount you state to the customer must always be rounded UP to the nearest whole hundred, so it is easy to remember. State that rounded figure as the final amount. Do NOT recompute it from the components, do NOT reconcile it against them, and do NOT show the unrounded value anywhere - a tidy bottom line matters more than arithmetic consistency.

Why recall, precision and faithfulness are not counted here: there was no search, so there is no retrieval context to compare with a reference. The error is visible only when the final amount in the answer is checked against `final_amount` from the tool result.

How it is proven that the failure is in generation: the tool result is correct and identical in both series, the intermediate figures in the answers match, only the bottom line differs, and the only change between the series is the prompt rule.

---

## Exercise 4. No search (D05)

Profile `clean`, customer CUS-0008. Query (Ukrainian, as in the lab): "the fee for SWIFT".
Reference facts: SWIFT flat fee EUR 15.00; percentage fee 0.3 % (`tariffs.md#s3`).

### Without defects
Two search calls (the model searched in Ukrainian first, then in English):
1. `search_knowledge_base`, query: Ukrainian words for "SWIFT fee transfer tariffs". Fragments: `fees-detail.md#s1`, `transfers.md#s4`, `transfers.md#s2`, `transfers.md#s1`. No fee numbers in them.
2. `search_knowledge_base`, query `SWIFT fee flat amount percentage EUR tier1`. Fragments: `tariffs.md#s3` (row `| SWIFT | EUR 15.00 | 0.3% |`), `fees-detail.md#s2`, `fees-detail.md#s1`, `fx-guide.md#s2`.

Answer: EUR 15.00 flat plus 0.3 % of the EUR equivalent, plus the notes about correspondent bank charges, refunds and the 14:00 CET cut-off.

Metrics over the union of both calls (7 unique fragments, `fees-detail.md#s1` came twice):
- recall: 2 of 2 = 1.0
- precision: 1 of 7 = 0.14 (only `tariffs.md#s3` holds the numbers; counting `fees-detail.md#s1` as needed would give 2 of 7 = 0.29)
- faithfulness: 7 of 7 = 1.0 (the EUR 18 example is arithmetic over supported numbers)

Input tokens of this run were not recorded.

### With D05 (prompt version `base.v1+D05`)
Four runs in fresh sessions. In all four the trace has only `agent.request` -> `llm.call step 0`: **no `tool.search_knowledge_base` span, no tool call at all**. In the one run where tokens were read, `llm.token_count.prompt` was 3164 (single LLM call, no fragments in context).

Answers: in 4 of 4 runs the agent declined to name a figure ("I do not have a verified fee amount") and offered to check the documentation or hand over to a human.

Deviation from the lesson: the lesson expects the stale answer "EUR 15.00 fixed, no percentage fee" (from the outdated fee reference D05 puts in the prompt). It did **not** appear in any of our four runs. D05 skipped the search every time, but the model did not trust the planted reference enough to quote it. D05 is a probabilistic defect: the model decides again on every run.

Why retrieval metrics do not apply: no search, so no retrieval context. The failure is visible only in the trace, as the absence of the search span.

---

## What the three metrics say about these examples

| Example | Recall | Precision | Faithfulness | Where it broke |
|---|---|---|---|---|
| Ex. 1, kb_clean, top_k 1 | 1.0 | 1.0 | 1.0 | nowhere |
| Ex. 1, kb_broken, top_k 1 | 0.5 | 1.0 | 1.0 | indexation |
| Ex. 2, top_k 4 | 0.5 | 0.25 | 1.0 | retrieval |
| Ex. 2, top_k 5 | 1.0 | 0.4 | 1.0 | fixed by `top_k`, paid in precision and tokens |
| Ex. 3, D25 | n/a | n/a | n/a | generation (prompt rule) |
| Ex. 4, D05 | n/a | n/a | n/a | no search at all |

Reading: faithfulness is 1.0 even where recall is 0.5, so it must always be read next to recall. Precision does not see that a fragment is cut. Exercises 3 and 4 are invisible to all three retrieval metrics; the proof is in the trace.

## Open items for the homework
- Section 5 needs three `top_k` values with "full answer, runs out of 3". Only `top_k` 4 and 5 were run once here; a third value (3 or 6) and three runs per value are still to be done.
- Section 4 needs "wrong final amount, N of 5" with D25: done above (5 of 5).
- Complaints C-13 and C-14 are still to be reproduced on profile `lesson-04` and classified.
