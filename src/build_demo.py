"""Build demo/index.html: the investigator page with the latest run's results embedded."""
import base64, hashlib, json, os, random, sys

sys.path.insert(0, os.path.dirname(__file__))
from documents import render
from ingest import build_master

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def html_json(data):
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return (payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def script_csp_hash(html):
    script = html.split("<script>", 1)[1].split("</script>", 1)[0]
    digest = hashlib.sha256(script.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def main():
    with open(os.path.join(ROOT, "out", "results.json"), encoding="utf-8") as f:
        res = json.load(f)
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    rows = res["rows"]
    top = sorted(rows, key=lambda r: -r["score"])[:260]      # enough detail for a review cap of up to 12%
    keep = ("id", "segment", "requested_limit", "declared_revenue", "invoice_total", "inflows_12m",
            "tenure_months", "score", "reasons", "is_fraud", "scheme")
    # document intake samples: the first 8 applications that need review and the first 4 that pass
    with open(os.path.join(ROOT, "out", "ingest_evaluation.json"), encoding="utf-8") as f:
        ingest_report = json.load(f)
    rng, samples, need, okay = random.Random(cfg["seed"] + 2), [], 8, 4
    for r in rows:
        docs = render(r, rng)
        master, labels, ready = build_master(docs)
        if (ready and okay) or (not ready and need):
            okay, need = okay - ready, need - (not ready)
            samples.append({"id": r["id"], "ready": ready,
                            "docs": [{"doc_id": d["doc_id"], "label": labels[d["doc_id"]], "noise": d["noise"], "text": d["lines"]} for d in docs],
                            "master": {k: v for k, v in master.items() if k != "monthly_inflows"}})
        if not need and not okay:
            break
    samples.sort(key=lambda a: a["ready"])
    data = {"intake": {"report": ingest_report, "samples": samples}, "report": res["report"],
            "run_id": res["report"]["run_id"], "priority": cfg["priority_score"],
            "all": [[r["id"], r["score"], r["is_fraud"], r["requested_limit"]] for r in rows],
            "detail": [{k: r[k] for k in keep} for r in top]}
    with open(os.path.join(ROOT, "demo", "template.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*DATA*/null", html_json(data))
    html = html.replace("/*CSP_HASH*/", script_csp_hash(html))
    with open(os.path.join(ROOT, "demo", "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("demo/index.html written,", len(html) // 1024, "KB")


if __name__ == "__main__":
    main()
