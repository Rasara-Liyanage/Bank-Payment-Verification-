from review_messages import get_review_message


cases = [
    (
        "Missing SMS",
        "NOT_FOUND",
        [],
        "CHECK_SMS_INGESTION_AND_RETRY",
    ),
    (
        "Unreadable transaction reference",
        "INSUFFICIENT_DATA",
        [],
        "REQUEST_CLEAR_TRANSACTION_REFERENCE",
    ),
    (
        "Multiple SMS candidates",
        "AMBIGUOUS",
        [],
        "REVIEW_AMBIGUOUS_SMS",
    ),
    (
        "Slip issue takes priority over waiting for SMS",
        "NOT_FOUND",
        ["AMOUNT_MINOR_UNKNOWN"],
        "REVIEW_SLIP_AND_ORDER",
    ),
    (
        "Invalid payment timing",
        "FIELDS_MATCH",
        ["CLAIMED_PAYMENT_DATE_BEFORE_ORDER"],
        "REVIEW_PAYMENT_DATE",
    ),
    (
        "Conflicting evidence",
        "CONFLICT",
        [],
        "REVIEW_CONFLICTING_EVIDENCE",
    ),
    (
        "Incomplete SMS evidence",
        "INCOMPLETE",
        [],
        "REVIEW_INCOMPLETE_EVIDENCE",
    ),
    (
        "Unknown status falls back to manual review",
        "OTHER",
        [],
        "MANUAL_REVIEW",
    ),
]


for label, status, issues, expected_action in cases:
    evidence = {
        "sms_match_status": status,
        "preliminary_issues": issues + [
            "BANK_EVIDENCE_NOT_CHECKED",
            "PAYMENT_OWNERSHIP_NOT_VERIFIED",
        ],
    }

    reason, action, message = get_review_message(evidence)

    assert action == expected_action, (
        f"{label}: expected {expected_action}, got {action}"
    )
    assert reason.strip(), label
    assert message.strip(), label

    print(f"PASS: {label}")

print("All 8 review message checks passed.")
print("No database changes were made.")