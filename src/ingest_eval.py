"""Evaluate document ingestion end to end.

For 1,000 applications: render four noisy documents each, extract, validate, and compare with the truth.
Reports labelling accuracy, field accuracy, how many files go to document review, the dangerous case
(wrong but trusted), and whether fraud routing from extracted figures matches routing from true figures.
"""
import json, os, random, sys, time

sys.path.insert(0, os.path.dirname(__file__))
from generate import generate
from documents import render
from ingest import build_master, REQUIRED
from checks import build_link_index
from score import score_file, threshold_for_cap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = 1000
TRUTH = {"declared_revenue": "declared_revenue", "invoice_total": "invoice_total",
         "vat_revenue": "invoice_total", "inflows_12m": "inflows_12m"}


def main():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    recs, suspects = generate(cfg["n_applications"], cfg["fraud_rate"], cfg["seed"])
    index = build_link_index(recs)
    threshold = threshold_for_cap([score_file(r, cfg, index, set(suspects))[0] for r in recs[:2000]], cfg["flag_cap"])
    rng = random.Random(cfg["seed"] + 1)
    sample = recs[2000:2000 + N]

    docs_n = label_ok = fields_n = trusted = trusted_right = wrong_trusted = review = missing = 0
    ready_n = route_same = 0
    noise_seen, examples, wrong_examples = {}, [], []
    t0 = time.perf_counter()
    for rec in sample:
        docs = render(rec, rng)
        master, labels, ready = build_master(docs)
        for d in docs:
            docs_n += 1
            label_ok += labels[d["doc_id"]] == d["true_type"]
            for n in d["noise"]:
                noise_seen[n] = noise_seen.get(n, 0) + 1
        for name in REQUIRED:
            cell = master[name]
            # the bank statement prints whole-million months, so its true total is their sum
            truth = sum(rec["monthly_inflows"]) if name == "inflows_12m" else rec[TRUTH[name]]
            fields_n += 1
            right = cell["value"] is not None and abs(cell["value"] - truth) <= 0.005 * max(1, truth)
            if cell["status"] == "VALIDATED":
                trusted += 1
                trusted_right += right
                if not right:
                    wrong_trusted += 1
                    wrong_examples.append({"file": rec["id"], "field": name, "extracted": cell["value"], "truth": truth,
                                           "source_doc": cell["source_doc"], "line": cell["line"]})
            elif cell["status"] == "NEEDS_REVIEW":
                review += 1
            else:
                missing += 1
        if ready:
            ready_n += 1
            got = dict(rec, declared_revenue=master["declared_revenue"]["value"],
                       invoice_total=master["invoice_total"]["value"], inflows_12m=master["inflows_12m"]["value"],
                       monthly_inflows=master["monthly_inflows"])
            a = score_file(rec, cfg, index, set(suspects))[0] >= threshold
            b = score_file(got, cfg, index, set(suspects))[0] >= threshold
            route_same += a == b
        if len(examples) < 3 and (not ready or len(examples) == 0):
            examples.append({"file": rec["id"], "ready_for_checks": ready,
                             "documents": [{"doc_id": d["doc_id"], "label": labels[d["doc_id"]], "noise": d["noise"],
                                            "text": d["lines"]} for d in docs],
                             "master_data": {k: v for k, v in master.items() if k != "monthly_inflows"}})
    ms = (time.perf_counter() - t0) * 1000 / N

    report = {
        "applications": N, "documents": docs_n,
        "labelling_accuracy": round(label_ok / docs_n, 4),
        "fields": fields_n,
        "fields_trusted": trusted, "fields_trusted_share": round(trusted / fields_n, 4),
        "accuracy_of_trusted_fields": round(trusted_right / max(1, trusted), 4),
        "fields_sent_to_review": review, "fields_missing": missing,
        "wrong_but_trusted": wrong_trusted,
        "applications_straight_through": ready_n, "straight_through_share": round(ready_n / N, 4),
        "applications_to_document_review": N - ready_n,
        "fraud_routing_agreement_on_straight_through": round(route_same / max(1, ready_n), 4),
        "ms_per_application": round(ms, 3), "model_cost_per_application_vnd": 0,
        "noise_injected": noise_seen, "wrong_but_trusted_examples": wrong_examples[:5],
        "note": "Synthetic text documents with simulated scan damage. Real scans, stamps, handwriting and "
                "layouts are far harder. These numbers test the validation logic, not OCR quality.",
    }
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    with open(os.path.join(ROOT, "out", "ingest_evaluation.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open(os.path.join(ROOT, "out", "master_data_examples.json"), "w", encoding="utf-8") as f:
        json.dump(examples, f, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
