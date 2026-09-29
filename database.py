import sqlite3
from contextlib import closing
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "payments.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with closing(get_connection()) as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    amount_minor INTEGER NOT NULL
                        CHECK (amount_minor > 0),
                    currency TEXT NOT NULL DEFAULT 'LKR'
                        CHECK (currency = 'LKR'),
                    payment_reference TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (customer_id)
                        REFERENCES customers(id)
                )
            """)


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
    print(f"Database location: {DB_PATH}")