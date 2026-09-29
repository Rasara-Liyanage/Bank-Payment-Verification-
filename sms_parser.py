import json
import re
from contextlib import closing
from datetime import date

from database import get_connection
from payment_parser import parse_amount


SMS_PATTERN = re.compile(
    r"LKR\s+"
    r"(?P<amount>(?:[0-9]{1,12}|[0-9]{1,3}(?:,[0-9]{3}){1,3})"
    r"(?:\.[0-9]{1,2})?)"
    r"\s+credited\s+to\s+A/C\s+"
    r"(?P<account>[0-9]{6,20}|[Xx*]{2,16}[0-9]{4})"
    r"\.\s+Ref\s+"
    r"(?P<transaction>[A-Za-z0-9][A-Za-z0-9/-]{2,63})"
    r"\."
    r"(?:\s+Order\s+"
    r"(?P<order>[A-Za-z0-9][A-Za-z0-9/-]{2,63})"
    r"\.)?"
    r"\s+Date\s+"
    r"(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
    r"\.",
    re.IGNORECASE | re.ASCII,
)


def parse_bank_sms(text):
    result = {
        "parse_status": "UNSUPPORTED",
        "amount_minor": None,
        "currency": None,
        "receiving_account": None,
        "account_suffix": None,
        "account_is_masked": None,
        "transaction_reference": None,
        "order_reference": None,
        "payment_date": None,
        "issues": [],
    }

    normalized_text = " ".join(text.split())
    match = SMS_PATTERN.fullmatch(normalized_text)

    if match is None:
        result["issues"] = ["UNSUPPORTED_SMS_FORMAT"]
        return result

    amount = parse_amount(
        f"Amount: LKR {match.group('amount')}"
    )

    if amount["amount_minor"] is None:
        result["parse_status"] = "INVALID"
        result["issues"] = ["INVALID_SMS_AMOUNT"]
        return result

    try:
        payment_date = date.fromisoformat(match.group("date"))
    except ValueError:
        result["parse_status"] = "INVALID"
        result["issues"] = ["INVALID_SMS_DATE"]
        return result

    account = match.group("account")
    is_masked = not account.isdigit()
    order_reference = match.group("order")

    issues = []

    if is_masked:
        issues.append("MASKED_ACCOUNT_REQUIRES_RESOLUTION")

    if order_reference is None:
        issues.append("ORDER_REFERENCE_MISSING")

    result.update({
        "parse_status": "PARSED",
        "amount_minor": amount["amount_minor"],
        "currency": "LKR",
        "receiving_account": None if is_masked else account,
        "account_suffix": account[-4:],
        "account_is_masked": is_masked,
        "transaction_reference": match.group("transaction"),
        "order_reference": order_reference,
        "payment_date": payment_date.isoformat(),
        "issues": issues,
    })

    return result


if __name__ == "__main__":
    with closing(get_connection()) as connection:
        rows = connection.execute("""
            SELECT id, source, raw_text
            FROM bank_sms
            WHERE id IN (?, ?)
            ORDER BY id
        """, ("SMS-DEMO-001", "SMS-DEMO-002")).fetchall()

    for row in rows:
        print(f"\n{row['id']} | source={row['source']}")
        print(json.dumps(parse_bank_sms(row["raw_text"]), indent=2))