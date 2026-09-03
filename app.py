"""
Reimbursement Tracker — multi-user version
Run with:  streamlit run app.py
"""

import os
from datetime import date

import pandas as pd
import streamlit as st

import db
import calc
import auth

st.set_page_config(page_title="Reimbursement Tracker", layout="wide")
db.init_db()


# ---------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("Reimbursement Tracker — Sign in")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_clicked = st.form_submit_button("Sign in", type="primary")
    if login_clicked:
        user = auth.check_login(username.strip(), password)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Incorrect username or password.")
    st.stop()

current_user = st.session_state.user
is_manager = current_user["role"] == "manager"

# ---------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------

def load_dataframe(employee_filter=None):
    rows = db.get_all_bills(employee_name=employee_filter)
    cols = ["id", "employee_name", "description", "date_submitted", "period", "bill_amount",
            "reimbursed_amount", "clearing_date", "screenshot_path", "approved_pdf_path", "remarks"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df["month"] = df["date_submitted"].apply(calc.month_name)
    df["balance_due"] = df.apply(lambda r: calc.balance_due(r["bill_amount"], r["reimbursed_amount"]), axis=1)
    df["status"] = df.apply(lambda r: calc.status(r["bill_amount"], r["reimbursed_amount"]), axis=1)
    df["days_outstanding"] = df.apply(
        lambda r: calc.days_outstanding(r["date_submitted"], r["bill_amount"], r["reimbursed_amount"]), axis=1)
    return df


def save_uploaded_file(uploaded_file, bill_id, kind):
    """kind is 'shot' or 'pdf' — used to keep filenames distinct per bill."""
    if uploaded_file is None:
        return None
    ext = os.path.splitext(uploaded_file.name)[1]
    dest_name = f"bill_{bill_id}_{kind}{ext}"
    dest_path = os.path.join(db.SCREENSHOT_DIR, dest_name)
    with open(dest_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest_path


# ---------------------------------------------------------------
# HEADER / SIDEBAR
# ---------------------------------------------------------------
st.sidebar.write(f"Signed in as **{current_user['display_name']}** ({current_user['role']})")
if st.sidebar.button("Sign out"):
    st.session_state.user = None
    st.rerun()

st.title("Reimbursement Tracker")

if is_manager:
    tab_names = ["Dashboard", "All Bills", "Add New Bill", "Manage Team"]
else:
    tab_names = ["My Dashboard", "My Bills", "Add New Bill"]

tabs = st.tabs(tab_names)

# For an employee, everything is scoped to their own name automatically.
scope_employee = None if is_manager else current_user["display_name"]

# ---------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------
with tabs[0]:
    if is_manager:
        employee_options = ["All"] + auth.all_employee_names()
        picked = st.selectbox("Show data for", employee_options)
        df = load_dataframe(None if picked == "All" else picked)
    else:
        df = load_dataframe(scope_employee)

    total_bills = len(df)
    total_billed = df["bill_amount"].sum() if not df.empty else 0
    total_reimbursed = df["reimbursed_amount"].sum() if not df.empty else 0
    balance_outstanding = df["balance_due"].sum() if not df.empty else 0
    fully_cleared = (df["status"] == "Cleared").sum() if not df.empty else 0
    still_open = total_bills - fully_cleared

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Bills", total_bills)
    c2.metric("Total Billed", f"{total_billed:,.0f}")
    c3.metric("Total Reimbursed", f"{total_reimbursed:,.0f}")
    c4.metric("Balance Outstanding", f"{balance_outstanding:,.0f}")
    c5.metric("Fully Cleared", fully_cleared)
    c6.metric("Partial / Pending", still_open)

    st.divider()
    left, right = st.columns(2)
    with left:
        st.subheader("Reimbursed vs Outstanding")
        if total_billed > 0:
            st.bar_chart(pd.DataFrame({
                "Category": ["Reimbursed", "Outstanding"],
                "Amount": [total_reimbursed, balance_outstanding],
            }).set_index("Category"))
        else:
            st.caption("No bills yet.")
    with right:
        if is_manager:
            st.subheader("Outstanding Balance by Employee")
            all_df = load_dataframe(None)
            if not all_df.empty:
                by_emp = all_df.groupby("employee_name")["balance_due"].sum()
                st.bar_chart(by_emp)
            else:
                st.caption("No bills yet.")
        else:
            st.subheader("Bills by Status")
            if not df.empty:
                st.bar_chart(df["status"].value_counts())
            else:
                st.caption("No bills yet.")

# ---------------------------------------------------------------
# ALL BILLS / MY BILLS
# ---------------------------------------------------------------
with tabs[1]:
    if is_manager:
        employee_options = ["All"] + auth.all_employee_names()
        filt = st.selectbox("Filter by employee", employee_options, key="bills_filter")
        df = load_dataframe(None if filt == "All" else filt)
    else:
        df = load_dataframe(scope_employee)

    if df.empty:
        st.info("No bills yet.")
    else:
        st.caption("Edit Reimbursed Amount, dates, or Remarks directly below, then press Save changes. "
                    "Balance Due and Status update on their own.")

        display_df = df.copy()
        display_df["Screenshot"] = display_df["screenshot_path"].apply(
            lambda p: "Attached" if p and os.path.exists(p) else "None")
        display_df["Approved PDF"] = display_df["approved_pdf_path"].apply(
            lambda p: "Attached" if p and os.path.exists(p) else "None")

        show_cols = ["id", "employee_name", "description", "date_submitted", "period", "month",
                     "bill_amount", "reimbursed_amount", "balance_due", "status",
                     "clearing_date", "days_outstanding", "Screenshot", "Approved PDF", "remarks"]

        col_config = {
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "employee_name": st.column_config.TextColumn("Employee", disabled=not is_manager),
            "description": st.column_config.TextColumn("Bill / Expense Description"),
            "date_submitted": st.column_config.TextColumn("Date Submitted (YYYY-MM-DD)"),
            "period": st.column_config.TextColumn("Period"),
            "month": st.column_config.TextColumn("Month", disabled=True),
            "bill_amount": st.column_config.NumberColumn("Bill Amount"),
            "reimbursed_amount": st.column_config.NumberColumn("Reimbursed Amount"),
            "balance_due": st.column_config.NumberColumn("Balance Due", disabled=True),
            "status": st.column_config.TextColumn("Status", disabled=True),
            "clearing_date": st.column_config.TextColumn("Clearing Date (YYYY-MM-DD)"),
            "days_outstanding": st.column_config.TextColumn("Days Outstanding", disabled=True),
            "Screenshot": st.column_config.TextColumn("Screenshot", disabled=True),
            "Approved PDF": st.column_config.TextColumn("Approved PDF", disabled=True),
            "remarks": st.column_config.TextColumn("Remarks"),
        }

        edited = st.data_editor(
            display_df[show_cols], column_config=col_config,
            hide_index=True, use_container_width=True, key="bills_editor",
        )

        if st.button("Save changes", type="primary"):
            for _, row in edited.iterrows():
                original = df.loc[df["id"] == row["id"]].iloc[0]
                db.update_bill(
                    bill_id=int(row["id"]),
                    employee_name=row["employee_name"] if is_manager else original["employee_name"],
                    description=row["description"],
                    date_submitted=row["date_submitted"],
                    period=row["period"],
                    bill_amount=float(row["bill_amount"] or 0),
                    reimbursed_amount=float(row["reimbursed_amount"] or 0),
                    clearing_date=row["clearing_date"] or None,
                    screenshot_path=original["screenshot_path"],
                    approved_pdf_path=original["approved_pdf_path"],
                    remarks=row["remarks"],
                )
            st.success("Changes saved.")
            st.rerun()

        st.divider()
        st.subheader("Attach files to a bill")
        bill_choice = st.selectbox(
            "Select a bill",
            options=df["id"].tolist(),
            format_func=lambda i: f"#{i} - {df.loc[df['id'] == i, 'description'].values[0]}",
        )
        colA, colB = st.columns(2)
        with colA:
            shot_upload = st.file_uploader("Screenshot (proof of clearance)", type=["png", "jpg", "jpeg"], key="shot_up")
            if shot_upload is not None and st.button("Attach screenshot"):
                bill = db.get_bill(int(bill_choice))
                path = save_uploaded_file(shot_upload, bill_choice, "shot")
                db.update_bill(bill["id"], bill["employee_name"], bill["description"], bill["date_submitted"],
                                bill["period"], bill["bill_amount"], bill["reimbursed_amount"],
                                bill["clearing_date"], path, bill["approved_pdf_path"], bill["remarks"])
                st.success("Screenshot attached.")
                st.rerun()
        with colB:
            pdf_upload = st.file_uploader("Original approved bill (PDF)", type=["pdf"], key="pdf_up")
            if pdf_upload is not None and st.button("Attach approved PDF"):
                bill = db.get_bill(int(bill_choice))
                path = save_uploaded_file(pdf_upload, bill_choice, "pdf")
                db.update_bill(bill["id"], bill["employee_name"], bill["description"], bill["date_submitted"],
                                bill["period"], bill["bill_amount"], bill["reimbursed_amount"],
                                bill["clearing_date"], bill["screenshot_path"], path, bill["remarks"])
                st.success("Approved PDF attached.")
                st.rerun()

        current = db.get_bill(int(bill_choice))
        if current:
            if current.get("screenshot_path") and os.path.exists(current["screenshot_path"]):
                st.image(current["screenshot_path"], caption="Screenshot", width=300)
            if current.get("approved_pdf_path") and os.path.exists(current["approved_pdf_path"]):
                with open(current["approved_pdf_path"], "rb") as f:
                    st.download_button("Download approved bill PDF", f, file_name=os.path.basename(current["approved_pdf_path"]))

        if is_manager:
            st.divider()
            st.subheader("Delete a bill")
            del_choice = st.selectbox(
                "Select a bill to delete", options=df["id"].tolist(),
                format_func=lambda i: f"#{i} - {df.loc[df['id'] == i, 'description'].values[0]}",
                key="delete_select",
            )
            if st.button("Delete selected bill"):
                db.delete_bill(int(del_choice))
                st.warning(f"Bill #{del_choice} deleted.")
                st.rerun()

# ---------------------------------------------------------------
# ADD NEW BILL
# ---------------------------------------------------------------
with tabs[2]:
    st.subheader("Add a new bill")
    with st.form("add_bill_form", clear_on_submit=True):
        if is_manager:
            employee_name = st.selectbox("Employee", auth.all_employee_names())
        else:
            employee_name = current_user["display_name"]
            st.text_input("Employee", value=employee_name, disabled=True)

        description = st.text_input("Bill / Expense Description")
        col1, col2 = st.columns(2)
        with col1:
            date_submitted = st.date_input("Date of Submission", value=date.today())
            bill_amount = st.number_input("Bill Amount", min_value=0.0, step=100.0)
            has_clearing_date = st.checkbox("Clearing date known?")
            clearing_date = st.date_input("Clearing Date", value=date.today()) if has_clearing_date else None
        with col2:
            period = st.text_input("Period (e.g. 1 Aug - 5 Aug 2026)")
            reimbursed_amount = st.number_input("Reimbursed Amount so far", min_value=0.0, step=100.0)
            screenshot = st.file_uploader("Screenshot (optional)", type=["png", "jpg", "jpeg"])
            approved_pdf = st.file_uploader("Original approved bill PDF (optional)", type=["pdf"])
        remarks = st.text_area("Remarks")

        submitted = st.form_submit_button("Save bill", type="primary")
        if submitted:
            if not description.strip():
                st.error("Bill description is required.")
            else:
                db.add_bill(
                    employee_name=employee_name,
                    description=description.strip(),
                    date_submitted=date_submitted.isoformat(),
                    period=period.strip(),
                    bill_amount=bill_amount,
                    reimbursed_amount=reimbursed_amount,
                    clearing_date=clearing_date.isoformat() if clearing_date else None,
                    screenshot_path=None,
                    approved_pdf_path=None,
                    remarks=remarks.strip(),
                )
                new_id = db.get_all_bills()[-1]["id"]
                shot_path = save_uploaded_file(screenshot, new_id, "shot") if screenshot else None
                pdf_path = save_uploaded_file(approved_pdf, new_id, "pdf") if approved_pdf else None
                if shot_path or pdf_path:
                    bill = db.get_bill(new_id)
                    db.update_bill(new_id, bill["employee_name"], bill["description"], bill["date_submitted"],
                                    bill["period"], bill["bill_amount"], bill["reimbursed_amount"],
                                    bill["clearing_date"], shot_path or bill["screenshot_path"],
                                    pdf_path or bill["approved_pdf_path"], bill["remarks"])
                st.success("Bill saved.")
                st.rerun()

# ---------------------------------------------------------------
# MANAGE TEAM (manager only)
# ---------------------------------------------------------------
if is_manager:
    with tabs[3]:
        st.subheader("Team members")
        users = auth.load_users()
        st.table(pd.DataFrame(users)[["display_name", "username", "role"]])

        st.divider()
        st.subheader("Add a team member")
        with st.form("add_user_form", clear_on_submit=True):
            new_display = st.text_input("Full name (shown on bills)")
            new_username = st.text_input("Username (for login)")
            new_password = st.text_input("Password", type="password")
            new_role = st.selectbox("Role", ["employee", "manager"])
            add_clicked = st.form_submit_button("Add team member", type="primary")
            if add_clicked:
                if not (new_display and new_username and new_password):
                    st.error("Fill in all fields.")
                elif auth.add_user(new_username.strip(), new_password, new_role, new_display.strip()):
                    st.success(f"{new_display} added.")
                    st.rerun()
                else:
                    st.error("That username already exists.")

        st.divider()
        st.subheader("Remove a team member")
        removable = [u["username"] for u in users if u["username"] != current_user["username"]]
        if removable:
            del_user = st.selectbox("Select username to remove", removable)
            if st.button("Remove team member"):
                auth.delete_user(del_user)
                st.warning(f"{del_user} removed.")
                st.rerun()
        else:
            st.caption("No other team members to remove.")
