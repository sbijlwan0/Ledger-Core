import unittest
from ledger.core import Ledger, RATE_DEN
from ledger import money


def scenario_ledger():
    L = Ledger({"ACC-001": "AED", "ACC-002": "BHD"})
    L.credit("E1", 1, "ACC-001", 120000, 1); L.debit("E2", 1, "ACC-001", 95000, 1)
    L.authorize("E3", 2, "ACC-001", "Auth-A", 20000, 2)
    L.credit("E4", 3, "ACC-001", 40000, 3)
    L.settle("E5", 4, "ACC-001", "Auth-A", 18500, 4)
    L.debit("E7", 5, "ACC-001", 62000, 2); L.assess_fees(5)
    L.reverse("E9", 6, "ACC-001", "E7", 2); L.assess_fees(6)
    return L


class InterestTests(unittest.TestCase):
    def test_capitalized_total_equals_rounded_exact_total_and_sum_of_daily(self):
        L = scenario_ledger()
        rows = L.accruals("ACC-001", 6)
        exact = money.div_round_half_up(sum(r.numer for r in rows), RATE_DEN)
        self.assertEqual(sum(r.amount for r in rows), exact)   # 92 cents


if __name__ == "__main__":
    unittest.main()
