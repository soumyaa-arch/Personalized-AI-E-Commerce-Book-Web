"""
Purpose:
    Convert the cleaned book CSV dataset into the SQLite database used
    by the AI Book Store project.

"""

from pathlib import Path
import sqlite3
import pandas as pd


# ---------------------------------------------------------
# 1. PROJECT PATHS
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parent

CSV_PATH = ROOT / "final_books_dataset_clean.csv"
DB_PATH = ROOT / "bookstore.db"


# ---------------------------------------------------------
# 2. DATABASE TABLE
# ---------------------------------------------------------

CREATE_BOOKS_TABLE = """
CREATE TABLE IF NOT EXISTS books (
    book_id INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn TEXT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    publisher TEXT,
    publication_year INTEGER,
    avg_rating REAL,
    price REAL,
    ml_text TEXT
);
"""


# ---------------------------------------------------------
# 3. LOAD AND PREPARE DATA
# ---------------------------------------------------------

def load_dataset():
    """Read the cleaned CSV file."""
    df = pd.read_csv(CSV_PATH)

    print(f"CSV rows loaded: {len(df)}")
    print("Columns found:")
    print(df.columns.tolist())

    return df


def prepare_dataset(df):
    """
    Rename the cleaned dataset columns to the names used by
    the SQLite books table and prepare ml_text for recommendation.
    """

    # Adjust these names if your CSV uses slightly different labels.
    column_mapping = {
        "ISBN": "isbn",
        "Book-Title": "title",
        "Book-Author": "author",
        "Publisher": "publisher",
        "Year-Of-Publication": "publication_year",
        "Avg-Book-Rating": "avg_rating",
        "Price": "price",
    }

    df = df.rename(columns=column_mapping)

    required_columns = [
        "isbn",
        "title",
        "author",
        "publisher",
        "publication_year",
        "avg_rating",
        "price",
    ]

    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(
            f"Required columns are missing from the CSV: {missing}"
        )

    # Remove completely duplicated records.
    df = df.drop_duplicates()

    # Clean important text fields.
    text_columns = ["isbn", "title", "author", "publisher"]

    for column in text_columns:
        df[column] = df[column].fillna("").astype(str).str.strip()

    # Convert numeric fields safely.
    df["publication_year"] = pd.to_numeric(
        df["publication_year"], errors="coerce"
    )

    df["avg_rating"] = pd.to_numeric(
        df["avg_rating"], errors="coerce"
    )

    df["price"] = pd.to_numeric(
        df["price"], errors="coerce"
    )

    # Create the text used by the recommendation model.
    df["ml_text"] = (
        df["title"] + " "
        + df["author"] + " "
        + df["publisher"]
    ).str.strip()

    # Keep only the fields required by the SQLite books table.
    df = df[
        [
            "isbn",
            "title",
            "author",
            "publisher",
            "publication_year",
            "avg_rating",
            "price",
            "ml_text",
        ]
    ]

    return df


# ---------------------------------------------------------
# 4. CREATE DATABASE AND INSERT BOOKS
# ---------------------------------------------------------

def create_database():
    """Create the SQLite database and books table."""
    conn = sqlite3.connect(DB_PATH)

    conn.execute(CREATE_BOOKS_TABLE)

    conn.commit()

    return conn


def insert_books(conn, df):
    """Insert the prepared DataFrame into the books table."""

    # Remove old catalogue records so the script can be safely
    # rerun without duplicating all books.
    conn.execute("DELETE FROM books")

    df.to_sql(
        "books",
        conn,
        if_exists="append",
        index=False,
    )

    conn.commit()


# ---------------------------------------------------------
# 5. VERIFY DATABASE
# ---------------------------------------------------------

def verify_database(conn):
    """Check how many books were inserted."""

    count = conn.execute(
        "SELECT COUNT(*) FROM books"
    ).fetchone()[0]

    print(f"Books stored in SQLite: {count}")


# ---------------------------------------------------------
# 6. MAIN PROGRAM
# ---------------------------------------------------------

def main():

    print("========================================")
    print(" CSV → SQLite Book Catalogue Importer")
    print("========================================")

    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found:\n{CSV_PATH}"
        )

    # Step 1: Read CSV
    df = load_dataset()

    # Step 2: Validate and prepare data
    df = prepare_dataset(df)

    # Step 3: Create/connect to SQLite
    conn = create_database()

    try:
        # Step 4: Insert books
        insert_books(conn, df)

        # Step 5: Verify
        verify_database(conn)

    finally:
        conn.close()

    print("\nDatabase created/updated successfully.")
    print(f"Database: {DB_PATH}")


if __name__ == "__main__":
    main()
