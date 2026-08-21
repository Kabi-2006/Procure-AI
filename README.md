# ProcureAI

ProcureAI is a runnable hackathon MVP for AI-assisted procurement. It accepts vendor quotation PDFs, extracts commercial fields, compares suppliers with a transparent weighted model, supports manager approval, and generates a purchase-order PDF.

## Included features

- Responsive procurement dashboard
- Vendor directory and vendor creation
- RFQ creation and tracking
- PDF/TXT quotation upload
- Local document-field extraction with no paid API key
- Three sample quotation PDFs
- Deterministic vendor scoring and ranking
- Explainable recommendation
- Manager approval workflow
- Downloadable purchase-order PDF
- SQLite persistence
- Swagger API documentation
- Automated backend tests

## Software to install

1. **Python 3.11 or 3.12** — select “Add Python to PATH” during installation.
2. **Node.js 22 LTS or newer** — includes npm.
3. A modern browser such as Chrome, Edge or Firefox.
4. VS Code is optional but recommended.

No MySQL, XAMPP, Docker, paid AI API, or separate database installation is required. SQLite is created automatically.

## Quick setup on Windows

1. Extract the ZIP.
2. Open the extracted `procure-ai` folder.
3. Double-click `setup_windows.bat` once.
4. Wait until it displays `Setup complete`.
5. Double-click `run_windows.bat`.
6. Keep both terminal windows open.
7. Open `http://localhost:5173`.

The setup script creates a virtual environment, installs Python and Node dependencies, and generates the sample quotation PDFs.

## Manual setup

### Backend

```bash
cd backend
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install and start:

```bash
pip install -r requirements.txt
cd ..
python scripts/generate_samples.py
cd backend
uvicorn app.main:app --reload --port 8000
```

Backend API: `http://127.0.0.1:8000`  
Swagger documentation: `http://127.0.0.1:8000/docs`

### Frontend

Open a second terminal in the main project folder:

```bash
npm install
npm run dev
```

Frontend: `http://localhost:5173`

## Demo sequence

1. Open **Overview**.
2. Click **Run demo analysis**.
3. The app processes three included quotation PDFs.
4. Review the ranked suppliers under **Smart comparison**.
5. Click **Approve winner**.
6. Click **Generate PO**.
7. Open the downloaded purchase-order PDF.

To test a custom quotation, use the same labeled format as the included samples:

```text
QUOTATION NUMBER: QT-1001
CURRENCY: INR
ITEM: Industrial sensor | QTY: 20 | UNIT: Nos | UNIT_PRICE: 4500
SUBTOTAL: 90000
DISCOUNT: 1000
TAX: 16020
SHIPPING: 500
GRAND TOTAL: 105520
DELIVERY DAYS: 7
WARRANTY MONTHS: 24
PAYMENT TERMS: Net 30 days
```

The offline extractor is intentionally deterministic for a reliable hackathon demo. A production version can replace `parse_quotation()` with a multimodal LLM or cloud document-intelligence service while retaining the same validated JSON structure.

## Tests

Backend:

```bash
cd backend
.venv\Scripts\activate
pytest -q
```

Frontend production build:

```bash
npm run build
```

## Project structure

```text
procure-ai/
├── app/                    React/Vinext frontend
├── backend/
│   ├── app/main.py         FastAPI, SQLite and procurement logic
│   ├── tests/              API workflow tests
│   ├── uploads/            Runtime quotation uploads
│   └── generated/          Generated purchase orders
├── sample_data/quotations/ Included demonstration PDFs
├── scripts/                Sample document generator
├── docs/                   Architecture and demo notes
├── setup_windows.bat       One-time Windows setup
└── run_windows.bat         Windows launcher
```

## Default scoring weights

| Criterion | Weight |
|---|---:|
| Price | 40% |
| Delivery | 20% |
| Vendor quality | 15% |
| Warranty | 10% |
| Payment terms | 10% |
| Compliance | 5% |

AI/document processing extracts the values. Application code performs arithmetic and ranking so that results remain consistent and auditable.

## Reset the application

Stop both servers and delete `backend/procureai.db`. The database and initial demonstration records will be recreated the next time the backend starts.

## Security limitations

This is a hackathon MVP. It uses synthetic data and does not include production authentication, encryption-at-rest, malware scanning, organization isolation, or external ERP integration. Do not upload confidential commercial documents without adding the required security controls.
