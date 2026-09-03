# Reimbursement Tracker (multi-user)

A local/online app for tracking team reimbursement bills — dashboard, per-employee
tracking, dropdowns, date pickers, file attachments (screenshots + the original
approved bill as a PDF), a manager approval workflow, and an email alert whenever
someone submits a new bill.

## First-time login

The app creates two starter accounts the first time it runs:

| Username    | Password   | Role     |
|-------------|------------|----------|
| manager     | manager123 | Manager  |
| employee1   | pass123    | Employee |

Sign in as **manager**, go to **Manage Team**, and add your real team members there.
Remove the starter `employee1` account once real people are added.

## Approval workflow

Every new bill starts as **Pending Approval**. The manager can Approve or Disapprove
it either from the dropdown in the bills table, or with the one-click Approve/
Disapprove buttons under "View or attach files for a bill". This status is separate
from the reimbursement Status (Pending/Partially Cleared/Cleared) — approval is
about whether the expense is allowed at all; reimbursement status is about whether
it's been paid back.

## Email notifications

Whenever anyone submits a new bill, the app tries to email the manager with the
employee's name, the amount, and the bill description — plain text only, no
links (some IT policies block emails containing links, so this is left out on
purpose). This needs a one-time setup:

1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` (same folder
   structure, just remove `.example` from the name).
2. Fill in the `[email]` section:
   - `smtp_server` / `smtp_port` — for Gmail, use `smtp.gmail.com` and `587`.
   - `sender_email` — the Gmail address the notification is sent *from* (can be a
     dedicated account you create just for this).
   - `sender_password` — **not your normal Gmail password.** Turn on 2-Step
     Verification on that Google account, then create an "App Password" at
     myaccount.google.com/apppasswords and use that 16-character code here.
   - `manager_email` — where the notification should land.
3. When adding a Handler/Draftsman in Manage Team, fill in their email address —
   every handler with an email on file is automatically CC'd on new-bill
   notifications, no extra setup needed.
4. **Never commit `secrets.toml` to GitHub** — it contains a password.
5. **On Streamlit Community Cloud**, secrets work differently: open your app, go to
   Settings > Secrets, and paste the same `[email]` block there instead of uploading
   a file. That keeps the password off GitHub entirely.

If email isn't set up yet, the app still works fine — bills save normally, and a
small note explains that email isn't configured instead of failing.

## What each role sees

- **Manager** — Dashboard and All Bills show every employee's bills (with a filter
  to view one person at a time), can add a bill on behalf of any team member,
  approve/disapprove bills, edit or delete any bill, and manages team accounts in
  Manage Team.
- **Handler / Draftsman** — a separate role for whoever actually uploads approved
  bills into NetSuite. Sees only bills the manager has already Approved, tracks
  each one as "Not Uploaded" or "Uploaded" (with the date), can view or download
  the approved PDF for each, and can bulk-download all pending ones as a ZIP. Can't
  approve/disapprove bills, add new bills, or manage the team — just the upload
  step after approval.
- **Employee** — sees only their own bills and dashboard, can add their own bills
  (blocked after the 3rd of the month — see below), and can view their own approval
  status, but cannot approve bills or see anyone else's data.

## SkyElectric Expense Claim Form (your original tool, hosted by the app)

At the bottom of the Add New Bill tab, an "Open SkyElectric Expense Claim Form"
button opens your actual file — same HTML, same tabs (Travel Request, Expense
Claim, Send & Export), same Smart Wizard, same real jsPDF-generated PDF — full
screen in a new tab, exactly as it's always worked. It's served directly by this
app (from the `static/` folder) rather than embedded in a cramped scrolling box.
Fill it out, use its own "Download PDF" button as before, then come back to the
Add New Bill form above and attach that downloaded PDF under "Original approved
bill PDF" when you save the bill — that's the one extra step that connects the
form's output to the ledger.

This intentionally does not try to recreate the form in Python — that produced a
lower-quality result. Running your real file is the only way to get an exact
match, since its PDF generation is JavaScript that only your browser can execute;
this app can host and serve that file, but can't reach into what it produces to
save it automatically.

## Submission deadline rule

Every bill now has its own **Billing Month** (which month's expenses it covers),
separate from the Date of Submission (when it's actually being entered). The rule:
a bill for a given billing month must be submitted on or before the 3rd of the
*following* month — so an August bill can be added any time up to 3 September,
even though the submission date itself is in September. The Add New Bill form
defaults the Billing Month to last month, shows the exact deadline as you pick a
month, and blocks an employee from saving past it with an explanation. The manager
can still add a late entry, but must tick a confirmation checkbox first. Every bill
list shows a "Submission" column (On time / Late) so this is visible at a glance,
and the Dashboard has a "Late Submissions" count. Bills saved before this feature
existed (no Billing Month set) fall back to the old rule of "submitted on or before
the 3rd of whatever month it was literally submitted in."

## Setup (one time)

```
pip install -r requirements.txt
```

## Run locally

```
streamlit run app.py
```

Opens at `http://localhost:8501`.

## Files

- `app.py` — the Streamlit app
- `db.py` — SQLite storage (all bill reads/writes go through here)
- `calc.py` — balance / status / late-submission calculations
- `auth.py` — user accounts (stored in `users.json`, created on first run)
- `notify.py` — sends the manager email when a new bill is submitted
- `static/expense_claim_form.html` — your original expense claim form, served as-is
- `.streamlit/config.toml` — enables Streamlit's static file serving so the form above is reachable by URL
- `.streamlit/secrets.toml.example` — template for email settings (copy and fill in)
- `reimbursements.db` — created automatically on first run
- `screenshots/` — uploaded screenshots and approved-bill PDFs are saved here

## Month closing / Archive

Each employee's Dashboard and All Bills only ever shows bills that still have a
balance due. Once a bill is fully paid (Balance Due = 0), it stays in the active
ledger until the manager clicks **"Close month — archive fully paid bills"** on
the **Archive** tab. That moves every currently fully-paid bill, across the whole
team, out of the active ledger and into the Archive — nothing is deleted, it's
just kept out of the day-to-day view. Bills still Pending or Partially Cleared are
left alone regardless of when this is run.

The Archive tab itself lets anyone look up their own archived bills (or, for the
manager, everyone's, with an employee filter), and the manager can restore a bill
back to the active ledger if it was archived by mistake.

## Data persistence — please read

This still uses a local SQLite file and local folder for storage. On Streamlit
Community Cloud's free tier, that storage isn't guaranteed to survive every
restart or redeploy — it has already reset unexpectedly once. If losing data isn't
acceptable, ask about switching to Google Sheets + Drive or a small free cloud
database (Supabase) for guaranteed persistence — that's a separate, slightly bigger
change from everything else in this file.

**Team logins specifically** — go to Manage Team > "Backup / restore team
credentials" and click "Download team credentials backup" any time you've added
or changed accounts. Keep that file somewhere safe on your computer. If a reboot
or redeploy ever wipes the logins, upload that same file back in on that same
screen and click Confirm restore — no need to re-add everyone by hand. This only
covers logins, not the bills themselves.

**Bill data — this is the important one.** Go to Manage Team > "Backup / restore
bill data" and download two things regularly (e.g. right after closing each
month): the bill data backup (a `.json` with every bill, amount, status, approval,
and archive record) and the attachments backup (a `.zip` of every screenshot and
approved PDF). Keep both somewhere safe. If storage ever gets wiped, upload the
`.json` back in under "Restore bill data" and confirm — bill IDs are preserved, so
if you also restore the attachments `.zip`, screenshots and PDFs line back up
correctly with the right bills automatically.
