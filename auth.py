"""
Lightweight username/password accounts, stored in users.json next to this file.
This is basic auth meant for a small trusted team, not for sensitive/regulated data.
"""

import json
import os

USERS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")

DEFAULT_USERS = [
    {"username": "manager", "password": "manager123", "role": "manager", "display_name": "Manager"},
    {"username": "employee1", "password": "pass123", "role": "employee", "display_name": "Employee One"},
]


def load_users():
    if not os.path.exists(USERS_PATH):
        save_users(DEFAULT_USERS)
        users = list(DEFAULT_USERS)
    else:
        with open(USERS_PATH, "r") as f:
            users = json.load(f)

    # Migration: older deployments only had manager/employee roles. Ensure at least
    # one admin exists by promoting the first manager account, so there's always
    # someone able to grant admin rights to others going forward.
    if not any(u.get("role") == "admin" for u in users):
        for u in users:
            if u.get("role") == "manager":
                u["role"] = "admin"
                save_users(users)
                break

    return users


def save_users(users):
    with open(USERS_PATH, "w") as f:
        json.dump(users, f, indent=2)


def check_login(username, password):
    for u in load_users():
        if u["username"] == username and u["password"] == password:
            return u
    return None


def add_user(username, password, role, display_name, email=""):
    users = load_users()
    if any(u["username"] == username for u in users):
        return False
    users.append({
        "username": username, "password": password, "role": role,
        "display_name": display_name, "email": email,
    })
    save_users(users)
    return True


def delete_user(username):
    users = load_users()
    users = [u for u in users if u["username"] != username]
    save_users(users)


def change_password(username, new_password):
    """Updates a single user's password. Returns True if the account was found and updated."""
    users = load_users()
    found = False
    for u in users:
        if u["username"] == username:
            u["password"] = new_password
            found = True
            break
    if found:
        save_users(users)
    return found


def change_role(username, new_role):
    """Updates a single user's role. Returns True if the account was found and updated."""
    users = load_users()
    found = False
    for u in users:
        if u["username"] == username:
            u["role"] = new_role
            found = True
            break
    if found:
        save_users(users)
    return found


def all_employee_names():
    """Only people with the 'employee' role — used for whom a bill can be attributed to."""
    return [u["display_name"] for u in load_users() if u["role"] == "employee"]


def all_display_names():
    """Every account, regardless of role — used for team management listings."""
    return [u["display_name"] for u in load_users()]


def handler_emails():
    """Email addresses of every account with the 'handler' role that has one on file."""
    return [u["email"] for u in load_users() if u.get("role") == "handler" and u.get("email")]


def validate_users_backup(data):
    """Checks a parsed backup file has the right shape before it's allowed to overwrite
    the live accounts. Returns (ok: bool, message: str)."""
    if not isinstance(data, list):
        return False, "File isn't a valid backup — expected a list of accounts."
    if len(data) == 0:
        return False, "Backup file is empty."
    required = {"username", "password", "role", "display_name"}
    seen_usernames = set()
    for i, u in enumerate(data):
        if not isinstance(u, dict):
            return False, f"Entry #{i + 1} isn't a valid account record."
        missing = required - set(u.keys())
        if missing:
            return False, f"Entry #{i + 1} is missing: {', '.join(missing)}."
        if u["username"] in seen_usernames:
            return False, f"Duplicate username in backup: {u['username']}."
        seen_usernames.add(u["username"])
    if not any(u.get("role") in ("manager", "admin") for u in data):
        return False, "Backup has no manager or admin account — refusing to restore (you'd be locked out)."
    return True, f"Looks valid — {len(data)} account(s)."
