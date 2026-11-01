"""Section 5 check on the broken index.

Same question as lab exercise 1, customer CUS-0003, index kb_broken,
top_k 1 and 5. Does the chunk with the end of the Tier 3 row
(tariffs.md#b4) ever arrive, and does the agent say EUR 5,000?

    python measure_broken.py ../paypilot-l03-eval > reports/5-broken-index-runs.json
"""
import json
import os
import sys

kit = sys.argv[1] if len(sys.argv) > 1 else "../paypilot-l03-eval"
sys.path.insert(0, kit)
import stand  # noqa: E402

QUESTION = ("Search the Verta documentation: what FX spread applies to my "
            "account and what is my free monthly conversion allowance?")
RUNS = 3

stand.set_profile("clean")
stand.set_defects(None)

out = []
for top_k in (1, 5):
    os.environ["STAND_SETTINGS"] = json.dumps(
        {"top_k": top_k, "index": "kb_broken"})
    for n in range(1, RUNS + 1):
        res = stand.chat(QUESTION, customer_id="CUS-0003")
        tree = stand.trace(res["request_id"])
        searches = [c for c in stand.tool_calls(tree)
                    if c["name"] == "search_knowledge_base"]
        fragments = [f["id"] for c in searches
                     for f in (c["result"] or {}).get("fragments", [])]
        answer = res.get("answer", "")
        out.append({
            "top_k": top_k,
            "run": n,
            "search_calls": len(searches),
            "fragments": fragments,
            "got_b4": "tariffs.md#b4" in fragments,
            "says_5000": "5,000" in answer,
            "says_spread": "0.5" in answer,
            "answer": answer,
        })
        print(f"top_k {top_k} run {n}: searches={len(searches)} "
              f"b4={out[-1]['got_b4']} 5000={out[-1]['says_5000']}",
              file=sys.stderr)

print(json.dumps(out, indent=2, ensure_ascii=False))
