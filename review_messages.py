PRELIMINARY_MARKERS = {
    "BANK_EVIDENCE_NOT_CHECKED",
    "PAYMENT_OWNERSHIP_NOT_VERIFIED",
}


def get_review_message(evidence):
    status = evidence.get("sms_match_status")

    issues = (
        set(evidence.get("preliminary_issues", []))
        - PRELIMINARY_MARKERS
    )

    if status == "AMBIGUOUS":
        return (
            "Several SMS candidates match the transaction reference.",
            "REVIEW_AMBIGUOUS_SMS",
            "More than one payment record requires review. "
            "Please contact the business before making another payment.",
        )

    if status == "INSUFFICIENT_DATA":
        return (
            "The slip transaction reference could not be identified.",
            "REQUEST_CLEAR_TRANSACTION_REFERENCE",
            "We could not read the transaction reference on your slip. "
            "Please provide a clear, complete slip showing that reference.",
        )

    if issues & {
        "PAYMENT_DATE_UNKNOWN",
        "CLAIMED_PAYMENT_DATE_BEFORE_ORDER",
        "CLAIMED_PAYMENT_DATE_AFTER_SUBMISSION",
    }:
        return (
            "The payment date is missing, unreadable, or outside the allowed dates.",
            "REVIEW_PAYMENT_DATE",
            "We could not confirm the payment date for this order. "
            "Please check your slip and contact the business.",
        )

    if issues:
        return (
            "Slip comparisons or business account settings require review.",
            "REVIEW_SLIP_AND_ORDER",
            "Some payment details could not be confirmed for this order. "
            "Please check the slip and contact the business.",
        )

    if status == "NOT_FOUND":
        return (
            "No supported SMS record matches this transaction in the configured account.",
            "CHECK_SMS_INGESTION_AND_RETRY",
            "We have not yet matched your slip to a bank notification. "
            "The business needs to check its payment records. "
            "Please do not pay again solely because verification is pending.",
        )

    if status == "CONFLICT":
        return (
            "The slip, order, and SMS comparisons contain conflicting values.",
            "REVIEW_CONFLICTING_EVIDENCE",
            "The payment details do not agree across the available records. "
            "Please contact the business for a review.",
        )

    if status == "INCOMPLETE":
        return (
            "The SMS comparisons are missing required information.",
            "REVIEW_INCOMPLETE_EVIDENCE",
            "The available payment records do not contain enough information. "
            "The business needs to review the payment.",
        )

    return (
        "The available evidence requires further review.",
        "MANUAL_REVIEW",
        "We could not safely verify this payment. "
        "Please contact the business.",
    )