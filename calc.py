"""
Pure calculation helpers, shared by the app and the tests.
Keeping these separate from db.py and app.py makes them easy to check on their own.
"""

from datetime import date, datetime


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
