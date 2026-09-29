import json
import tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import database
import sms_matching
import verification_service
from demo_decisions import run_demo_decision
import demo_decisions


ACCOUNT = "001234567890"
DAY = "2026-09-28"
REFERENCE = "BST-TEST-001"


def run_case(
    label,
    expected,
    changes=None,
    sms_count=1,
    source="SIMULATED",
    expected_issue=None,
    expected_match=None,
):
    values = {
        "amount": "5000.00",
        "account": ACCOUNT,
        "day": DAY,
        "reference": REFERENCE,
    }
    values.update(changes or {})

    slip = (
        f"Amount: LKR {values['amount']}\n"
        f"Receiving Account: {values['account']}\n"
        "Transaction Reference: TEST-TXN-001\n"
        f"Order Reference: {values['reference']}\n"
        f"Payment Date: {values['day']}"
    )

    sms = (
        f"LKR {values['amount']} credited to A/C {values['account']}. "
        f"Ref TEST-TXN-001. Order {values['reference']}. "
        f"Date {values['day']}."
    )

    with tempfile.TemporaryDirectory() as directory:
        with patch.object(
            database,
            "DB_PATH",
            Path(directory) / "test.db",
        ):
            database.init_db()

            with closing(database.get_connection()) as connection:
                connection.executescript("""
                    CREATE TABLE business_accounts (
                        id TEXT PRIMARY KEY,
                        account_number TEXT NOT NULL,
                        active INTEGER NOT NULL,
                        currency TEXT NOT NULL
                    );

                    ALTER TABLE orders ADD COLUMN bank_account_id TEXT
                        REFERENCES business_accounts(id);

                    CREATE TABLE submissions (
                        id TEXT PRIMARY KEY,
                        order_id TEXT NOT NULL REFERENCES orders(id),
                        submitted_at TEXT NOT NULL
                    );

                    CREATE TABLE bank_sms (
                        id TEXT PRIMARY KEY,
                        bank_account_id TEXT NOT NULL
                            REFERENCES business_accounts(id),
                        source TEXT NOT NULL,
                        raw_text TEXT NOT NULL
                    );
                """)

                with connection:
                    connection.execute(
                        "INSERT INTO customers VALUES (?, ?)",
                        ("TEST-CUSTOMER", "Test customer"),
                    )

                    connection.execute(
                        "INSERT INTO business_accounts VALUES (?, ?, ?, ?)",
                        ("TEST-BANK", ACCOUNT, 1, "LKR"),
                    )

                    connection.execute(
                        "INSERT INTO orders "
                        "(id, customer_id, amount_minor, currency, "
                        "payment_reference, created_at, bank_account_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            "TEST-ORDER",
                            "TEST-CUSTOMER",
                            500000,
                            "LKR",
                            REFERENCE,
                            "2026-09-28T02:00:00+00:00",
                            "TEST-BANK",
                        ),
                    )

                    connection.execute(
                        "INSERT INTO submissions VALUES (?, ?, ?)",
                        (
                            "TEST-SUB",
                            "TEST-ORDER",
                            "2026-09-28T04:00:00+00:00",
                        ),
                    )

                    for number in range(sms_count):
                        connection.execute(
                            "INSERT INTO bank_sms VALUES (?, ?, ?, ?)",
                            (
                                f"TEST-SMS-{number}",
                                "TEST-BANK",
                                source,
                                sms,
                            ),
                        )

            ocr_result = {
                "submission_id": "TEST-SUB",
                "cached": True,
                "text": slip,
            }

            with (
                patch.object(
                    demo_decisions,
                    "process_submission_ocr",
                    return_value=ocr_result,
                ),
                patch.object(
                    verification_service,
                    "process_submission_ocr",
                    return_value=ocr_result,
                ),
                patch.object(
                    sms_matching,
                    "process_submission_ocr",
                    return_value=ocr_result,
                ),
            ):
                result = run_demo_decision("TEST-SUB")

            assert result["decision"] == expected, (label, result)

            with closing(database.get_connection()) as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM payment_allocations"
                ).fetchone()[0]

                records = connection.execute(
                    "SELECT result_json, evidence_json "
                    "FROM verification_decisions"
                ).fetchall()

            expected_count = 1 if expected == "APPROVED" else 0

            assert count == expected_count, label
            assert len(records) == 1, label
            assert json.loads(records[0]["result_json"]) == result, label

            evidence = json.loads(records[0]["evidence_json"])

            if expected_issue:
                assert (
                    expected_issue in evidence["preliminary_issues"]
                ), evidence

            if expected_match:
                assert (
                    evidence["sms_match_status"] == expected_match
                ), evidence

    print(f"PASS: {label}")


def main():
    run_case(
        "Valid demo evidence approves",
        "APPROVED",
        expected_match="FIELDS_MATCH",
    )

    run_case(
        "Wrong receiving account does not approve",
        "NEEDS VERIFICATION",
        {"account": "009999999999"},
        expected_issue="RECEIVING_ACCOUNT_MISMATCH",
    )

    run_case(
        "Payment before order does not approve",
        "NEEDS VERIFICATION",
        {"day": "2026-09-27"},
        expected_issue="CLAIMED_PAYMENT_DATE_BEFORE_ORDER",
    )

    run_case(
        "Payment after submission does not approve",
        "NEEDS VERIFICATION",
        {"day": "2026-09-29"},
        expected_issue="CLAIMED_PAYMENT_DATE_AFTER_SUBMISSION",
    )

    run_case(
        "Multiple SMS candidates do not approve",
        "NEEDS VERIFICATION",
        sms_count=2,
        expected_match="AMBIGUOUS",
    )

    run_case(
        "Missing SMS does not approve",
        "NEEDS VERIFICATION",
        sms_count=0,
        expected_match="NOT_FOUND",
    )

    run_case(
        "Wrong amount is rejected",
        "REJECTED",
        {"amount": "4000.00"},
        expected_issue="AMOUNT_MINOR_MISMATCH",
    )

    run_case(
        "Wrong order reference does not approve",
        "NEEDS VERIFICATION",
        {"reference": "BST-OTHER-001"},
        expected_issue="ORDER_REFERENCE_MISMATCH",
    )

    run_case(
        "DEVICE source cannot use demo approval",
        "NEEDS VERIFICATION",
        source="DEVICE",
        expected_match="FIELDS_MATCH",
    )

    print("All 9 verification scenario checks passed.")
    print("Your payments.db was not changed.")


if __name__ == "__main__":
    main()