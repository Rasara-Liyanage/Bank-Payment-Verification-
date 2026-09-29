import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from database import get_connection
from payment_ledger import create_ledger_table
from sms_matching import match_submission_sms
from sms_parser import parse_bank_sms
from ocr_service import process_submission_ocr
from review_messages import get_review_message

def save_decision(
    connection,
    submission_id,
    evidence,
    decision,
    reason,
    next_action,
    customer_message,
    allocation_id=None,
):
    decision_id = uuid4().hex

    result = {
        "decision_id": decision_id,
        "environment": "DEMO",
        "submission_id": submission_id,
        "decision": decision,
        "reason": reason,
        "next_action": next_action,
        "customer_message": customer_message,
        "allocation_id": allocation_id,
        "notice": "SIMULATED EVIDENCE - NOT A REAL PAYMENT APPROVAL",
    }

    connection.execute("""
        INSERT INTO verification_decisions (
            id, submission_id, environment, decision,
            result_json, evidence_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        decision_id,
        submission_id,
        "DEMO",
        decision,
        json.dumps(result),
        json.dumps(evidence),
        datetime.now(timezone.utc).isoformat(),
    ))

    return result


def run_demo_decision(submission_id):
    with closing(get_connection()) as read_connection:
        before = read_connection.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()

    if before is None:
        raise ValueError("Submission not found.")

    submission_snapshot = dict(before)
    ocr_result = process_submission_ocr(submission_id)

    with closing(get_connection()) as connection:
        with connection:
            create_ledger_table(connection)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS verification_decisions (
                    id TEXT PRIMARY KEY,
                    submission_id TEXT NOT NULL,
                    environment TEXT NOT NULL CHECK (environment = 'DEMO'),
                    decision TEXT NOT NULL CHECK (
                        decision IN (
                            'APPROVED',
                            'REJECTED',
                            'NEEDS VERIFICATION'
                        )
                    ),
                    result_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (submission_id) REFERENCES submissions(id)
                )
            """)

        with connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT * FROM submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()

            if current is None or dict(current) != submission_snapshot:
                raise ValueError(
                    "Submission changed during OCR. Please retry."
                )

            evidence = match_submission_sms(
                submission_id,
                connection=connection,
                ocr_result=ocr_result,
            )

            def finish(decision, reason, action, message, allocation_id=None):
                return save_decision(
                    connection, submission_id, evidence,
                    decision, reason, action, message, allocation_id,
                )

            candidate_ids = evidence["candidate_sms_ids"]

            if len(candidate_ids) != 1:
                reason, action, message = get_review_message(evidence)

                return finish(
                    "NEEDS VERIFICATION",
                    reason,
                    action,
                    message,
                )

            sms_row = connection.execute("""
                SELECT id, bank_account_id, source, raw_text
                FROM bank_sms WHERE id = ?
            """, (candidate_ids[0],)).fetchone()

            if sms_row is None or sms_row["source"] != "SIMULATED":
                return finish(
                    "NEEDS VERIFICATION",
                    "This workflow accepts simulated evidence only.",
                    "USE_APPROPRIATE_REVIEW_WORKFLOW",
                    "Your payment requires further verification.",
                )

            sms = parse_bank_sms(sms_row["raw_text"])

            if sms["parse_status"] != "PARSED":
                return finish(
                    "NEEDS VERIFICATION",
                    "The SMS could not be parsed.",
                    "REVIEW_SMS",
                    "Your payment requires further verification.",
                )

            bank_account_id = sms_row["bank_account_id"]
            transaction_reference = sms["transaction_reference"]
            order_id = evidence["order_id"]

            existing = connection.execute("""
                SELECT id, order_id
                FROM payment_allocations
                WHERE environment = 'DEMO'
                    AND bank_account_id = ?
                    AND transaction_reference = ?
            """, (bank_account_id, transaction_reference)).fetchone()

            if existing is not None and existing["order_id"] != order_id:
                return finish(
                    "REJECTED",
                    "This demo transaction is allocated to another order.",
                    "REQUEST_CORRECT_PAYMENT",
                    "This payment has already been used for another order. "
                    "Please provide the correct payment slip.",
                )

            preliminary_issues = set(evidence["preliminary_issues"]) - {
                "BANK_EVIDENCE_NOT_CHECKED",
                "PAYMENT_OWNERSHIP_NOT_VERIFIED",
            }

            checks = evidence["sms_checks"]

            mismatches = {
                check["field"]
                for check in checks
                if check["result"] == "MISMATCH"
            }

            has_unknown = any(
                check["result"] == "UNKNOWN" for check in checks
            )

            if (
                mismatches == {"sms_amount_vs_order"}
                and not has_unknown
                and preliminary_issues == {"AMOUNT_MINOR_MISMATCH"}
            ):
                return finish(
                    "REJECTED",
                    "The demo slip and SMS agree on an amount "
                    "that differs from the order total.",
                    "RESOLVE_AMOUNT_MISMATCH",
                    "The payment amount does not match your order. "
                    "Please check the amount and contact the business.",
                )

            if (
                evidence["sms_match_status"] != "FIELDS_MATCH"
                or preliminary_issues
                or sms["issues"]
            ):
                reason, action, message = get_review_message(evidence)

                return finish(
                    "NEEDS VERIFICATION",
                    reason,
                    action,
                    message,
                )

            if existing is not None:
                return finish(
                    "APPROVED",
                    "This demo payment was already allocated to this order.",
                    "NO_NEW_ALLOCATION",
                    "This payment has already been recorded for your order.",
                    existing["id"],
                )

            order_allocation = connection.execute("""
                SELECT id FROM payment_allocations
                WHERE environment = 'DEMO' AND order_id = ?
            """, (order_id,)).fetchone()

            if order_allocation is not None:
                return finish(
                    "NEEDS VERIFICATION",
                    "This order already has a different allocated payment.",
                    "REVIEW_ADDITIONAL_PAYMENT",
                    "A payment is already recorded for this order. "
                    "Please contact the business about this additional payment.",
                )

            allocation_id = uuid4().hex

            connection.execute("""
                INSERT INTO payment_allocations (
                    id, environment, bank_account_id,
                    transaction_reference, order_id, submission_id,
                    sms_id, amount_minor, currency, allocated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                allocation_id,
                "DEMO",
                bank_account_id,
                transaction_reference,
                order_id,
                submission_id,
                sms_row["id"],
                sms["amount_minor"],
                sms["currency"],
                datetime.now(timezone.utc).isoformat(),
            ))

            return finish(
                "APPROVED",
                "Demo evidence checks passed and the payment was allocated.",
                "MARK_DEMO_ORDER_PAID",
                "Your payment has been verified for this order.",
                allocation_id,
            )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python demo_decisions.py SUBMISSION_ID")
        sys.exit(1)

    try:
        result = run_demo_decision(sys.argv[1])
        print(json.dumps(result, indent=2))
    except sqlite3.IntegrityError:
        print(
            "Allocation was blocked by a database constraint. "
            "The transaction was rolled back; manual review is required."
        )
        sys.exit(1)
    except (sqlite3.Error, OSError, ValueError, RuntimeError) as error:
        print(f"Demo verification could not complete: {error}")
        sys.exit(1)