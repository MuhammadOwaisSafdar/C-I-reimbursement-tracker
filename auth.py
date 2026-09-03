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
        return DEFAULT_USERS
    with open(USERS_PATH, "r") as f:
        return json.load(f)


def save_users(users):
    with open(USERS_PATH, "w") as f:
        json.dump(users, f, indent=2)


def check_login(username, password):
    for u in load_users():
        if u["username"] == username and u["password"] == password:
            return u
    return None


def add_user(username, password, role, display_name):
    users = load_users()
    if any(u["username"] == username for u in users):
        return False
    users.append({"username": username, "password": password, "role": role, "display_name": display_name})
    save_users(users)
    return True


def delete_user(username):
    users = load_users()
    users = [u for u in users if u["username"] != username]
    save_users(users)


def all_employee_names():
    """Only people with the 'employee' role — used for whom a bill can be attributed to."""
    return [u["display_name"] for u in load_users() if u["role"] == "employee"]


def all_display_names():
    """Every account, regardless of role — used for team management listings."""
    return [u["display_name"] for u in load_users()]
