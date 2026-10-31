"""Order history and order-detail services for the bookstore."""

from __future__ import annotations
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "bookstore.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_user_orders(user_id: int, page: int = 1, page_size: int = 8, status: str = "All"):
    """Return paginated orders belonging only to the requested user."""
    page = max(1, int(page))
    page_size = max(1, min(50, int(page_size)))
    offset = (page - 1) * page_size

    conn = get_connection()
    try:
        params = [int(user_id)]
        where = "WHERE o.user_id = ?"
        if status and status != "All":
            where += " AND o.status = ?"
            params.append(status)

        total = conn.execute(
            f"SELECT COUNT(*) FROM orders o {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT o.order_id, o.total_amount, o.status, o.order_date,
                   o.customer_name, o.city, o.state, o.payment_method,
                   COALESCE(SUM(oi.quantity), 0) AS item_count
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            {where}
            GROUP BY o.order_id
            ORDER BY o.order_date DESC, o.order_id DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()

        return rows, int(total)
    finally:
        conn.close()


def get_order_details(user_id: int, order_id: int):
    """Return an order and its line items only when it belongs to the user."""
    conn = get_connection()
    try:
        order = conn.execute(
            """
            SELECT order_id, user_id, total_amount, status, order_date,
                   customer_name, customer_email, shipping_address,
                   city, state, pincode, payment_method
            FROM orders
            WHERE order_id = ? AND user_id = ?
            LIMIT 1
            """,
            (int(order_id), int(user_id)),
        ).fetchone()
        if order is None:
            return None, []

        items = conn.execute(
            """
            SELECT oi.order_item_id, oi.book_id, oi.quantity, oi.unit_price,
                   b.title, b.author,
                   (oi.quantity * oi.unit_price) AS line_total
            FROM order_items oi
            JOIN books b ON b.book_id = oi.book_id
            WHERE oi.order_id = ?
            ORDER BY oi.order_item_id ASC
            """,
            (int(order_id),),
        ).fetchall()
        return order, items
    finally:
        conn.close()
