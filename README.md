# BuildStart Payment Verifier

A local prototype for reviewing bank-transfer slip submissions against a customer's order, configured business account, bank SMS evidence, and previous transaction allocations. It uses a conservative three-way decision: `APPROVED`, `REJECTED`, or `NEEDS VERIFICATION`.

> **Demo safety:** All included orders, slips and SMS are synthetic. An `APPROVED` result means only that the demo evidence passed the prototype's checks. It is not a real bank confirmation and must not be used to release goods or funds.

## Run locally (Windows PowerShell)

1. Install Python 3.11+ and Tesseract OCR. During Tesseract installation, include the English language data. If Tesseract is not on `PATH`, set `TESSERACT_CMD` to its full executable path.
2. Open PowerShell in this folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python setup_demo.py
uvicorn main:app --reload
```

If PowerShell blocks venv activation, run the commands without activation using `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`, then `.\.venv\Scripts\python.exe setup_demo.py` and `.\.venv\Scripts\python.exe -m uvicorn main:app --reload`.

Open `http://127.0.0.1:8000/dashboard`. Use **Upload payment** to submit one of the generated demo slips against its matching order, then open the submission and select **Run demo verification**. The form also displays the expected order amount. Swagger API documentation is at `/docs`.

For OCR on Windows when needed:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

For Windows `curl.exe` SMS ingestion, set a fresh local secret before starting Uvicorn (at least 32 characters):

```powershell
$env:DEMO_SMS_API_KEY = "replace-with-a-long-random-local-demo-key"
$env:DEMO_SMS_BANK_ACCOUNT_ID = "BANK-001"
```

The SMS endpoint is `POST /demo/sms` and requires `X-Demo-SMS-Key`. It accepts only simulated demo messages; do not send sensitive or real bank data to this prototype. A sample request is in `demo_sms_input.json` if supplied by your working copy; otherwise see `sms_ingestion.py` for the exact JSON field names.

## Architecture

```text
Slip upload -> size/type validation -> SHA-256 identity -> SQLite submission
                                      -> OCR once per image/pipeline version
Order + parsed slip + bank SMS -> conservative matching -> transaction ledger
                                                       -> decision + reason
Business review dashboard <- evidence, history, original image, next action
```

- **FastAPI** exposes the upload, OCR, SMS and review endpoints.
- **SQLite** stores customers, orders, business accounts, submissions, OCR cache, SMS, decisions and payment allocations.
- **Pillow + Tesseract** extract text locally. OCR output is treated as untrusted claims, never as proof of receipt.
- **Deterministic parsers and rules** compare amount, currency, receiving account, order reference, transaction reference and date.
- **SMS matching** uses multiple fields and requires a unique candidate. Same-amount-only evidence is not enough.
- **Allocation ledger** has unique constraints to prevent allocating the same transaction, SMS, submission or order twice in the demo environment.
- **Dashboard** separates customer-submitted image/OCR claims from system conclusions and shows decision history, bank-message evidence, reasons and next actions.

## Verification policy

Approval is allowed in the demo only when a uniquely matched simulated SMS and the slip/order checks agree, the configured business account is active, the date is plausible, and the transaction has not already been allocated. A known amount mismatch, reused transaction or conflicting evidence prevents approval. Missing, ambiguous, malformed or non-simulated SMS evidence results in `NEEDS VERIFICATION`; unclear or missing OCR fields also stay out of the approval path. A rejection is reserved for a sufficiently established invalid/reused case; the system does not infer fraud from appearance alone.

The prototype recognizes exact duplicate image bytes using SHA-256 and transaction reuse using account plus transaction reference. A different crop or recompressed image has a different hash, so the app also compares extracted transaction identity and relies on the unique allocation ledger. Perceptual image similarity is not implemented.

## Cost and performance

OCR runs locally, only after upload or an explicit verify action. OCR text is cached by content hash and pipeline version so identical image bytes are processed once. Cheap deterministic parsing handles routine checks. The prototype makes no paid AI calls and does not send images to a third party. Escalation to a human avoids spending on an expensive model when evidence is weak. For 100,000+ submissions/month, move from SQLite to a managed relational database, put OCR behind a worker queue, store images in private object storage, add tenant isolation, rate limits, retention controls, monitoring, and per-bank SMS adapters; use a model only on uncertain cases and measure its false-approval rate before deployment.

## Tests and demo

Run the included deterministic checks with:

```powershell
python check_parser.py
python check_fields.py
python check_dates.py
python check_sms_parser.py
python check_reference_roles.py
python check_ledger.py
python check_ocr_cache.py
python check_review_messages.py
python check_verification_scenarios.py
python check_verification_transaction.py
```

These cover parsing, fields/dates, OCR caching, reference roles, duplicate/reused allocations, uncertain SMS matches, conflicting/missing evidence, and transaction consistency. The scenario checks stub OCR text to make decision-rule tests deterministic. `DEMO_GUIDE.md` gives a short live-demo sequence.

## Known limits

- A bank SMS is not cryptographically authenticated; the prototype's SMS API key is only a demo gate, not a bank integration.
- OCR and text formats vary by bank, language, image quality and device; OCR can misread digits.
- Exact image hashes do not recognize all visually similar edits; transaction-level checks mitigate reuse only when identity fields are extracted.
- No user login, roles, tenant isolation, production secrets management, TLS deployment, retention/deletion policy, malware scanning, audit export, or real bank connection is included.
- The demo database and data are single-business and single-machine. Never put real customer data or credentials into it.

## Debugging notes

1. **OCR cache integrity:** Caching only by a filename would allow file replacement under the same name. The implementation stores a SHA-256 of uploaded bytes and verifies it again before image serving/OCR; the cache key also includes the pipeline version.
2. **Repeated or altered SMS IDs:** A retried message should be idempotent, while reusing an ID with different content must not silently overwrite evidence. Ingestion now returns `ALREADY_EXISTS` only for identical content and rejects conflicting content.
3. **Amount-only false matches:** Two customers can pay the same amount near the same time. Matching therefore combines amount, receiving account, order reference, transaction reference/date where available, and accepts only a unique candidate; ambiguous evidence goes to human review.

## Important files

- `main.py`: application and route registration.
- `upload_routes.py`: safe image upload and OCR endpoint.
- `verification_service.py`, `sms_matching.py`, `demo_decisions.py`: evidence comparison, candidate matching and demo decisions.
- `payment_ledger.py`: uniqueness constraints for payment allocation.
- `ocr_service.py`, `payment_parser.py`, `sms_parser.py`: local extraction/parsing.
- `dashboard_routes.py`, `templates/`: business review workflow.
- `setup_demo.py`: idempotent synthetic demo setup.
- `ENGINEERING_REPORT.md`: design, fraud, cost, limitations and scale plan.
