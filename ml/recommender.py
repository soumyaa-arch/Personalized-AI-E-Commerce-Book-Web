from pathlib import Path
import math
import sqlite3
from datetime import datetime, timezone
import joblib

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'bookstore.db'
MODEL_PATH = ROOT / 'ml' / 'models' / 'content_recommender.joblib'

# Stronger signals indicate clearer user intent.
INTERACTION_WEIGHTS = {
    'view': 1.0,
    'wishlist': 3.0,
    'cart': 4.0,
    'purchase': 6.0,
}


def load_model():
    return joblib.load(MODEL_PATH)


def _rows_by_ids(conn, ids):
    if not ids:
        return []
    placeholders = ','.join('?' for _ in ids)
    rows = conn.execute(
        f'''SELECT book_id, isbn, title, author, publisher, publication_year, avg_rating, price
            FROM books WHERE book_id IN ({placeholders})''', ids
    ).fetchall()
    order = {int(book_id): i for i, book_id in enumerate(ids)}
    return sorted(rows, key=lambda r: order.get(int(r['book_id']), 0))


def _recommend_similar_with_payload(payload, book_id, n=8):
    ids = payload['book_ids']
    id_to_index = payload.get('id_to_index')
    if id_to_index is None:
        id_to_index = {int(v): i for i, v in enumerate(ids)}
    idx = id_to_index.get(int(book_id))
    if idx is None:
        return []

    distances, indices = payload['nn'].kneighbors(
        payload['matrix'][idx],
        n_neighbors=min(n + 1, len(ids)),
    )
    candidate_ids = []
    candidate_scores = {}
    for distance, neighbor_idx in zip(distances[0], indices[0]):
        candidate_id = int(ids[int(neighbor_idx)])
        if candidate_id == int(book_id):
            continue
        # Cosine distance is in [0, 1] for these normalized TF-IDF vectors.
        candidate_scores[candidate_id] = max(0.0, 1.0 - float(distance))
        candidate_ids.append(candidate_id)
        if len(candidate_ids) >= n:
            break

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = _rows_by_ids(conn, candidate_ids)
        row_map = {int(r['book_id']): r for r in rows}
        result = []
        for rank, candidate_id in enumerate(candidate_ids, start=1):
            row = row_map.get(candidate_id)
            if row is not None:
                item = dict(row)
                item['similarity_rank'] = rank
                item['similarity_score'] = candidate_scores.get(candidate_id, 0.0)
                result.append(item)
        return result
    finally:
        conn.close()


def recommend_similar_from_model(payload, book_id, n=8):
    return _recommend_similar_with_payload(payload, book_id, n)


def recommend_similar(book_id, n=8):
    return recommend_similar_from_model(load_model(), book_id, n)


def _parse_created_at(value):
    if not value:
        return None
    try:
        # SQLite CURRENT_TIMESTAMP is UTC without a timezone suffix.
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _recency_factor(created_at, half_life_days=30.0):
    dt = _parse_created_at(created_at)
    if dt is None:
        return 0.5
    age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
    return math.exp(-math.log(2) * age_days / half_life_days)


def get_user_interaction_profile(user_id, limit=30):
    """Return the strongest recent interaction signals for one user."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            '''SELECT book_id, interaction_type, created_at
               FROM user_interactions
               WHERE user_id = ?
               ORDER BY created_at DESC, interaction_id DESC
               LIMIT ?''',
            (int(user_id), int(limit)),
        ).fetchall()
    finally:
        conn.close()

    profile = []
    for row in rows:
        interaction = str(row['interaction_type']).lower()
        base = INTERACTION_WEIGHTS.get(interaction, 0.0)
        if base <= 0:
            continue
        profile.append({
            'book_id': int(row['book_id']),
            'interaction_type': interaction,
            'created_at': row['created_at'],
            'weight': base * _recency_factor(row['created_at']),
        })
    return profile


def get_personalized_recommendations(user_id, n=8, interaction_limit=30):
    """Generate personalized content-based recommendations from this user's history.

    This is a hybrid of interaction weighting and content similarity. It is not
    collaborative filtering: no other user's behaviour is used.
    """
    profile = get_user_interaction_profile(user_id, interaction_limit)
    payload = load_model()
    valid_ids = set(int(x) for x in payload['book_ids'])

    if not profile:
        return [], {'personalized': False, 'interaction_count': 0, 'seed_count': 0}

    # Keep the strongest signal for each interacted book so repeated views do not
    # overwhelm a deliberate wishlist/cart/purchase action.
    seed_weights = {}
    seed_types = {}
    for item in profile:
        bid = item['book_id']
        if bid not in valid_ids:
            continue
        if item['weight'] > seed_weights.get(bid, -1):
            seed_weights[bid] = item['weight']
            seed_types[bid] = item['interaction_type']

    if not seed_weights:
        return [], {'personalized': False, 'interaction_count': 0, 'seed_count': 0}

    # Cap seed count to keep page response fast for highly active users.
    seeds = sorted(seed_weights, key=lambda bid: seed_weights[bid], reverse=True)[:8]
    scores = {}
    reasons = {}
    for seed_id in seeds:
        seed_weight = seed_weights[seed_id]
        # Fetch extra neighbours because some candidates may have been interacted with already.
        neighbors = _recommend_similar_with_payload(payload, seed_id, n=min(24, max(12, n * 3)))
        for item in neighbors:
            bid = int(item['book_id'])
            if bid in seed_weights:
                continue
            similarity = float(item.get('similarity_score', 0.0))
            if similarity <= 0:
                continue
            contribution = seed_weight * similarity
            scores[bid] = scores.get(bid, 0.0) + contribution
            reasons.setdefault(bid, []).append((seed_id, seed_types[seed_id], similarity))

    if not scores:
        return [], {'personalized': True, 'interaction_count': len(profile), 'seed_count': len(seeds)}

    ranked_ids = sorted(scores, key=lambda bid: (-scores[bid], bid))[:n]
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = _rows_by_ids(conn, ranked_ids)
    finally:
        conn.close()

    row_map = {int(row['book_id']): row for row in rows}
    result = []
    for rank, bid in enumerate(ranked_ids, start=1):
        row = row_map.get(bid)
        if row is None:
            continue
        item = dict(row)
        item['personalization_score'] = round(scores[bid], 6)
        item['recommendation_rank'] = rank
        best_reason = max(reasons.get(bid, []), key=lambda x: x[2], default=None)
        if best_reason:
            item['reason_interaction'] = best_reason[1]
            item['reason_similarity'] = round(best_reason[2], 4)
        result.append(item)

    return result, {
        'personalized': True,
        'interaction_count': len(profile),
        'seed_count': len(seeds),
    }


def recommend_for_user(user_id, n=8):
    """Backward-compatible personalized recommendation entry point."""
    recommendations, _ = get_personalized_recommendations(user_id, n=n)
    return recommendations
