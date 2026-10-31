from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "bookstore.db"


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def ensure_cart(c, user_id):
    row = c.execute("SELECT cart_id FROM carts WHERE user_id=?", (user_id,)).fetchone()
    if row:
        return row[0]
    return c.execute("INSERT INTO carts(user_id) VALUES(?)", (user_id,)).lastrowid


def add(c, user_id, book_id, qty=1):
    cart_id = ensure_cart(c, user_id)
    row = c.execute("SELECT cart_item_id FROM cart_items WHERE cart_id=? AND book_id=?", (cart_id, book_id)).fetchone()
    if row:
        c.execute("UPDATE cart_items SET quantity=quantity+? WHERE cart_item_id=?", (qty, row[0]))
    else:
        c.execute("INSERT INTO cart_items(cart_id,book_id,quantity) VALUES(?,?,?)", (cart_id, book_id, qty))
    return cart_id


def test_cart_add_update_remove_and_totals_are_consistent():
    c = conn()
    user_id = c.execute("SELECT user_id FROM users ORDER BY user_id LIMIT 1").fetchone()[0]
    book_id = c.execute("SELECT book_id FROM books ORDER BY book_id LIMIT 1").fetchone()[0]
    # Preserve any existing cart state for the test user.
    original = c.execute("SELECT cart_id FROM carts WHERE user_id=?", (user_id,)).fetchone()
    original_items = []
    if original:
        original_items = [tuple(r) for r in c.execute("SELECT book_id, quantity FROM cart_items WHERE cart_id=?", (original[0],)).fetchall()]
        c.execute("DELETE FROM cart_items WHERE cart_id=?", (original[0],))
    try:
        cart_id = add(c, user_id, book_id, 1)
        add(c, user_id, book_id, 2)
        row = c.execute("SELECT quantity FROM cart_items WHERE cart_id=? AND book_id=?", (cart_id, book_id)).fetchone()
        assert row[0] == 3

        price = c.execute("SELECT price FROM books WHERE book_id=?", (book_id,)).fetchone()[0]
        total = c.execute("SELECT SUM(ci.quantity*b.price) FROM cart_items ci JOIN books b ON b.book_id=ci.book_id WHERE ci.cart_id=?", (cart_id,)).fetchone()[0]
        assert abs(total - price * 3) < 1e-9

        item_id = c.execute("SELECT cart_item_id FROM cart_items WHERE cart_id=? AND book_id=?", (cart_id, book_id)).fetchone()[0]
        c.execute("UPDATE cart_items SET quantity=? WHERE cart_item_id=?", (5, item_id))
        assert c.execute("SELECT quantity FROM cart_items WHERE cart_item_id=?", (item_id,)).fetchone()[0] == 5

        c.execute("DELETE FROM cart_items WHERE cart_item_id=?", (item_id,))
        assert c.execute("SELECT COUNT(*) FROM cart_items WHERE cart_item_id=?", (item_id,)).fetchone()[0] == 0
        c.commit()
    finally:
        # Restore original state exactly.
        cart = c.execute("SELECT cart_id FROM carts WHERE user_id=?", (user_id,)).fetchone()
        if cart:
            c.execute("DELETE FROM cart_items WHERE cart_id=?", (cart[0],))
            for bid, qty in original_items:
                c.execute("INSERT INTO cart_items(cart_id,book_id,quantity) VALUES(?,?,?)", (cart[0], bid, qty))
            if not original_items and original is None:
                c.execute("DELETE FROM carts WHERE cart_id=?", (cart[0],))
        c.commit()
        c.close()


def test_cart_schema_enforces_unique_book_per_cart_and_positive_quantity():
    c = conn()
    user_id = c.execute("SELECT user_id FROM users ORDER BY user_id LIMIT 1").fetchone()[0]
    book_id = c.execute("SELECT book_id FROM books ORDER BY book_id LIMIT 1").fetchone()[0]
    cart_id = ensure_cart(c, user_id)
    old = c.execute("SELECT quantity FROM cart_items WHERE cart_id=? AND book_id=?", (cart_id, book_id)).fetchone()
    try:
        c.execute("INSERT INTO cart_items(cart_id,book_id,quantity) VALUES(?,?,1)", (cart_id, book_id))
        c.commit()
        try:
            c.execute("INSERT INTO cart_items(cart_id,book_id,quantity) VALUES(?,?,1)", (cart_id, book_id))
            c.commit()
            raise AssertionError("Duplicate cart item was accepted")
        except sqlite3.IntegrityError:
            c.rollback()
        try:
            c.execute("INSERT INTO cart_items(cart_id,book_id,quantity) VALUES(?,?,0)", (cart_id, book_id + 1))
            c.commit()
            raise AssertionError("Zero quantity was accepted")
        except sqlite3.IntegrityError:
            c.rollback()
    finally:
        c.execute("DELETE FROM cart_items WHERE cart_id=? AND book_id=?", (cart_id, book_id))
        if old:
            c.execute("INSERT INTO cart_items(cart_id,book_id,quantity) VALUES(?,?,?)", (cart_id, book_id, old[0]))
        c.commit()
        c.close()
