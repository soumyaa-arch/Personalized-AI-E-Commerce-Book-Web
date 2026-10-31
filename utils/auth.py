
import hashlib
import hmac
import re
import secrets
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "bookstore.db"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def validate_registration(name, email, password):
    name = (name or "").strip()
    email = (email or "").strip().lower()
    if len(name) < 2:
        return False, "Name must contain at least 2 characters."
    if not EMAIL_PATTERN.match(email):
        return False, "Please enter a valid email address."
    if len(password or "") < 6:
        return False, "Password must contain at least 6 characters."
    return True, ""

def hash_password(password):
    salt = secrets.token_bytes(16)
    iterations = 310_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"

def verify_password(password, stored_hash):
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        calculated = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"),
            bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(calculated.hex(), digest_hex)
    except (ValueError, TypeError):
        return False

def register_user(name, email, password):
    valid, message = validate_registration(name, email, password)
    if not valid:
        return False, message
    email = email.strip().lower()
    conn = get_connection()
    try:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            return False, "An account with this email already exists."
        conn.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (name.strip(), email, hash_password(password), "customer")
        )
        conn.commit()
        return True, "Account created successfully."
    finally:
        conn.close()

def authenticate_user(email, password):
    email = (email or "").strip().lower()
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT user_id, name, email, password_hash, role FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        if not user or not verify_password(password or "", user["password_hash"]):
            return None
        return {
            "user_id": user["user_id"], "name": user["name"],
            "email": user["email"], "role": user["role"]
        }
    finally:
        conn.close()

def get_user(user_id):
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT user_id, name, email, role, created_at FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return dict(user) if user else None
    finally:
        conn.close()
