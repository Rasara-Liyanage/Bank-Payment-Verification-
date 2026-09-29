from payment_parser import parse_payment_fields


cases = [
    (
        "Explicit order reference",
        "Order Reference: BST-DEMO-001",
        "BST-DEMO-001",
        None,
        None,
    ),
    (
        "Payment reference stays unclassified",
        "Payment Reference: DEMO-TXN-001",
        None,
        None,
        "DEMO-TXN-001",
    ),
    (
        "Generic reference stays unclassified",
        "Reference: BST-DEMO-001",
        None,
        None,
        "BST-DEMO-001",
    ),
    (
        "Explicit roles remain separate",
        (
            "Order Reference: BST-DEMO-001\n"
            "Transaction Reference: DEMO-TXN-001\n"
            "Payment Reference: OTHER-001"
        ),
        "BST-DEMO-001",
        "DEMO-TXN-001",
        "OTHER-001",
    ),
    (
        "Conflicting order references are blocked",
        (
            "Order Reference: BST-DEMO-001\n"
            "Order Reference: BST-DEMO-002"
        ),
        None,
        None,
        None,
    ),
]


for label, text, expected_order, expected_transaction, expected_other in cases:
    fields = parse_payment_fields(text)

    actual = (
        fields["order_reference"]["value"],
        fields["transaction_reference"]["value"],
        fields["unclassified_reference"]["value"],
    )

    expected = (
        expected_order,
        expected_transaction,
        expected_other,
    )

    assert actual == expected, (
        f"{label}: expected {expected}, got {actual}"
    )

    if label == "Conflicting order references are blocked":
        assert (
            "CONFLICTING_VALUES"
            in fields["order_reference"]["issues"]
        )

    print(f"PASS: {label}")

print("All 5 reference role checks passed.")
print("No database changes were made.")