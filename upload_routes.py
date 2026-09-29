import hashlib
import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from database import BASE_DIR, get_connection

from ocr_service import process_submission_ocr

from payment_parser import parse_payment_fields


router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = BASE_DIR / "uploads"
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000

ALLOWED_FORMATS = {
    "JPEG": ".jpg",
    "PNG": ".png",
}


@router.post("/orders/{order_id}/submissions", status_code=201)
def upload_slip(order_id: str, file: UploadFile = File(...)):
    # Check that the order exists.
    with closing(get_connection()) as connection:
        order = connection.execute(
            "SELECT id FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()

    if order is None:
        raise HTTPException(404, "Order not found.")

    # Read only up to the allowed size plus one byte.
    content = file.file.read(MAX_FILE_BYTES + 1)

    if not content:
        raise HTTPException(400, "The uploaded file is empty.")

    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "The image must be 5 MiB or smaller.")

    # Check the actual image content, not its filename.
    try:
        with Image.open(BytesIO(content)) as image:
            image_format = image.format

            if image_format not in ALLOWED_FORMATS:
                raise HTTPException(415, "Only JPEG and PNG are supported.")

            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(413, "The image exceeds 20 megapixels.")

            if getattr(image, "n_frames", 1) != 1:
                raise HTTPException(415, "Animated images are not supported.")

            image.verify()

        # Reopen and decode pixels to detect damaged image data.
        with Image.open(BytesIO(content)) as image:
            image.load()

    except Image.DecompressionBombError:
        raise HTTPException(413, "The image dimensions are too large.")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise HTTPException(400, "The file is not a readable JPEG or PNG.")

    submission_id = uuid4().hex
    filename = submission_id + ALLOWED_FORMATS[image_format]
    image_path = UPLOAD_DIR / filename

    image_sha256 = hashlib.sha256(content).hexdigest()
    submitted_at = datetime.now(timezone.utc).isoformat()

    status = "NEEDS VERIFICATION"
    reason = "Image received. Payment verification has not run yet."

    # Save the original image and its database record.
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(content)

        with closing(get_connection()) as connection:
            with connection:
                connection.execute("""
                    INSERT INTO submissions (
                        id,
                        order_id,
                        image_filename,
                        image_sha256,
                        submitted_at,
                        status,
                        reason
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    submission_id,
                    order_id,
                    filename,
                    image_sha256,
                    submitted_at,
                    status,
                    reason,
                ))

    except (OSError, sqlite3.Error):
        logger.exception("Failed to save submission")

        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Failed to remove incomplete upload")

        raise HTTPException(500, "Could not save the upload. Please retry.")

    return {
        "submission_id": submission_id,
        "order_id": order_id,
        "status": status,
        "reason": reason,
        "next_action": "Await payment verification.",
    }

@router.post("/submissions/{submission_id}/ocr")
def run_submission_ocr(submission_id: str):
    with closing(get_connection()) as connection:
        submission = connection.execute(
            "SELECT id FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()

    if submission is None:
        raise HTTPException(404, "Submission not found.")

    try:
        result = process_submission_ocr(submission_id)

    except ValueError:
        logger.exception("OCR input validation failed")
        raise HTTPException(
            409,
            "Stored image could not be verified. Manual review is required.",
        )

    except (OSError, RuntimeError):
        logger.exception("OCR processing failed")
        raise HTTPException(
            503,
            "OCR is currently unavailable. Please retry or request manual review.",
        )

    extracted_fields = parse_payment_fields(result["text"])

    return {
        **result,
        "ocr_status": (
            "TEXT_EXTRACTED" if result["text"] else "NO_TEXT_DETECTED"
        ),
        "extracted_fields": extracted_fields,
        "message": (
            "Extracted fields are unverified claims from the image. "
            "They do not prove that a payment occurred."
        ),
    }