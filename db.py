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
            remarks TEXT,
            approval_status TEXT NOT NULL DEFAULT 'Pending Approval',
            netsuite_status TEXT NOT NULL DEFAULT 'Not Uploaded',
            netsuite_upload_date TEXT,
            archived INTEGER NOT NULL DEFAULT 0,
            archived_date TEXT
        )
        """
    )
    # Migrations for databases created before these columns existed.
    existing_cols = [row["name"] for row in conn.execute("PRAGMA table_info(bills)").fetchall()]
    if "approval_status" not in existing_cols:
        conn.execute("ALTER TABLE bills ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'Pending Approval'")
    if "netsuite_status" not in existing_cols:
        conn.execute("ALTER TABLE bills ADD COLUMN netsuite_status TEXT NOT NULL DEFAULT 'Not Uploaded'")
    if "netsuite_upload_date" not in existing_cols:
        conn.execute("ALTER TABLE bills ADD COLUMN netsuite_upload_date TEXT")
    if "archived" not in existing_cols:
        conn.execute("ALTER TABLE bills ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
    if "archived_date" not in existing_cols:
        conn.execute("ALTER TABLE bills ADD COLUMN archived_date TEXT")
    conn.commit()
    conn.close()


def add_bill(employee_name, description, date_submitted, period, bill_amount,
             reimbursed_amount, clearing_date, screenshot_path, approved_pdf_path, remarks,
             approval_status="Pending Approval"):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO bills
            (employee_name, description, date_submitted, period, bill_amount,
             reimbursed_amount, clearing_date, screenshot_path, approved_pdf_path, remarks, approval_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (employee_name, description, date_submitted, period, bill_amount,
         reimbursed_amount, clearing_date, screenshot_path, approved_pdf_path, remarks, approval_status),
    )
    conn.commit()
    conn.close()


def update_bill(bill_id, employee_name, description, date_submitted, period, bill_amount,
                 reimbursed_amount, clearing_date, screenshot_path, approved_pdf_path, remarks,
                 approval_status=None):
    conn = get_connection()
    if approval_status is None:
        existing = conn.execute("SELECT approval_status FROM bills WHERE id = ?", (bill_id,)).fetchone()
        approval_status = existing["approval_status"] if existing else "Pending Approval"
    conn.execute(
        """
        UPDATE bills
        SET employee_name = ?, description = ?, date_submitted = ?, period = ?, bill_amount = ?,
            reimbursed_amount = ?, clearing_date = ?, screenshot_path = ?, approved_pdf_path = ?, remarks = ?,
            approval_status = ?
        WHERE id = ?
        """,
        (employee_name, description, date_submitted, period, bill_amount,
         reimbursed_amount, clearing_date, screenshot_path, approved_pdf_path, remarks,
         approval_status, bill_id),
    )
    conn.commit()
    conn.close()


def set_approval_status(bill_id, approval_status):
    conn = get_connection()
    conn.execute("UPDATE bills SET approval_status = ? WHERE id = ?", (approval_status, bill_id))
    conn.commit()
    conn.close()


def set_netsuite_status(bill_id, netsuite_status, upload_date=None):
    conn = get_connection()
    conn.execute(
        "UPDATE bills SET netsuite_status = ?, netsuite_upload_date = ? WHERE id = ?",
        (netsuite_status, upload_date, bill_id),
    )
    conn.commit()
    conn.close()


def delete_bill(bill_id):
    conn = get_connection()
    conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
    conn.commit()
    conn.close()


def get_all_bills(employee_name=None, include_archived=False):
    conn = get_connection()
    archived_clause = "" if include_archived else "AND archived = 0"
    if employee_name:
        rows = conn.execute(
            f"SELECT * FROM bills WHERE employee_name = ? {archived_clause} ORDER BY date_submitted ASC, id ASC",
            (employee_name,),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM bills WHERE 1=1 {archived_clause} ORDER BY date_submitted ASC, id ASC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_archived_bills(employee_name=None):
    conn = get_connection()
    if employee_name:
        rows = conn.execute(
            "SELECT * FROM bills WHERE employee_name = ? AND archived = 1 ORDER BY archived_date DESC, id DESC",
            (employee_name,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM bills WHERE archived = 1 ORDER BY archived_date DESC, id DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def archive_cleared_bills():
    """Archives every currently active, fully-paid bill (bill_amount <= reimbursed_amount).
    Returns the number of bills archived."""
    conn = get_connection()
    today = date.today().isoformat()
    cursor = conn.execute(
        """
        UPDATE bills
        SET archived = 1, archived_date = ?
        WHERE archived = 0 AND bill_amount <= reimbursed_amount
        """,
        (today,),
    )
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def unarchive_bill(bill_id):
    conn = get_connection()
    conn.execute("UPDATE bills SET archived = 0, archived_date = NULL WHERE id = ?", (bill_id,))
    conn.commit()
    conn.close()


def get_bill(bill_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
