"""
Reimbursement Tracker — multi-user version
Run with:  streamlit run app.py
"""

import os
import io
import json
import zipfile
import base64
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import db
import calc
import auth
import notify

st.set_page_config(page_title="C&I Reimbursement Tracker", page_icon="💼", layout="wide")
db.init_db()


# ---------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.markdown(
        """
        <style>
        #MainMenu, footer, header {visibility: hidden;}
        .login-hero {
            background: linear-gradient(135deg, #1F4E78 0%, #2E6DA4 100%);
            padding: 36px 40px;
            border-radius: 14px 14px 0 0;
            color: white;
            text-align: center;
        }
        .login-hero h1 {
            margin: 0;
            font-size: 26px;
            font-weight: 700;
            letter-spacing: 0.3px;
        }
        .login-hero p {
            margin: 6px 0 0 0;
            font-size: 14px;
            opacity: 0.9;
        }
        .login-card {
            border: 1px solid #E3E8EF;
            border-radius: 0 0 14px 14px;
            padding: 28px 40px 32px 40px;
            background: #FFFFFF;
            box-shadow: 0 4px 18px rgba(0,0,0,0.06);
        }
        .login-footer {
            text-align: center;
            font-size: 12px;
            color: #8A93A3;
            margin-top: 14px;
        }
        div[data-testid="stForm"] {
            border: none;
            padding: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.markdown(
            """
            <div class="login-hero">
                <h1>Sky Electric (Pvt.) Ltd.</h1>
                <p>C&amp;I Operations &nbsp;•&nbsp; Reimbursement Tracker</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.caption("Track submission, clearance, and outstanding balances for Commercial & Industrial project expenses.")
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="e.g. owais")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            login_clicked = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if login_clicked:
            user = auth.check_login(username.strip(), password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Incorrect username or password.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(
            '<div class="login-footer">Internal use only — Sky Electric C&amp;I Operations</div>',
            unsafe_allow_html=True,
        )
    st.stop()

current_user = st.session_state.user
is_manager = current_user["role"] == "manager"
is_handler = current_user["role"] == "handler"

# ---------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------

def load_dataframe(employee_filter=None):
    rows = db.get_all_bills(employee_name=employee_filter)
    cols = ["id", "employee_name", "description", "date_submitted", "period", "bill_amount",
            "reimbursed_amount", "clearing_date", "screenshot_path", "approved_pdf_path", "remarks",
            "approval_status", "netsuite_status", "netsuite_upload_date", "billing_month"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df["month"] = df.apply(
        lambda r: calc.billing_month_label(r["billing_month"]) or calc.month_name(r["date_submitted"]), axis=1)
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


def file_exists(p):
    """Safely check a stored path — handles None, NaN, and pandas NA without crashing."""
    if p is None or not isinstance(p, str) or not p:
        return False
    try:
        return os.path.exists(p)
    except (TypeError, ValueError):
        return False


def render_pdf_viewer(pdf_path, label="View PDF"):
    """Shows a PDF inline inside an expander, using the browser's built-in PDF viewer."""
    with open(pdf_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    with st.expander(label):
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="500" '
            f'style="border: 1px solid #E3E8EF; border-radius: 6px;"></iframe>',
            unsafe_allow_html=True,
        )


@st.cache_resource
def expense_form_base64():
    """Builds a fully self-contained base64 blob of the expense claim form — the
    HTML with jsPDF inlined directly into it — so opening it makes zero server
    requests (sidesteps Streamlit's static-file serving, which forces .html/.js
    to text/plain, and avoids putting a giant data: URL in the address bar)."""
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    with open(os.path.join(static_dir, "expense_claim_form.html"), encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(static_dir, "jspdf.umd.min.js"), encoding="utf-8") as f:
        js = f.read()
    html = html.replace(
        '<script src="jspdf.umd.min.js"></script>',
        f"<script>{js}</script>",
    )
    return base64.b64encode(html.encode("utf-8")).decode("ascii")


# ---------------------------------------------------------------
# HEADER / SIDEBAR
# ---------------------------------------------------------------
st.sidebar.write(f"Signed in as **{current_user['display_name']}** ({current_user['role']})")
if st.sidebar.button("Sign out"):
    st.session_state.user = None
    st.rerun()

st.title("Reimbursement Tracker")

if is_manager:
    tab_names = ["Dashboard", "All Bills", "Add New Bill", "Archive", "Manage Team"]
elif is_handler:
    tab_names = ["Dashboard", "Bills to Upload"]
else:
    tab_names = ["My Dashboard", "My Bills", "Add New Bill", "Archive"]

tabs = st.tabs(tab_names)

# Manager and handler both see everyone's bills; an employee only sees their own.
scope_employee = None if (is_manager or is_handler) else current_user["display_name"]

# ---------------------------------------------------------------
# HANDLER / DRAFTSMAN — approved bills, NetSuite upload tracking
# ---------------------------------------------------------------
if is_handler:
    with tabs[0]:
        all_df = load_dataframe(None)
        approved_df = all_df[all_df["approval_status"] == "Approved"] if not all_df.empty else all_df

        total_approved = len(approved_df)
        uploaded_count = (approved_df["netsuite_status"] == "Uploaded").sum() if not approved_df.empty else 0
        not_uploaded_count = total_approved - uploaded_count
        approved_amount = approved_df["bill_amount"].sum() if not approved_df.empty else 0
        uploaded_amount = approved_df.loc[approved_df["netsuite_status"] == "Uploaded", "bill_amount"].sum() \
            if not approved_df.empty else 0
        pending_upload_amount = approved_amount - uploaded_amount

        row1 = st.columns(3)
        row1[0].metric("Approved Bills", total_approved)
        row1[1].metric("Uploaded to NetSuite", int(uploaded_count))
        row1[2].metric("Not Yet Uploaded", int(not_uploaded_count))

        row2 = st.columns(2)
        row2[0].metric("Approved Amount", f"{approved_amount:,.0f}")
        row2[1].metric("Amount Pending Upload", f"{pending_upload_amount:,.0f}")

        st.divider()
        st.subheader("Not Yet Uploaded, by Employee")
        if not approved_df.empty:
            pending_df = approved_df[approved_df["netsuite_status"] != "Uploaded"]
            if not pending_df.empty:
                st.bar_chart(pending_df.groupby("employee_name")["bill_amount"].sum())
            else:
                st.caption("Everything approved so far has been uploaded.")
        else:
            st.caption("No approved bills yet.")

    with tabs[1]:
        employee_options = ["All"] + auth.all_employee_names()
        filt = st.selectbox("Filter by employee", employee_options, key="handler_filter")
        status_filt = st.radio("Show", ["Not Uploaded", "Uploaded", "All"], horizontal=True)

        all_df = load_dataframe(None if filt == "All" else filt)
        approved_df = all_df[all_df["approval_status"] == "Approved"] if not all_df.empty else all_df
        if status_filt != "All" and not approved_df.empty:
            approved_df = approved_df[approved_df["netsuite_status"] == status_filt]

        if approved_df.empty:
            st.info("No approved bills match this view.")
        else:
            pdf_rows = approved_df[approved_df["approved_pdf_path"].apply(file_exists)]
            if not pdf_rows.empty:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for _, r in pdf_rows.iterrows():
                        path = r["approved_pdf_path"]
                        filename = f"{r['id']}_{r['description']}{os.path.splitext(path)[1]}"
                        filename = "".join(c for c in filename if c not in '\\/:*?"<>|')
                        if filt == "All":
                            safe_employee = "".join(c for c in r["employee_name"] if c not in '\\/:*?"<>|').strip() or "Unassigned"
                            arcname = f"{safe_employee}/{filename}"
                        else:
                            arcname = filename
                        zf.write(path, arcname=arcname)
                zip_buffer.seek(0)
                st.download_button(
                    "Download these approved bill PDFs (ZIP)", data=zip_buffer,
                    file_name="approved_bills.zip", mime="application/zip",
                )
                st.caption(f"{len(pdf_rows)} bill(s) with an approved PDF, ready for NetSuite.")

            st.divider()
            for _, r in approved_df.sort_values("date_submitted").iterrows():
                with st.container(border=True):
                    cols = st.columns([3, 2, 2, 2])
                    cols[0].write(f"**{r['description']}** — {r['employee_name']}")
                    cols[1].write(f"Amount: {r['bill_amount']:,.0f}")
                    cols[2].write(f"NetSuite: **{r['netsuite_status']}**")
                    if r["netsuite_status"] == "Uploaded" and r.get("netsuite_upload_date"):
                        cols[2].caption(f"Uploaded {r['netsuite_upload_date']}")
                    with cols[3]:
                        if r["netsuite_status"] != "Uploaded":
                            if st.button("Mark uploaded", key=f"upload_{r['id']}"):
                                db.set_netsuite_status(int(r["id"]), "Uploaded", date.today().isoformat())
                                st.rerun()
                        else:
                            if st.button("Revert to not uploaded", key=f"revert_{r['id']}"):
                                db.set_netsuite_status(int(r["id"]), "Not Uploaded", None)
                                st.rerun()
                    if file_exists(r.get("approved_pdf_path")):
                        render_pdf_viewer(r["approved_pdf_path"], label=f"View PDF — bill #{r['id']}")
    st.stop()

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
    late_count = df.apply(
        lambda r: calc.is_late_submission(r["date_submitted"], r["billing_month"]), axis=1).sum() \
        if not df.empty else 0
    pending_approval = (df["approval_status"] == "Pending Approval").sum() if not df.empty else 0

    row1 = st.columns(4)
    row1[0].metric("Total Bills", total_bills)
    row1[1].metric("Total Billed", f"{total_billed:,.0f}")
    row1[2].metric("Total Reimbursed", f"{total_reimbursed:,.0f}")
    row1[3].metric("Balance Outstanding", f"{balance_outstanding:,.0f}")

    row2 = st.columns(4)
    row2[0].metric("Fully Cleared", fully_cleared)
    row2[1].metric("Partial / Pending", still_open)
    row2[2].metric("Late Submissions", int(late_count))
    row2[3].metric("Pending Approval", int(pending_approval))

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

    no_bills_at_all = df.empty

    status_filt = st.radio(
        "Show", ["Unpaid & Partial", "All", "Fully Cleared"], horizontal=True, key="bills_status_filter")
    if not df.empty and status_filt == "Unpaid & Partial":
        df = df[df["status"] != "Cleared"]
    elif not df.empty and status_filt == "Fully Cleared":
        df = df[df["status"] == "Cleared"]

    if df.empty:
        if no_bills_at_all:
            st.info("No bills yet.")
        elif status_filt == "Unpaid & Partial":
            st.success("Nothing unpaid or partial right now — everything here is fully cleared.")
        else:
            st.info("No fully cleared bills in this view yet.")
    else:
        st.caption("Edit Reimbursed Amount, dates, or Remarks directly below, then press Save changes. "
                    "Balance Due and Status update on their own.")

        pdf_rows = df[df["approved_pdf_path"].apply(file_exists)]
        if not pdf_rows.empty:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for _, r in pdf_rows.iterrows():
                    path = r["approved_pdf_path"]
                    filename = f"{r['id']}_{r['description']}{os.path.splitext(path)[1]}"
                    filename = "".join(c for c in filename if c not in '\\/:*?"<>|')
                    if is_manager and filt == "All":
                        safe_employee = "".join(c for c in r["employee_name"] if c not in '\\/:*?"<>|').strip() or "Unassigned"
                        arcname = f"{safe_employee}/{filename}"
                    else:
                        arcname = filename
                    zf.write(path, arcname=arcname)
            zip_buffer.seek(0)
            if is_manager:
                label = "Download all approved bill PDFs (ZIP, by employee folder)" if filt == "All" \
                    else f"Download {filt}'s approved bill PDFs (ZIP)"
            else:
                label = "Download my approved bill PDFs (ZIP)"
            st.download_button(
                label, data=zip_buffer, file_name="approved_bills.zip", mime="application/zip",
            )
            st.caption(f"{len(pdf_rows)} bill(s) with an approved PDF attached.")
        else:
            st.caption("No approved bill PDFs attached yet for this view.")

        display_df = df.copy()
        display_df["Screenshot"] = display_df["screenshot_path"].apply(
            lambda p: "Attached" if file_exists(p) else "None")
        display_df["Approved PDF"] = display_df["approved_pdf_path"].apply(
            lambda p: "Attached" if file_exists(p) else "None")
        display_df["Submission"] = display_df.apply(
            lambda r: "Late" if calc.is_late_submission(r["date_submitted"], r["billing_month"]) else "On time",
            axis=1)

        show_cols = ["id", "employee_name", "description", "date_submitted", "Submission", "period", "month",
                     "bill_amount", "reimbursed_amount", "balance_due", "status", "approval_status",
                     "clearing_date", "days_outstanding", "Screenshot", "Approved PDF", "remarks"]

        col_config = {
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "employee_name": st.column_config.TextColumn("Employee", disabled=not is_manager),
            "description": st.column_config.TextColumn("Bill / Expense Description"),
            "date_submitted": st.column_config.TextColumn("Date Submitted (YYYY-MM-DD)"),
            "Submission": st.column_config.TextColumn("Submission", disabled=True),
            "period": st.column_config.TextColumn("Period"),
            "month": st.column_config.TextColumn("Month", disabled=True),
            "bill_amount": st.column_config.NumberColumn("Bill Amount"),
            "reimbursed_amount": st.column_config.NumberColumn("Reimbursed Amount"),
            "balance_due": st.column_config.NumberColumn("Balance Due", disabled=True),
            "status": st.column_config.TextColumn("Status", disabled=True),
            "approval_status": st.column_config.SelectboxColumn(
                "Approval", options=["Pending Approval", "Approved", "Disapproved"],
                disabled=not is_manager),
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
            missing_screenshot = []
            for _, row in edited.iterrows():
                original = df.loc[df["id"] == row["id"]].iloc[0]
                new_reimbursed = float(row["reimbursed_amount"] or 0)
                if new_reimbursed > 0 and not file_exists(original["screenshot_path"]):
                    missing_screenshot.append(int(row["id"]))

            if missing_screenshot:
                ids_str = ", ".join(f"#{i}" for i in missing_screenshot)
                st.error(
                    f"A screenshot is required as proof of clearance for bill(s) {ids_str} "
                    f"since a Reimbursed Amount is set. Attach one below under 'View or attach "
                    f"files for a bill' first, then save changes again."
                )
            else:
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
                        approval_status=row["approval_status"] if is_manager else original["approval_status"],
                    )
                st.success("Changes saved.")
                st.rerun()

        st.divider()
        st.subheader("View or attach files for a bill")
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
            if file_exists(current.get("screenshot_path")):
                st.image(current["screenshot_path"], caption="Screenshot", width=300)
            if file_exists(current.get("approved_pdf_path")):
                render_pdf_viewer(current["approved_pdf_path"], label="View approved bill PDF")
                with open(current["approved_pdf_path"], "rb") as f:
                    st.download_button("Download approved bill PDF", f, file_name=os.path.basename(current["approved_pdf_path"]))

            st.write(f"**Approval status:** {current['approval_status']}")
            if is_manager:
                colApp, colDis = st.columns(2)
                with colApp:
                    if st.button("Approve this bill", type="primary"):
                        db.set_approval_status(current["id"], "Approved")
                        st.success("Bill approved.")
                        st.rerun()
                with colDis:
                    if st.button("Disapprove this bill"):
                        db.set_approval_status(current["id"], "Disapproved")
                        st.warning("Bill disapproved.")
                        st.rerun()

            st.divider()
            st.caption("Notify the manager (CC: handlers) about this specific bill, whenever you want — nothing sends automatically.")
            if st.button("Send notification email for this bill", key=f"notify_{current['id']}"):
                sent, msg = notify.send_bill_notification(
                    employee_name=current["employee_name"], description=current["description"],
                    bill_amount=current["bill_amount"], date_submitted=current["date_submitted"],
                    bill_id=current["id"],
                )
                if sent:
                    st.success(msg)
                else:
                    st.warning(msg)

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
    st.info(
        "Company rule: a bill must be submitted on or before the 3rd of the month "
        "AFTER the billing month it covers — e.g. an August bill can be submitted "
        "any time up to 3 September."
    )

    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    prev_month_date = (date.today().replace(day=1) - timedelta(days=1))
    default_month_index = prev_month_date.month - 1
    default_year = prev_month_date.year

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
            bill_amount = st.number_input("Bill Amount *", min_value=0.0, step=100.0)
            has_clearing_date = st.checkbox("Clearing date known?")
            clearing_date = st.date_input("Clearing Date", value=date.today()) if has_clearing_date else None
        with col2:
            bmcol1, bmcol2 = st.columns(2)
            with bmcol1:
                billing_month_name = st.selectbox(
                    "Billing Month — which month's expenses is this for?",
                    month_names, index=default_month_index)
            with bmcol2:
                billing_year = st.number_input(
                    "Year", min_value=2020, max_value=2100, value=default_year, step=1)
            period = st.text_input("Period * (e.g. 1 Aug - 15 Aug 2026)")
            reimbursed_amount = st.number_input("Reimbursed Amount so far", min_value=0.0, step=100.0)
            screenshot = st.file_uploader(
                "Screenshot — required once Reimbursed Amount is entered (proof of clearance)",
                type=["png", "jpg", "jpeg"])
            approved_pdf = st.file_uploader("Original approved bill PDF *", type=["pdf"])
        remarks = st.text_area("Remarks")

        billing_month_value = date(int(billing_year), month_names.index(billing_month_name) + 1, 1)
        deadline = calc.billing_deadline(billing_month_value)
        st.caption(f"Deadline to submit a {billing_month_name} {billing_year} bill: {deadline.strftime('%d %b %Y')}")
        st.caption("* Required fields. The approved bill PDF is also required. A screenshot "
                    "is required only once a Reimbursed Amount is entered.")

        manager_override = False
        if is_manager:
            manager_override = st.checkbox(
                "Confirm late submission (only needed if past the deadline shown above)")

        submitted = st.form_submit_button("Save bill", type="primary")
        if submitted:
            late = calc.is_late_submission(date_submitted, billing_month_value)
            if not description.strip():
                st.error("Bill description is required.")
            elif bill_amount <= 0:
                st.error("Bill Amount is required and must be greater than 0.")
            elif not period.strip():
                st.error("Period is required.")
            elif approved_pdf is None:
                st.error("The original approved bill PDF is required.")
            elif reimbursed_amount > 0 and screenshot is None:
                st.error(
                    "A screenshot is required as proof of clearance once you enter a "
                    "Reimbursed Amount — attach one, or set Reimbursed Amount back to 0."
                )
            elif late and not is_manager:
                st.error(
                    f"A {billing_month_name} {billing_year} bill must be submitted by "
                    f"{deadline.strftime('%d %b %Y')}. This is late — please ask your "
                    f"manager to add it if it must be backdated."
                )
            elif late and is_manager and not manager_override:
                st.error("Check the confirmation box above to save a late submission.")
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
                    billing_month=billing_month_value.isoformat(),
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

                st.session_state["last_added_bill"] = new_id
                st.rerun()

    if st.session_state.get("last_added_bill"):
        st.success(f"Bill saved (#{st.session_state['last_added_bill']}).")
        st.caption("To email a notification about it, go to 'View or attach files for a bill', "
                    "select this bill, and use the Send notification email button there.")
        del st.session_state["last_added_bill"]

    st.divider()
    st.subheader("SkyElectric Expense Claim Form")
    st.caption(
        "Opens your original form, full-screen, exactly as it's always worked — "
        "same tabs, same Smart Wizard, same PDF export. Fill it out there, tap its "
        "'Download PDF' button as usual, then come back to the form above and attach "
        "that PDF under 'Original approved bill PDF' when you save the bill."
    )
    _form_b64 = expense_form_base64()
    _button_html = f"""
    <button id="openFormBtn" style="display:inline-block;background:#1F4E78;color:white;
        padding:10px 18px;border-radius:8px;border:none;font-weight:600;font-size:14px;
        cursor:pointer;font-family:inherit;">
        Open SkyElectric Expense Claim Form
    </button>
    <div id="openFormStatus" style="margin-top:8px;font-size:12px;color:#8A93A3;font-family:inherit;"></div>
    <script>
    document.getElementById('openFormBtn').addEventListener('click', function() {{
        var statusEl = document.getElementById('openFormStatus');
        try {{
            var b64 = "{_form_b64}";
            var byteChars = atob(b64);
            var byteNumbers = new Array(byteChars.length);
            for (var i = 0; i < byteChars.length; i++) {{
                byteNumbers[i] = byteChars.charCodeAt(i);
            }}
            var byteArray = new Uint8Array(byteNumbers);
            var blob = new Blob([byteArray], {{ type: 'text/html;charset=utf-8' }});
            var url = URL.createObjectURL(blob);
            var w = window.open(url, '_blank');
            if (!w) {{
                statusEl.textContent = 'Your browser blocked the popup — allow popups for this site and click again.';
            }}
        }} catch (e) {{
            statusEl.textContent = 'Could not open the form: ' + e.message;
        }}
    }});
    </script>
    """
    st.components.v1.html(_button_html, height=70)

# ---------------------------------------------------------------
# ARCHIVE — fully paid bills removed from the active ledger at month close
# ---------------------------------------------------------------
with tabs[3]:
    st.subheader("Archive")
    st.caption(
        "Fully paid bills are moved here at month close, so the active ledger only "
        "shows what's still outstanding. Nothing here is deleted — it's kept for records."
    )

    if is_manager:
        st.divider()
        st.subheader("Close the month")
        st.write(
            "This moves every currently fully-paid bill (Balance Due = 0) across the "
            "whole team out of the active ledger and into this Archive. Bills that are "
            "still Pending or Partially Cleared are left untouched."
        )
        if st.button("Close month — archive fully paid bills", type="primary"):
            archived_count = db.archive_cleared_bills()
            if archived_count:
                st.success(f"Archived {archived_count} fully paid bill(s).")
            else:
                st.info("Nothing to archive — no fully paid bills right now.")
            st.rerun()
        st.divider()

    if is_manager:
        employee_options = ["All"] + auth.all_employee_names()
        archive_filt = st.selectbox("Filter by employee", employee_options, key="archive_filter")
        archived_rows = db.get_archived_bills(None if archive_filt == "All" else archive_filt)
    else:
        archived_rows = db.get_archived_bills(current_user["display_name"])

    if not archived_rows:
        st.info("No archived bills yet.")
    else:
        archive_df = pd.DataFrame(archived_rows)
        archive_df["month"] = archive_df["date_submitted"].apply(calc.month_name)
        archive_df["Screenshot"] = archive_df["screenshot_path"].apply(
            lambda p: "Attached" if file_exists(p) else "None")
        archive_df["Approved PDF"] = archive_df["approved_pdf_path"].apply(
            lambda p: "Attached" if file_exists(p) else "None")

        show_cols = ["id", "employee_name", "description", "date_submitted", "month", "period",
                     "bill_amount", "reimbursed_amount", "clearing_date", "approval_status",
                     "netsuite_status", "archived_date", "Screenshot", "Approved PDF", "remarks"]
        st.dataframe(archive_df[show_cols], hide_index=True, use_container_width=True)

        if is_manager:
            st.divider()
            st.subheader("Restore a bill to the active ledger")
            restore_choice = st.selectbox(
                "Select an archived bill", options=archive_df["id"].tolist(),
                format_func=lambda i: f"#{i} - {archive_df.loc[archive_df['id'] == i, 'description'].values[0]}",
                key="restore_bill",
            )
            if st.button("Restore to active ledger"):
                db.unarchive_bill(int(restore_choice))
                st.success(f"Bill #{restore_choice} restored.")
                st.rerun()

# ---------------------------------------------------------------
# MANAGE TEAM (manager only)
# ---------------------------------------------------------------
if is_manager:
    with tabs[4]:
        st.subheader("Team members")
        users = auth.load_users()
        team_df = pd.DataFrame(users)
        if "email" not in team_df.columns:
            team_df["email"] = ""
        st.table(team_df[["display_name", "username", "role", "email"]].fillna(""))

        st.divider()
        st.subheader("Add a team member")
        with st.form("add_user_form", clear_on_submit=True):
            new_display = st.text_input("Full name (shown on bills)")
            new_username = st.text_input("Username (for login)")
            new_password = st.text_input("Password", type="password")
            new_role = st.selectbox("Role", ["employee", "manager", "handler"])
            new_email = st.text_input(
                "Email (required for Handler/Draftsman — used to CC new-bill notifications)")
            add_clicked = st.form_submit_button("Add team member", type="primary")
            if add_clicked:
                if not (new_display and new_username and new_password):
                    st.error("Fill in all fields.")
                elif new_role == "handler" and not new_email.strip():
                    st.error("An email address is required for the Handler/Draftsman role.")
                elif auth.add_user(new_username.strip(), new_password, new_role,
                                    new_display.strip(), email=new_email.strip()):
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

        st.divider()
        st.subheader("Backup / restore team credentials")
        st.caption(
            "A reboot or redeploy can reset this app's storage, which wipes team logins. "
            "Download a backup after adding people, and keep it somewhere safe on your "
            "computer — if that ever happens, restore from it here instead of re-adding everyone by hand."
        )

        backup_json = json.dumps(auth.load_users(), indent=2)
        st.download_button(
            "Download team credentials backup",
            data=backup_json,
            file_name="team_credentials_backup.json",
            mime="application/json",
        )

        st.write("")
        restore_file = st.file_uploader("Restore from a backup file", type=["json"], key="restore_users")
        if restore_file is not None:
            try:
                parsed = json.loads(restore_file.getvalue().decode("utf-8"))
            except Exception:
                st.error("That file isn't valid JSON — is it really a backup file from this app?")
                parsed = None
            if parsed is not None:
                ok, message = auth.validate_users_backup(parsed)
                if not ok:
                    st.error(message)
                else:
                    st.info(message)
                    st.warning("This will replace every current login with what's in the backup file.")
                    if st.button("Confirm restore", type="primary"):
                        auth.save_users(parsed)
                        st.success("Team credentials restored. Please sign out and back in.")
                        st.rerun()

        st.divider()
        st.subheader("Backup / restore bill data")
        st.caption(
            "This is the important one — it covers every bill: amounts, statuses, "
            "approvals, NetSuite tracking, and archive history. Download it regularly "
            "(e.g. after closing each month) and keep the file somewhere safe. If this "
            "app's storage ever gets wiped, restore from here instead of losing everything."
        )

        all_bills_backup = db.get_all_bills(include_archived=True)
        bills_backup_json = json.dumps(all_bills_backup, indent=2)
        st.download_button(
            f"Download bill data backup ({len(all_bills_backup)} bills)",
            data=bills_backup_json,
            file_name=f"bills_backup_{date.today().isoformat()}.json",
            mime="application/json",
        )

        # Attachments (screenshots + approved PDFs) live on disk, separate from the database.
        attachment_files = [f for f in os.listdir(db.SCREENSHOT_DIR)
                             if os.path.isfile(os.path.join(db.SCREENSHOT_DIR, f))]
        if attachment_files:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname in attachment_files:
                    zf.write(os.path.join(db.SCREENSHOT_DIR, fname), arcname=fname)
            zip_buffer.seek(0)
            st.download_button(
                f"Download attachments backup ({len(attachment_files)} files — screenshots & PDFs)",
                data=zip_buffer,
                file_name=f"attachments_backup_{date.today().isoformat()}.zip",
                mime="application/zip",
            )
        else:
            st.caption("No attachments uploaded yet, nothing to back up there.")

        st.write("")
        st.markdown("**Restore bill data**")
        restore_bills_file = st.file_uploader("Restore from a bill data backup (.json)", type=["json"], key="restore_bills")
        if restore_bills_file is not None:
            try:
                parsed_bills = json.loads(restore_bills_file.getvalue().decode("utf-8"))
            except Exception:
                st.error("That file isn't valid JSON — is it really a backup file from this app?")
                parsed_bills = None
            if parsed_bills is not None:
                ok, message = db.validate_bills_backup(parsed_bills)
                if not ok:
                    st.error(message)
                else:
                    st.info(message)
                    st.warning(
                        "This will completely replace every current bill with what's in this "
                        "file. If you also have an attachments ZIP backup, restore that too "
                        "so screenshots and PDFs still match up."
                    )
                    if st.button("Confirm restore of bill data", type="primary"):
                        try:
                            db.replace_all_bills(parsed_bills)
                            st.success(f"Restored {len(parsed_bills)} bill(s).")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Restore failed: {e}")

        st.markdown("**Restore attachments**")
        restore_zip_file = st.file_uploader("Restore from an attachments backup (.zip)", type=["zip"], key="restore_attachments")
        if restore_zip_file is not None:
            st.warning("This will replace every file currently in the attachments folder with what's in this ZIP.")
            if st.button("Confirm restore of attachments", type="primary"):
                try:
                    with zipfile.ZipFile(io.BytesIO(restore_zip_file.getvalue())) as zf:
                        names = zf.namelist()
                        if any(os.path.isabs(n) or ".." in n.split("/") for n in names):
                            st.error("This ZIP contains unsafe file paths and was not restored.")
                        else:
                            for existing in os.listdir(db.SCREENSHOT_DIR):
                                existing_path = os.path.join(db.SCREENSHOT_DIR, existing)
                                if os.path.isfile(existing_path):
                                    os.remove(existing_path)
                            zf.extractall(db.SCREENSHOT_DIR)
                            st.success(f"Restored {len(names)} attachment file(s).")
                            st.rerun()
                except zipfile.BadZipFile:
                    st.error("That file isn't a valid ZIP archive.")
