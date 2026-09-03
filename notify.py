"""
Sends an email to the manager (CC: every handler/draftsman with an email on
file) whenever a new bill is submitted.

Reads SMTP settings from Streamlit secrets (st.secrets["email"]), so no
credentials are hardcoded or committed to GitHub. See README for setup.

No links are included in the email body (some IT policies block emails
containing links) — it's a plain-text notification only.

Expected secrets.toml shape:

    [email]
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "yourapp@gmail.com"
    sender_password = "your-16-char-app-password"
    manager_email = "manager@company.com"
"""

import smtplib
from email.mime.text import MIMEText

import streamlit as st

import auth


def _get_email_config():
    try:
        cfg = st.secrets["email"]
        required = ["smtp_server", "smtp_port", "sender_email", "sender_password", "manager_email"]
        if all(k in cfg for k in required):
            return cfg
    except Exception:
        pass
    return None


def send_bill_notification(employee_name, description, bill_amount, date_submitted, bill_id):
    """Best-effort email to the manager, CC'd to handlers. Returns (sent: bool, message: str)."""
    cfg = _get_email_config()
    if cfg is None:
        return False, "Email isn't configured yet — ask your admin to add SMTP details in Streamlit secrets."

    cc_list = auth.handler_emails()

    subject = f"New bill submitted — {employee_name} — {bill_amount:,.0f}"
    body = (
        f"{employee_name} has submitted a new reimbursement bill.\n\n"
        f"Description: {description}\n"
        f"Amount: {bill_amount:,.0f}\n"
        f"Date submitted: {date_submitted}\n"
        f"Bill ID: {bill_id}\n\n"
        f"Sign in to the Reimbursement Tracker as usual to Approve or Disapprove this bill."
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = cfg["sender_email"]
    msg["To"] = cfg["manager_email"]
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)

    all_recipients = [cfg["manager_email"]] + cc_list

    try:
        with smtplib.SMTP(cfg["smtp_server"], int(cfg["smtp_port"]), timeout=10) as server:
            server.starttls()
            server.login(cfg["sender_email"], cfg["sender_password"])
            server.sendmail(cfg["sender_email"], all_recipients, msg.as_string())
        if cc_list:
            return True, f"Email sent to manager, CC: {', '.join(cc_list)}."
        return True, "Email sent to manager."
    except Exception as e:
        return False, f"Email could not be sent ({e}). The bill was still saved."
