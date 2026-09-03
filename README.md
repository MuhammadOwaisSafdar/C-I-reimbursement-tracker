# Reimbursement Tracker (multi-user)

A local/online app for tracking team reimbursement bills — dashboard, per-employee
tracking, dropdowns, date pickers, and file attachments (screenshots + the original
approved bill as a PDF). Data is saved to a SQLite file (`reimbursements.db`) in this
folder.

## First-time login

The app creates two starter accounts the first time it runs:

| Username    | Password   | Role     |
|-------------|------------|----------|
| manager     | manager123 | Manager  |
| employee1   | pass123    | Employee |

Sign in as **manager**, go to the **Manage Team** tab, and add your real team members
there (set their own usernames/passwords). You can remove the starter `employee1`
account once you've added real people. Change the manager password too — open
`users.json` in a text editor and edit the `password` field for `manager`.

This is basic, plaintext-password login meant for a small trusted team — not
suitable for sensitive/regulated data or a large organization.

## What each role sees

- **Manager** — Dashboard and All Bills show every employee's bills (with a filter
  to view one person at a time), can add a bill on behalf of any team member,
  can edit or delete any bill, and manages team accounts in Manage Team.
- **Employee** — sees only their own bills and dashboard, can add their own bills,
  cannot see or edit anyone else's data.

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
- `calc.py` — balance / status / days-outstanding calculations
- `auth.py` — user accounts (stored in `users.json`, created on first run)
- `reimbursements.db` — created automatically on first run
- `screenshots/` — uploaded screenshots and approved-bill PDFs are saved here

## Putting it online (so your manager and team can use it from anywhere)

The simplest free option is **Streamlit Community Cloud**. Ask me and I'll walk
you through it step by step — it takes a free GitHub account and about 10 minutes,
no coding involved.

One thing worth knowing upfront: on the free tier, the app's storage isn't
guaranteed to be permanent — if the app redeploys or sleeps for a long time,
uploaded files and the database could reset. For a small team logging bills
regularly, this is usually fine in practice, but if you can't afford to ever
lose data, ask me about connecting it to a small free cloud database instead
of the local file — that's a bit more setup but fully persistent.
