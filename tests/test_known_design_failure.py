"""KNOWN FAILURE against my own design. This test is expected to be RED.

The rule says an authorization is approved only if available balance stays >= 0
after the hold. A reader naturally extends that to an invariant:

    "every APPROVED authorization is covered at its own value date."

My design does NOT guarantee that. Approval is a point-in-time decision made with
the information booked so far, and the ledger is append-only, so it is never
re-evaluated. E7 is booked on Day 5 but value-dated Day 2, which retroactively
drives Day 2 to -370.00 (-395.00 after the Day-2 fee), underneath Auth-A, which was
properly approved on Day 2 against a balance of 250.00.
"""
import unittest
from ledger.replay import ACCOUNTS, EVENTS, apply
from ledger.core import Ledger


class KnownDesignFailure(unittest.TestCase):
    def test_every_approved_auth_is_still_covered_after_restatement(self):
        led = Ledger(ACCOUNTS)
        for ev in sorted(EVENTS, key=lambda e: e["booked"]):
            if ev["booked"] <= 5:
                apply(led, ev)
        led.assess_fees(5)                      # EOD Day 5: E7 is in, E9 has not happened yet

        approved = [d for d in led.decisions if d.kind == "AUTHORIZATION" and d.outcome == "APPROVED"]
        self.assertTrue(approved)               # Auth-A
        for d in approved:
            # Restated available at the auth's own value date, counting only this hold.
            restated_available = led.balance(d.account, d.value_day) - d.amount
            # FAILS for Auth-A: -395.00 - 200.00 = -595.00
            self.assertGreaterEqual(
                restated_available, 0,
                f"{d.ref} was approved but is uncovered at D{d.value_day} once back-dated entries land: "
                f"{restated_available / 100:.2f}. The design has no re-evaluation, hold-reduction or "
                f"compensating-decline path for retroactively exposed approvals.")


if __name__ == "__main__":
    unittest.main()
