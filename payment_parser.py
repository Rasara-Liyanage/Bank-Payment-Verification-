"order_reference"
import re
from datetime import date
from decimal import Decimal


AMOUNT_LABEL = re.compile(
    r"^(?:amount|total amount|payment amount)\s*:\s*(.*)$",
    re.IGNORECASE,
)

LKR_VALUE = re.compile(
    r"LKR\s+"
    r"(?P<number>(?:[0-9]{1,12}|[0-9]{1,3}(?:,[0-9]{3}){1,3})"
    r"(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)


def parse_amount(text):
    candidates = []
    issues = []
    found_label = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        label_match = AMOUNT_LABEL.fullmatch(line)

        if label_match is None:
            continue

        found_label = True
        value_match = LKR_VALUE.fullmatch(label_match.group(1).strip())

        if value_match is None:
            issues.append("UNREADABLE_OR_UNSUPPORTED_AMOUNT")
            continue

        number = value_match.group("number").replace(",", "")
        amount_minor = int(Decimal(number) * 100)

        if amount_minor <= 0:
            issues.append("INVALID_AMOUNT")
            continue

        candidates.append({
            "amount_minor": amount_minor,
            "currency": "LKR",
            "source_line": line,
        })

    unique_amounts = {
        candidate["amount_minor"] for candidate in candidates
    }

    if not found_label:
        issues.append("AMOUNT_NOT_FOUND")

    if len(unique_amounts) > 1:
        issues.append("CONFLICTING_AMOUNTS")

    amount_minor = None

    if len(unique_amounts) == 1 and not issues:
        amount_minor = next(iter(unique_amounts))

    return {
        "amount_minor": amount_minor,
        "currency": "LKR" if amount_minor is not None else None,
        "candidates": candidates,
        "issues": sorted(set(issues)),
    }

def parse_labeled_field(text, labels, value_pattern):
    candidates = []
    issues = []
    found_label = False

    for raw_line in text.splitlines():
        label, separator, value = raw_line.partition(":")

        if not separator:
            continue

        normalized_label = " ".join(label.lower().split())

        if normalized_label not in labels:
            continue

        found_label = True
        value = value.strip()

        if re.fullmatch(value_pattern, value, flags=re.ASCII) is None:
            issues.append("UNREADABLE_OR_UNSUPPORTED_VALUE")
            continue

        candidates.append({
            "value": value,
            "source_line": raw_line.strip(),
        })

    unique_values = {
        candidate["value"] for candidate in candidates
    }

    if not found_label:
        issues.append("FIELD_NOT_FOUND")

    if len(unique_values) > 1:
        issues.append("CONFLICTING_VALUES")

    selected_value = None

    if len(unique_values) == 1 and not issues:
        selected_value = next(iter(unique_values))

    return {
        "value": selected_value,
        "candidates": candidates,
        "issues": sorted(set(issues)),
    }


def parse_payment_fields(text):
    reference_pattern = r"[A-Za-z0-9][A-Za-z0-9/-]{2,63}"

    return {
        "amount": parse_amount(text),
        "payment_date": parse_payment_date(text),

        "receiving_account": parse_labeled_field(
            text,
            {
                "receiving account",
                "beneficiary account",
                "to account",
            },
            r"[0-9]{6,20}",
        ),

        "transaction_reference": parse_labeled_field(
            text,
            {
                "transaction reference",
                "transaction id",
                "bank reference",
            },
            reference_pattern,
        ),

        "order_reference": parse_labeled_field(
            text,
            {"order reference"},
            reference_pattern,
        ),

        "unclassified_reference": parse_labeled_field(
            text,
            {"reference", "ref", "payment reference"},
            reference_pattern,
        ),
    }

def parse_payment_date(text):
    result = parse_labeled_field(
        text,
        {"payment date", "transaction date"},
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}",
    )

    issues = set(result["issues"])

    for candidate in result["candidates"]:
        try:
            date.fromisoformat(candidate["value"])
        except ValueError:
            issues.add("INVALID_CALENDAR_DATE")

    result["issues"] = sorted(issues)

    if issues:
        result["value"] = None

    result["precision"] = (
        "day" if result["value"] is not None else None
    )

    return result