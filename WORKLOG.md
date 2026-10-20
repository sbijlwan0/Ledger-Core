# WORKLOG

Timestamps are real UTC wall-clock times from `date -u` in the build sandbox, appended as I worked.

- 2026-10-20T19:45:56Z  Started. Read spec; hand-computing the event stream before writing any code.
- 2026-10-20T19:45:56Z  Hand-check: with E7 in force, value-day closes are d1=250, d2=-370, d3=30, d4=-155, d5=-155. So E7 => THREE negative days (2,4,5), not one. Criterion 2 looks wrong.
- 2026-10-20T19:45:56Z  10.000/3 in fils = 3333.33.. so 3.334 x3 = 10.002. Criterion 7 wrong. Rounded daily interest (0.10,0.09,0.25,0.17,0.16,0.16) sums to 0.93 vs exact 0.918; criterion 8 'discard remainder' contradicts the exact-sum rule.
- 2026-10-20T19:45:57Z  Commit 1: analysis only.
- 2026-10-20T19:46:18Z  Commit 2: money.py + core.py (no fees/interest yet). Auth state is derived by folding the decision log; nothing mutated.
- 2026-10-20T19:46:39Z  Commit 3: fees work (days 2,4,5). Naive interest (round each day, sum) gives 0.93 but exact is 0.918 -> 0.92. Test is RED on purpose; committed to keep the abandoned approach in history.
- 2026-10-20T19:46:45Z  Commit 4: replaced naive rounding with cumulative rounding + hard invariant check in capitalize_interest. Interest test green. ACC-001 daily = 0.10,0.09,0.25,0.17,0.15,0.16 = 0.92.
- 2026-10-20T19:47:12Z  Commit 5: replay.py. Fixed tuple-unpack crash in close_day; moved re-sequence notice out of the errors list (it is not an error). Output matches hand numbers: fees D2/D4/D5, Auth-B DECLINED, interest 0.92.
- 2026-10-20T19:47:38Z  Commit 6: test suite. One red result was MY test bug (called assess_fees(6) on a ledger with no E9, where Day 6 really is negative); fixed the test, engine unchanged. Also removed a nonsense assertion I had typed in the c6 test.
- 2026-10-20T19:47:45Z  Commit 7: commit 6 was NOT green - I committed without reading the exit status and the message said green. Assertion was wrong (subtracted interest that is value-dated D6). Fixed forward in a new commit; history not rewritten.
