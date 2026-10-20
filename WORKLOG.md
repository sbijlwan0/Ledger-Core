# WORKLOG

Timestamps are real UTC wall-clock times from `date -u` in the build sandbox, appended as I worked.

- 2026-10-20T19:45:56Z  Started. Read spec; hand-computing the event stream before writing any code.
- 2026-10-20T19:45:56Z  Hand-check: with E7 in force, value-day closes are d1=250, d2=-370, d3=30, d4=-155, d5=-155. So E7 => THREE negative days (2,4,5), not one. Criterion 2 looks wrong.
- 2026-10-20T19:45:56Z  10.000/3 in fils = 3333.33.. so 3.334 x3 = 10.002. Criterion 7 wrong. Rounded daily interest (0.10,0.09,0.25,0.17,0.16,0.16) sums to 0.93 vs exact 0.918; criterion 8 'discard remainder' contradicts the exact-sum rule.
