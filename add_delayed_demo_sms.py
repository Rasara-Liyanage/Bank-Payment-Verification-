from contextlib import closing
from datetime import datetime, timezone

from database import get_connection


SMS_ID = "SMS-DEMO-003"
SOURCE_MESSAGE_ID = "demo-message-003"

# Fixed test evidence for the slip created on 2026-09-28.
RAW_TEXT = (
    "LKR 5,000.00 credited to A/C 001234567890. "
    "Ref DEMO-TXN-003. "
    "Order BST-DEMO-002. "
    "Date 2026-09-28."
)


def main():
    now = datetime.now(timezone.utc).isoformat()

    with closing(get_connection()) as connection:
        with connection:
            account = connection.execute(
                """
                SELECT id
                FROM business_accounts
                WHERE bank_code = ?
                  AND account_number = ?
                  AND currency = ?
                  AND active = 1
                """,
                ("DEMO-BANK", "001234567890", "LKR"),
            ).fetchone()

            if account is None:
                raise ValueError("The active demo bank account was not found.")

            existing = connection.execute(
                """
                SELECT id, bank_account_id, source,
                       source_message_id, sender, raw_text
                FROM bank_sms
                WHERE id = ?
                   OR (
                       source = 'SIMULATED'
                       AND bank_account_id = ?
                       AND source_message_id = ?
                   )
                """,
                (SMS_ID, account["id"], SOURCE_MESSAGE_ID),
            ).fetchall()

            if existing:
                expected = {
                    "id": SMS_ID,
                    "bank_account_id": account["id"],
                    "source": "SIMULATED",
                    "source_message_id": SOURCE_MESSAGE_ID,
                    "sender": "DEMO-BANK",
                    "raw_text": RAW_TEXT,
                }

                if len(existing) != 1 or dict(existing[0]) != expected:
                    raise ValueError(
                        "Conflicting SMS data exists. No changes were made."
                    )

                message = "Demo SMS already exists. No duplicate was added."

            else:
                connection.execute(
                    """
                    INSERT INTO bank_sms (
                        id,
                        bank_account_id,
                        source,
                        source_message_id,
                        sender,
                        raw_text,
                        received_at,
                        ingested_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        SMS_ID,
                        account["id"],
                        "SIMULATED",
                        SOURCE_MESSAGE_ID,
                        "DEMO-BANK",
                        RAW_TEXT,
                        now,
                        now,
                    ),
                )

                message = "Delayed demo SMS added."

    print(message)
    print(f"{SMS_ID} | source=SIMULATED")
    print(RAW_TEXT)
    print("SIMULATED TEST DATA - NOT A REAL BANK MESSAGE.")


if __name__ == "__main__":
    main()