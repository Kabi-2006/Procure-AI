# ProcureAI Architecture

## Request flow

The React frontend calls a versioned FastAPI REST API. FastAPI stores structured records in SQLite, uploaded documents on local disk, and generated purchase orders in a separate output directory.

Quotation processing follows this sequence:

1. Validate the extension and 10 MB size limit.
2. Save the source document.
3. Extract PDF text using PyMuPDF.
4. Convert labeled commercial terms into validated fields.
5. Recalculate totals and store the extraction result.
6. Score vendors in ordinary Python code.
7. Require manager approval.
8. Generate the PO with ReportLab.

## Production upgrades

- SQLite → PostgreSQL
- Local files → private S3-compatible object storage
- Synchronous extraction → Redis/Celery worker queue
- Demo users → OAuth/OpenID Connect with role-based access
- Local parser → provider-independent multimodal AI gateway
- Local server → Docker containers behind HTTPS
- Basic logs → centralized monitoring and alerting

## Main security boundary

The AI/document service is not authorized to approve suppliers or calculate final financial values. It only extracts and explains. Deterministic application services calculate scores and an authorized human approves the selection.
