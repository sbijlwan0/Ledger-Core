# In-memory account ledger core

Python 3.9+, standard library only. No web layer, persistence, UI or database.

## Run

```
python -m ledger.replay                  # replay E1..E10, print the per-day report
python -m ledger.replay --strict-order   # replay in exactly the listed order (E10 arrives late)
python -m unittest tests.test_ledger tests.test_interest   # 20 tests, all green
python -m unittest discover -s tests -t .                  # full suite: 1 DESIGNED failure (see below)
```

**The full suite is supposed to exit non-zero.** `tests/test_known_design_failure.py` is a
deliberately red test against my own design (approvals are not re-evaluated after back-dated
entries). Its docstring and inline comments say what it reveals. Everything else passes.

## Reading the output

Each `=== DAY n ===` block prints, in order:

- **events**: every event booked that day with its outcome (ACCEPTED / APPROVED / DECLINED / REJECTED) and reason.
- **value-dated closing ledger, restated**: balance for value days 1..n as known at that close, *before* that close's fees. This is where Day 2 shows `-370.00` at the end of Day 5.
- **fee assessments**: fees booked at this close, each labelled with the *value day* it was assessed for. A fee booked on Day 5 can carry value day D2.
- **closing ledger balance**: for today's value day: `pre-fee`, `post-fee`, and (Day 6 only) after interest capitalization; plus `available` (ledger minus active holds).
- **interest** (Day 6 only): the six daily accruals per account and the single capitalized credit.
- **authorization states**: ACTIVE HOLD / SETTLED / DECLINED / UNKNOWN, derived from the decision log.
- **notes / errors**: `errors` lists rejected events (E6). `notes` carries non-error remarks (re-sequencing, late arrival).

`=== FINAL ===` dumps the append-only journal. `#seq` is one counter shared by journal
entries *and* decision records, so journal numbers have gaps by design.

## Layout

```
ledger/money.py    integer minor-unit helpers, half-up rounding, equal split
ledger/core.py     Ledger: append-only entries + decision log, fees, interest
ledger/replay.py   event stream, driver, report renderer
tests/             acceptance-criteria tests, rule tests, one designed failure
NUMBERS.md  AMBIGUITIES.md  REJECTED.md  WORKLOG.md
```
