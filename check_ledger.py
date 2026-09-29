import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from payment_ledger import create_ledger_table


def insert_allocation(
    connection,
    allocation_id,
    transaction_reference,
    order_id,
    submission_id,
    sms_id,
    bank_account_id="BANK-001",
):
    with connection:
        connection.execute("""
            INSERT INTO payment_allocations (
                id,
                environment,
                bank_account_id,
                transaction_reference,
                order_id,
                submission_id,
                sms_id,
                amount_minor,
                currency,
                allocated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            allocation_id,
            "DEMO",
            bank_account_id,
            transaction_reference,
            order_id,
            submission_id,
            sms_id,
            500000,
            "LKR",
            datetime.now(timezone.utc).isoformat(),
        ))


def expect_blocked(connection, name, *args, **kwargs):
    try:
        insert_allocation(connection, *args, **kwargs)
    except sqlite3.IntegrityError:
        print(f"PASS: {name}")
    else:
        raise AssertionError(
            f"FAIL: {name} - database allowed the allocation"
        )


def main():
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        # Minimal parent records for testing ledger constraints.
        connection.executescript("""
            CREATE TABLE business_accounts (id TEXT PRIMARY KEY);
            CREATE TABLE orders (id TEXT PRIMARY KEY);
            CREATE TABLE submissions (id TEXT PRIMARY KEY);
            CREATE TABLE bank_sms (id TEXT PRIMARY KEY);

            INSERT INTO business_accounts VALUES ('BANK-001');

            INSERT INTO orders VALUES ('ORD-001'), ('ORD-002');

            INSERT INTO submissions VALUES ('SUB-001'), ('SUB-002');

            INSERT INTO bank_sms VALUES ('SMS-001'), ('SMS-002');
        """)

        with connection:
            create_ledger_table(connection)

        insert_allocation(
            connection,
            "ALLOC-001", "TXN-001", "ORD-001", "SUB-001", "SMS-001",
        )
        print("PASS: First allocation succeeds")

        expect_blocked(
            connection,
            "Same transaction cannot pay another order",
            "ALLOC-002", "TXN-001", "ORD-002", "SUB-002", "SMS-002",
        )

        expect_blocked(
            connection,
            "Same order cannot receive a second allocation",
            "ALLOC-003", "TXN-002", "ORD-001", "SUB-002", "SMS-002",
        )

        expect_blocked(
            connection,
            "Same SMS cannot be allocated twice",
            "ALLOC-004", "TXN-002", "ORD-002", "SUB-002", "SMS-001",
        )

        expect_blocked(
            connection,
            "Same submission cannot be allocated twice",
            "ALLOC-005", "TXN-002", "ORD-002", "SUB-001", "SMS-002",
        )

        expect_blocked(
            connection,
            "Unknown bank account is blocked",
            "ALLOC-006", "TXN-002", "ORD-002", "SUB-002", "SMS-002",
            bank_account_id="BANK-MISSING",
        )

        insert_allocation(
            connection,
            "ALLOC-007", "TXN-002", "ORD-002", "SUB-002", "SMS-002",
        )

        count = connection.execute(
            "SELECT COUNT(*) FROM payment_allocations"
        ).fetchone()[0]

        assert count == 2, f"Expected 2 allocations, found {count}"
        print("PASS: Different payment can pay a different order")

    print("All 7 ledger checks passed.")
    print("Your payments.db was not changed.")


if __name__ == "__main__":
    main()