"""Wishlist service functions scoped to the authenticated user."""
from __future__ import annotations
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "bookstore.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_user_wishlist(user_id: int):
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT w.wishlist_id, w.book_id, w.added_at,
                      b.isbn, b.title, b.author, b.publisher,
                      b.publication_year, b.avg_rating, b.price
               FROM wishlist w
               JOIN books b ON b.book_id = w.book_id
               WHERE w.user_id = ?
               ORDER BY datetime(w.added_at) DESC, w.wishlist_id DESC""",
            (int(user_id),),
        ).fetchall()
    finally:
        conn.close()


def remove_from_wishlist(user_id: int, book_id: int) -> tuple[bool, str]:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM wishlist WHERE user_id = ? AND book_id = ?",
            (int(user_id), int(book_id)),
        )
        if cur.rowcount == 0:
            return False, "Wishlist item not found."
        conn.commit()
        return True, "Removed from wishlist."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()
