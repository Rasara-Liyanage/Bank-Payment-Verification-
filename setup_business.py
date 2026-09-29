from contextlib import closing

from database import get_connection, init_db


DEMO_ACCOUNT_ID = "BANK-001"


def setup_business():
    init_db()

    with closing(get_connection()) as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS business_accounts (
                    id TEXT PRIMARY KEY,
                    business_name TEXT NOT NULL,
                    bank_code TEXT NOT NULL,
                    account_number TEXT NOT NULL,
                    currency TEXT NOT NULL CHECK (currency = 'LKR'),
                    active INTEGER NOT NULL DEFAULT 1
                        CHECK (active IN (0, 1)),
                    UNIQUE (bank_code, account_number)
                )
            """)

            connection.execute("""
                INSERT INTO business_accounts (
                    id,
                    business_name,
                    bank_code,
                    account_number,
                    currency,
                    active
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
            """, (
                DEMO_ACCOUNT_ID,
                "BuildStart Demo Store",
                "DEMO-BANK",
                "001234567890",
                "LKR",
                1,
            ))

            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(orders)"
                ).fetchall()
            }

            if "bank_account_id" not in columns:
                connection.execute("""
                    ALTER TABLE orders
                    ADD COLUMN bank_account_id TEXT
                    REFERENCES business_accounts(id)
                """)

            connection.execute("""
                UPDATE orders
                SET bank_account_id = ?
                WHERE id IN (?, ?)
                    AND bank_account_id IS NULL
            """, (
                DEMO_ACCOUNT_ID,
                "ORD-001",
                "ORD-002",
            ))

        rows = connection.execute("""
            SELECT
                orders.id AS order_id,
                business_accounts.business_name,
                business_accounts.bank_code,
                business_accounts.account_number,
                business_accounts.currency
            FROM orders
            JOIN business_accounts
                ON orders.bank_account_id = business_accounts.id
            WHERE orders.id IN (?, ?)
            ORDER BY orders.id
        """, ("ORD-001", "ORD-002")).fetchall()

    print("Demo business account setup completed.")
    print("DEMO DATA ONLY - DO NOT SEND MONEY.")

    for row in rows:
        print(
            f"{row['order_id']} -> "
            f"{row['bank_code']} / "
            f"{row['account_number']} / "
            f"{row['currency']}"
        )

    if len(rows) != 2:
        print("WARNING: Both demo orders were not found. Check seed data.")


if __name__ == "__main__":
    setup_business()