import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from invoicing import group_roster, split_amount  # noqa: E402


class SplitAmountTests(unittest.TestCase):
    def test_known_amount(self):
        # 154,800 all-in -> base 150,000 -> 120,000 untaxed + 30,000 taxed + 4,800 tax
        self.assertEqual(split_amount(154800), {
            "untaxed": 120000, "taxed_subtotal": 30000, "tax": 4800, "taxed_total": 34800,
        })

    def test_always_sums_back_to_quoted_amount(self):
        rng = random.Random(42)
        for _ in range(10000):
            total = rng.randint(1000, 5_000_000)
            s = split_amount(total)
            self.assertEqual(s["untaxed"] + s["taxed_subtotal"] + s["tax"], total, total)

    def test_untaxed_line_absorbs_rounding(self):
        s = split_amount(160321)
        self.assertEqual(s["tax"], round(s["taxed_subtotal"] * 0.16))
        self.assertEqual(s["untaxed"], 160321 - s["taxed_total"])

    def test_custom_share_and_rate(self):
        s = split_amount(118000, untaxed_share=0.0, tax_rate=0.18)
        self.assertEqual((s["untaxed"], s["taxed_subtotal"], s["tax"]), (0, 100000, 18000))


class GroupRosterTests(unittest.TestCase):
    ROWS = [
        {"client": "A", "email": "a@x", "line_item": "Office 1", "amount": 154800,
         "item_type": "Standard", "invoice_day": 1, "next_invoice_no": 5, "row_index": 2},
        {"client": "A", "email": "a@x", "line_item": "Office 2", "amount": 100000,
         "item_type": "Standard", "invoice_day": 1, "next_invoice_no": 5, "row_index": 3},
        {"client": "A", "email": "a@x", "line_item": "Static IP", "amount": 5000,
         "item_type": "Untaxed Only", "invoice_day": 1, "next_invoice_no": 5, "row_index": 4},
        {"client": "B", "email": "b@x", "line_item": "Desk", "amount": 25000,
         "item_type": "Standard", "invoice_day": 14, "next_invoice_no": 9, "row_index": 5},
        {"client": None, "email": None, "line_item": None, "amount": None,
         "item_type": None, "invoice_day": None, "next_invoice_no": None, "row_index": 6},
    ]

    def test_multi_line_client_becomes_one_invoice_pair(self):
        groups = group_roster(self.ROWS)
        self.assertEqual([g["client"] for g in groups], ["A", "B"])
        a = groups[0]
        self.assertEqual([i["desc"] for i in a["untaxed_items"]], ["Office 1", "Office 2", "Static IP"])
        self.assertEqual([i["desc"] for i in a["taxed_items"]], ["Office 1", "Office 2"])
        self.assertEqual(a["row_indexes"], [2, 3, 4])

    def test_untaxed_only_fee_is_not_split(self):
        a = group_roster(self.ROWS)[0]
        self.assertEqual(a["untaxed_items"][2]["unit_price"], 5000)

    def test_client_total_matches_roster(self):
        a = group_roster(self.ROWS)[0]
        untaxed = sum(i["unit_price"] for i in a["untaxed_items"])
        taxed = sum(i["unit_price"] for i in a["taxed_items"])
        tax = sum(line["tax"] for line in a["lines"])
        self.assertEqual(untaxed + taxed + tax, 154800 + 100000 + 5000)

    def test_multi_line_totals_never_drift(self):
        # Two offices whose combined subtotal re-rounds differently from the
        # per-office taxes: the client must still be billed exactly 90,445 + 53,086.
        rows = [dict(self.ROWS[0], amount=90445), dict(self.ROWS[1], amount=53086)]
        g = group_roster(rows)[0]
        untaxed = sum(i["unit_price"] for i in g["untaxed_items"])
        taxed = sum(i["unit_price"] for i in g["taxed_items"])
        tax = sum(line["tax"] for line in g["lines"])
        self.assertNotEqual(round(taxed * 0.16), tax)  # the case that used to drift
        self.assertEqual(untaxed + taxed + tax, 90445 + 53086)

    def test_day_filter(self):
        groups = group_roster(self.ROWS, day_filter=14)
        self.assertEqual([g["client"] for g in groups], ["B"])


if __name__ == "__main__":
    unittest.main()
