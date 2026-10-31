import sqlite3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.admin import ALLOWED_STATUSES, get_admin_metrics, get_order_status_counts, require_admin, search_users


def test_admin_guard_and_metrics():
    assert require_admin({"role": "admin"}) is True
    assert require_admin({"role": "customer"}) is False
    assert require_admin(None) is False
    metrics = get_admin_metrics()
    assert metrics["total_books"] == 149942
    assert metrics["total_users"] >= 1
    assert metrics["total_orders"] >= 0


def test_admin_queries_and_statuses():
    assert "Confirmed" in ALLOWED_STATUSES
    assert len(get_order_status_counts()) >= 0
    rows = search_users("admin", limit=10)
    assert all("email" in row.keys() for row in rows)


def test_database_foreign_keys_clean():
    conn = sqlite3.connect(ROOT / "bookstore.db")
    try:
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert violations == []
    finally:
        conn.close()
