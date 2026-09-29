from contextlib import closing

from database import get_connection


def create_ledger_table(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS payment_allocations (
            id TEXT PRIMARY KEY,

            environment TEXT NOT NULL
                CHECK (environment IN ('DEMO', 'LIVE')),

            bank_account_id TEXT NOT NULL,

            transaction_reference TEXT NOT NULL
                CHECK (length(trim(transaction_reference)) > 0),

            order_id TEXT NOT NULL,
            submission_id TEXT NOT NULL,
            sms_id TEXT NOT NULL,

            amount_minor INTEGER NOT NULL
                CHECK (amount_minor > 0),

            currency TEXT NOT NULL
                CHECK (currency = 'LKR'),

            allocated_at TEXT NOT NULL,

            FOREIGN KEY (bank_account_id)
                REFERENCES business_accounts(id),

            FOREIGN KEY (order_id)
                REFERENCES orders(id),

            FOREIGN KEY (submission_id)
                REFERENCES submissions(id),

            FOREIGN KEY (sms_id)
                REFERENCES bank_sms(id),

            UNIQUE (
                environment,
                bank_account_id,
                transaction_reference
            ),

            UNIQUE (
                environment,
                order_id
            ),

            UNIQUE (
                environment,
                sms_id
            ),

            UNIQUE (
                environment,
                submission_id
            )
        )
    """)


def setup_ledger():
    with closing(get_connection()) as connection:
        with connection:
            create_ledger_table(connection)

        count = connection.execute(
            "SELECT COUNT(*) FROM payment_allocations"
        ).fetchone()[0]

    print("Payment allocation ledger is ready.")
    print(f"Existing allocations: {count}")


if __name__ == "__main__":
    setup_ledger()