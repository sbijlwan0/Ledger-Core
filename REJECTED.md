# REJECTED

## Acceptance criteria refused (4 of 8)

### Criterion 2 - "E7 causes exactly one overdraft fee, on Day 2." REFUSED
E7 (AED 620.00, value D2, booked Day 5) makes the value-dated closing balances
D1 250.00, **D2 -370.00**, D3 30.00, **D4 -155.00**, **D5 -155.00**. Day 4 and Day 5 are also
negative because E7 is a permanent entry from Day 2 onward and E5 (-185.00) lands on Day 4. The fee rule is
"once per day per account when that day's closing ledger balance is negative", so E7 causes **three** fees:
D2, D4, D5 (AED 75.00 total), all booked at the Day 5 close. Replay output and
`test_c2_REFUSED_e7_causes_three_fees_not_one` confirm it.

### Criterion 6 - "After E9, all balances and fees return to their pre-E7 values." REFUSED
E9 reverses E7 only. The ledger is append-only, so the reversal is a new +620.00 entry; E7 and the three
fees remain. Fees are not refunded (no rule says so). Final D4 balance is 415.00, not the pre-E7
465.00; D5 is 390.00 not 465.00; three fee records still exist. After E9 the *E7 effect* is neutralised,
not the *consequences* of E7. (Test: `test_c6_REFUSED_...`.)

### Criterion 7 - "The three BHD instalments must each be BHD 3.334." REFUSED
3.334 x 3 = 10.002 BHD, which credits two fils more than the event. 10.000 does not divide by three at three decimals; the
instalments are 3.333, 3.333, 3.334. (Test: `test_c7_REFUSED_...`.)

### Criterion 8 - "If rounded daily accruals do not sum to the capitalized total, the remainder is discarded." REFUSED
The spec says the rounded accruals *must sum exactly* to the capitalized total, which excludes silently discarding
anything. Dropping the remainder would produce a total that is not the sum of the posted daily amounts or
not the rounded exact total. The engine carries the residual forward (cumulative rounding), and
`capitalize_interest` raises if the sum ever differs. (Test: `test_c8_REFUSED_...`.)

## Criteria accepted, with caveats

1. **Day 2 closing balance at end of Day 5, pre-fee = AED -370.00.** Correct (1200 - 950 - 620).
3. **Day 4 settlement of Auth-A must be accepted.** Correct: Auth-A was approved against 250.00 and the hold (200.00)
   covers the 185.00 settlement.
4. **Unknown-authorization settlement rejected, funds stay.** Correct (E6). No ledger entry is written.
5. **Approved Auth-B hold reduces available, not ledger.** True as a conditional, but **vacuous here**: Auth-B is
   DECLINED (available -155.00 - 90.00 = -245.00). I accept the statement, flag that the stream never
   exercises it, and test it on a separate funded account.

## Approaches abandoned mid-build (real, from the git history)

1. **Per-day rounded interest, summed.** Built first (commit `feat: overdraft fees; naive per-day...`).
   A test showed 0.93 against the exact 0.918 -> 0.92. Replaced by cumulative rounding.
   The naive commit and its red test are left in history on purpose.
2. **A test that called `assess_fees(6)` on a ledger without E9** to prove "fees are assessed once". Day 6 was genuinely
   negative there, so a fourth fee was correct and my test was wrong; I rewrote the test, not the engine.
3. **A muddled c6 assertion** that subtracted interest from a balance that never contained it (interest is value-dated D6).
   My commit message called it green when it was red; fixed forward, history kept.
