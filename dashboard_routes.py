import json
from contextlib import closing
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from database import BASE_DIR, get_connection

import hashlib

import sqlite3

from demo_decisions import run_demo_decision


router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

SRI_LANKA_TIME = timezone(timedelta(hours=5, minutes=30))

BADGE_CLASSES = {
    "APPROVED": "approved",
    "REJECTED": "rejected",
    "NEEDS VERIFICATION": "pending",
    "NOT REVIEWED": "unreviewed",
}


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    with closing(get_connection()) as connection:
        rows = connection.execute("""
            SELECT
                submissions.id,
                submissions.submitted_at,
                orders.id AS order_id,
                orders.amount_minor,
                orders.currency,
                customers.name AS customer_name,
                decisions.result_json
            FROM submissions
            JOIN orders ON submissions.order_id = orders.id
            JOIN customers ON orders.customer_id = customers.id
            LEFT JOIN verification_decisions AS decisions
                ON decisions.id = (
                    SELECT latest.id
                    FROM verification_decisions AS latest
                    WHERE latest.submission_id = submissions.id
                        AND latest.environment = 'DEMO'
                    ORDER BY latest.created_at DESC, latest.rowid DESC
                    LIMIT 1
                )
            ORDER BY submissions.submitted_at DESC, submissions.id DESC
        """).fetchall()

    submissions = []

    counts = {
        "APPROVED": 0,
        "REJECTED": 0,
        "NEEDS VERIFICATION": 0,
        "NOT REVIEWED": 0,
    }

    for row in rows:
        item = dict(row)
        saved_result = item.pop("result_json")

        if saved_result:
            decision = json.loads(saved_result)
            item["decision"] = decision["decision"]
            item["reason"] = decision["reason"]
        else:
            item["decision"] = "NOT REVIEWED"
            item["reason"] = "No demo decision has been recorded yet."

        item["badge_class"] = BADGE_CLASSES.get(
            item["decision"], "unreviewed"
        )

        amount = item["amount_minor"]
        item["amount_display"] = (
            f"{item['currency']} {amount // 100:,}.{amount % 100:02d}"
        )

        item["submitted_display"] = (
            datetime.fromisoformat(item["submitted_at"])
            .astimezone(SRI_LANKA_TIME)
            .strftime("%Y-%m-%d %H:%M")
        )

        counts[item["decision"]] += 1
        submissions.append(item)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "submissions": submissions,
            "counts": counts,
            "total": len(submissions),
        },
    )

@router.get(
    "/dashboard/submissions/{submission_id}",
    response_class=HTMLResponse,
)
def submission_detail(request: Request, submission_id: str):
    with closing(get_connection()) as connection:
        submission_row = connection.execute(
            """
            SELECT
                submissions.id,
                submissions.submitted_at,
                orders.id AS order_id,
                orders.amount_minor,
                orders.currency,
                orders.payment_reference,
                customers.name AS customer_name
            FROM submissions
            JOIN orders
                ON orders.id = submissions.order_id
            JOIN customers
                ON customers.id = orders.customer_id
            WHERE submissions.id = ?
            """,
            (submission_id,),
        ).fetchone()

        if submission_row is None:
            raise HTTPException(
                status_code=404,
                detail="Submission not found",
            )

        decision_rows = connection.execute(
            """
            SELECT result_json, evidence_json, created_at
            FROM verification_decisions
            WHERE submission_id = ?
              AND environment = 'DEMO'
            ORDER BY created_at DESC, rowid DESC
            """,
            (submission_id,),
        ).fetchall()

    submission = dict(submission_row)

    amount = submission["amount_minor"]
    submission["amount_display"] = (
        f"{submission['currency']} "
        f"{amount // 100:,}.{amount % 100:02d}"
    )

    submission["submitted_display"] = (
        datetime.fromisoformat(submission["submitted_at"])
        .astimezone(SRI_LANKA_TIME)
        .strftime("%Y-%m-%d %H:%M:%S")
    )

    history = []

    for row in decision_rows:
        result = json.loads(row["result_json"])

        history.append(
            {
                "result": result,
                "created_display": (
                    datetime.fromisoformat(row["created_at"])
                    .astimezone(SRI_LANKA_TIME)
                    .strftime("%Y-%m-%d %H:%M:%S")
                ),
            }
        )

    latest = history[0]["result"] if history else None

    evidence = (
        json.loads(decision_rows[0]["evidence_json"])
        if decision_rows
        else {}
    )
    display_evidence = load_display_evidence(submission_id, evidence)
    return templates.TemplateResponse(
        request=request,
        name="submission_detail.html",
        context={
            "submission": submission,
            "latest": latest,
            "history": history,
            "evidence": evidence,
            "ocr_record": display_evidence["ocr_record"],
            "sms_messages": display_evidence["sms_messages"],
            "missing_sms_ids": display_evidence["missing_sms_ids"],
        },
    )

@router.get(
    "/dashboard/submissions/{submission_id}/image",
    response_class=Response,
)
def submission_image(submission_id: str):
    with closing(get_connection()) as connection:
        submission = connection.execute(
            """
            SELECT image_filename, image_sha256
            FROM submissions
            WHERE id = ?
            """,
            (submission_id,),
        ).fetchone()

    if submission is None:
        raise HTTPException(
            status_code=404,
            detail="Submission not found",
        )

    uploads_dir = (BASE_DIR / "uploads").resolve()
    image_path = (
        uploads_dir / submission["image_filename"]
    ).resolve()

    if not image_path.is_relative_to(uploads_dir):
        raise HTTPException(
            status_code=409,
            detail="Invalid stored image location",
        )

    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }

    media_type = media_types.get(image_path.suffix.lower())

    if media_type is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported stored image format",
        )

    try:
        image_bytes = image_path.read_bytes()
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Stored image not found",
        ) from None
    except OSError:
        raise HTTPException(
            status_code=503,
            detail="Stored image could not be read",
        ) from None

    actual_hash = hashlib.sha256(image_bytes).hexdigest()

    if actual_hash != submission["image_sha256"]:
        raise HTTPException(
            status_code=409,
            detail="Stored image does not match the uploaded file",
        )

    return Response(
        content=image_bytes,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )

def load_display_evidence(submission_id: str, evidence: dict):
    candidate_ids = list(
        dict.fromkeys(evidence.get("candidate_sms_ids", []))
    )

    sms_messages = []
    missing_sms_ids = []

    with closing(get_connection()) as connection:
        ocr_row = connection.execute(
            """
            SELECT
                ocr_results.extracted_text,
                ocr_results.pipeline_version,
                ocr_results.processed_at
            FROM submissions
            JOIN ocr_results
                ON ocr_results.image_sha256 = submissions.image_sha256
            WHERE submissions.id = ?
            ORDER BY
                ocr_results.processed_at DESC,
                ocr_results.pipeline_version DESC
            LIMIT 1
            """,
            (submission_id,),
        ).fetchone()

        for sms_id in candidate_ids:
            sms_row = connection.execute(
                """
                SELECT id, source, sender, raw_text
                FROM bank_sms
                WHERE id = ?
                """,
                (sms_id,),
            ).fetchone()

            if sms_row is None:
                missing_sms_ids.append(sms_id)
            else:
                sms_messages.append(dict(sms_row))

    ocr_record = dict(ocr_row) if ocr_row is not None else None

    return {
        "ocr_record": ocr_record,
        "sms_messages": sms_messages,
        "missing_sms_ids": missing_sms_ids,
    }

@router.post(
    "/dashboard/submissions/{submission_id}/verify-demo",
    response_class=RedirectResponse,
)
def verify_demo_from_dashboard(submission_id: str):
    with closing(get_connection()) as connection:
        submission = connection.execute(
            "SELECT id FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()

    if submission is None:
        raise HTTPException(
            status_code=404,
            detail="Submission not found",
        )

    try:
        run_demo_decision(submission_id)

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=(
                "The decision could not be saved because of a "
                "database constraint. Return to the submission "
                "and review its latest decision before retrying."
            ),
        ) from None

    except ValueError:
        raise HTTPException(
            status_code=409,
            detail=(
                "The evidence could not be processed. "
                "Check the stored submission and image."
            ),
        ) from None

    except (OSError, RuntimeError):
        raise HTTPException(
            status_code=503,
            detail=(
                "Verification is temporarily unavailable. "
                "Check that the image is accessible and "
                "Tesseract is installed."
            ),
        ) from None

    return RedirectResponse(
        url=f"/dashboard/submissions/{submission_id}",
        status_code=303,
    )

@router.get("/dashboard/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT
                orders.id,
                orders.amount_minor,
                orders.currency,
                customers.name AS customer_name
            FROM orders
            JOIN customers
                ON customers.id = orders.customer_id
            ORDER BY orders.id
            """
        ).fetchall()

    orders = []

    for row in rows:
        order = dict(row)
        amount = order["amount_minor"]

        order["amount_display"] = (
            f"{order['currency']} "
            f"{amount // 100:,}.{amount % 100:02d}"
        )

        orders.append(order)

    return templates.TemplateResponse(
        request=request,
        name="upload.html",
        context={"orders": orders},
    )