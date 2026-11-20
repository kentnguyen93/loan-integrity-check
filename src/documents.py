"""Synthetic Vietnamese loan documents, rendered as text, with scanner-style noise.

Four document types per application, the ones the fraud checks depend on:
  - income statement extract (declared revenue)
  - VAT declaration (revenue declared to the tax authority, by quarter)
  - e-invoice listing (invoices issued)
  - bank statement summary (money actually received, by month)
Record values are in VND million; documents print full VND, or thousands when the unit line says so.
"""
import unicodedata


def vn(n):
    """Vietnamese number format: dots as thousands separators."""
    return f"{int(round(n)):,}".replace(",", ".")


def strip_diacritics(s):
    s = s.replace("Đ", "D").replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _split(total, parts, rng):
    w = [rng.uniform(0.8, 1.2) for _ in range(parts)]
    out = [int(total * x / sum(w)) for x in w]
    out[-1] += int(total) - sum(out)
    return out


def render(rec, rng):
    """Return the four documents for one application as {doc_id, true_type, lines}."""
    m = 1_000_000
    docs = []
    unit, div = ("nghìn đồng", 1000) if rng.random() < 0.10 else ("đồng", 1)
    net = rec["declared_revenue"] * m // div
    deductions = int(net * rng.uniform(0, 0.02))
    docs.append({"true_type": "income_statement", "lines": [
        "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH", "Năm 2025", f"Đơn vị tính: {unit}",
        f"01. Doanh thu bán hàng và cung cấp dịch vụ: {vn(net + deductions)}",
        f"02. Các khoản giảm trừ doanh thu: {vn(deductions)}",
        f"10. Doanh thu thuần về bán hàng và cung cấp dịch vụ: {vn(net)}"]})
    inv = rec["invoice_total"] * m
    q = _split(inv, 4, rng)
    docs.append({"true_type": "vat_declaration", "lines": [
        "TỜ KHAI THUẾ GIÁ TRỊ GIA TĂNG (Mẫu số 01/GTGT)", "Kỳ tính thuế: năm 2025", "Đơn vị tính: đồng"] +
        [f"Quý {i + 1} - Doanh thu hàng hóa, dịch vụ bán ra chịu thuế: {vn(x)}" for i, x in enumerate(q)] +
        [f"Tổng doanh thu chịu thuế cả năm: {vn(inv)}"]})
    docs.append({"true_type": "einvoice_listing", "lines": [
        "BẢNG KÊ HÓA ĐƠN ĐIỆN TỬ BÁN RA", "Kỳ: 01/2025 - 12/2025", "Đơn vị tính: đồng",
        f"Số lượng hóa đơn: {rng.randint(40, 4000)}",
        f"Tổng giá trị hóa đơn chưa thuế: {vn(inv)}"]})
    months = [x * m for x in rec["monthly_inflows"]]
    docs.append({"true_type": "bank_statement", "lines": [
        "SAO KÊ TÀI KHOẢN THANH TOÁN", "Từ ngày 01/01/2025 đến ngày 31/12/2025", "Đơn vị tính: đồng"] +
        [f"Tháng {i + 1:02d}/2025 - Tổng phát sinh ghi có: {vn(x)}" for i, x in enumerate(months)] +
        [f"Tổng phát sinh ghi có 12 tháng: {vn(sum(months))}"]})
    for i, d in enumerate(docs):
        d["doc_id"] = f"{rec['id']}-D{i + 1}"
        d["lines"], d["noise"] = _noise(d["lines"], rng)
    return docs


def _noise(lines, rng):
    """Scanner and OCR damage. Returns the damaged lines and what was done, for the evaluation."""
    done = []
    if rng.random() < 0.25:                                   # diacritics lost in OCR
        lines = [strip_diacritics(x) for x in lines]
        done.append("diacritics_lost")
    numbered = [i for i, x in enumerate(lines) if ": " in x and any(c.isdigit() for c in x.split(": ")[-1])]
    if numbered and rng.random() < 0.08:                      # digit read as a look-alike letter
        i = rng.choice(numbered)
        head, num = lines[i].rsplit(": ", 1)
        for a, b in (("0", "O"), ("1", "l"), ("5", "S")):
            if a in num:
                lines[i] = head + ": " + num.replace(a, b, 1)
                done.append("lookalike_letter")
                break
    if numbered and rng.random() < 0.04:                      # digit misread as another digit
        i = rng.choice(numbered)
        head, num = lines[i].rsplit(": ", 1)
        pos = [k for k, c in enumerate(num) if c.isdigit()]
        k = rng.choice(pos)
        lines[i] = head + ": " + num[:k] + str((int(num[k]) + rng.randint(1, 8)) % 10) + num[k + 1:]
        done.append("digit_misread")
    if rng.random() < 0.04 and len(lines) > 4:                # a line missing from the scan
        del lines[rng.randrange(2, len(lines))]
        done.append("line_dropped")
    return lines, done
