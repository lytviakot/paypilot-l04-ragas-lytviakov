""
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.engines import disputes, fx, limits, policy

AS_OF = date(2026, 9, 15)

CUSTOMERS = {
    "CUS-0001": ("tier1", 120.0),
    "CUS-0002": ("tier2", 800.0),
    "CUS-0005": ("tier2", 5000.0),
    "CUS-0007": ("tier2", 0.0),
    "CUS-0010": ("tier3", 15000.0),
}


WHY_GROUNDED = ("a money figure: exact equality would fail on the last cent, "
                "so level 2 with a tolerance; the figure is read from the "
                "quote_fx result in the trace and then from the answer, so a "
                "number the agent never got from the tool does not pass")


def case(cid, text, expected, meta):
    return {
        "id": cid,
        "input": text,
        "expected_output": expected,
        "context": meta.pop("context", {}),
        "additional_metadata": meta,
    }


def fx_cases():
    ""
    out = []
    plan = [
        ("FX-001", "CUS-0001", 200, "EUR", "USD"),
        ("FX-002", "CUS-0002", 3000, "EUR", "USD"),
        ("FX-003", "CUS-0005", 6000, "EUR", "USD"),
        ("FX-004", "CUS-0007", 2000, "EUR", "USD"),
        ("FX-005", "CUS-0010", 5000, "GBP", "EUR"),
        # hw2 edges: the free allowance is all-or-nothing
        ("FX-006", "CUS-0007", 1000, "EUR", "USD"),   # exactly on the limit
        ("FX-007", "CUS-0007", 1001, "EUR", "USD"),   # 1 EUR over it
        ("FX-008", "CUS-0001", 380, "EUR", "USD"),    # tier1: 120 used + 380 = 500, the allowance is used up to the cent
        ("FX-009", "CUS-0001", 381, "EUR", "USD"),    # tier1: 1 EUR over, spread on the whole amount
    ]
    for cid, cust, amount, frm, to in plan:
        tier, used = CUSTOMERS[cust]
        q = fx.quote(amount, frm, to, tier, allowance_used_eur=used)
        out.append(case(
            cid,
            f"I'm {cust}. Convert {amount} {frm} to {to}. "
            f"What is the final amount I receive?",
            f"{q.final_amount:.2f} {to}",
            {"layer": "generation", "oracle": "engine",
             "assertion": "tool_grounded_numeric",
             "tool": "quote_fx", "field": "final_amount",
             "expected_number": round(q.final_amount, 2), "tolerance": 0.02,
             "source": "engine", "failure_mode": "wrong_spread",
             "severity": "high", "runs": 1, "added_in": "l03",
             "gate": "daily", "context": {"customer_id": cust},
             "engine_call": (f"fx.quote({amount}, {frm!r}, {to!r}, {tier!r}, "
                             f"allowance_used_eur={used})"),
             "why_this_level": WHY_GROUNDED}))
        if q.spread_pct == 0:
            out.append(case(
                f"{cid}-S", f"I'm {cust}. What spread applies to a {amount} "
                f"{frm} conversion to {to}?",
                "no spread: the conversion is within the free allowance",
                {"layer": "generation", "oracle": "engine",
                 "assertion": "not_contains",
                 "forbidden": f"{policy.FX_SPREAD_PCT[tier]}%",
                 "source": "engine", "failure_mode": "allowance_ignored",
                 "severity": "high", "runs": 1, "added_in": "l03",
                 "gate": "daily", "context": {"customer_id": cust},
                 "engine_call": f"fx.quote(...).spread_pct == 0.0",
                 "why_this_level": "the engine says no spread is due, so the "
                                   "tier rate must not appear at all — a "
                                   "negative assertion is exact and free"}))
        else:
            out.append(case(
                f"{cid}-S", f"I'm {cust}. What spread applies to a {amount} "
                f"{frm} conversion to {to}?",
                f"{q.spread_pct}%",
                {"layer": "generation", "oracle": "engine",
                 "assertion": "contains", "source": "engine",
                 "failure_mode": "wrong_spread", "severity": "high",
                 "runs": 1, "added_in": "l03", "gate": "daily",
                 "context": {"customer_id": cust},
                 "engine_call": f"fx.FX_SPREAD_PCT[{tier!r}] via fx.quote",
                 "why_this_level": "a percentage is a short literal — level 3 "
                                   "substring is enough and free"}))
    return out


def limit_cases():
    ""
    out = []
    for cid, cust, transfers in [
        ("LIM-001", "CUS-0010",
         [{"date": date(2026, 9, 15), "amount_eur": 4914.0},
          {"date": date(2026, 9, 2), "amount_eur": 30420.0}]),
        ("LIM-002", "CUS-0001", []),
    ]:
        tier, _ = CUSTOMERS[cust]
        st = limits.status(tier, AS_OF, transfers)
        out.append(case(
            cid, f"I'm {cust}. How much of my MONTHLY transfer limit is left?",
            f"EUR {st.monthly_remaining_eur:,.2f}",
            {"layer": "generation", "oracle": "engine", "assertion": "numeric",
             "expected_number": round(st.monthly_remaining_eur, 2),
             "tolerance": 1.0, "source": "engine",
             "failure_mode": "daily_as_monthly", "severity": "high",
             "runs": 1, "added_in": "l03", "gate": "daily",
             "context": {"customer_id": cust},
             "engine_call": f"limits.status({tier!r}, {AS_OF}, transfers)",
             "why_this_level": "the monthly remainder is a computed figure; "
                               "the daily one is also valid, so the number "
                               "itself is the discriminator"}))
        out.append(case(
            f"{cid}-D", f"I'm {cust}. What is my remaining DAILY limit today?",
            f"EUR {st.daily_remaining_eur:,.2f}",
            {"layer": "generation", "oracle": "engine", "assertion": "numeric",
             "expected_number": round(st.daily_remaining_eur, 2),
             "tolerance": 1.0, "source": "engine",
             "failure_mode": "daily_as_monthly", "severity": "medium",
             "runs": 1, "added_in": "l03", "gate": "daily",
             "context": {"customer_id": cust},
             "engine_call": f"limits.status({tier!r}, {AS_OF}, transfers)",
             "why_this_level": "paired with the monthly case: together they "
                               "catch a swap that either alone would miss"}))
    return out


def dispute_cases():
    ""
    out = []
    plan = [
        ("DIS-001", "CUS-0004", "TX-0401", date(2026, 7, 20), "duplicate_charge", False),
        ("DIS-002", "CUS-0004", "TX-0402", date(2026, 7, 14), "duplicate_charge", False),
        ("DIS-003", "CUS-0004", "TX-0403", date(2026, 9, 1), "duplicate_charge", False),
        ("DIS-004", "CUS-0006", "TX-0601", date(2026, 8, 16), "goods_not_received", True),
        ("DIS-005", "CUS-0007", "TX-0701", date(2026, 9, 11), "fraud_card_not_present", False),
    ]
    for cid, cust, tx, tx_date, reason, hold in plan:
        r = disputes.check(reason, tx_date, "settled", AS_OF, hold)
        window = policy.DISPUTE_WINDOWS_DAYS[reason]
        out.append(case(
            cid,
            f"Transaction {tx} was on {tx_date.strftime('%d %B %Y')}. "
            f"Reason: {reason.replace('_', ' ')}. What is the dispute window "
            f"for this reason code, in days?",
            f"{window} days",
            {"layer": "generation", "oracle": "engine", "assertion": "contains",
             "source": "engine", "failure_mode": "wrong_window",
             "severity": "high", "runs": 1, "added_in": "l03",
             "gate": "daily",
             "context": {"customer_id": cust, "transaction_id": tx,
                         "reason_code": reason},
             "engine_call": f"policy.DISPUTE_WINDOWS_DAYS[{reason!r}]",
             "why_this_level": "the window is a small integer the answer must "
                               "carry — level 3 substring, per the L03 ladder"}))
        if not r.eligible:
            out.append(case(
                f"{cid}-N",
                f"Transaction {tx} was on {tx_date.strftime('%d %B %Y')}. "
                f"Reason: {reason.replace('_', ' ')}. Can I still dispute it?",
                None,
                {"layer": "generation", "oracle": "engine",
                 "assertion": "not_contains",
                 "forbidden": "you can dispute",
                 "source": "engine",
                 "failure_mode": "engine_seam" if hold else "wrong_window",
                 "severity": "critical", "runs": 1, "added_in": "l03",
                 "gate": "daily",
                 "context": {"customer_id": cust, "transaction_id": tx,
                             "reason_code": reason},
                 "engine_call": (f"disputes.check({reason!r}, {tx_date}, "
                                 f"'settled', {AS_OF}, "
                                 f"compliance_hold={hold}).eligible is False"),
                 "failing_check": next(
                     (k for k, v in r.checks.items() if v.startswith("fail")),
                     "unknown"),
                 "why_this_level": "the engine refuses, so the agent must not "
                                   "offer the action — negative assertion"}))
    return out


def complaint_cases():
    """hw2: complaints that are not in the demo set, brought to a case."""
    out = []
    # C-11 (CUS-0009): 120 days for a card-not-present fraud dispute
    # C-12 (CUS-0002): 60 days for a duplicate charge
    # both complaints are right, the dispute engine decides per reason code
    for cid, cust, tx, tx_date, reason, complaint in [
        ("DIS-008", "CUS-0009", "TX-0902", date(2026, 9, 12),
         "fraud_card_not_present", "C-11"),
        ("DIS-009", "CUS-0002", "TX-0201", date(2026, 9, 8),
         "duplicate_charge", "C-12"),
    ]:
        window = policy.DISPUTE_WINDOWS_DAYS[reason]
        out.append(case(
            cid,
            f"Transaction {tx} was on {tx_date.strftime('%d %B %Y')}. "
            f"Reason: {reason.replace('_', ' ')}. What is the dispute window "
            f"for this reason code, in days?",
            f"{window} days",
            {"layer": "generation", "oracle": "engine", "assertion": "contains",
             "source": "complaint", "complaint": complaint,
             "failure_mode": "wrong_window", "severity": "high", "runs": 1,
             "added_in": "hw2", "gate": "daily",
             "context": {"customer_id": cust, "transaction_id": tx,
                         "reason_code": reason},
             "engine_call": f"policy.DISPUTE_WINDOWS_DAYS[{reason!r}]",
             "why_this_level": "the window is a small integer the answer "
                               "must carry, so level 3 substring is enough"}))

    # C-03: the TechMart double charge from July, already past the window
    r = disputes.check("duplicate_charge", date(2026, 7, 14), "settled",
                       AS_OF, False)
    assert not r.eligible
    out.append(case(
        "DIS-010",
        "I'm CUS-0004. The TechMart double charge from July, transaction "
        "TX-0402. Can I still dispute it?",
        "must not offer the action (pattern-checked)",
        {"layer": "generation", "oracle": "engine",
         "assertion": "not_regex", "source": "complaint", "complaint": "C-03",
         "failure_mode": "wrong_window", "severity": "critical", "runs": 1,
         "added_in": "hw2", "gate": "daily",
         "context": {"customer_id": "CUS-0004", "transaction_id": "TX-0402",
                     "reason_code": "duplicate_charge"},
         "engine_call": "disputes.check('duplicate_charge', 2026-07-14, "
                        "'settled', 2026-09-15, compliance_hold=False)"
                        ".eligible is False",
         "forbidden_pattern": r"\byou can(?:\s+still)?\s+(?:dispute|open|file)\b"
                              r"|\bis(?:\s+still)?\s+eligible\b"
                              r"|\bremains\s+eligible\b"
                              r"|\bcan\s+be\s+(?:disputed|opened)\b",
         "why_this_level": "the engine refuses, so the agent must not offer "
                           "the action: a negative assertion with a pattern"}))

    # C-09: a supplier payment, the bot gave the daily remainder as monthly
    transfers = [{"date": date(2026, 9, 15), "amount_eur": 4914.0},
                 {"date": date(2026, 9, 2), "amount_eur": 30420.0}]
    st = limits.status("tier3", AS_OF, transfers)
    out.append(case(
        "LIM-005",
        "I'm CUS-0010. I have a big supplier payment coming. How much of my "
        "monthly transfer limit is left?",
        f"EUR {st.monthly_remaining_eur:,.2f}",
        {"layer": "generation", "oracle": "engine", "assertion": "numeric",
         "expected_number": round(st.monthly_remaining_eur, 2),
         "tolerance": 1.0, "source": "complaint", "complaint": "C-09",
         "failure_mode": "daily_as_monthly", "severity": "high", "runs": 1,
         "added_in": "hw2", "gate": "daily",
         "context": {"customer_id": "CUS-0010"},
         "engine_call": f"limits.status('tier3', {AS_OF}, transfers)",
         "why_this_level": "the daily and monthly remainders are both valid "
                           "numbers, the number itself tells them apart"}))
    return out


# the edge cases (and their "-S" spread twins) get the hw2 mark and source "edge"
EDGE_IDS = {"FX-006", "FX-007", "FX-008", "FX-009"}


def main():
    cases = fx_cases() + limit_cases() + dispute_cases() + complaint_cases()
    for c in cases:
        meta = c["additional_metadata"]
        if c["id"] in EDGE_IDS or c["id"].rstrip("-S") in EDGE_IDS:
            meta["source"] = "edge"
            meta["added_in"] = "hw2"
        c["context"].setdefault("clock", "2026-09-15T10:00:00Z")
        c["additional_metadata"] = {k: v for k, v in meta.items() if v is not None}
        print(json.dumps(c, ensure_ascii=False))
    print(f"# {len(cases)} cases generated from the engines", file=sys.stderr)


if __name__ == "__main__":
    main()
