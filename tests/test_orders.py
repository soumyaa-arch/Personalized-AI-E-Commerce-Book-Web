import shutil
import sqlite3
from pathlib import Path

from utils import orders


ROOT = Path(__file__).resolve().parents[1]


def _prepare_db(tmp_path, monkeypatch):
    db = tmp_path / "test_bookstore.db"
    shutil.copy2(ROOT / "bookstore.db", db)
    monkeypatch.setattr(orders, "DB_PATH", db)
    orders.ensure_order_columns()
    return db


def _cleanup(db, user_id, order_id=None):
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    if order_id:
        conn.execute("DELETE FROM user_interactions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        conn.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
    conn.execute("DELETE FROM cart_items WHERE cart_id IN (SELECT cart_id FROM carts WHERE user_id = ?)", (user_id,))
    conn.execute("DELETE FROM carts WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM wishlist WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM user_interactions WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def test_checkout_creates_order_snapshots_items_and_clears_cart(tmp_path, monkeypatch):
    db = _prepare_db(tmp_path, monkeypatch)
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)", ("Checkout Test", "checkout@test.local", "x"))
    user_id = conn.execute("SELECT user_id FROM users WHERE email = ?", ("checkout@test.local",)).fetchone()[0]
    conn.execute("INSERT INTO carts(user_id) VALUES(?)", (user_id,))
    cart_id = conn.execute("SELECT cart_id FROM carts WHERE user_id = ?", (user_id,)).fetchone()[0]
    book = conn.execute("SELECT book_id, price FROM books ORDER BY book_id LIMIT 1").fetchone()
    conn.execute("INSERT INTO cart_items(cart_id,book_id,quantity) VALUES(?,?,2)", (cart_id, book[0]))
    conn.commit()
    conn.close()

    ok, message, order_id = orders.create_order_from_cart(
        user_id, "Checkout Test", "checkout@test.local", "12 Main Road", "Bhubaneswar", "Odisha", "751001"
    )
    assert ok, message
    assert order_id is not None

    conn = sqlite3.connect(db)
    order = conn.execute("SELECT total_amount,status,customer_email,pincode FROM orders WHERE order_id=?", (order_id,)).fetchone()
    items = conn.execute("SELECT quantity,unit_price FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    cart_count = conn.execute("SELECT COUNT(*) FROM cart_items WHERE cart_id=?", (cart_id,)).fetchone()[0]
    purchase_count = conn.execute("SELECT COUNT(*) FROM user_interactions WHERE user_id=? AND interaction_type='purchase'", (user_id,)).fetchone()[0]
    conn.close()

    assert order[0] == 2 * book[1]
    assert order[1] == "Confirmed"
    assert order[2] == "checkout@test.local"
    assert order[3] == "751001"
    assert items == [(2, book[1])]
    assert cart_count == 0
    assert purchase_count == 1

    _cleanup(db, user_id, order_id)


def test_checkout_rejects_empty_cart_without_creating_order(tmp_path, monkeypatch):
    db = _prepare_db(tmp_path, monkeypatch)
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)", ("Empty Test", "empty@test.local", "x"))
    user_id = conn.execute("SELECT user_id FROM users WHERE email = ?", ("empty@test.local",)).fetchone()[0]
    conn.execute("INSERT INTO carts(user_id) VALUES(?)", (user_id,))
    conn.commit()
    conn.close()

    ok, message, order_id = orders.create_order_from_cart(
        user_id, "Empty Test", "empty@test.local", "12 Main Road", "Bhubaneswar", "Odisha", "751001"
    )
    assert not ok
    assert "empty" in message.lower()
    assert order_id is None

    conn = sqlite3.connect(db)
    count = conn.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (user_id,)).fetchone()[0]
    conn.close()
    assert count == 0
    _cleanup(db, user_id)


def test_checkout_rejects_invalid_pin(tmp_path, monkeypatch):
    db = _prepare_db(tmp_path, monkeypatch)
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)", ("PIN Test", "pin@test.local", "x"))
    user_id = conn.execute("SELECT user_id FROM users WHERE email = ?", ("pin@test.local",)).fetchone()[0]
    conn.execute("INSERT INTO carts(user_id) VALUES(?)", (user_id,))
    cart_id = conn.execute("SELECT cart_id FROM carts WHERE user_id=?", (user_id,)).fetchone()[0]
    book = conn.execute("SELECT book_id FROM books ORDER BY book_id LIMIT 1").fetchone()[0]
    conn.execute("INSERT INTO cart_items(cart_id,book_id,quantity) VALUES(?,?,1)", (cart_id, book))
    conn.commit()
    conn.close()

    ok, message, order_id = orders.create_order_from_cart(
        user_id, "PIN Test", "pin@test.local", "12 Main Road", "Bhubaneswar", "Odisha", "75100"
    )
    assert not ok
    assert "pin" in message.lower()
    assert order_id is None
    _cleanup(db, user_id)
