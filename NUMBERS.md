# NUMBERS

Every constant, why that value, and why not half (or double) it.

| Constant | Value | Where | Why this, why not half |
|---|---|---|---|
| Overdraft fee | 2500 minor units = AED 25.00 | `core.FEE_MINOR` | Given by the spec. Half (12.50) has no basis. Stored as an integer 2500 so it is exact at AED's 2 decimals. |
| Fee currency | AED only | `core.FEE_CCY` | The spec fixes the fee in AED. ACC-002 is BHD and no FX rate exists, so a fee there raises `LedgerError` instead of posting AED into a BHD account (AMBIGUITIES #5). |
| Daily rate | 4 / 10000 (0.04 %) | `core.RATE_NUM/DEN` | Given. Kept as an integer fraction so no float enters the maths. Half (0.02 %) would also land on exact rounding ties: 225.00 x 0.0002 = 0.045 exactly, which is why the rounding mode must be fixed in advance (next rows). |
| Rounding mode | half away from zero (half-up for the positive-only interest) | `money.div_round_half_up` | Commercial default; deterministic. Banker's rounding would be equally defensible, but ties do not occur in the given stream at 0.04 %, so the choice is untested by data and only pinned by this document. |
| Rounding strategy | cumulative, not per-day | `core.accruals` | Per-day rounding gave 0.93 vs the exact 0.918 (0.92). Cumulative rounding makes daily amounts sum to round(exact total) with the residual carried, not dropped. Built and abandoned first: see REJECTED.md. |
| AED scale | 10^2 | `money.DECIMALS` | Spec: 2 dp. |
| BHD scale | 10^3 | `money.DECIMALS` | Spec: 3 dp. Using 2 would lose 3.333 -> 3.33 and break the 10.000 sum. |
| Window | 6 days | `replay.WINDOW` | Spec. Interest has 6 accrual days (D1..D6) and capitalizes on D6. Half (3) would capitalize before E7/E9 ever arrive. |
| Instalment count | 3 | event E10 | Spec. |
| Instalment residual | +1 fil on the **last** instalment | `money.split_equal` | 10000 fils / 3 = 3333 r 1. One fil must go somewhere; 3.333 + 3.333 + 3.334 = 10.000. Last, not first, is a convention (AMBIGUITIES #17). 3.334 x 3 = 10.002 is the refused criterion. |
| Integer money | signed int minor units | everywhere | Floats cannot hold 0.1 or 0.04 % exactly. Decimal would work but integers make "amounts stored and rounded to their own precision" structurally true. |
| Fee-test balance | pre-fee for that day | `core.assess_fees` | Including the fee being decided makes the test circular (a +10.00 day would be -15.00 after the fee). |
| Auth hold released on settle | full hold (200.00), settle 185.00 | `core.settle` | Spec gives no partial-settlement carry-over; keeping 15.00 held with nothing to settle it would strand funds forever. |
| Test seed numbers | 1200.00, 950.00, ... | tests | Copied from the spec; the extra `X1/X2` case in the Criterion-5 test uses 500.00 / 90.00 only so that the approval clearly succeeds with a visible 410.00 available. |
