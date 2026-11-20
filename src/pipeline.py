"""Run the whole flow: generate -> check -> score -> route -> evaluate -> write outputs.

Safe to re-run: same seed and config give the same files and the same result.
Every routed file is written to an append-only audit log with the config hash.
Set "enabled": false in config.json to switch the check off: every file is then
routed CLEAR_CHECK_OFF and goes to the normal manual process.
"""
import hashlib, json, os, sys, time

sys.path.insert(0, os.path.dirname(__file__))
from generate import generate, SCHEMES
from checks import build_link_index
from score import score_file, threshold_for_cap, route

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def evaluate(rows, threshold):
    """Catch rate, precision and misses at the given threshold."""
    flagged = [r for r in rows if r["score"] >= threshold]
    fraud = [r for r in rows if r["is_fraud"]]
    caught = [r for r in flagged if r["is_fraud"]]
    value = lambda xs: sum(x["requested_limit"] for x in xs)
    by_scheme = {}
    for s in SCHEMES:
        tot = [r for r in fraud if r["scheme"] == s]
        by_scheme[s] = {"fraud": len(tot), "caught": len([r for r in tot if r["score"] >= threshold])}
    return {
        "files": len(rows), "flagged": len(flagged), "flag_rate": round(len(flagged) / len(rows), 4),
        "fraud": len(fraud), "caught": len(caught),
        "catch_rate_by_count": round(len(caught) / max(1, len(fraud)), 3),
        "catch_rate_by_value": round(value(caught) / max(1, value(fraud)), 3),
        "precision": round(len(caught) / max(1, len(flagged)), 3),
        "by_scheme": by_scheme,
        "missed_examples": [r["id"] for r in sorted(fraud, key=lambda r: r["score"]) if r["score"] < threshold][:5],
        "false_alarm_examples": [r["id"] for r in sorted(flagged, key=lambda r: -r["score"]) if not r["is_fraud"]][:5],
    }


def main():
    cfg = load_config()
    cfg_hash = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]
    run_id = f"run-{cfg['seed']}-{cfg_hash}"
    out = os.path.join(ROOT, "out")
    os.makedirs(out, exist_ok=True)

    recs, suspects = generate(cfg["n_applications"], cfg["fraud_rate"], cfg["seed"])
    index = build_link_index(recs)

    t0 = time.perf_counter()
    rows = []
    for rec in recs:
        if cfg["enabled"]:
            s, reasons = score_file(rec, cfg, index, set(suspects))
        else:
            s, reasons = 0.0, []
        rows.append({**rec, "score": s, "reasons": reasons})
    ms_per_file = (time.perf_counter() - t0) * 1000 / len(rows)

    # Set the threshold on the first half, measure on the second half it has never seen.
    half = len(rows) // 2
    calib, test = rows[:half], rows[half:]
    threshold = threshold_for_cap([r["score"] for r in calib], cfg["flag_cap"])
    for r in rows:
        r["route"] = route(r["score"], threshold, cfg["priority_score"]) if cfg["enabled"] else "CLEAR_CHECK_OFF"

    report = {"run_id": run_id, "enabled": cfg["enabled"], "threshold": threshold, "flag_cap": cfg["flag_cap"],
              "ms_per_file": round(ms_per_file, 3), "cost_per_file_vnd": 0,
              "calibration": evaluate(calib, threshold), "test": evaluate(test, threshold),
              "note": "Synthetic data. These numbers show the method works on the fraud patterns that were "
                      "simulated. They say nothing about catch rates on real Techcombank applications."}

    with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as f:
        json.dump({"report": report, "rows": test}, f)
    with open(os.path.join(out, "evaluation.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    with open(os.path.join(out, "audit_log.jsonl"), "w", encoding="utf-8") as f:     # rewritten per run id, so a re-run never duplicates
        for r in rows:
            f.write(json.dumps({"run_id": run_id, "config": cfg_hash, "file": r["id"], "score": r["score"],
                                "route": r["route"], "checks_fired": [x["check"] for x in r["reasons"]],
                                "actor": "system"}) + "\n")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()
