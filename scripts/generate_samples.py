from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "sample_data" / "quotations"
OUTPUT.mkdir(parents=True, exist_ok=True)

QUOTES = {
    "apex_quote.pdf": [
        "APEX INDUSTRIAL SYSTEMS", "QUOTATION NUMBER: APEX-Q-1042", "CURRENCY: INR",
        "ITEM: Industrial sensor package | QTY: 20 | UNIT: Nos | UNIT_PRICE: 4750",
        "SUBTOTAL: 95000", "DISCOUNT: 2000", "TAX: 16740", "SHIPPING: 1000",
        "GRAND TOTAL: 110740", "DELIVERY DAYS: 10", "WARRANTY MONTHS: 18",
        "PAYMENT TERMS: 50% advance, balance on delivery"
    ],
    "novatech_quote.pdf": [
        "NOVATECH COMPONENTS", "QUOTATION NUMBER: NOVA-Q-778", "CURRENCY: INR",
        "ITEM: Industrial sensor package | QTY: 20 | UNIT: Nos | UNIT_PRICE: 4900",
        "SUBTOTAL: 98000", "DISCOUNT: 1000", "TAX: 17460", "SHIPPING: 0",
        "GRAND TOTAL: 114460", "DELIVERY DAYS: 5", "WARRANTY MONTHS: 36",
        "PAYMENT TERMS: Net 30 days"
    ],
    "orion_quote.pdf": [
        "ORION SUPPLY WORKS", "QUOTATION NUMBER: ORION-2026-51", "CURRENCY: INR",
        "ITEM: Industrial sensor package | QTY: 20 | UNIT: Nos | UNIT_PRICE: 4500",
        "SUBTOTAL: 90000", "DISCOUNT: 3000", "TAX: 15660", "SHIPPING: 1800",
        "GRAND TOTAL: 104460", "DELIVERY DAYS: 18", "WARRANTY MONTHS: 12",
        "PAYMENT TERMS: Full payment before dispatch"
    ],
}

styles = getSampleStyleSheet()
for filename, lines in QUOTES.items():
    document = SimpleDocTemplate(str(OUTPUT / filename), pagesize=A4)
    story = [Paragraph(lines[0], styles["Title"]), Spacer(1, 18)]
    story.extend(Paragraph(line, styles["BodyText"]) for line in lines[1:])
    document.build(story)
print(f"Generated {len(QUOTES)} quotation PDFs in {OUTPUT}")
