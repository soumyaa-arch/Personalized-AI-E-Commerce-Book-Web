import sqlite3


def make_db(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
    PRAGMA foreign_keys = ON;
    CREATE TABLE users (
        user_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'customer',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE books (
        book_id INTEGER PRIMARY KEY,
        isbn TEXT, title TEXT, author TEXT, publisher TEXT,
        publication_year INTEGER, avg_rating REAL, price REAL
    );
    CREATE TABLE wishlist (
        wishlist_id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(user_id),
        book_id INTEGER NOT NULL REFERENCES books(book_id),
        added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, book_id)
    );
    INSERT INTO users(user_id,name,email,password_hash,role) VALUES (1,'Alice','alice@example.com','x','customer');
    INSERT INTO books(book_id,title,author,avg_rating,price) VALUES
        (10,'Book A','Author A',4.5,100),(11,'Book B','Author B',4.0,200);
    INSERT INTO wishlist(user_id,book_id) VALUES (1,10);
    """)
    conn.commit(); conn.close()
    return db


def test_wishlist_scoped_and_removable(tmp_path, monkeypatch):
    from utils import wishlist
    db = make_db(tmp_path)
    monkeypatch.setattr(wishlist, 'DB_PATH', db)

    rows = wishlist.get_user_wishlist(1)
    assert len(rows) == 1
    assert rows[0]['book_id'] == 10

    ok, _ = wishlist.remove_from_wishlist(1, 10)
    assert ok
    assert wishlist.get_user_wishlist(1) == []

    ok, _ = wishlist.remove_from_wishlist(1, 999)
    assert not ok


def test_profile_update_is_scoped(tmp_path, monkeypatch):
    from utils import profile
    db = make_db(tmp_path)
    monkeypatch.setattr(profile, 'DB_PATH', db)

    p = profile.get_profile(1)
    assert p['name'] == 'Alice'
    assert p['role'] == 'customer'

    ok, _ = profile.update_name(1, 'Alice Smith')
    assert ok
    assert profile.get_profile(1)['name'] == 'Alice Smith'

    ok, _ = profile.update_name(1, 'A')
    assert not ok
