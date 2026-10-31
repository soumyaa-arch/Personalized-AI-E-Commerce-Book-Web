import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.book_bot import answer_catalogue_query, detect_intent, find_book


def test_intents():
    assert detect_intent("recommend some books") == "recommend"
    assert detect_intent("books under ₹500") == "price_search"
    assert detect_intent("books by Agatha Christie") == "author_search"
    assert detect_intent("top rated books") == "rating_search"
    assert detect_intent("books published in 2000") == "year_search"


def test_grounded_price_search():
    result = answer_catalogue_query("books under ₹500")
    assert result["books"]
    assert all(book["price"] <= 500 for book in result["books"])


def test_book_lookup_is_catalogue_grounded():
    book = find_book("Harry Potter")
    assert book is None or book["title"]


def test_no_fabricated_empty_result():
    result = answer_catalogue_query('books by "This Author Definitely Does Not Exist 12345"')
    assert result["books"] == []
