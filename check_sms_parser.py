from sms_parser import parse_bank_sms


valid_sms = (
    "LKR 5,000.00 credited to A/C 001234567890. "
    "Ref DEMO-TXN-001. "
    "Order BST-DEMO-001. "
    "Date 2026-09-28."
)

result = parse_bank_sms(valid_sms)
assert result["parse_status"] == "PARSED"
assert result["amount_minor"] == 500000
assert result["receiving_account"] == "001234567890"
assert result["transaction_reference"] == "DEMO-TXN-001"
assert result["order_reference"] == "BST-DEMO-001"
assert result["issues"] == []
print("PASS: Valid demo SMS")


result = parse_bank_sms(
    valid_sms.replace("credited", "debited")
)
assert result["parse_status"] == "UNSUPPORTED"
assert result["amount_minor"] is None
print("PASS: Debit is not accepted as credit")


result = parse_bank_sms(
    valid_sms.replace("Order BST-DEMO-001. ", "")
)
assert result["parse_status"] == "PARSED"
assert result["order_reference"] is None
assert "ORDER_REFERENCE_MISSING" in result["issues"]
print("PASS: Missing order reference is flagged")


result = parse_bank_sms(
    valid_sms.replace("001234567890", "XXXX7890")
)
assert result["receiving_account"] is None
assert result["account_suffix"] == "7890"
assert result["account_is_masked"] is True
assert "MASKED_ACCOUNT_REQUIRES_RESOLUTION" in result["issues"]
print("PASS: Masked account remains incomplete")


result = parse_bank_sms(
    valid_sms.replace("2026-09-28", "2026-02-30")
)
assert result["parse_status"] == "INVALID"
assert "INVALID_SMS_DATE" in result["issues"]
print("PASS: Invalid date is detected")


result = parse_bank_sms(valid_sms + " Reversed.")
assert result["parse_status"] == "UNSUPPORTED"
assert result["amount_minor"] is None
print("PASS: Extra reversal text is not ignored")

print("All 6 SMS parser checks passed.")