import dataclasses
import unittest
from ledger import money
from ledger.core import Ledger, LedgerError, FEE_MINOR
from ledger.replay import ACCOUNTS, EVENTS, apply, run, close_day

A1, A2 = "ACC-001", "ACC-002"


def upto(day, close_last=False):
    """Replay booked-day order through `day`; optionally run the close of that day."""
    led = Ledger(ACCOUNTS)
    for ev in sorted(EVENTS, key=lambda e: e["booked"]):
        if ev["booked"] <= day:
            apply(led, ev)
    if close_last:
        led.assess_fees(day)
    return led


def fees(led, acct=A1):
    return [(e.value_day, e.booked_day) for e in led.entries if e.kind == "FEE" and e.account == acct]


class MoneyTests(unittest.TestCase):
    def test_precision_enforced(self):
        self.assertEqual(money.to_minor("1,200.00", "AED"), 120000)
        self.assertEqual(money.to_minor("10.000", "BHD"), 10000)
        with self.assertRaises(ValueError):
            money.to_minor("0.001", "AED")
        with self.assertRaises(ValueError):
            money.to_minor("0.0001", "BHD")

    def test_split_sums_exactly(self):
        self.assertEqual(money.split_equal(10000, 3), [3333, 3333, 3334])
        self.assertEqual(sum(money.split_equal(10000, 3)), 10000)


class CriteriaTests(unittest.TestCase):
    def test_c1_day2_balance_at_eod5_before_fee_is_minus_370(self):
        led = upto(5)                                        # E7 booked, no Day-5 close yet
        self.assertEqual(led.balance(A1, 2), -37000)

    def test_c2_REFUSED_e7_causes_three_fees_not_one(self):
        led = upto(5, close_last=True)
        self.assertEqual(sorted(v for v, _ in fees(led)), [2, 4, 5])
        # the Day-2 fee alone, as the criterion claims, would be wrong:
        self.assertNotEqual(len(fees(led)), 1)

    def test_c3_auth_a_settlement_accepted(self):
        led = upto(4)
        d = [d for d in led.decisions if d.event_id == "E5"][0]
        self.assertEqual(d.outcome, "ACCEPTED")
        self.assertEqual(led.holds(A1), 0)                   # hold released

    def test_c4_unknown_auth_rejected_and_funds_stay(self):
        before = upto(3)
        after = upto(4)
        d = [d for d in after.decisions if d.event_id == "E6"][0]
        self.assertEqual(d.outcome, "REJECTED")
        self.assertFalse([e for e in after.entries if e.event_id == "E6"])
        # only E5 moved money on Day 4
        self.assertEqual(after.balance(A1, 4), before.balance(A1, 4) - 18500)

    def test_c5_hold_reduces_available_not_ledger(self):
        led = Ledger(ACCOUNTS)
        led.credit("X1", 1, A1, 50000, 1)
        d = led.authorize("X2", 1, A1, "Auth-X", 9000, 1)
        self.assertEqual(d.outcome, "APPROVED")
        self.assertEqual(led.balance(A1, 1), 50000)
        self.assertEqual(led.available(A1, 1), 41000)

    def test_c5_in_this_stream_auth_b_is_declined_so_no_hold(self):
        led = upto(5)
        d = [d for d in led.decisions if d.event_id == "E8"][0]
        self.assertEqual(d.outcome, "DECLINED")              # -155.00 - 90.00 < 0
        self.assertEqual(led.holds(A1), 0)

    def test_c6_REFUSED_e9_does_not_restore_pre_e7_state(self):
        pre_e7 = Ledger(ACCOUNTS)
        for ev in EVENTS:
            if ev["id"] in ("E1", "E2", "E3", "E4", "E5", "E6"):
                apply(pre_e7, ev)
        led, _ = run(EVENTS)
        self.assertEqual(len(fees(led)), 3)                  # fees survive the reversal
        self.assertEqual(led.balance(A1, 4), 41500)                         # 415.00 ...
        self.assertNotEqual(led.balance(A1, 4), pre_e7.balance(A1, 4))      # ... not the pre-E7 465.00
        self.assertEqual(pre_e7.balance(A1, 4), 46500)
        self.assertEqual(led.balance(A1, 5), 39000)                         # 390.00 (interest is value-dated D6)

    def test_c7_REFUSED_instalments_are_3333_3333_3334(self):
        led, _ = run(EVENTS)
        parts = [e.amount for e in led.entries if e.event_id.startswith("E10.")]
        self.assertEqual(parts, [3333, 3333, 3334])
        self.assertEqual(sum(parts), 10000)
        self.assertNotEqual(3334 * 3, 10000)

    def test_c8_REFUSED_interest_remainder_is_carried_not_discarded(self):
        led, reps = run(EVENTS)
        rows = reps[-1]["interest"][A1]
        total = sum(r.amount for r in rows)
        self.assertEqual(total, 92)
        self.assertEqual([r.amount for r in rows], [10, 9, 25, 17, 15, 16])
        posted = [e.amount for e in led.entries if e.kind == "INTEREST" and e.account == A1]
        self.assertEqual(posted, [total])                    # exactly one credit == sum of daily
        bhd = [e.amount for e in led.entries if e.kind == "INTEREST" and e.account == A2]
        self.assertEqual(bhd, [8])                           # BHD 0.008


class RuleTests(unittest.TestCase):
    def test_fee_once_per_day_even_if_close_runs_twice(self):
        led = upto(5, close_last=True)
        led.assess_fees(5); led.assess_fees(5)   # re-running the same close adds nothing
        self.assertEqual(len(fees(led)), 3)
        self.assertTrue(all(-e.amount == FEE_MINOR for e in led.entries if e.kind == "FEE"))

    def test_fee_value_date_equals_day_assessed(self):
        led = upto(5, close_last=True)
        self.assertEqual([v for v, b in fees(led)], [2, 4, 5])
        self.assertTrue(all(b == 5 for _, b in fees(led)))   # booked at the Day-5 close

    def test_fee_on_aed_in_bhd_account_is_an_error_not_a_silent_post(self):
        led = Ledger(ACCOUNTS)
        led.debit("B1", 1, A2, 1000, 1)
        with self.assertRaises(LedgerError):
            led.assess_fees(1)

    def test_no_interest_on_negative_balance(self):
        led = Ledger(ACCOUNTS)
        led.debit("D1", 1, A1, 5000, 1)
        self.assertEqual([r.amount for r in led.accruals(A1, 3)], [0, 0, 0])

    def test_append_only(self):
        led, _ = run(EVENTS)
        snap = led.entries
        with self.assertRaises(dataclasses.FrozenInstanceError):
            snap[0].amount = 1
        with self.assertRaises(AttributeError):
            snap.append(None)
        led.credit("Z1", 6, A1, 100, 6)
        self.assertEqual(led.entries[:len(snap)], snap)      # prefix untouched
        self.assertEqual([e.seq for e in led.entries], sorted(e.seq for e in led.entries))
        self.assertIsNone(getattr(led, "delete", None))

    def test_double_reversal_and_reversal_of_unknown_rejected(self):
        led, _ = run(EVENTS)
        self.assertEqual(led.reverse("E11", 6, A1, "E7", 2).outcome, "REJECTED")
        self.assertEqual(led.reverse("E12", 6, A1, "NOPE", 2).outcome, "REJECTED")

    def test_replay_order_does_not_change_final_state(self):
        a, _ = run(EVENTS, strict=False)
        b, _ = run(EVENTS, strict=True)
        for acct in ACCOUNTS:
            self.assertEqual(a.balance(acct, 6), b.balance(acct, 6))
        self.assertEqual(fees(a), fees(b))


if __name__ == "__main__":
    unittest.main()
