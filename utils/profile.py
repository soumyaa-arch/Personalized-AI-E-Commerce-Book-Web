"""Profile service functions for the authenticated user."""
from __future__ import annotations
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "bookstore.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_profile(user_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT user_id, name, email, role, created_at FROM users WHERE user_id = ? LIMIT 1",
            (int(user_id),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_name(user_id: int, name: str) -> tuple[bool, str]:
    name = (name or "").strip()
    if len(name) < 2:
        return False, "Name must contain at least 2 characters."
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE users SET name = ? WHERE user_id = ?", (name, int(user_id)))
        if cur.rowcount == 0:
            conn.rollback()
            return False, "User account not found."
        conn.commit()
        return True, "Profile updated successfully."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()
