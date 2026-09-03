"""
Pure calculation helpers, shared by the app and the tests.
Keeping these separate from db.py and app.py makes them easy to check on their own.
"""

from datetime import date, datetime, timedelta


def parse_date(value):
    """Accepts a date, a datetime, an ISO string, or None/empty. Returns a date or None."""
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def month_name(date_submitted):
    d = parse_date(date_submitted)
    return d.strftime("%B") if d else ""


def balance_due(bill_amount, reimbursed_amount):
    bill_amount = bill_amount or 0
    reimbursed_amount = reimbursed_amount or 0
    return round(bill_amount - reimbursed_amount, 2)


def status(bill_amount, reimbursed_amount):
    bal = balance_due(bill_amount, reimbursed_amount)
    reimbursed_amount = reimbursed_amount or 0
    if bal <= 0:
        return "Cleared"
    if reimbursed_amount > 0:
        return "Partially Cleared"
    return "Pending"


def days_outstanding(date_submitted, bill_amount, reimbursed_amount, today=None):
    """Days since submission, only while a balance remains. Empty string otherwise."""
    if balance_due(bill_amount, reimbursed_amount) <= 0:
        return ""
    d = parse_date(date_submitted)
    if d is None:
        return ""
    today = today or date.today()
    return (today - d).days


def is_late_submission(date_submitted, billing_month=None):
    """Company rule: a bill for a given billing month must be submitted on or before
    the 3rd of the following month. billing_month is any date within the month the
    bill covers (e.g. any date in August for an August bill) — the day is ignored.

    If billing_month isn't provided (older bills saved before this field existed),
    falls back to the old rule: submitted on or before the 3rd of the month it was
    literally submitted in.
    """
    d = parse_date(date_submitted)
    if d is None:
        return False
    if billing_month is None:
        return d.day > 3
    bm = parse_date(billing_month)
    if bm is None:
        return d.day > 3
    deadline = billing_deadline(bm)
    return d > deadline


def billing_deadline(billing_month):
    """The 3rd of the month after the given billing month (any date within it)."""
    bm = parse_date(billing_month)
    year = bm.year + (bm.month // 12)
    month = bm.month % 12 + 1
    return date(year, month, 3)


def billing_month_label(billing_month):
    """Human-readable label, e.g. 'August 2026'. Empty string if not set."""
    bm = parse_date(billing_month)
    return bm.strftime("%B %Y") if bm else ""


# ---------------------------------------------------------------
# Travel auto-calculate — matches the original HTML form's rules
# ---------------------------------------------------------------

def trip_days(departure, return_date):
    """Number of days on trip, inclusive of both ends. 0 if dates are missing/invalid."""
    dep = parse_date(departure)
    ret = parse_date(return_date)
    if dep is None or ret is None or ret < dep:
        return 0
    return (ret - dep).days + 1


def trip_day_range(departure, return_date):
    """List of ISO date strings from departure to return, inclusive."""
    dep = parse_date(departure)
    ret = parse_date(return_date)
    if dep is None or ret is None or ret < dep:
        return []
    days = []
    d = dep
    while d <= ret:
        days.append(d.isoformat())
        d += timedelta(days=1)
    return days


def food_da_rate(level, same_day):
    """Daily food/DA rate for a management level.
    level: 'upper', 'middle', or 'junior'. same_day only matters for 'middle'.
    Returns (rate, label). rate is None for 'upper' (as-per-actual, needs manual entry).
    """
    if level == "upper":
        return None, "As per Actual"
    if level == "junior":
        return 1000, "Rs. 1,000 (fixed)"
    if level == "middle":
        if same_day:
            return 2000, "Rs. 2,000 (same-day)"
        return 3000, "Rs. 3,000 (overnight)"
    return None, ""


def fuel_amount(km, rate_per_km=15):
    """Own-vehicle fuel reimbursement: Rs. 15/km by default."""
    km = km or 0
    return round(km * rate_per_km, 2)


def accommodation_rate(level):
    """Company-billed accommodation cap by management level."""
    return {"upper": 18000, "middle": 12000, "junior": 8000}.get(level, 0)
