"""Admin dashboard queries and guarded order-management helpers."""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "bookstore.db"

ALLOWED_STATUSES = ("Confirmed", "Processing", "Shipped", "Delivered", "Cancelled")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def require_admin(user) -> bool:
    return bool(user and str(user.get("role", "")).lower() == "admin")


def get_admin_metrics():
    conn = get_connection()
    try:
        return dict(conn.execute("""
            SELECT
                (SELECT COUNT(*) FROM books) AS total_books,
                (SELECT COUNT(*) FROM users) AS total_users,
                (SELECT COUNT(*) FROM orders) AS total_orders,
                (SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status <> 'Cancelled') AS total_revenue,
                (SELECT COUNT(*) FROM carts WHERE EXISTS (SELECT 1 FROM cart_items ci WHERE ci.cart_id = carts.cart_id)) AS active_carts,
                (SELECT COUNT(*) FROM wishlist) AS wishlist_items,
                (SELECT COUNT(*) FROM user_interactions) AS interactions
        """).fetchone())
    finally:
        conn.close()


def get_order_status_counts():
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT status, COUNT(*) AS order_count
            FROM orders
            GROUP BY status
            ORDER BY order_count DESC, status ASC
        """).fetchall()
    finally:
        conn.close()


def get_top_interacted_books(limit=10):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT b.book_id, b.title, b.author, COUNT(ui.interaction_id) AS interactions
            FROM user_interactions ui
            JOIN books b ON b.book_id = ui.book_id
            GROUP BY b.book_id, b.title, b.author
            ORDER BY interactions DESC, b.title ASC
            LIMIT ?
        """, (int(limit),)).fetchall()
    finally:
        conn.close()


def get_top_ordered_books(limit=10):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT b.book_id, b.title, b.author,
                   COALESCE(SUM(oi.quantity), 0) AS units_sold,
                   COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS sales
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            JOIN books b ON b.book_id = oi.book_id
            WHERE o.status <> 'Cancelled'
            GROUP BY b.book_id, b.title, b.author
            ORDER BY units_sold DESC, sales DESC, b.title ASC
            LIMIT ?
        """, (int(limit),)).fetchall()
    finally:
        conn.close()


def get_recent_orders(limit=20, status="All"):
    conn = get_connection()
    try:
        params = []
        where = ""
        if status and status != "All":
            where = "WHERE o.status = ?"
            params.append(status)
        params.append(int(limit))
        return conn.execute(f"""
            SELECT o.order_id, o.order_date, o.status, o.total_amount,
                   o.customer_name, o.customer_email, u.email AS account_email,
                   COALESCE(SUM(oi.quantity), 0) AS item_count
            FROM orders o
            JOIN users u ON u.user_id = o.user_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            {where}
            GROUP BY o.order_id
            ORDER BY datetime(o.order_date) DESC, o.order_id DESC
            LIMIT ?
        """, params).fetchall()
    finally:
        conn.close()


def update_order_status(order_id: int, status: str) -> tuple[bool, str]:
    status = str(status).strip()
    if status not in ALLOWED_STATUSES:
        return False, "Invalid order status."
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE orders SET status = ? WHERE order_id = ?",
            (status, int(order_id)),
        )
        if cur.rowcount == 0:
            conn.rollback()
            return False, "Order not found."
        conn.commit()
        return True, "Order status updated."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def search_users(query="", limit=30):
    conn = get_connection()
    try:
        params = []
        where = ""
        if str(query).strip():
            term = f"%{str(query).strip()}%"
            where = "WHERE name LIKE ? OR email LIKE ?"
            params.extend([term, term])
        params.append(int(limit))
        return conn.execute(f"""
            SELECT user_id, name, email, role, created_at
            FROM users
            {where}
            ORDER BY datetime(created_at) DESC, user_id DESC
            LIMIT ?
        """, params).fetchall()
    finally:
        conn.close()
