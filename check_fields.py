from payment_parser import parse_payment_fields


sample = """
Amount: LKR 5000.00
Receiving Account: 001234567890
Transaction Reference: TXN-839201
Order Reference: BST-DEMO-001
"""

result = parse_payment_fields(sample)

assert result["amount"]["amount_minor"] == 500000
assert result["receiving_account"]["value"] == "001234567890"
assert result["transaction_reference"]["value"] == "TXN-839201"
assert result["order_reference"]["value"] == "BST-DEMO-001"
print("PASS: Clear fields and leading zeros")


result = parse_payment_fields("Reference: ABC-123")

assert result["transaction_reference"]["value"] is None
assert result["order_reference"]["value"] is None
assert result["unclassified_reference"]["value"] == "ABC-123"
print("PASS: Generic reference is not assigned a role")


result = parse_payment_fields(
    "Receiving Account: 001234567890\n"
    "Receiving Account: 009876543210"
)

assert result["receiving_account"]["value"] is None
assert "CONFLICTING_VALUES" in result["receiving_account"]["issues"]
print("PASS: Conflicting accounts")


result = parse_payment_fields(
    "From Account: 001234567890\n"
    "Account: 009876543210"
)

assert result["receiving_account"]["value"] is None
print("PASS: Sender and ambiguous accounts are not receiving accounts")


result = parse_payment_fields("Receiving Account: XXXX1234")

assert result["receiving_account"]["value"] is None
assert (
    "UNREADABLE_OR_UNSUPPORTED_VALUE"
    in result["receiving_account"]["issues"]
)
print("PASS: Masked account is not treated as a full account")

print("All 5 field checks passed.")