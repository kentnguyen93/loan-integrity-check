"""Health checks on the last run. Writes out/alerts.json and exits 1 if any alert fires.

Run after pipeline.py (for example from a scheduler). An alert means: look before trusting the queue.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOLERANCE = 0.15          # flag rate may sit 15% above or 40% below the cap before someone is told


def main():
    with open(os.path.join(ROOT, "out", "evaluation.json"), encoding="utf-8") as f:
        rep = json.load(f)
    alerts = []
    cap, rate = rep["flag_cap"], rep["test"]["flag_rate"]
    if not rep["enabled"]:
        alerts.append({"level": "critical", "what": "Check is switched off. All files are going to the manual process."})
    else:
        if rate > cap * (1 + TOLERANCE):
            alerts.append({"level": "warning", "what": f"Flag rate {rate:.1%} is above the {cap:.0%} cap. "
                           "Investigators are getting more files than agreed. Recalibrate the threshold."})
        if rate < cap * 0.6:
            alerts.append({"level": "warning", "what": f"Flag rate {rate:.1%} is far below the {cap:.0%} cap. "
                           "Input data may be missing or a check may have stopped firing."})
        if rep["test"]["flagged"] == 0:
            alerts.append({"level": "critical", "what": "No files flagged at all. Treat the run as failed."})
        if rep["ms_per_file"] > 50:
            alerts.append({"level": "warning", "what": f"Scoring took {rep['ms_per_file']} ms per file, above the 50 ms budget."})
    with open(os.path.join(ROOT, "out", "alerts.json"), "w", encoding="utf-8") as f:
        json.dump({"run_id": rep["run_id"], "alerts": alerts}, f, indent=2)
    for a in alerts:
        print(f"[{a['level'].upper()}] {a['what']}")
    if not alerts:
        print("No alerts.")
    sys.exit(1 if alerts else 0)


if __name__ == "__main__":
    main()
