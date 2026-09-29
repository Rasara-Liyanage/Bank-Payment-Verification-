from contextlib import closing
from datetime import datetime, timedelta, timezone

from database import get_connection


SRI_LANKA_TIME = timezone(timedelta(hours=5, minutes=30))


def setup_bank_sms():
    now = datetime.now(timezone.utc)
    received_at = now.isoformat()
    payment_day = now.astimezone(SRI_LANKA_TIME).date().isoformat()

    messages = [
        (
            "SMS-DEMO-001",
            "BANK-001",
            "SIMULATED",
            "demo-message-001",
            "DEMO-BANK",
            (
                "LKR 5,000.00 credited to A/C 001234567890. "
                "Ref DEMO-TXN-001. "
                "Order BST-DEMO-001. "
                f"Date {payment_day}."
            ),
            received_at,
            received_at,
        ),
        (
            "SMS-DEMO-002",
            "BANK-001",
            "SIMULATED",
            "demo-message-002",
            "DEMO-BANK",
            (
                "LKR 4,000.00 credited to A/C 001234567890. "
                "Ref DEMO-TXN-002. "
                "Order BST-DEMO-001. "
                f"Date {payment_day}."
            ),
            received_at,
            received_at,
        ),
    ]

    with closing(get_connection()) as connection:
        account = connection.execute(
            "SELECT id FROM business_accounts WHERE id = ?",
            ("BANK-001",),
        ).fetchone()

        if account is None:
            raise ValueError(
                "Demo bank account is missing. Run setup_business.py first."
            )

        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS bank_sms (
                    id TEXT PRIMARY KEY,
                    bank_account_id TEXT NOT NULL,
                    source TEXT NOT NULL
                        CHECK (
                            source IN ('SIMULATED', 'MANUAL', 'DEVICE')
                        ),
                    source_message_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    FOREIGN KEY (bank_account_id)
                        REFERENCES business_accounts(id),
                    UNIQUE (
                        source,
                        bank_account_id,
                        source_message_id
                    )
                )
            """)

            connection.executemany("""
                INSERT INTO bank_sms (
                    id,
                    bank_account_id,
                    source,
                    source_message_id,
                    sender,
                    raw_text,
                    received_at,
                    ingested_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    source,
                    bank_account_id,
                    source_message_id
                ) DO NOTHING
            """, messages)

        rows = connection.execute("""
            SELECT id, source, raw_text
            FROM bank_sms
            WHERE id IN (?, ?)
            ORDER BY id
        """, ("SMS-DEMO-001", "SMS-DEMO-002")).fetchall()

    print("Bank SMS table is ready.")
    print("These messages are SIMULATED test data.")

    for row in rows:
        print()
        print(f"{row['id']} | source={row['source']}")
        print(row["raw_text"])


if __name__ == "__main__":
    setup_bank_sms()