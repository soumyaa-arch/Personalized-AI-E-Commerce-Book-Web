from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.auth import (
    authenticate_user,
    get_connection,
    get_user,
    hash_password,
    register_user,
    validate_registration,
    verify_password,
)


def test_password_hashing_and_verification():
    stored = hash_password("StrongPass123")
    assert stored != "StrongPass123"
    assert verify_password("StrongPass123", stored) is True
    assert verify_password("WrongPassword", stored) is False


def test_registration_validation():
    assert validate_registration("A", "valid@example.com", "123456")[0] is False
    assert validate_registration("Valid User", "bad-email", "123456")[0] is False
    assert validate_registration("Valid User", "valid@example.com", "123")[0] is False
    assert validate_registration("Valid User", "valid@example.com", "123456")[0] is True


def test_register_login_and_duplicate_email():
    email = f"stage4_{uuid.uuid4().hex[:10]}@example.com"
    ok, message = register_user("Test User", email, "StrongPass123")
    assert ok is True, message
    duplicate, _ = register_user("Test User", email, "StrongPass123")
    assert duplicate is False
    user = authenticate_user(email, "StrongPass123")
    assert user is not None
    assert user["email"] == email
    assert authenticate_user(email, "WrongPassword") is None
    fetched = get_user(user["user_id"])
    assert fetched is not None
    assert fetched["email"] == email
    conn = get_connection()
    try:
        conn.execute("DELETE FROM users WHERE email = ?", (email,))
        conn.commit()
    finally:
        conn.close()


def test_admin_account_role():
    user = authenticate_user("admin@bookstore.local", "Admin@12345")
    assert user is not None
    assert user["role"] == "admin"


def test_public_registration_always_creates_customer():
    email = f"stage16_{uuid.uuid4().hex[:10]}@example.com"
    ok, _ = register_user("Stage Sixteen", email, "StrongPass123")
    assert ok is True
    user = authenticate_user(email, "StrongPass123")
    assert user is not None
    assert user["role"] == "customer"
    conn = get_connection()
    try:
        conn.execute("DELETE FROM users WHERE email = ?", (email,))
        conn.commit()
    finally:
        conn.close()
