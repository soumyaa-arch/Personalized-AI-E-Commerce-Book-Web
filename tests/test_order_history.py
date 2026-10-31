import shutil
import sqlite3
from pathlib import Path

from utils import order_history
from utils import orders

ROOT = Path(__file__).resolve().parents[1]


def _prepare_db(tmp_path, monkeypatch):
    db = tmp_path / "test_bookstore.db"
    shutil.copy2(ROOT / "bookstore.db", db)
    monkeypatch.setattr(order_history, "DB_PATH", db)
    monkeypatch.setattr(orders, "DB_PATH", db)
    orders.ensure_order_columns()
    return db


def _seed_order(db, email="history@test.local"):
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)", ("History Test", email, "x"))
    user_id = conn.execute("SELECT user_id FROM users WHERE email=?", (email,)).fetchone()[0]
    conn.execute("INSERT INTO carts(user_id) VALUES(?)", (user_id,))
    cart_id = conn.execute("SELECT cart_id FROM carts WHERE user_id=?", (user_id,)).fetchone()[0]
    book = conn.execute("SELECT book_id, price FROM books ORDER BY book_id LIMIT 1").fetchone()
    conn.execute("INSERT INTO cart_items(cart_id,book_id,quantity) VALUES(?,?,2)", (cart_id, book[0]))
    conn.commit()
    conn.close()
    ok, message, order_id = orders.create_order_from_cart(
        user_id, "History Test", email, "12 Main Road", "Bhubaneswar", "Odisha", "751001"
    )
    assert ok, message
    return user_id, order_id


def _cleanup(db):
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM user_interactions WHERE user_id IN (SELECT user_id FROM users WHERE email LIKE '%@test.local')")
    conn.execute("DELETE FROM order_items WHERE order_id IN (SELECT order_id FROM orders WHERE user_id IN (SELECT user_id FROM users WHERE email LIKE '%@test.local'))")
    conn.execute("DELETE FROM orders WHERE user_id IN (SELECT user_id FROM users WHERE email LIKE '%@test.local')")
    conn.execute("DELETE FROM cart_items WHERE cart_id IN (SELECT cart_id FROM carts WHERE user_id IN (SELECT user_id FROM users WHERE email LIKE '%@test.local'))")
    conn.execute("DELETE FROM carts WHERE user_id IN (SELECT user_id FROM users WHERE email LIKE '%@test.local')")
    conn.execute("DELETE FROM users WHERE email LIKE '%@test.local'")
    conn.commit()
    conn.close()


def test_get_user_orders_is_paginated_and_scoped(tmp_path, monkeypatch):
    db = _prepare_db(tmp_path, monkeypatch)
    user_id, order_id = _seed_order(db)
    rows, total = order_history.get_user_orders(user_id, page=1, page_size=8)
    assert total == 1
    assert len(rows) == 1
    assert rows[0]["order_id"] == order_id
    assert rows[0]["item_count"] == 2
    _cleanup(db)


def test_get_order_details_returns_items_for_owner(tmp_path, monkeypatch):
    db = _prepare_db(tmp_path, monkeypatch)
    user_id, order_id = _seed_order(db, "owner@test.local")
    order, items = order_history.get_order_details(user_id, order_id)
    assert order is not None
    assert order["order_id"] == order_id
    assert len(items) == 1
    assert items[0]["quantity"] == 2
    _cleanup(db)


def test_get_order_details_blocks_other_user(tmp_path, monkeypatch):
    db = _prepare_db(tmp_path, monkeypatch)
    user_id, order_id = _seed_order(db, "owner2@test.local")
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)", ("Other", "other@test.local", "x"))
    other_id = conn.execute("SELECT user_id FROM users WHERE email=?", ("other@test.local",)).fetchone()[0]
    conn.commit()
    conn.close()

    order, items = order_history.get_order_details(other_id, order_id)
    assert order is None
    assert items == []
    _cleanup(db)
