"""Combine check results into one score and a route. Advisory only: nothing here declines a loan."""
from checks import FILE_CHECKS, links, suspect_list


def score_file(rec, cfg, link_index, suspects):
    tol = cfg["tolerance"][rec["segment"]]
    results = {name: fn(rec, tol) for name, fn in FILE_CHECKS.items()}
    results["links"] = links(rec, link_index)
    results["suspect_list"] = suspect_list(rec, suspects)
    # "noisy OR": each check independently raises suspicion; several weak signals add up,
    # and one strong signal is enough. Easy to explain: score = 1 - product(1 - weight * strength).
    clean = 1.0
    reasons = []
    for name, (strength, reason, evidence) in results.items():
        contribution = cfg["weights"][name] * strength
        clean *= 1 - contribution
        if strength > 0:
            reasons.append({"check": name, "strength": round(strength, 2),
                            "contribution": round(contribution, 2), "reason": reason, "evidence": evidence})
    reasons.sort(key=lambda r: -r["contribution"])
    return round(1 - clean, 4), reasons


def threshold_for_cap(scores, flag_cap):
    """Lowest score that keeps the share of flagged files at or under the cap."""
    ranked = sorted(scores, reverse=True)
    k = max(1, int(len(ranked) * flag_cap))
    return max(ranked[k - 1], 0.0001)


def route(score, threshold, priority_score):
    if score >= max(threshold, priority_score):
        return "REVIEW_PRIORITY"       # confident: investigator sees it first
    if score >= threshold:
        return "REVIEW"                # uncertain: human review queue
    return "CLEAR"                     # passes on untouched
