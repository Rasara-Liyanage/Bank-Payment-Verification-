import json
import sys
from contextlib import closing, nullcontext

from database import get_connection
from ocr_service import process_submission_ocr
from payment_parser import parse_payment_fields
from sms_parser import parse_bank_sms
from verification_service import compare_field, run_preliminary_checks


def match_submission_sms(submission_id, *, connection=None, ocr_result=None):
    preliminary = run_preliminary_checks(
        submission_id,
        connection=connection,
        ocr_result=ocr_result,
    )

    context = (
        closing(get_connection())
        if connection is None
        else nullcontext(connection)
    )

    with context as connection:
        order = connection.execute("""
            SELECT
                orders.id AS order_id,
                orders.amount_minor,
                orders.currency,
                orders.payment_reference,
                orders.bank_account_id,
                business_accounts.account_number
            FROM submissions
            JOIN orders ON submissions.order_id = orders.id
            LEFT JOIN business_accounts
                ON orders.bank_account_id = business_accounts.id
            WHERE submissions.id = ?
        """, (submission_id,)).fetchone()

        sms_rows = connection.execute("""
            SELECT id, source, raw_text
            FROM bank_sms
            WHERE bank_account_id = ?
            ORDER BY id
        """, (order["bank_account_id"],)).fetchall()

    ocr = (
        ocr_result
        if ocr_result is not None
        else process_submission_ocr(submission_id)
    )
    fields = parse_payment_fields(ocr["text"])

    result = {
        "submission_id": submission_id,
        "order_id": order["order_id"],
        "decision": "NEEDS VERIFICATION",
        "preliminary_checks": preliminary["checks"],
        "preliminary_issues": preliminary["issues"],
        "sms_match_status": "NOT_FOUND",
        "candidate_sms_ids": [],
        "sms_source": None,
        "sms_checks": [],
        "reason": "",
    }

    transaction_reference = fields["transaction_reference"]["value"]

    if transaction_reference is None:
        result["sms_match_status"] = "INSUFFICIENT_DATA"
        result["reason"] = (
            "The slip transaction reference could not be identified."
        )
        return result

    candidates = []

    for sms_row in sms_rows:
        parsed = parse_bank_sms(sms_row["raw_text"])

        if (
            parsed["parse_status"] == "PARSED"
            and parsed["transaction_reference"] == transaction_reference
        ):
            candidates.append({
                "id": sms_row["id"],
                "source": sms_row["source"],
                "parsed": parsed,
            })

    result["candidate_sms_ids"] = [
        candidate["id"] for candidate in candidates
    ]

    if not candidates:
        result["reason"] = (
            "No supported SMS record matches the transaction reference "
            "within this order's configured bank account."
        )
        return result

    if len(candidates) > 1:
        result["sms_match_status"] = "AMBIGUOUS"
        result["reason"] = (
            "Several SMS records have this transaction reference. "
            "Manual review is required."
        )
        return result

    candidate = candidates[0]
    sms = candidate["parsed"]
    result["sms_source"] = candidate["source"]

    comparisons = [
        ("sms_amount_vs_order",
         order["amount_minor"], sms["amount_minor"]),

        ("sms_currency_vs_order",
         order["currency"], sms["currency"]),

        ("sms_account_vs_config",
         order["account_number"], sms["receiving_account"]),

        ("sms_order_reference_vs_order",
         order["payment_reference"], sms["order_reference"]),

        ("sms_amount_vs_slip",
         fields["amount"]["amount_minor"], sms["amount_minor"]),

        ("sms_currency_vs_slip",
         fields["amount"]["currency"], sms["currency"]),

        ("sms_account_vs_slip",
         fields["receiving_account"]["value"], sms["receiving_account"]),

        ("sms_order_reference_vs_slip",
         fields["order_reference"]["value"], sms["order_reference"]),

        ("sms_date_vs_slip",
         fields["payment_date"]["value"], sms["payment_date"]),
    ]

    checks = [
        compare_field(name, expected, extracted)
        for name, expected, extracted in comparisons
    ]

    result["sms_checks"] = checks
    outcomes = {check["result"] for check in checks}

    if "MISMATCH" in outcomes:
        result["sms_match_status"] = "CONFLICT"
        result["reason"] = (
            "An SMS candidate was found, but some evidence conflicts."
        )
    elif "UNKNOWN" in outcomes:
        result["sms_match_status"] = "INCOMPLETE"
        result["reason"] = (
            "An SMS candidate was found, but required fields are missing."
        )
    else:
        result["sms_match_status"] = "FIELDS_MATCH"
        result["reason"] = (
            "Compared fields agree. Source authentication, date-policy "
            "checks and payment reuse checks are still required."
        )

    if candidate["source"] == "SIMULATED":
        result["reason"] += (
            " This SMS is simulated and cannot prove a real payment."
        )

    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python sms_matching.py SUBMISSION_ID")
        sys.exit(1)

    try:
        result = match_submission_sms(sys.argv[1])
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"SMS matching could not complete: {error}")
        sys.exit(1)