"""Grounded bookstore chatbot utilities.

No generative model is required: every catalogue answer is built from SQLite,
and recommendation answers use the existing content-based recommender.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from difflib import SequenceMatcher

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "bookstore.db"

PRICE_RE = re.compile(r"(?:under|below|less than|up to)\s*(?:₹|rs\.?|inr\s*)?([0-9][0-9,]*(?:\.[0-9]+)?)", re.I)
RATING_RE = re.compile(r"(?:rating|rated)\s*(?:of|above|over|at least|>=)?\s*([0-5](?:\.[0-9])?)", re.I)
YEAR_RE = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def detect_intent(message: str) -> str:
    text = _clean(message).lower()
    if not text:
        return "empty"
    if any(x in text for x in ("help", "what can you do", "how do i use")):
        return "help"
    if any(x in text for x in ("recommend", "suggest", "similar", "what should i read", "books for me")):
        return "recommend"
    if any(x in text for x in ("under ", "below ", "less than", "cheap", "price", "₹", "rs ", "inr")):
        return "price_search"
    if any(x in text for x in ("by author", "author", "written by", "books by", "by ", "books of")):
        return "author_search"
    if any(x in text for x in ("publisher", "published by")):
        return "publisher_search"
    if any(x in text for x in ("rating", "rated", "top rated", "best rated")):
        return "rating_search"
    if any(x in text for x in ("year", "published in", "publication")) or YEAR_RE.search(text):
        return "year_search"
    if any(x in text for x in ("tell me about", "details", "information about", "info about")):
        return "book_details"
    if any(x in text for x in ("hello", "hi", "hey", "good morning", "good evening")):
        return "greeting"
    if any(x in text for x in ("how to order", "how do i order", "checkout", "buy a book")):
        return "ordering_help"
    return "catalogue_search"


def _extract_price(text: str):
    match = PRICE_RE.search(text)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def _extract_year(text: str):
    match = YEAR_RE.search(text)
    return int(match.group(1)) if match else None


def _extract_quoted_or_named_query(text: str) -> str:
    quoted = re.search(r"[\"']([^\"']+)[\"']", text)
    if quoted:
        return _clean(quoted.group(1))
    patterns = [
        r"(?:written by|books by|by author|author|by)\s+(.+)$",
        r"(?:about|details for|information about|info about)\s+(.+)$",
        r"(?:find|search|show|look for)\s+(?:books?\s+)?(?:by\s+)?(.+)$",
    ]
    low = text.lower()
    for pattern in patterns:
        m = re.search(pattern, low, re.I)
        if m:
            value = _clean(m.group(1))
            value = re.sub(r"\b(?:please|books|book)\b$", "", value, flags=re.I).strip()
            if value:
                return value
    return _clean(text)


def search_catalogue(query: str = "", limit: int = 6, max_price=None, min_rating=None, year=None):
    conditions, params = [], []
    query = _clean(query)
    if query:
        like = f"%{query}%"
        conditions.append("(title LIKE ? OR author LIKE ? OR publisher LIKE ?)")
        params.extend([like, like, like])
    if max_price is not None:
        conditions.append("price <= ?")
        params.append(float(max_price))
    if min_rating is not None:
        conditions.append("avg_rating >= ?")
        params.append(float(min_rating))
    if year is not None:
        conditions.append("publication_year = ?")
        params.append(int(year))

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    conn = _conn()
    try:
        return conn.execute(
            f"""SELECT book_id, title, author, publisher, publication_year, avg_rating, price
                FROM books{where}
                ORDER BY avg_rating IS NULL, avg_rating DESC, title COLLATE NOCASE ASC
                LIMIT ?""",
            params + [int(limit)],
        ).fetchall()
    finally:
        conn.close()


def find_book(query: str):
    query = _clean(query)
    if not query:
        return None
    conn = _conn()
    try:
        exact = conn.execute(
            """SELECT book_id, title, author, publisher, publication_year, avg_rating, price
               FROM books WHERE title = ? COLLATE NOCASE LIMIT 1""", (query,)
        ).fetchone()
        if exact:
            return exact
        rows = conn.execute(
            """SELECT book_id, title, author, publisher, publication_year, avg_rating, price
               FROM books WHERE title LIKE ? OR author LIKE ?
               ORDER BY avg_rating IS NULL, avg_rating DESC LIMIT 25""",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        if not rows:
            return None
        q = query.lower()
        return max(rows, key=lambda r: max(SequenceMatcher(None, q, str(r['title']).lower()).ratio(),
                                           SequenceMatcher(None, q, str(r['author']).lower()).ratio()))
    finally:
        conn.close()


def format_books(rows):
    return [
        {
            "book_id": int(r["book_id"]),
            "title": str(r["title"] or "Untitled"),
            "author": str(r["author"] or "Unknown Author"),
            "publisher": str(r["publisher"] or "Unknown Publisher"),
            "publication_year": r["publication_year"],
            "avg_rating": float(r["avg_rating"]) if r["avg_rating"] is not None else None,
            "price": float(r["price"] or 0),
        }
        for r in rows
    ]


def answer_catalogue_query(message: str, personalized_recommendations=None):
    """Return a structured, database-grounded answer."""
    intent = detect_intent(message)
    text = _clean(message)
    low = text.lower()

    if intent == "empty":
        return {"intent": intent, "text": "Please type a book title, author, price, rating, or recommendation request.", "books": []}
    if intent == "greeting":
        return {"intent": intent, "text": "Hello! 👋 I can help you find books, authors, prices, ratings, publication years, and recommendations from this bookstore catalogue.", "books": []}
    if intent == "help":
        return {"intent": intent, "text": "Try: “books by Agatha Christie”, “books under ₹500”, “top rated books”, “books published in 2000”, “recommend some books”, or “tell me about [book title]”.", "books": []}
    if intent == "ordering_help":
        return {"intent": intent, "text": "To order a book, open its details, choose Add to Cart or Buy Now, then continue through the Cart and Checkout pages. Checkout will be connected in the next development stage.", "books": []}

    if intent == "recommend":
        if personalized_recommendations:
            return {"intent": intent, "text": "Here are recommendations based on your bookstore activity:", "books": format_books(personalized_recommendations)}
        rows = search_catalogue(limit=6)
        return {"intent": intent, "text": "You have not built enough activity for personalized results yet, so here are highly rated catalogue picks:", "books": format_books(rows)}

    if intent == "book_details":
        query = _extract_quoted_or_named_query(text)
        book = find_book(query)
        if not book:
            return {"intent": intent, "text": f"I could not find a catalogue book matching “{query}”. Try the exact title or author name.", "books": []}
        return {"intent": intent, "text": "Here is the closest catalogue match:", "books": format_books([book])}

    price = _extract_price(text)
    rating_match = RATING_RE.search(text)
    min_rating = float(rating_match.group(1)) if rating_match else None
    year = _extract_year(text)

    if intent == "author_search":
        query = _extract_quoted_or_named_query(text)
    elif intent == "publisher_search":
        query = _extract_quoted_or_named_query(text)
    else:
        query = _extract_quoted_or_named_query(text)

    if intent == "price_search":
        rows = search_catalogue(query="", limit=6, max_price=price) if price is not None else search_catalogue(query, limit=6)
        text_answer = f"I found books priced at or below ₹{price:,.0f}." if price is not None else "Here are matching catalogue results."
    elif intent == "rating_search":
        rows = search_catalogue(query="", limit=6, min_rating=min_rating or 4.0)
        text_answer = f"Here are books with a rating of at least {(min_rating or 4.0):.1f} ⭐."
    elif intent == "year_search":
        rows = search_catalogue(query="", limit=6, year=year) if year else search_catalogue(query, limit=6)
        text_answer = f"Here are books published in {year}." if year else "Here are matching catalogue results."
    else:
        rows = search_catalogue(query=query, limit=6)
        if intent == "author_search":
            text_answer = f"Here are catalogue books matching author “{query}”."
        elif intent == "publisher_search":
            text_answer = f"Here are catalogue books matching publisher “{query}”."
        else:
            text_answer = f"Here are catalogue results matching “{query}”."

    if not rows:
        text_answer += " I couldn't find a matching book in the current catalogue."
    return {"intent": intent, "text": text_answer, "books": format_books(rows)}
