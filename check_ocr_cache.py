import hashlib
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import ocr_service


def expect_blocked(label, exception_type, action):
    try:
        action()
    except exception_type:
        print(f"PASS: {label}")
    else:
        raise AssertionError(f"FAIL: {label}")


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        uploads = root / "uploads"
        uploads.mkdir()

        image_path = uploads / "test.png"
        original = b"Test bytes for the cached path only"
        image_path.write_bytes(original)
        image_hash = hashlib.sha256(original).hexdigest()

        def test_connection():
            connection = sqlite3.connect(root / "test.db")
            connection.row_factory = sqlite3.Row
            return connection

        with closing(test_connection()) as connection:
            with connection:
                connection.execute(
                    "CREATE TABLE submissions ("
                    "id TEXT PRIMARY KEY, image_filename TEXT, image_sha256 TEXT)"
                )

                connection.execute(
                    "CREATE TABLE ocr_results ("
                    "image_sha256 TEXT, pipeline_version TEXT, "
                    "extracted_text TEXT, processed_at TEXT, "
                    "PRIMARY KEY(image_sha256, pipeline_version))"
                )

                connection.execute(
                    "INSERT INTO submissions VALUES (?, ?, ?)",
                    ("TEST-SUB", "test.png", image_hash),
                )

                connection.execute(
                    "INSERT INTO ocr_results VALUES (?, ?, ?, ?)",
                    (
                        image_hash,
                        ocr_service.PIPELINE_VERSION,
                        "Cached test text",
                        "2026-09-28T00:00:00+00:00",
                    ),
                )

        with (
            patch.object(ocr_service, "BASE_DIR", root),
            patch.object(
                ocr_service,
                "get_connection",
                test_connection,
            ),
            patch.object(
                ocr_service.pytesseract,
                "image_to_string",
            ) as engine,
        ):
            def run():
                return ocr_service.process_submission_ocr("TEST-SUB")

            result = run()

            assert result["cached"] is True
            assert result["text"] == "Cached test text"
            engine.assert_not_called()

            print("PASS: Unchanged image reuses cache without running OCR")

            image_path.write_bytes(b"Changed bytes")

            expect_blocked(
                "Changed image is blocked",
                ValueError,
                run,
            )

            image_path.unlink()

            expect_blocked(
                "Missing image is blocked",
                FileNotFoundError,
                run,
            )

            (root / "outside.png").write_bytes(original)

            with closing(test_connection()) as connection:
                with connection:
                    connection.execute(
                        "UPDATE submissions "
                        "SET image_filename = ? WHERE id = ?",
                        ("../outside.png", "TEST-SUB"),
                    )

            expect_blocked(
                "Path outside uploads is blocked",
                ValueError,
                run,
            )

            expect_blocked(
                "Unknown submission is blocked",
                ValueError,
                lambda: ocr_service.process_submission_ocr("UNKNOWN"),
            )

            engine.assert_not_called()

    print("All 5 OCR cache checks passed.")
    print("Your payments.db and uploaded images were not changed.")


if __name__ == "__main__":
    main()