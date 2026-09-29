import json
import sys
from contextlib import closing, nullcontext
from datetime import date, datetime, timedelta, timezone

from database import get_connection
from ocr_service import process_submission_ocr
from payment_parser import parse_payment_fields


SRI_LANKA_TIME = timezone(timedelta(hours=5, minutes=30))


def compare_field(field_name, expected, extracted):
    if expected is None or extracted is None:
        result = "UNKNOWN"
    elif expected == extracted:
        result = "MATCH"
    else:
        result = "MISMATCH"

    return {
        "field": field_name,
        "expected": expected,
        "extracted": extracted,
        "result": result,
    }


def run_preliminary_checks(submission_id, *, connection=None, ocr_result=None):
    context = (
        closing(get_connection())
        if connection is None
        else nullcontext(connection)
    )

    with context as connection:
        row = connection.execute("""
            SELECT
                submissions.id AS submission_id,
                submissions.submitted_at,
                orders.id AS order_id,
                orders.amount_minor,
                orders.currency,
                orders.payment_reference,
                orders.created_at AS order_created_at,
                business_accounts.account_number,
                business_accounts.active AS account_active,
                business_accounts.currency AS account_currency
            FROM submissions
            JOIN orders
                ON submissions.order_id = orders.id
            LEFT JOIN business_accounts
                ON orders.bank_account_id = business_accounts.id
            WHERE submissions.id = ?
        """, (submission_id,)).fetchone()

    if row is None:
        raise ValueError("Submission not found.")

    if ocr_result is None:
        ocr_result = process_submission_ocr(submission_id)
    fields = parse_payment_fields(ocr_result["text"])

    checks = [
        compare_field(
            "amount_minor",
            row["amount_minor"],
            fields["amount"]["amount_minor"],
        ),
        compare_field(
            "currency",
            row["currency"],
            fields["amount"]["currency"],
        ),
        compare_field(
            "receiving_account",
            row["account_number"],
            fields["receiving_account"]["value"],
        ),
        compare_field(
            "order_reference",
            row["payment_reference"],
            fields["order_reference"]["value"],
        ),
    ]

    issues = []

    if (
        row["account_number"] is None
        or row["account_active"] != 1
        or row["account_currency"] != row["currency"]
    ):
        issues.append("BUSINESS_ACCOUNT_CONFIGURATION_REQUIRES_REVIEW")

    for check in checks:
        if check["result"] != "MATCH":
            issues.append(
                f"{check['field'].upper()}_{check['result']}"
            )

    payment_date = fields["payment_date"]["value"]

    if payment_date is None:
        issues.append("PAYMENT_DATE_UNKNOWN")
    else:
        claimed_date = date.fromisoformat(payment_date)

        order_day = datetime.fromisoformat(
            row["order_created_at"]
        ).astimezone(SRI_LANKA_TIME).date()

        submission_day = datetime.fromisoformat(
            row["submitted_at"]
        ).astimezone(SRI_LANKA_TIME).date()

        if claimed_date < order_day:
            issues.append("CLAIMED_PAYMENT_DATE_BEFORE_ORDER")

        if claimed_date > submission_day:
            issues.append("CLAIMED_PAYMENT_DATE_AFTER_SUBMISSION")

    if fields["transaction_reference"]["value"] is None:
        issues.append("TRANSACTION_REFERENCE_UNKNOWN")

    issues.append("BANK_EVIDENCE_NOT_CHECKED")
    issues.append("PAYMENT_OWNERSHIP_NOT_VERIFIED")

    return {
        "submission_id": submission_id,
        "order_id": row["order_id"],
        "stage": "PRELIMINARY_CHECKS",
        "decision": "NEEDS VERIFICATION",
        "reason": (
            "Preliminary comparisons do not establish that payment "
            "was received and belongs to this order."
        ),
        "checks": checks,
        "issues": issues,
        "next_action": (
            "Review unclear or conflicting fields and obtain "
            "independent bank evidence."
        ),
        "ocr_cached": ocr_result["cached"],
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python verification_service.py SUBMISSION_ID")
        sys.exit(1)

    try:
        result = run_preliminary_checks(sys.argv[1])
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Preliminary checks could not complete: {error}")
        sys.exit(1)