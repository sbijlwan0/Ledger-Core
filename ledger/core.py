"""In-memory, append-only account ledger. Amounts are signed integer minor units."""
from dataclasses import dataclass
from . import money

FEE_CCY, FEE_MINOR = "AED", 2500          # AED 25.00
RATE_NUM, RATE_DEN = 4, 10000             # 0.04 % per day, simple (no compounding)


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class Entry:
    seq: int
    event_id: str
    booked_day: int
    value_day: int
    account: str
    kind: str          # CREDIT DEBIT SETTLEMENT REVERSAL FEE INTEREST
    amount: int        # signed: + credit, - debit
    ref: str = ""


@dataclass(frozen=True)
class Decision:
    seq: int
    event_id: str
    booked_day: int
    kind: str          # CREDIT DEBIT AUTHORIZATION SETTLEMENT REVERSAL
    account: str
    outcome: str       # ACCEPTED APPROVED DECLINED REJECTED
    reason: str = ""
    ref: str = ""
    amount: int = 0
    value_day: int = 0


class Ledger:
    def __init__(self, accounts):
        self._ccy = dict(accounts)
        self._entries, self._decisions = [], []
        self._seq = 0
        self._capitalized = False

    # ---- read side (copies; internal lists are never exposed) ----
    @property
    def entries(self):
        return tuple(self._entries)

    @property
    def decisions(self):
        return tuple(self._decisions)

    def currency(self, account):
        return self._ccy[account]

    def balance(self, account, day, booked_by=None):
        """Ledger balance: all entries with value_day <= day (holds excluded).
        booked_by limits to entries booked on or before that day (as-booked view)."""
        return sum(e.amount for e in self._entries
                   if e.account == account and e.value_day <= day
                   and (booked_by is None or e.booked_day <= booked_by))

    def _auths(self):
        out = {}
        for d in self._decisions:
            if d.kind == "AUTHORIZATION" and d.outcome in ("APPROVED", "DECLINED"):
                out[d.ref] = dict(state="HOLD" if d.outcome == "APPROVED" else "DECLINED",
                                  amount=d.amount, account=d.account, value_day=d.value_day)
            elif d.kind == "SETTLEMENT" and d.outcome == "ACCEPTED":
                out[d.ref].update(state="SETTLED", settled=d.amount)
        return out

    def holds(self, account):
        return sum(a["amount"] for a in self._auths().values()
                   if a["account"] == account and a["state"] == "HOLD")

    def available(self, account, day):
        return self.balance(account, day) - self.holds(account)

    def auth_table(self):
        """(auth_id, state, detail) in first-seen order. State is derived from the decision log."""
        auths, rows, seen = self._auths(), [], []
        for d in self._decisions:
            if d.kind in ("AUTHORIZATION", "SETTLEMENT") and d.ref not in seen:
                seen.append(d.ref)
        for r in seen:
            a = auths.get(r)
            ccy = self._ccy[a["account"]] if a else None
            if a is None:
                rows.append((r, "UNKNOWN", "never authorized; settlement rejected"))
            elif a["state"] == "SETTLED":
                rows.append((r, "SETTLED", f"hold {money.fmt(a['amount'], ccy)} released, settled {money.fmt(a['settled'], ccy)}"))
            elif a["state"] == "HOLD":
                rows.append((r, "ACTIVE HOLD", money.fmt(a["amount"], ccy)))
            else:
                rows.append((r, "DECLINED", "no hold created"))
        return rows

    # ---- write side (append only) ----
    def _post(self, eid, booked, value, account, kind, amount, ref=""):
        self._seq += 1
        e = Entry(self._seq, eid, booked, value, account, kind, amount, ref)
        self._entries.append(e)
        return e

    def _decide(self, eid, booked, kind, account, outcome, reason="", ref="", amount=0, value_day=0):
        self._seq += 1
        d = Decision(self._seq, eid, booked, kind, account, outcome, reason, ref, amount, value_day)
        self._decisions.append(d)
        return d

    def _check(self, account, amount=1):
        if account not in self._ccy:
            raise LedgerError(f"unknown account {account}")
        if amount <= 0:
            raise LedgerError("amount must be positive")

    def credit(self, eid, booked, account, amount, value_day):
        self._check(account, amount)
        self._post(eid, booked, value_day, account, "CREDIT", amount)
        return self._decide(eid, booked, "CREDIT", account, "ACCEPTED", amount=amount, value_day=value_day)

    def credit_instalments(self, eid, booked, account, total, n, value_day):
        self._check(account, total)
        parts = money.split_equal(total, n)
        for i, p in enumerate(parts, 1):
            self._post(f"{eid}.{i}", booked, value_day, account, "CREDIT", p)
        ccy = self._ccy[account]
        why = "instalments " + ", ".join(money.fmt(p, ccy, False) for p in parts)
        return self._decide(eid, booked, "CREDIT", account, "ACCEPTED", why, amount=total, value_day=value_day)

    def debit(self, eid, booked, account, amount, value_day):
        # Debits are never refused for overdrawing: only authorizations are gated (AMBIGUITIES #15).
        self._check(account, amount)
        self._post(eid, booked, value_day, account, "DEBIT", -amount)
        return self._decide(eid, booked, "DEBIT", account, "ACCEPTED", amount=amount, value_day=value_day)

    def authorize(self, eid, booked, account, auth_id, amount, value_day):
        self._check(account, amount)
        if auth_id in self._auths():
            return self._decide(eid, booked, "AUTHORIZATION", account, "REJECTED",
                                "duplicate authorization id", auth_id, amount, value_day)
        ccy = self._ccy[account]
        avail_after = self.balance(account, value_day) - self.holds(account) - amount
        if avail_after >= 0:
            return self._decide(eid, booked, "AUTHORIZATION", account, "APPROVED",
                                f"available after hold {money.fmt(avail_after, ccy)}", auth_id, amount, value_day)
        return self._decide(eid, booked, "AUTHORIZATION", account, "DECLINED",
                            f"available after hold {money.fmt(avail_after, ccy)} < 0", auth_id, amount, value_day)

    def settle(self, eid, booked, account, auth_id, amount, value_day):
        self._check(account, amount)
        a = self._auths().get(auth_id)
        rej = lambda why: self._decide(eid, booked, "SETTLEMENT", account, "REJECTED", why, auth_id, amount, value_day)
        if a is None:
            return rej(f"authorization {auth_id} not present in ledger; funds not moved")
        if a["account"] != account:
            return rej("authorization belongs to another account")
        if a["state"] != "HOLD":
            return rej(f"authorization is {a['state']}, not an active hold")
        if amount > a["amount"]:
            return rej("settlement exceeds held amount")
        self._post(eid, booked, value_day, account, "SETTLEMENT", -amount, auth_id)
        return self._decide(eid, booked, "SETTLEMENT", account, "ACCEPTED", "", auth_id, amount, value_day)

    def reverse(self, eid, booked, account, ref_event, value_day):
        """Reverse = append counter-entries; the original is never touched."""
        targets = [e for e in self._entries if e.account == account and e.kind in ("CREDIT", "DEBIT")
                   and (e.event_id == ref_event or e.event_id.startswith(ref_event + "."))]
        rej = lambda why: self._decide(eid, booked, "REVERSAL", account, "REJECTED", why, ref_event, 0, value_day)
        if not targets:
            return rej(f"{ref_event} not found or not reversible")
        if any(e.kind == "REVERSAL" and e.ref in {t.event_id for t in targets} for e in self._entries):
            return rej(f"{ref_event} already reversed")
        for t in targets:
            self._post(f"{eid}:{t.event_id}", booked, value_day, account, "REVERSAL", -t.amount, t.event_id)
        return self._decide(eid, booked, "REVERSAL", account, "ACCEPTED", "", ref_event, sum(-t.amount for t in targets), value_day)
