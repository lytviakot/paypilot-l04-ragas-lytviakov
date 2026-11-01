"""Build the retrieval cases for golden.jsonl.

The reference of every case is a passage copied from the Verta corpus.
The script checks that the passage really is in the file, so nobody can
write a reference by looking at what the agent answered.

Run on the host (plain Python, no packages):
    python generate_retrieval.py > sets/_retrieval_generated.jsonl
"""
import json
import os
import re
import sys
from pathlib import Path

CORPUS = Path(os.environ.get(
    "CORPUS_DIR", "../paypilot-stand-main/app/rag/corpus"))

# id, question, corpus file, reference passage, regex the answer must match,
# source (complaint / edge / corpus), complaint id, what breaks, severity
CASES = [
    ("RET-001",
     "Search the documentation and quote the exact FX spread table for every tier, with the free monthly conversion allowance.",
     "tariffs.md",
     "| Tier 1 | 1.5% | EUR 500 | | Tier 2 | 0.9% | EUR 1,000 | | Tier 3 | 0.5% | EUR 5,000 |",
     r"(?![\s\S]*1,500)(?=[\s\S]*1\.5\s*%)(?=[\s\S]*0\.9\s*%)(?=[\s\S]*0\.5\s*%)(?=[\s\S]*5,000)",
     "complaint", "C-13", "chunked_table", "high"),
    ("RET-002",
     "What is the free monthly conversion allowance for a Tier 3 customer?",
     "tariffs.md",
     "| Tier 3 | 0.5% | EUR 5,000 |",
     r"5,000",
     "complaint", "C-13", "chunked_table", "high"),
    ("RET-003",
     "Search the documentation and give me BOTH the reason code list AND the exact dispute window in days for a duplicate charge.",
     "disputes.md",
     "| duplicate_charge | 60 |",
     r"(?=[\s\S]*fraud_card_not_present)(?=[\s\S]*goods_not_received)(?=[\s\S]*service_not_rendered)(?=[\s\S]*unauthorized_debit)(?=[\s\S]*\b60\b)",
     "complaint", "C-14", "split_answer", "high"),
    ("RET-004",
     "How many days do I have to file a dispute for a duplicate charge?",
     "disputes.md",
     "| duplicate_charge | 60 |",
     r"\b60\b",
     "corpus", None, "chunked_table", "high"),
    ("RET-005",
     "Which dispute reason code has the shortest window, and how many days is it?",
     "disputes.md",
     "| unauthorized_debit | 56 |",
     r"(?=[\s\S]*unauthorized_debit)(?=[\s\S]*\b56\b)",
     "edge", None, "chunked_table", "medium"),
    ("RET-006",
     "How much is the fee for a SWIFT transfer?",
     "tariffs.md",
     "| SWIFT | EUR 15.00 | 0.3% |",
     r"(?=[\s\S]*\b15(?:\.00)?\b)(?=[\s\S]*0\.3\s*%)",
     "corpus", None, "no_search", "high"),
    ("RET-007",
     "Search the documentation once and tell me both the FX spread and the daily transfer limit for Tier 2.",
     "limits.md",
     "| Tier 2 | EUR 20,000 | EUR 200,000 |",
     r"(?=[\s\S]*0\.9\s*%)(?=[\s\S]*20,000)",
     "edge", None, "split_answer", "high"),
    ("RET-008",
     "What is the cut-off time for SWIFT transfers?",
     "transfers.md",
     "SWIFT transfers submitted after 14:00 CET are processed the next business day.",
     r"14:00",
     "corpus", None, "missed_fragment", "medium"),
    ("RET-009",
     "How quickly is provisional credit applied when a fraud dispute is over EUR 50?",
     "disputes-process.md",
     "a provisional credit is applied within two business days.",
     r"\b(?:two|2) business days\b",
     "corpus", None, "missed_fragment", "medium"),
    ("RET-010",
     "How long does a card authorisation hold last?",
     "accounts.md",
     "A card authorisation places a hold for up to 7 calendar days.",
     r"\b(?:7|seven)\b",
     "corpus", None, "missed_fragment", "low"),
    ("RET-011",
     "During which hours can I talk to a human agent?",
     "service-levels.md",
     "Human agents are available 08:00-20:00 CET;",
     r"(?=[\s\S]*08:00)(?=[\s\S]*20:00)",
     "corpus", None, "missed_fragment", "medium"),
    ("RET-012",
     "If a conversion crosses the free allowance boundary, is the spread charged only on the part above it?",
     "fx-operations.md",
     "A conversion that would cross the allowance boundary has the tier spread applied to the entire conversion, not only to the portion above the boundary.",
     r"\b(?:entire|whole)\s+(?:conversion|amount)\b",
     "edge", None, "missed_fragment", "high"),
]


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main() -> int:
    sys.stdout.reconfigure(newline="\n")  # keep LF on Windows, the set_hash depends on it
    bad = 0
    for (cid, question, doc, ref, pattern, source, complaint,
         failure, severity) in CASES:
        path = CORPUS / doc
        if squash(ref) not in squash(path.read_text(encoding="utf-8")):
            print(f"{cid}: reference not found in {doc}", file=sys.stderr)
            bad += 1
            continue
        meta = {
            "layer": "retrieval",
            "oracle": "corpus",
            "assertion": "regex",
            "pattern": pattern,
            "reference": ref,
            "corpus_source": doc,
            "source": source,
            "failure_mode": failure,
            "severity": severity,
            "runs": 1,
            "gate": "daily",
            "added_in": "hw3",
            "why_this_level": "the key fact is a number or a code word from the docs, so a pattern is enough",
        }
        if complaint:
            meta["complaint"] = complaint
        case = {
            "id": cid,
            "input": question,
            "expected_output": f"answer contains the facts of: {ref}",
            "context": {"clock": "2026-09-15T10:00:00Z"},
            "additional_metadata": meta,
        }
        print(json.dumps(case, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
