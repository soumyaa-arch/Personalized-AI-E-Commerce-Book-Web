from pathlib import Path
import sqlite3
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'bookstore.db'
MODEL_DIR = ROOT / 'ml' / 'models'
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def main():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('''
        SELECT book_id, title, author, publisher, publication_year, avg_rating, price, ml_text
        FROM books ORDER BY book_id
    ''').fetchall()
    conn.close()

    ids = [int(r[0]) for r in rows]
    texts = []
    for r in rows:
        text = r[7] or ' '.join(str(x or '') for x in r[1:4])
        texts.append(text)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents='unicode',
        ngram_range=(1, 2),
        min_df=2,
        max_features=120_000,
        sublinear_tf=True,
        dtype='float32',
    )
    matrix = vectorizer.fit_transform(texts)

    nn = NearestNeighbors(metric='cosine', algorithm='brute', n_neighbors=11, n_jobs=-1)
    nn.fit(matrix)

    payload = {
        'book_ids': ids,
        'vectorizer': vectorizer,
        'matrix': matrix,
        'nn': nn,
        'version': 1,
        'feature_description': 'TF-IDF title + author + publisher content-based recommendation',
    }
    out = MODEL_DIR / 'content_recommender.joblib'
    joblib.dump(payload, out, compress=3)
    print(f'books={len(ids)} features={matrix.shape[1]} nnz={matrix.nnz}')
    print(f'saved={out}')


if __name__ == '__main__':
    main()
