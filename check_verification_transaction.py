import sqlite3
from contextlib import closing
from unittest.mock import patch

import database
import sms_matching
from check_verification_scenarios import run_case


original_parser = sms_matching.parse_bank_sms
write_blocked = []


def parse_with_competing_write(text):
    if not write_blocked:
        with closing(
            sqlite3.connect(database.DB_PATH, timeout=0)
        ) as other:
            try:
                with other:
                    other.execute(
                        "UPDATE bank_sms SET raw_text = ?",
                        (text.replace("5000.00", "4000.00"),),
                    )

            except sqlite3.OperationalError as error:
                if "locked" not in str(error).lower():
                    raise

                write_blocked.append(True)

            else:
                raise AssertionError(
                    "SMS changed while matching was in progress."
                )

    return original_parser(text)


if __name__ == "__main__":
    with patch.object(
        sms_matching,
        "parse_bank_sms",
        side_effect=parse_with_competing_write,
    ):
        run_case(
            "Valid decision is saved with its allocation",
            "APPROVED",
        )

    assert write_blocked == [True]

    print("PASS: Concurrent SMS update is blocked during verification")
    print("Your payments.db was not changed.")