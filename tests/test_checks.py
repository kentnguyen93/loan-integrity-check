"""Run with: python3 -m unittest discover tests"""
import io, json, os, shutil, sys, tempfile, unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from checks import revenue_gap, round_trip, links, build_link_index
from score import score_file, threshold_for_cap, route
from generate import generate
from ingest import number, label, extract
import ingest_eval

TOL = {"revenue_gap_start": 1.4, "revenue_gap_full": 3.0, "invoice_gap_start": 1.4, "invoice_gap_full": 3.0}


def rec(**kw):
    base = {"id": "A", "segment": "SME", "requested_limit": 500, "declared_revenue": 1000, "invoice_total": 900,
            "inflows_12m": 1000, "monthly_inflows": [83] * 12, "related_return_share": 0.02,
            "top_counterparty_share": 0.2, "director": "D1", "address": "A1", "phone": "P1", "tenure_months": 36}
    base.update(kw)
    return base


class Checks(unittest.TestCase):
    def test_consistent_file_scores_zero_on_revenue(self):
        self.assertEqual(revenue_gap(rec(), TOL)[0], 0.0)

    def test_inflated_revenue_scores_full(self):
        self.assertEqual(revenue_gap(rec(declared_revenue=4000), TOL)[0], 1.0)

    def test_round_trip_ramps(self):
        self.assertEqual(round_trip(rec(related_return_share=0.1), TOL)[0], 0.0)
        self.assertGreater(round_trip(rec(related_return_share=0.6), TOL)[0], 0.99)

    def test_shared_phone_is_stronger_than_shared_address(self):
        a, b, c = rec(id="A"), rec(id="B", director="D2", address="A2"), rec(id="C", director="D3", phone="P3")
        idx = build_link_index([a, b, c])
        self.assertGreater(links(b, idx)[0], links(c, idx)[0])   # B shares a phone with A; C shares only an address

    def test_route_bands(self):
        self.assertEqual(route(0.1, 0.2, 0.8), "CLEAR")
        self.assertEqual(route(0.3, 0.2, 0.8), "REVIEW")
        self.assertEqual(route(0.9, 0.2, 0.8), "REVIEW_PRIORITY")

    def test_threshold_respects_cap(self):
        scores = [i / 100 for i in range(100)]
        thr = threshold_for_cap(scores, 0.05)
        self.assertEqual(len([s for s in scores if s >= thr]), 5)

    def test_generation_is_repeatable(self):
        self.assertEqual(generate(200, 0.05, 7), generate(200, 0.05, 7))


class Ingest(unittest.TestCase):
    def test_vietnamese_number_format(self):
        self.assertEqual(number("12.345.000.000"), (12345000000, 0.99))

    def test_lookalike_letter_is_repaired_but_trusted_less(self):
        value, conf = number("1O.5OO.OOO")
        self.assertEqual(value, 10500000)
        self.assertLess(conf, 0.80)

    def test_label_works_without_diacritics(self):
        self.assertEqual(label(["SAO KE TAI KHOAN THANH TOAN", "x"]), "bank_statement")

    def test_bad_arithmetic_goes_to_review(self):
        doc = {"doc_id": "T-D2", "lines": ["TỜ KHAI THUẾ GIÁ TRỊ GIA TĂNG", "Kỳ", "Đơn vị tính: đồng",
               "Quý 1 - Doanh thu: 100.000.000", "Quý 2 - Doanh thu: 100.000.000", "Quý 3 - Doanh thu: 100.000.000",
               "Quý 4 - Doanh thu: 100.000.000", "Tổng doanh thu chịu thuế cả năm: 500.000.000"]}
        self.assertEqual(extract(doc)[1]["vat_revenue"]["status"], "NEEDS_REVIEW")

    def test_ingestion_writes_utf8_when_default_is_cp1252(self):
        real_open = open

        def windows_open(file, mode="r", *args, **kwargs):
            if "w" in mode and "b" not in mode:
                kwargs.setdefault("encoding", "cp1252")
            return real_open(file, mode, *args, **kwargs)

        with tempfile.TemporaryDirectory() as root:
            shutil.copy(os.path.join(os.path.dirname(__file__), "..", "config.json"),
                        os.path.join(root, "config.json"))
            with mock.patch.object(ingest_eval, "ROOT", root), \
                    mock.patch.object(ingest_eval, "N", 1), \
                    mock.patch("builtins.open", side_effect=windows_open), \
                    redirect_stdout(io.StringIO()):
                ingest_eval.main()
            with real_open(os.path.join(root, "out", "master_data_examples.json"), encoding="utf-8") as f:
                examples = json.load(f)
        self.assertEqual(len(examples), 1)


if __name__ == "__main__":
    unittest.main()
