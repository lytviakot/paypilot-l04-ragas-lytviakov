"""Section 5 of the report: run one question at several top_k values.

For every run it records the fragments the search returned, the answer,
and the input tokens of the whole turn. Each run is a fresh session.

Uses stand.py from the kit, so give it the kit folder:
    python measure_topk.py ../paypilot-l03-eval > reports/4-topk-runs.json
The stand must be running on localhost:8000.
"""
import json
import os
import re
import sys

kit = sys.argv[1] if len(sys.argv) > 1 else "../paypilot-l03-eval"
sys.path.insert(0, kit)
import stand  # noqa: E402

QUESTION = ("Search the documentation once and tell me both the FX spread "
            "and the daily transfer limit for Tier 2.")
TOP_KS = [4, 5, 6]
RUNS = 3

stand.set_profile("clean")
stand.set_defects(None)

out = []
for top_k in TOP_KS:
    os.environ["STAND_SETTINGS"] = json.dumps(
        {"top_k": top_k, "index": "kb_clean"})
    for n in range(1, RUNS + 1):
        res = stand.chat(QUESTION)
        tree = stand.trace(res["request_id"])
        searches = [c for c in stand.tool_calls(tree)
                    if c["name"] == "search_knowledge_base"]
        fragments = [f["id"] for c in searches
                     for f in (c["result"] or {}).get("fragments", [])]
        answer = res.get("answer", "")
        usage = res.get("usage") or {}
        out.append({
            "top_k": top_k,
            "run": n,
            "search_calls": len(searches),
            "search_query": searches[0]["arguments"]["query"] if searches else None,
            "fragments": fragments,
            "has_spread": bool(re.search(r"0\.9\s*%", answer)),
            "has_daily_limit": "20,000" in answer,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "answer": answer,
        })
        print(f"top_k {top_k} run {n}: {len(fragments)} fragments, "
              f"spread={out[-1]['has_spread']} limit={out[-1]['has_daily_limit']} "
              f"in={usage.get('input_tokens')}", file=sys.stderr)

print(json.dumps(out, indent=2, ensure_ascii=False))
