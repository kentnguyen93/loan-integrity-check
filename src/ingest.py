"""Document ingestion: label each document, extract its figures, validate them, build the master data table.

Every extracted value keeps its source document, line, confidence and validation status.
A value is trusted only if it passes an arithmetic or cross-document check. Anything else goes to a person.

The four extractors below are plain parsers. Each has the same interface (lines in, fields out), so an OCR
or language-model extractor can replace one without touching the rest. That swap needs its own evaluation.
"""
import re
from documents import strip_diacritics

LABELS = {                      # labelling: keywords that identify a document type, matched without diacritics
    "income_statement": "bao cao ket qua hoat dong kinh doanh",
    "vat_declaration": "to khai thue gia tri gia tang",
    "einvoice_listing": "bang ke hoa don dien tu",
    "bank_statement": "sao ke tai khoan",
}
LOOKALIKE = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "S": "5"})


def norm(s):
    return strip_diacritics(s).lower()


def label(lines):
    head = norm(" ".join(lines[:2]))
    for name, key in LABELS.items():
        if key in head:
            return name
    return "unknown"


def number(text):
    """Parse a Vietnamese-format number. Returns (value, confidence) or (None, 0)."""
    raw = text.strip()
    conf = 0.99
    if re.search(r"[OolIS]", raw):                 # repair look-alike letters, but trust the result less
        raw, conf = raw.translate(LOOKALIKE), 0.70
    digits = raw.replace(".", "")
    if not digits.isdigit():
        return None, 0.0
    return int(digits), conf


def _fields(lines):
    """All 'label: number' lines as (line_no, normalised label, value, confidence)."""
    out = []
    for i, line in enumerate(lines):
        if ": " in line:
            head, tail = line.rsplit(": ", 1)
            v, c = number(tail)
            if v is not None:
                out.append((i + 1, norm(head), v, c))
    return out


def _unit(lines):
    for line in lines:
        n = norm(line)
        if "don vi tinh" in n:
            return 1000 if "nghin" in n else 1_000_000 if "trieu" in n else 1
    return None                                     # unit line missing: cannot be sure of the scale


def _find(fields, key):
    return next((f for f in fields if key in f[1]), None)


def extract(doc):
    """Return {field: {value (VND million), source_doc, line, confidence, status, note}} for one document."""
    lines, kind = doc["lines"], label(doc["lines"])
    f, unit, out = _fields(lines), _unit(lines), {}

    def put(name, hit, ok, note=""):
        if hit is None:
            out[name] = {"value": None, "source_doc": doc["doc_id"], "line": None, "confidence": 0.0,
                         "status": "MISSING", "note": "field not found in document"}
            return
        conf = hit[3] if ok else min(hit[3], 0.50)
        if unit is None:
            conf, note = min(conf, 0.40), "unit line missing"
        out[name] = {"value": round(hit[2] * (unit or 1) / 1_000_000, 3), "source_doc": doc["doc_id"],
                     "line": hit[0], "confidence": conf,
                     "status": "VALIDATED" if ok and conf >= 0.80 else "NEEDS_REVIEW", "note": note}

    if kind == "income_statement":
        gross, ded, net = _find(f, "01. doanh thu"), _find(f, "02. cac khoan giam tru"), _find(f, "10. doanh thu thuan")
        ok = bool(gross and ded and net) and gross[2] - ded[2] == net[2]
        put("declared_revenue", net, ok, "" if ok else "gross minus deductions does not equal net revenue")
    elif kind == "vat_declaration":
        quarters, total = [x for x in f if x[1].startswith("quy ")], _find(f, "tong doanh thu chiu thue")
        ok = bool(total) and len(quarters) == 4 and sum(x[2] for x in quarters) == total[2]
        put("vat_revenue", total, ok, "" if ok else "quarters do not add up to the annual total")
    elif kind == "einvoice_listing":
        put("invoice_total", _find(f, "tong gia tri hoa don"), True)      # checked against VAT in build_master
    elif kind == "bank_statement":
        months, total = [x for x in f if x[1].startswith("thang ")], _find(f, "12 thang")
        ok = bool(total) and len(months) == 12 and sum(x[2] for x in months) == total[2]
        put("inflows_12m", total, ok, "" if ok else "months do not add up to the 12-month total")
        out["monthly_inflows"] = [round(x[2] / 1_000_000) for x in months] if len(months) == 12 else None
    return kind, out


REQUIRED = ("declared_revenue", "invoice_total", "vat_revenue", "inflows_12m")


def build_master(docs):
    """Master data table for one application, plus whether it can go on to the fraud checks."""
    master, labels = {}, {}
    for d in docs:
        kind, fields = extract(d)
        labels[d["doc_id"]] = kind
        master.update(fields)
    for name in REQUIRED:                               # a document that was never recognised leaves a gap
        master.setdefault(name, {"value": None, "source_doc": None, "line": None, "confidence": 0.0,
                                 "status": "MISSING", "note": "no document of the right type was recognised"})
    inv, vat = master["invoice_total"], master["vat_revenue"]
    if inv["value"] and vat["value"]:                   # cross-document check: invoices issued vs revenue declared for VAT
        if abs(inv["value"] - vat["value"]) > 0.02 * max(inv["value"], vat["value"]):
            for x in (inv, vat):
                x["status"], x["note"] = "NEEDS_REVIEW", "e-invoice total and VAT declaration differ by more than 2%"
                x["confidence"] = min(x["confidence"], 0.50)
    elif inv["value"] and inv["status"] == "VALIDATED":  # nothing to check the invoice total against
        inv["status"], inv["note"], inv["confidence"] = "NEEDS_REVIEW", "no VAT figure to check against", 0.50
    ready = all(master[n]["status"] == "VALIDATED" for n in REQUIRED) and master.get("monthly_inflows")
    return master, labels, bool(ready)
