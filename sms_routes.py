import logging
import os
import secrets
import sqlite3

from fastapi import APIRouter, HTTPException, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from sms_ingestion import ingest_simulated_sms, SMSConflictError


router = APIRouter()
logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(
    name="X-Demo-SMS-Key",
    auto_error=False,
)


def require_demo_sms_key(
    supplied_key: str | None = Security(api_key_header),
):
    expected_key = os.getenv("DEMO_SMS_API_KEY", "")

    if len(expected_key) < 32:
        raise HTTPException(
            status_code=503,
            detail="Demo SMS API key is not configured.",
        )

    if supplied_key is None or not secrets.compare_digest(
        supplied_key.encode("utf-8"),
        expected_key.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid demo SMS API key.",
        )


@router.post(
    "/demo/sms",
    tags=["Demo SMS"],
    dependencies=[Security(require_demo_sms_key)],
)
def receive_demo_sms(payload: dict):
    allowed_account = os.getenv("DEMO_SMS_BANK_ACCOUNT_ID", "")

    if not allowed_account:
        raise HTTPException(
            status_code=503,
            detail="Demo SMS bank account is not configured.",
        )

    if payload.get("bank_account_id") != allowed_account:
        raise HTTPException(
            status_code=403,
            detail="This endpoint is not configured for that bank account.",
        )

    try:
        result = ingest_simulated_sms(payload)

    except SMSConflictError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from None

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from None

    except sqlite3.Error:
        logger.exception("Demo SMS database operation failed.")

        raise HTTPException(
            status_code=503,
            detail="SMS storage is temporarily unavailable.",
        ) from None

    status_code = (
        201 if result["ingestion_status"] == "CREATED" else 200
    )

    return JSONResponse(
        status_code=status_code,
        content=result,
    )