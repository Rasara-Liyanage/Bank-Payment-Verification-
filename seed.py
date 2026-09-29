from contextlib import closing
from datetime import datetime, timezone

from database import get_connection, init_db


def seed_data():
    init_db()

    created_at = datetime.now(timezone.utc).isoformat()

    customers = [
        ("CUS-001", "Demo Customer A"),
        ("CUS-002", "Demo Customer B"),
    ]

    orders = [
        (
            "ORD-001",
            "CUS-001",
            500000,
            "LKR",
            "BST-DEMO-001",
            created_at,
        ),
        (
            "ORD-002",
            "CUS-002",
            500000,
            "LKR",
            "BST-DEMO-002",
            created_at,
        ),
    ]

    with closing(get_connection()) as connection:
        with connection:
            connection.executemany("""
                INSERT INTO customers (id, name)
                VALUES (?, ?)
                ON CONFLICT(id) DO NOTHING
            """, customers)

            connection.executemany("""
                INSERT INTO orders (
                    id,
                    customer_id,
                    amount_minor,
                    currency,
                    payment_reference,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
            """, orders)

    print("Demo customers and orders are ready.")


if __name__ == "__main__":
    seed_data()