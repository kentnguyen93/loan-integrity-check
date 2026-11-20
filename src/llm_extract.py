"""Optional language-model extraction experiment. NOT YET RUN: needs an Anthropic API key.

This standalone script sends the 10-application trial set to a model, compares its four headline figures
with trial/truth.json, and prints accuracy, cost per application, and response time. It is not part of the
core pipeline. The script does not yet pass model output through the ingestion validation rules or route
applications, so its output must not be treated as validated production data.

Usage:

    export ANTHROPIC_API_KEY=...
    python3 src/llm_extract.py

Model and prices are set below; check both against the provider's current documentation before use.
"""
import json, os, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = "claude-haiku-5-5"
PRICE_PER_M = {"input": 0.10, "output": 0.50}      # USD per million tokens; verify before use
PROMPT = """You are reading scanned Vietnamese loan documents for one business. The scan may have lost
diacritics, misread a digit, or dropped a line. Numbers use dots as thousands separators. Respect the
"Don vi tinh" unit line (dong, nghin dong, trieu dong).

Return JSON only, values in VND million:
{"declared_revenue": [number, note], "vat_revenue": [number, note],
 "invoice_total": [number, note], "inflows_12m": [number, note]}

declared_revenue = net revenue (line 10) on the income statement. vat_revenue = annual total on the VAT
declaration. invoice_total = total on the e-invoice listing. inflows_12m = 12-month credit total on the
bank statement. Report each figure AS PRINTED. If the arithmetic on the page disagrees with the printed
figure, do not correct it: say so in the note. Use note "ok" when nothing looks wrong.

Documents:
"""


def ask(documents_text):
    body = json.dumps({"model": MODEL, "max_tokens": 400,
                       "messages": [{"role": "user", "content": PROMPT + documents_text}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
        "content-type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    text = out["content"][0]["text"]
    answer = json.loads(text[text.index("{"):text.rindex("}") + 1])
    usage = out.get("usage", {})
    cost = (usage.get("input_tokens", 0) * PRICE_PER_M["input"] + usage.get("output_tokens", 0) * PRICE_PER_M["output"]) / 1e6
    return answer, cost, time.perf_counter() - t0


def main():
    with open(os.path.join(ROOT, "trial", "documents.txt"), encoding="utf-8") as f:
        blocks = [b for b in f.read().split("=== ") if b.strip()]
    with open(os.path.join(ROOT, "trial", "truth.json"), encoding="utf-8") as f:
        truth = json.load(f)
    right = total = 0
    costs, times, wrong = [], [], []
    for b in blocks:
        app, text = b.split("\n", 1)
        answer, cost, secs = ask(text)
        costs.append(cost)
        times.append(secs)
        for field, t in truth[app].items():
            total += 1
            v = answer[field][0]
            ok = v is not None and abs(v - t) <= 0.005 * max(1, t)
            right += ok
            if not ok:
                wrong.append({"file": app, "field": field, "model": v, "truth": t, "note": answer[field][1]})
    print(json.dumps({"model": MODEL, "fields": total, "correct": right, "accuracy": round(right / total, 3),
                      "usd_per_application": round(sum(costs) / len(costs), 6),
                      "seconds_per_application": round(sum(times) / len(times), 2), "wrong": wrong}, indent=2))


if __name__ == "__main__":
    main()
