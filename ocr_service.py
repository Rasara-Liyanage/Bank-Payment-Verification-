import hashlib
import os
import shutil
import sys
from contextlib import closing
from datetime import datetime, timezone

import pytesseract
from PIL import Image, ImageOps

from database import BASE_DIR, get_connection
from io import BytesIO


pytesseract.pytesseract.tesseract_cmd = (
    os.getenv("TESSERACT_CMD")
    or shutil.which("tesseract")
    or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

PIPELINE_VERSION = "eng-psm6-exif-v1"


def process_submission_ocr(submission_id):
    with closing(get_connection()) as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS ocr_results (
                    image_sha256 TEXT NOT NULL,
                    pipeline_version TEXT NOT NULL,
                    extracted_text TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    PRIMARY KEY (image_sha256, pipeline_version)
                )
            """)

        submission = connection.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()

        if submission is None:
            raise ValueError("Submission not found.")

        cached = connection.execute("""
            SELECT extracted_text
            FROM ocr_results
            WHERE image_sha256 = ? AND pipeline_version = ?
        """, (
            submission["image_sha256"],
            PIPELINE_VERSION,
        )).fetchone()

        uploads_dir = (BASE_DIR / "uploads").resolve()
    image_path = (uploads_dir / submission["image_filename"]).resolve()

    if not image_path.is_relative_to(uploads_dir):
        raise ValueError("Stored image is outside the uploads directory.")

    image_bytes = image_path.read_bytes()
    actual_hash = hashlib.sha256(image_bytes).hexdigest()

    if actual_hash != submission["image_sha256"]:
        raise ValueError("Stored image does not match its recorded hash.")

    if cached is not None:
        return {
            "submission_id": submission_id,
            "cached": True,
            "text": cached["extracted_text"],
        }

    with Image.open(BytesIO(image_bytes)) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")

        try:
            text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 6",
                timeout=15,
            ).strip()
        finally:
            image.close()

    processed_at = datetime.now(timezone.utc).isoformat()

    with closing(get_connection()) as connection:
        with connection:
            connection.execute("""
                INSERT INTO ocr_results (
                    image_sha256,
                    pipeline_version,
                    extracted_text,
                    processed_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(image_sha256, pipeline_version) DO NOTHING
            """, (
                submission["image_sha256"],
                PIPELINE_VERSION,
                text,
                processed_at,
            ))

    return {
        "submission_id": submission_id,
        "cached": False,
        "text": text,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python ocr_service.py SUBMISSION_ID")
        sys.exit(1)

    try:
        result = process_submission_ocr(sys.argv[1])
        print(f"Cached: {result['cached']}")
        print("OCR RESULT:")
        print(result["text"] or "[No text detected]")
    except (OSError, ValueError, RuntimeError) as error:
        print(f"OCR could not complete: {error}")
        sys.exit(1)