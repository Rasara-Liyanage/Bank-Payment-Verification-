from payment_parser import parse_payment_fields


cases = [
    (
        "Valid payment date",
        "Payment Date: 2026-09-27",
        "2026-09-27",
        None,
    ),
    (
        "Valid leap day",
        "Transaction Date: 2024-02-29",
        "2024-02-29",
        None,
    ),
    (
        "Invalid calendar date",
        "Payment Date: 2026-02-30",
        None,
        "INVALID_CALENDAR_DATE",
    ),
    (
        "Invalid leap day",
        "Payment Date: 2026-02-29",
        None,
        "INVALID_CALENDAR_DATE",
    ),
    (
        "Ambiguous date format",
        "Payment Date: 03/04/2026",
        None,
        "UNREADABLE_OR_UNSUPPORTED_VALUE",
    ),
    (
        "Conflicting dates",
        "Payment Date: 2026-09-27\nTransaction Date: 2026-09-26",
        None,
        "CONFLICTING_VALUES",
    ),
    (
        "Missing payment date",
        "Amount: LKR 5000.00",
        None,
        "FIELD_NOT_FOUND",
    ),
]

for name, text, expected_value, expected_issue in cases:
    result = parse_payment_fields(text)["payment_date"]

    assert result["value"] == expected_value, (name, result)

    if expected_issue is None:
        assert result["issues"] == [], (name, result)
        assert result["precision"] == "day", (name, result)
    else:
        assert expected_issue in result["issues"], (name, result)
        assert result["precision"] is None, (name, result)

    print(f"PASS: {name}")

print("All 7 date checks passed.")