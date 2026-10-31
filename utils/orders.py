"""Checkout and order creation services for the bookstore."""

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


def ensure_order_columns() -> None:
    """Add checkout snapshot fields to existing databases without losing data."""
    conn = get_connection()
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(orders)")}
        additions = {
            "customer_name": "TEXT",
            "customer_email": "TEXT",
            "shipping_address": "TEXT",
            "city": "TEXT",
            "state": "TEXT",
            "pincode": "TEXT",
            "payment_method": "TEXT",
        }
        for name, sql_type in additions.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE orders ADD COLUMN {name} {sql_type}")
        conn.commit()
    finally:
        conn.close()


def get_checkout_items(user_id: int):
    """Return the user's current cart with catalogue prices used for checkout."""
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT ci.cart_item_id, ci.book_id, ci.quantity,
                   b.isbn, b.title, b.author, b.price,
                   (ci.quantity * b.price) AS line_total
            FROM carts c
            JOIN cart_items ci ON ci.cart_id = c.cart_id
            JOIN books b ON b.book_id = ci.book_id
            WHERE c.user_id = ?
            ORDER BY ci.added_at ASC, ci.cart_item_id ASC
            """,
            (int(user_id),),
        ).fetchall()
    finally:
        conn.close()


def create_order_from_cart(
    user_id: int,
    customer_name: str,
    customer_email: str,
    shipping_address: str,
    city: str,
    state: str,
    pincode: str,
    payment_method: str = "Demo Payment",
):
    """Atomically snapshot the cart into an order, record purchases, and clear the cart."""
    fields = {
        "customer_name": customer_name.strip(),
        "customer_email": customer_email.strip().lower(),
        "shipping_address": shipping_address.strip(),
        "city": city.strip(),
        "state": state.strip(),
        "pincode": pincode.strip(),
        "payment_method": payment_method.strip() or "Demo Payment",
    }
    if not all(fields.values()):
        return False, "Please complete all checkout fields.", None
    if not fields["pincode"].isdigit() or len(fields["pincode"]) != 6:
        return False, "Please enter a valid 6-digit PIN code.", None

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")

        user = conn.execute(
            "SELECT user_id, name, email FROM users WHERE user_id = ? LIMIT 1",
            (int(user_id),),
        ).fetchone()
        if user is None:
            raise ValueError("User account was not found.")

        cart = conn.execute(
            "SELECT cart_id FROM carts WHERE user_id = ? LIMIT 1",
            (int(user_id),),
        ).fetchone()
        if cart is None:
            raise ValueError("Your cart is empty.")

        items = conn.execute(
            """
            SELECT ci.book_id, ci.quantity, b.price, b.title
            FROM cart_items ci
            JOIN books b ON b.book_id = ci.book_id
            WHERE ci.cart_id = ?
            ORDER BY ci.cart_item_id ASC
            """,
            (cart["cart_id"],),
        ).fetchall()
        if not items:
            raise ValueError("Your cart is empty.")

        # Prices are snapshotted into order_items so future catalogue price changes
        # cannot alter the historical order total.
        total_amount = sum(float(item["price"]) * int(item["quantity"]) for item in items)
        cursor = conn.execute(
            """
            INSERT INTO orders (
                user_id, total_amount, status,
                customer_name, customer_email, shipping_address,
                city, state, pincode, payment_method
            ) VALUES (?, ?, 'Confirmed', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(user_id), total_amount,
                fields["customer_name"], fields["customer_email"],
                fields["shipping_address"], fields["city"], fields["state"],
                fields["pincode"], fields["payment_method"],
            ),
        )
        order_id = int(cursor.lastrowid)

        conn.executemany(
            """
            INSERT INTO order_items (order_id, book_id, quantity, unit_price)
            VALUES (?, ?, ?, ?)
            """,
            [
                (order_id, int(item["book_id"]), int(item["quantity"]), float(item["price"]))
                for item in items
            ],
        )

        # Purchases are the strongest personalization signal and are recorded
        # in the same transaction as the order.
        conn.executemany(
            """
            INSERT INTO user_interactions (user_id, book_id, interaction_type)
            VALUES (?, ?, 'purchase')
            """,
            [(int(user_id), int(item["book_id"])) for item in items],
        )

        conn.execute(
            "DELETE FROM cart_items WHERE cart_id = ?",
            (cart["cart_id"],),
        )
        conn.execute(
            "UPDATE carts SET updated_at = CURRENT_TIMESTAMP WHERE cart_id = ?",
            (cart["cart_id"],),
        )

        conn.commit()
        return True, "Order placed successfully.", order_id
    except Exception as exc:
        conn.rollback()
        return False, str(exc), None
    finally:
        conn.close()


def get_order_confirmation(user_id: int, order_id: int):
    """Fetch a user's own order and its items for the confirmation page."""
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
