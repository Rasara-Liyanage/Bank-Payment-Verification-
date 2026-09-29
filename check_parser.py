from payment_parser import parse_amount


cases = [
    (
        "Clear amount",
        "Amount: LKR 5000.00",
        500000,
        [],
    ),
    (
        "Comma and cents",
        "Total Amount: LKR 1,250.50",
        125050,
        [],
    ),
    (
        "Unrelated numbers",
        "Account: 009010472979\n100\n200\n50",
        None,
        ["AMOUNT_NOT_FOUND"],
    ),
    (
        "Conflicting amounts",
        "Amount: LKR 5000.00\nTotal Amount: LKR 7000.00",
        None,
        ["CONFLICTING_AMOUNTS"],
    ),
    (
        "Invalid comma grouping",
        "Amount: LKR 5,00.00",
        None,
        ["UNREADABLE_OR_UNSUPPORTED_AMOUNT"],
    ),
    (
        "OCR letter inside amount",
        "Amount: LKR 5O00.00",
        None,
        ["UNREADABLE_OR_UNSUPPORTED_AMOUNT"],
    ),
    (
        "Valid line plus unreadable line",
        "Amount: LKR 5000.00\nTotal Amount: LKR ???",
        None,
        ["UNREADABLE_OR_UNSUPPORTED_AMOUNT"],
    ),
]

for name, text, expected_amount, expected_issues in cases:
    result = parse_amount(text)

    assert result["amount_minor"] == expected_amount, (name, result)
    assert result["issues"] == expected_issues, (name, result)

    print(f"PASS: {name}")

print("All 7 parser checks passed.")