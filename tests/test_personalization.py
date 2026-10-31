from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "bookstore.db"


def _connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def test_cold_start_personalization_returns_no_personal_history():
    from ml.recommender import get_personalized_recommendations

    conn = _connection()
    try:
        user_id = conn.execute("SELECT user_id FROM users ORDER BY user_id LIMIT 1").fetchone()[0]
        conn.execute("DELETE FROM user_interactions WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

    recommendations, meta = get_personalized_recommendations(user_id, n=8)
    assert recommendations == []
    assert meta["personalized"] is False
    assert meta["interaction_count"] == 0


def test_personalization_uses_user_activity_and_excludes_seed():
    from ml.recommender import get_personalized_recommendations

    conn = _connection()
    user_id = conn.execute("SELECT user_id FROM users ORDER BY user_id LIMIT 1").fetchone()[0]
    seed_ids = [r[0] for r in conn.execute("SELECT book_id FROM books ORDER BY avg_rating DESC, book_id LIMIT 2").fetchall()]
    try:
        conn.execute("DELETE FROM user_interactions WHERE user_id = ?", (user_id,))
        for book_id, interaction_type in zip(seed_ids, ["view", "wishlist"]):
            conn.execute(
                "INSERT INTO user_interactions (user_id, book_id, interaction_type) VALUES (?, ?, ?)",
                (user_id, book_id, interaction_type),
            )
        conn.commit()

        recommendations, meta = get_personalized_recommendations(user_id, n=8)
        assert meta["personalized"] is True
        assert meta["interaction_count"] == 2
        assert meta["seed_count"] == 2
        assert 0 < len(recommendations) <= 8
        recommended_ids = {int(item["book_id"]) for item in recommendations}
        assert not recommended_ids.intersection(seed_ids)
        assert all("personalization_score" in item for item in recommendations)
    finally:
        conn.execute("DELETE FROM user_interactions WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
