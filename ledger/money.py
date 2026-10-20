"""Integer minor-unit money helpers. No floats anywhere in the engine."""
from decimal import Decimal

DECIMALS = {"AED": 2, "BHD": 3}


def to_minor(text, ccy):
    """Parse a decimal string into minor units. Over-precise input is an
    error, never silently rounded (amounts are stored at their own precision)."""
    places = DECIMALS[ccy]
    scaled = Decimal(str(text).replace(",", "")).scaleb(places)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{text} has more than {places} decimals for {ccy}")
    return int(scaled)


def fmt(minor, ccy, with_ccy=True):
    places = DECIMALS[ccy]
    q, r = divmod(abs(minor), 10 ** places)
    s = f"{'-' if minor < 0 else ''}{q:,}.{r:0{places}d}"
    return f"{ccy} {s}" if with_ccy else s


def div_round_half_up(num, den):
    """num/den rounded half away from zero, integers only."""
    q, r = divmod(abs(num), den)
    if 2 * r >= den:
        q += 1
    return q if num >= 0 else -q


def split_equal(total, n):
    """Split total (>0) into n parts as equal as the unit allows; the
    indivisible remainder goes to the last part so the parts sum exactly."""
    assert total > 0 and n > 0
    base, rem = divmod(total, n)
    parts = [base] * n
    parts[-1] += rem
    return parts
