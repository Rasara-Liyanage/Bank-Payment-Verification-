# Engineering report: BuildStart Payment Verifier

## 1. Approach and architecture

The prototype receives a customer's slip image and associated order. FastAPI validates uploaded bytes as a readable JPEG/PNG, enforces a 5 MiB limit and pixel ceiling, computes a SHA-256 digest, and records an immutable submission identity in SQLite. Pillow normalizes image orientation; local Tesseract OCR extracts text. OCR results are cached using both the image digest and an OCR pipeline version. Deterministic parsers convert text into candidate amount, currency, receiving account, transaction reference, order reference and payment date. The dashboard shows the uploaded image and extracted claims alongside the independent order and bank-message evidence.

The implementation intentionally separates three stages: extraction (what the slip appears to say), evidence matching (what order and bank SMS support), and a decision with a reason and next action. A visible `DEMO` label is stored with decision results; this prototype does not integrate with a real bank.

## 2. How the system verifies order ownership

The order supplies the expected customer, amount, currency, payment reference, creation time and configured receiving account. The slip's OCR fields are compared to those expected values. Candidate bank SMS messages are parsed and matched using several available fields, including amount, account, order reference, transaction reference and date. A match on amount alone is inadequate because unrelated customers can send equal amounts. The matcher therefore requires a unique candidate and records unknown or conflicting fields. A missing SMS, multiple candidates, parser failure, non-simulated source, or incomplete fields produces `NEEDS VERIFICATION`.

Only a unique simulated bank message whose key fields agree with the order and slip can proceed to demo approval. Before the decision is committed, the code rechecks the submission snapshot and writes the allocation under a database transaction. Database uniqueness rules prevent reuse of one transaction reference, SMS, submission or order allocation. The submission snapshot guards against the underlying image/order record changing during OCR.

## 3. Duplicate, reused, old and suspicious payment handling

The upload stores SHA-256 for exact-byte duplicate detection and verifies the digest before later display/OCR. The OCR cache is keyed by that digest and parser pipeline version. Exact duplicates do not cause repeated OCR work. Different image encodings or crops have different hashes; the extracted transaction reference and unique ledger constraints provide a second identity layer. If transaction text cannot be read reliably, the app falls back to manual verification.

Old payments are screened using order creation, submission time and claimed payment date. A payment date before order creation or after submission is flagged. Wrong amounts/accounts, mismatched references, repeated transaction IDs, ambiguous SMS candidates and conflicts between SMS and OCR block automatic approval. A known reused allocation can be rejected; uncertain evidence is not called fraud and is routed for review. Pixel-level tamper detection and perceptual image similarity are not implemented, so visual plausibility is never treated as proof.

## 4. Bank SMS and customer experience

An authenticated demo HTTP endpoint accepts structured simulated SMS data and validates the configured business account, message identity, timestamps and input size. Retries with identical content are idempotent; an existing message ID with different content is rejected. SMS arriving after a slip can be ingested and the case re-run. Parsers isolate fields from raw message text, and the dashboard displays the raw message plus its source and matching status. The demo key protects only the prototype endpoint; it does not establish bank authenticity.

The review page prioritizes customer, order, expected amount, submitted image, evidence result, decision, reason and next action. Internal risk flags remain in the business review context. Customer-facing review messages ask for a clearer image, corrected amount, or time to verify, and avoid revealing internal fraud rules.

## 5. Cost and performance

All OCR is local and no paid AI API is called. The image is OCR-processed only when requested; repeat processing of identical bytes and pipeline version uses the cache. Simple parsing and rule checks are cheap and predictable. Human review is used for ambiguous evidence, rather than paying to run a large model on every image. For production, an OCR or vision model could be evaluated only for low-confidence OCR cases, with cost and false-approval rates measured against human-labeled data before enabling it.

## 6. Testing and debugging

The repository contains focused executable checks for amount/date/account parsing, SMS format handling, reference roles, OCR cache integrity, ledger constraints, review messages, end-to-end decision scenarios, and transaction consistency. Decision scenarios substitute fixed OCR text so rule outcomes are repeatable. Cases include valid simulated evidence, wrong account and dates, amount mismatches, duplicate/reused payments, multiple SMS candidates, conflicting evidence, and missing or non-simulated evidence. The design target is asymmetric: a false approval has greater cost than a manual review, so insufficient or ambiguous evidence must not approve.

Three engineering issues shaped the implementation:

1. **Cached OCR could become stale or detached from the uploaded bytes.** A filename is not a stable content identity. The implementation keys cached OCR by SHA-256 plus pipeline version and re-hashes stored bytes before reuse/display. The cache checks cover hash changes and repeat processing.
2. **SMS retries and ID collisions have different meanings.** A normal retry should be harmless, but different text under the same source message ID indicates conflicting evidence. Ingestion now treats exact retries as idempotent and rejects content conflicts rather than overwriting.
3. **Matching by amount can attach one customer's payment to another order.** Equal amounts and nearby arrival times are common. Matching now checks multiple fields, requires one candidate, and sends ambiguous cases to review. A uniqueness-constrained ledger prevents a previously allocated transaction from being approved again.

These controls reduce avoidable false approvals but do not establish authenticity of synthetic or manually supplied bank messages. The check scripts should be run in the supplied environment before presenting results; this report does not claim that tests were executed in the recipient's Windows environment.

## 7. Limitations and production plan

The prototype supports one demo business, a local SQLite file and English synthetic slips/SMS. It has no live bank integration, bank-signature validation, tenant isolation, user authentication/roles, deployment TLS, managed key storage, privacy retention schedule, tamper-evident audit export or production-grade observability. OCR depends on installed Tesseract and may misread low-quality images, dates and digits. Exact hashes do not detect every modified image. SMS sender names can be spoofed outside a trusted bank integration.

At 100,000+ submissions each month, I would add a multi-tenant relational database with tenant-scoped keys, private object storage and signed access, a queued worker service for OCR, bounded retries and dead-letter handling, per-bank parsers with versioned fixtures, and monitoring for latency, cost, unknown-field rates, review workload and false-approval incidents. I would require human-reviewed labels and shadow evaluation before introducing any model; use a model only for difficult OCR cases, retain deterministic bank/order checks as gates, and roll out bank adapters gradually. Fail-closed behavior and a documented manual review queue remain necessary when external services are unavailable.
