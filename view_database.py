"""
Database Viewer for AI E-Commerce Book Store

Place this file in the same folder as bookstore.db, then run:

    python view_database.py

The script does NOT modify the database.
"""

from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).resolve().parent / "bookstore.db"


def connect_db():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"\nDatabase not found:\n{DB_PATH}\n\n"
            "Put view_database.py in the same folder as bookstore.db."
        )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_tables(conn):
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [row["name"] for row in rows]


def get_columns(conn, table):
    return conn.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()


def row_count(conn, table):
    return conn.execute(
        f'SELECT COUNT(*) FROM "{table}"'
    ).fetchone()[0]


def show_schema(conn, table):
    columns = get_columns(conn, table)

    print("\n" + "=" * 90)
    print(f"TABLE STRUCTURE: {table}")
    print("=" * 90)

    print(f"{'Column':<30} {'Type':<15} {'PK':<5} {'Nullable':<10}")
    print("-" * 90)

    for col in columns:
        print(
            f"{col['name']:<30} "
            f"{(col['type'] or 'TEXT'):<15} "
            f"{('YES' if col['pk'] else 'NO'):<5} "
            f"{('NO' if col['notnull'] else 'YES'):<10}"
        )


def show_rows(conn, table, limit=None):
    query = f'SELECT * FROM "{table}"'

    if limit is not None:
        query += f" LIMIT {int(limit)}"

    rows = conn.execute(query).fetchall()

    print("\n" + "=" * 90)
    print(f"TABLE DATA: {table}")
    print("=" * 90)

    if not rows:
        print("No rows found.")
        return

    columns = list(rows[0].keys())
    data = []

    widths = {
        column: min(max(len(column), 10), 35)
        for column in columns
    }

    for row in rows:
        values = []

        for column in columns:
            value = row[column]
            text = "NULL" if value is None else str(value)

            if len(text) > 35:
                text = text[:32] + "..."

            values.append(text)
            widths[column] = min(
                max(widths[column], len(text)),
                35
            )

        data.append(values)

    print(
        " | ".join(
            column.ljust(widths[column])
            for column in columns
        )
    )

    print(
        "-+-".join(
            "-" * widths[column]
            for column in columns
        )
    )

    for values in data:
        print(
            " | ".join(
                value.ljust(widths[column])
                for value, column in zip(values, columns)
            )
        )

    print(f"\nRows displayed: {len(rows)}")


def database_summary(conn, tables):
    print("\n" + "=" * 90)
    print("AI E-COMMERCE BOOK STORE - DATABASE VIEWER")
    print("=" * 90)
    print(f"Database: {DB_PATH}")
    print(f"Number of tables: {len(tables)}")

    print("\nTABLE SUMMARY")
    print("-" * 90)

    for number, table in enumerate(tables, 1):
        print(
            f"{number}. {table:<25} "
            f"{row_count(conn, table):>10,} rows"
        )


def main():
    try:
        conn = connect_db()
    except FileNotFoundError as error:
        print(error)
        return

    try:
        tables = get_tables(conn)

        if not tables:
            print("No tables found in bookstore.db.")
            return

        while True:
            database_summary(conn, tables)

            print("\nMENU")
            print("1. View table data")
            print("2. View table structure")
            print("3. View first 5 rows of every table")
            print("4. Exit")

            choice = input("\nEnter choice: ").strip()

            if choice == "4":
                print("\nDatabase viewer closed.")
                break

            if choice == "3":
                for table in tables:
                    show_rows(conn, table, limit=5)

                input("\nPress Enter to continue...")
                continue

            if choice not in ("1", "2"):
                print("\nInvalid choice.")
                continue

            print("\nAVAILABLE TABLES")
            for number, table in enumerate(tables, 1):
                print(f"{number}. {table}")

            selection = input(
                "\nEnter table number or table name: "
            ).strip()

            if selection.isdigit():
                number = int(selection)

                if 1 <= number <= len(tables):
                    table = tables[number - 1]
                else:
                    print("\nInvalid table number.")
                    continue
            elif selection in tables:
                table = selection
            else:
                print("\nInvalid table name.")
                continue

            if choice == "2":
                show_schema(conn, table)
                input("\nPress Enter to continue...")
                continue

            total = row_count(conn, table)

            print(f"\n{table} contains {total:,} rows.")

            print("\n1. First 10 rows")
            print("2. First 50 rows")
            print("3. All rows")
            print("4. Back")

            view_choice = input("\nChoose: ").strip()

            if view_choice == "1":
                show_rows(conn, table, 10)
            elif view_choice == "2":
                show_rows(conn, table, 50)
            elif view_choice == "3":
                print(
                    "\nNote: Large tables such as books contain "
                    "about 150,000 rows, so displaying everything "
                    "may produce a very large terminal output."
                )
                confirm = input(
                    "Type YES to display all rows: "
                ).strip()

                if confirm == "YES":
                    show_rows(conn, table)
                else:
                    print("Cancelled.")
            elif view_choice == "4":
                continue
            else:
                print("\nInvalid choice.")
                continue

            input("\nPress Enter to continue...")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
