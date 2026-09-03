"""
SQLite storage layer for the Reimbursement Tracker app.
All data lives in reimbursements.db, next to this file.
"""

import sqlite3
import os
from datetime import date

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reimbursements.db")
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")

os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL,
            date_submitted TEXT NOT NULL,
            period TEXT,
            bill_amount REAL NOT NULL DEFAULT 0,
            reimbursed_amount REAL NOT NULL DEFAULT 0,
            clearing_date TEXT,
            screenshot_path TEXT,
            approved_pdf_path TEXT,
            remarks TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def add_bill(employee_name, description, date_submitted, period, bill_amount,
             reimbursed_amount, clearing_date, screenshot_path, approved_pdf_path, remarks):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO bills
            (employee_name, description, date_submitted, period, bill_amount,
             reimbursed_amount, clearing_date, screenshot_path, approved_pdf_path, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (employee_name, description, date_submitted, period, bill_amount,
         reimbursed_amount, clearing_date, screenshot_path, approved_pdf_path, remarks),
    )
    conn.commit()
    conn.close()


def update_bill(bill_id, employee_name, description, date_submitted, period, bill_amount,
                 reimbursed_amount, clearing_date, screenshot_path, approved_pdf_path, remarks):
    conn = get_connection()
    conn.execute(
        """
        UPDATE bills
        SET employee_name = ?, description = ?, date_submitted = ?, period = ?, bill_amount = ?,
            reimbursed_amount = ?, clearing_date = ?, screenshot_path = ?, approved_pdf_path = ?, remarks = ?
        WHERE id = ?
        """,
        (employee_name, description, date_submitted, period, bill_amount,
         reimbursed_amount, clearing_date, screenshot_path, approved_pdf_path, remarks, bill_id),
    )
    conn.commit()
    conn.close()


def delete_bill(bill_id):
    conn = get_connection()
    conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
    conn.commit()
    conn.close()


def get_all_bills(employee_name=None):
    conn = get_connection()
    if employee_name:
        rows = conn.execute(
            "SELECT * FROM bills WHERE employee_name = ? ORDER BY date_submitted ASC, id ASC",
            (employee_name,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM bills ORDER BY date_submitted ASC, id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_bill(bill_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
