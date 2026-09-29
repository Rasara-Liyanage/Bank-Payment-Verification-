import json
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from database import get_connection
from sms_parser import parse_bank_sms


class SMSConflictError(ValueError):
    pass

LIMITS = {
    "bank_account_id": 80,
    "source_message_id": 160,
    "sender": 100,
    "raw_text": 4000,
    "received_at": 80,
}


def ingest_simulated_sms(payload):
    if not isinstance(payload, dict) or set(payload) != set(LIMITS):
        raise ValueError(
            "Provide exactly these fields: " + ", ".join(LIMITS)
        )

    for name, limit in LIMITS.items():
        value = payload[name]

        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > limit
        ):
            raise ValueError(f"Invalid or oversized field: {name}")

    for name in (
        "bank_account_id",
        "source_message_id",
        "sender",
        "received_at",
    ):
        if payload[name] != payload[name].strip():
            raise ValueError(
                f"Remove surrounding whitespace from: {name}"
            )

    try:
        received = datetime.fromisoformat(payload["received_at"])
    except ValueError:
        raise ValueError(
            "received_at must be an ISO timestamp."
        ) from None

    if received.tzinfo is None or received.utcoffset() is None:
        raise ValueError(
            "received_at must include a timezone offset."
        )

    received_at = received.astimezone(timezone.utc).isoformat()
    parsed = parse_bank_sms(payload["raw_text"])

    with closing(get_connection()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")

            account = connection.execute(
                "SELECT id FROM business_accounts "
                "WHERE id = ? AND active = 1",
                (payload["bank_account_id"],),
            ).fetchone()

            if account is None:
                raise ValueError(
                    "An active configured bank account is required."
                )

            existing = connection.execute(
                "SELECT id, sender, raw_text, received_at FROM bank_sms "
                "WHERE source = 'SIMULATED' AND bank_account_id = ? "
                "AND source_message_id = ?",
                (
                    payload["bank_account_id"],
                    payload["source_message_id"],
                ),
            ).fetchone()

            if existing is not None:
                old_received = datetime.fromisoformat(
                    existing["received_at"]
                )

                same = (
                    existing["sender"] == payload["sender"]
                    and existing["raw_text"] == payload["raw_text"]
                    and old_received == received
                )

                if not same:
                    raise SMSConflictError(
                        "Message ID already exists with different content. "
                        "No changes were made."
                    )

                sms_id = existing["id"]
                status = "ALREADY_EXISTS"

            else:
                sms_id = uuid4().hex

                connection.execute(
                    "INSERT INTO bank_sms "
                    "(id, bank_account_id, source, source_message_id, "
                    "sender, raw_text, received_at, ingested_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        sms_id,
                        payload["bank_account_id"],
                        "SIMULATED",
                        payload["source_message_id"],
                        payload["sender"],
                        payload["raw_text"],
                        received_at,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

                status = "CREATED"

    return {
        "sms_id": sms_id,
        "ingestion_status": status,
        "source": "SIMULATED",
        "parse_status": parsed["parse_status"],
        "issues": parsed["issues"],
        "notice": "SIMULATED TEST DATA - NOT A REAL BANK MESSAGE",
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python sms_ingestion.py MESSAGE.json")
        sys.exit(1)

    try:
        payload = json.loads(
            Path(sys.argv[1]).read_text(encoding="utf-8-sig")
        )

        result = ingest_simulated_sms(payload)
        print(json.dumps(result, indent=2))

    except (OSError, ValueError) as error:
        print(f"SMS ingestion failed: {error}")
        sys.exit(1)