from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'bookstore.db'
MODEL_PATH = ROOT / 'ml' / 'models' / 'content_recommender.joblib'


def test_model_artifact_exists_and_matches_catalogue():
    from ml.recommender import load_model

    assert MODEL_PATH.exists()
    payload = load_model()
    conn = sqlite3.connect(DB_PATH)
    try:
        count = conn.execute('SELECT COUNT(*) FROM books').fetchone()[0]
    finally:
        conn.close()
    assert len(payload['book_ids']) == count == 149942
    assert payload['matrix'].shape[0] == count
    assert payload['matrix'].shape[1] > 0


def test_similar_books_are_real_and_exclude_seed():
    from ml.recommender import recommend_similar

    conn = sqlite3.connect(DB_PATH)
    seed = conn.execute('SELECT book_id FROM books ORDER BY book_id LIMIT 1').fetchone()[0]
    try:
        recommendations = recommend_similar(seed, n=8)
        assert len(recommendations) == 8
        ids = {int(r['book_id']) for r in recommendations}
        assert seed not in ids
        assert len(ids) == 8
        for item in recommendations:
            assert item['title']
            assert item['author']
    finally:
        conn.close()
