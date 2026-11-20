"""Synthetic business-loan applications. No real customer data.

Each record holds what the applicant DECLARES (revenue, invoices) and what the
bank could OBSERVE in its own accounts (inflows, counterparties, links).
Fraud is injected in five schemes, one of which is built to evade every check,
so the evaluation has honest misses. Honest noise (cash-heavy shops, seasonal
spikes, shared market addresses) is included so there are false positives too.
"""
import random

SCHEMES = ["inflated_revenue", "fake_invoices", "round_tripping", "shell_ring", "straw_borrower"]


def _honest(rng, i):
    seg = "SME" if rng.random() < 0.35 else "HOUSEHOLD"
    if seg == "SME":
        revenue = rng.lognormvariate(9.6, 0.8)          # VND million a year, median about 15,000
        capture = rng.uniform(0.70, 1.05)                # share of revenue seen in bank inflows
        invoices = revenue * rng.uniform(0.80, 1.05)
        limit = min(10000, max(300, revenue * rng.uniform(0.05, 0.25)))
    else:
        revenue = rng.lognormvariate(7.3, 0.7)           # median about 1,500
        capture = rng.uniform(0.35, 1.0)                 # cash-heavy: much revenue never hits the account
        invoices = revenue * rng.uniform(0.30, 0.90)
        limit = min(700, max(30, revenue * rng.uniform(0.05, 0.30)))
    inflows = revenue * capture
    monthly = [inflows / 12 * rng.uniform(0.8, 1.2) for _ in range(12)]
    if rng.random() < 0.08:                              # real seasonal peak before applying
        for m in (9, 10, 11):
            monthly[m] *= rng.uniform(1.6, 2.4)
    related_return = rng.betavariate(1.2, 30)
    if rng.random() < 0.03:                              # legitimate group company flows
        related_return = rng.uniform(0.15, 0.35)
    return {
        "id": f"APP-{i:05d}", "segment": seg, "requested_limit": round(limit),
        "declared_revenue": round(revenue * rng.uniform(0.95, 1.10)),
        "invoice_total": round(invoices), "inflows_12m": round(sum(monthly)),
        "monthly_inflows": [round(x) for x in monthly],
        "related_return_share": round(related_return, 3),
        "top_counterparty_share": round(rng.betavariate(2, 6), 3),
        "director": f"D{i:05d}", "address": f"A{i:05d}", "phone": f"P{i:05d}",
        "tenure_months": rng.randint(4, 120), "scheme": None, "is_fraud": False,
    }


def _make_fraud(rng, rec, scheme, careful):
    """Turn an honest record into a fraudulent one. `careful` fraudsters leave weaker traces."""
    k = 0.55 if careful else 1.0
    rec["scheme"], rec["is_fraud"] = scheme, True
    cap = 10000 if rec["segment"] == "SME" else 700
    rec["requested_limit"] = round(min(cap, rec["requested_limit"] * rng.uniform(1.5, 3.0)))
    infl = rec["inflows_12m"]
    if scheme == "inflated_revenue":
        rec["declared_revenue"] = round(infl * (1 + k * rng.uniform(2.5, 6.0)))
    elif scheme == "fake_invoices":
        rec["invoice_total"] = round(infl * (1 + k * rng.uniform(1.5, 5.0)))
        rec["declared_revenue"] = round(rec["invoice_total"] * rng.uniform(0.95, 1.05))
        rec["top_counterparty_share"] = round(rng.uniform(0.5, 0.9), 3)
    elif scheme == "round_tripping":
        boost = 1 + k * rng.uniform(1.0, 3.0)            # turnover pumped by cycling money
        rec["monthly_inflows"] = [round(x * boost) for x in rec["monthly_inflows"]]
        rec["inflows_12m"] = sum(rec["monthly_inflows"])
        rec["declared_revenue"] = round(rec["inflows_12m"] * rng.uniform(0.95, 1.1))
        rec["invoice_total"] = round(rec["inflows_12m"] * rng.uniform(0.85, 1.0))
        rec["related_return_share"] = round(min(0.95, k * rng.uniform(0.45, 0.85)), 3)
    elif scheme == "shell_ring":
        for m in (9, 10, 11):
            rec["monthly_inflows"][m] = round(rec["monthly_inflows"][m] * (1 + k * rng.uniform(1.0, 2.5)))
        rec["inflows_12m"] = sum(rec["monthly_inflows"])
        rec["tenure_months"] = rng.randint(2, 9)
    # straw_borrower: a real, clean business fronting for someone else. Nothing to see in these data.


def generate(n, fraud_rate, seed):
    rng = random.Random(seed)
    recs = [_honest(rng, i) for i in range(n)]
    # honest look-alikes for the link check: shared market addresses, owners with two real businesses
    for _ in range(int(n * 0.02)):
        a, b = rng.sample(recs, 2)
        b["address"] = a["address"]
    for _ in range(int(n * 0.005)):
        a, b = rng.sample(recs, 2)
        b["director"] = a["director"]
    fraud = rng.sample(recs, int(n * fraud_rate))
    weights = [0.25, 0.22, 0.18, 0.20, 0.15]
    ring, ring_id, suspects = [], 0, set()
    for rec in fraud:
        scheme = rng.choices(SCHEMES, weights)[0]
        _make_fraud(rng, rec, scheme, careful=rng.random() < 0.35)
        if scheme == "shell_ring":
            ring.append(rec)
            if len(ring) == rng.randint(3, 6) or rec is fraud[-1]:
                ring_id += 1
                for j, r in enumerate(ring):             # nominee directors, one controller behind them
                    r["phone"] = f"RING{ring_id}"
                    if j % 2 == 0:
                        r["address"] = f"RINGADDR{ring_id}"
                if rng.random() < 0.3:                    # controller already on the bank's suspect list
                    suspects.add(f"RING{ring_id}")
                ring = []
    rng.shuffle(recs)
    return recs, sorted(suspects)
