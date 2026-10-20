"""Replays the event stream and prints, per day: closing ledger balance, fee
assessments, authorization states and errors.

    python -m ledger.replay                 # stable-sorted by booked day (default)
    python -m ledger.replay --strict-order  # exactly the listed order E1..E10
"""
import sys
from . import money
from .core import Ledger

ACCOUNTS = {"ACC-001": "AED", "ACC-002": "BHD"}
WINDOW = 6

EVENTS = [
    dict(id="E1", booked=1, type="CREDIT", acct="ACC-001", amount="1200.00", vd=1),
    dict(id="E2", booked=1, type="DEBIT", acct="ACC-001", amount="950.00", vd=1),
    dict(id="E3", booked=2, type="AUTHORIZATION", acct="ACC-001", auth="Auth-A", amount="200.00", vd=2),
    dict(id="E4", booked=3, type="CREDIT", acct="ACC-001", amount="400.00", vd=3),
    dict(id="E5", booked=4, type="SETTLEMENT", acct="ACC-001", auth="Auth-A", amount="185.00", vd=4),
    dict(id="E6", booked=4, type="SETTLEMENT", acct="ACC-001", auth="Auth-Z", amount="180.00", vd=4),
    dict(id="E7", booked=5, type="DEBIT", acct="ACC-001", amount="620.00", vd=2),
    dict(id="E8", booked=5, type="AUTHORIZATION", acct="ACC-001", auth="Auth-B", amount="90.00", vd=5),
    dict(id="E9", booked=6, type="REVERSAL", acct="ACC-001", ref="E7", vd=2),
    dict(id="E10", booked=5, type="CREDIT", acct="ACC-002", amount="10.000", vd=5, instalments=3),
]


def apply(led, ev):
    a, t = ev["acct"], ev["type"]
    ccy = led.currency(a)
    amt = money.to_minor(ev["amount"], ccy) if "amount" in ev else None
    if t == "CREDIT":
        if ev.get("instalments"):
            return led.credit_instalments(ev["id"], ev["booked"], a, amt, ev["instalments"], ev["vd"])
        return led.credit(ev["id"], ev["booked"], a, amt, ev["vd"])
    if t == "DEBIT":
        return led.debit(ev["id"], ev["booked"], a, amt, ev["vd"])
    if t == "AUTHORIZATION":
        return led.authorize(ev["id"], ev["booked"], a, ev["auth"], amt, ev["vd"])
    if t == "SETTLEMENT":
        return led.settle(ev["id"], ev["booked"], a, ev["auth"], amt, ev["vd"])
    if t == "REVERSAL":
        return led.reverse(ev["id"], ev["booked"], a, ev["ref"], ev["vd"])
    raise ValueError(t)


def close_day(led, day, decisions, notes):
    """End-of-day: snapshot (pre-fee, restated), assess fees, capitalize on the last day."""
    rep = dict(day=day, decisions=decisions, notes=list(notes))
    rep["restated_prefee"] = {a: [led.balance(a, d) for d in range(1, day + 1)] for a in ACCOUNTS}
    rep["fees"] = led.assess_fees(day)
    rep["closing_post_fee"] = {a: led.balance(a, day, booked_by=day) for a in ACCOUNTS}
    rep["interest"] = led.capitalize_interest(day, WINDOW) if day == WINDOW else None
    rep["closing_final"] = {a: led.balance(a, day, booked_by=day) for a in ACCOUNTS}
    rep["available"] = {a: led.available(a, day) for a in ACCOUNTS}
    rep["auths"] = led.auth_table()
    rep["errors"] = [f"{d.event_id} {d.kind} {d.ref}: REJECTED - {d.reason}"
                     for _, d in decisions if d.outcome == "REJECTED"]
    return rep


def run(events, strict=False, out=None):
    led = Ledger(ACCOUNTS)
    order = list(events) if strict else sorted(events, key=lambda e: e["booked"])  # stable
    reports, day, today, notes = [], 1, [], []
    if not strict and [e["id"] for e in order] != [e["id"] for e in events]:
        notes.append("stream re-sequenced by booked day (stable): " + ",".join(e["id"] for e in order))
    for ev in order:
        while day < ev["booked"]:
            reports.append(close_day(led, day, today, notes)); day += 1; today, notes = [], []
        if ev["booked"] < day:
            notes.append(f"{ev['id']} booked Day {ev['booked']} arrived after Day {ev['booked']} closed (late-arriving); accepted")
        today.append((ev, apply(led, ev)))
    while day <= WINDOW:
        reports.append(close_day(led, day, today, notes)); day += 1; today, notes = [], []
    if out:
        for r in reports:
            out(render(led, r))
        out(render_final(led))
    return led, reports


def _f(m, a, c=True):
    return money.fmt(m, ACCOUNTS[a], c)


def render(led, r):
    L = [f"=== DAY {r['day']} ==="]
    L.append("events:" if r["decisions"] else "events: (none)")
    for ev, d in r["decisions"]:
        amt = _f(d.amount, ev["acct"]) if d.amount else ""
        tag = f"{d.outcome}" + (f" ({d.reason})" if d.reason else "")
        L.append(f"  {ev['id']:<3} booked D{ev['booked']} vd D{ev['vd']}  {ev['type']:<13} {ev['acct']} {ev.get('auth', ev.get('ref', ''))} {amt} -> {tag}")
    L.append("value-dated closing ledger, restated as known now, BEFORE this close's fees:")
    for a, bals in r["restated_prefee"].items():
        L.append(f"  {a}: " + "  ".join(f"d{i}={money.fmt(b, ACCOUNTS[a], False)}" for i, b in enumerate(bals, 1)))
    L.append("fee assessments (booked today):")
    if not r["fees"]:
        L.append("  none")
    for e in r["fees"]:
        L.append(f"  {e.account}: {_f(-e.amount, e.account)} for value day D{e.value_day} (pre-fee balance negative)")
    L.append("closing ledger balance, value day = today:")
    for a in ACCOUNTS:
        extra = f"  -> after interest capitalization {_f(r['closing_final'][a], a)}" if r["interest"] else ""
        L.append(f"  {a}: pre-fee {_f(r['restated_prefee'][a][-1], a)} | post-fee {_f(r['closing_post_fee'][a], a)}{extra}"
                 f" | available {_f(r['available'][a], a)}")
    if r["interest"]:
        L.append("interest accruals (0.04%/day, positive balances, cumulative rounding) -> one credit, value D6:")
        for a, rows in r["interest"].items():
            L.append(f"  {a}: " + "  ".join(f"d{x.day}={money.fmt(x.amount, ACCOUNTS[a], False)}" for x in rows)
                     + f"  | sum={_f(sum(x.amount for x in rows), a)} capitalized={_f(sum(x.amount for x in rows), a)}")
    L.append("authorization states:" if r["auths"] else "authorization states: none")
    for aid, st, det in r["auths"]:
        L.append(f"  {aid}: {st} - {det}")
    for n in r["notes"]:
        L.append(f"note: {n}")
    L.append("errors:" if r["errors"] else "errors: none")
    for e in r["errors"]:
        L.append(f"  {e}")
    return "\n".join(L) + "\n"


def render_final(led):
    L = ["=== FINAL (append-only journal) ==="]
    for e in led.entries:
        L.append(f"  #{e.seq:<2} {e.event_id:<14} booked D{e.booked_day} vd D{e.value_day} {e.account} {e.kind:<10} {_f(e.amount, e.account)} {e.ref}")
    for a in ACCOUNTS:
        L.append(f"  closing {a} @D{WINDOW}: {_f(led.balance(a, WINDOW), a)}")
    return "\n".join(L)


if __name__ == "__main__":
    run(EVENTS, strict="--strict-order" in sys.argv, out=print)
