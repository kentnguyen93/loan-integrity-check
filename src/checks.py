"""The cross-checks. Each returns (strength 0..1, reason, evidence dict).

Every check compares something the applicant declared with something the bank
can observe, or looks for links between applicants. Each is a few lines so an
investigator, an auditor or a reviewer can read exactly why a file was flagged.
"""
from collections import defaultdict


def _ramp(x, start, full):
    """0 below `start`, 1 above `full`, straight line between."""
    if x <= start:
        return 0.0
    return min(1.0, (x - start) / (full - start))


def revenue_gap(rec, tol):
    ratio = rec["declared_revenue"] / max(1, rec["inflows_12m"])
    s = _ramp(ratio, tol["revenue_gap_start"], tol["revenue_gap_full"])
    return s, f"Declared revenue is {ratio:.1f}x the money seen in the account", {
        "declared_revenue": rec["declared_revenue"], "inflows_12m": rec["inflows_12m"], "ratio": round(ratio, 2)}


def invoice_gap(rec, tol):
    ratio = rec["invoice_total"] / max(1, rec["inflows_12m"])
    s = _ramp(ratio, tol["invoice_gap_start"], tol["invoice_gap_full"])
    return s, f"Invoices issued are {ratio:.1f}x the money received", {
        "invoice_total": rec["invoice_total"], "inflows_12m": rec["inflows_12m"], "ratio": round(ratio, 2)}


def round_trip(rec, tol):
    share = rec["related_return_share"]
    s = _ramp(share, 0.20, 0.55)
    return s, f"{share:.0%} of inflows went straight back to related accounts", {"related_return_share": share}


def spike(rec, tol):
    m = rec["monthly_inflows"]
    before, last = sum(m[:9]) / 9, sum(m[9:]) / 3
    ratio = last / max(1, before)
    s = _ramp(ratio, 1.8, 3.2)
    return s, f"Inflows in the last 3 months are {ratio:.1f}x the earlier average", {
        "avg_first_9_months": round(before), "avg_last_3_months": round(last), "ratio": round(ratio, 2)}


def tenure(rec, tol):
    t = rec["tenure_months"]
    s = 1.0 if t < 6 else 0.0
    return s, f"Account is only {t} months old", {"tenure_months": t}


def build_link_index(recs):
    """Who shares a director, phone or address with whom."""
    idx = {k: defaultdict(list) for k in ("director", "phone", "address")}
    for r in recs:
        for k in idx:
            idx[k][r[k]].append(r["id"])
    return idx


def links(rec, index):
    shared = {}
    for k in ("director", "phone", "address"):
        others = [x for x in index[k][rec[k]] if x != rec["id"]]
        if others:
            shared[k] = others
    n_people = len(set(shared.get("director", []) + shared.get("phone", [])))
    n_addr = len(shared.get("address", []))
    # a shared phone or director is strong; a shared address alone is weak (markets, office blocks)
    s = min(1.0, 0.45 * n_people + 0.12 * n_addr)
    what = ", ".join(f"{k} with {len(v)} other applicant(s)" for k, v in shared.items())
    return s, f"Shares {what}" if shared else "No links", {"shared": shared}


def suspect_list(rec, suspects):
    hit = [k for k in ("director", "phone", "address") if rec[k] in suspects]
    return (1.0 if hit else 0.0), f"Matches the suspect list on {', '.join(hit)}" if hit else "No match", {"matched_on": hit}


FILE_CHECKS = {"revenue_gap": revenue_gap, "invoice_gap": invoice_gap, "round_trip": round_trip,
               "spike": spike, "tenure": tenure}
