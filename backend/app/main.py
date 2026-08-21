from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import fitz
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "backend" / "procureai.db"
UPLOAD_DIR = ROOT / "backend" / "uploads"
GENERATED_DIR = ROOT / "backend" / "generated"
SAMPLE_DIR = ROOT / "sample_data" / "quotations"
for directory in (UPLOAD_DIR, GENERATED_DIR, SAMPLE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ProcureAI API", version="1.0.0", description="RFQ-to-purchase-order procurement intelligence API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    connection = db()
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS vendors(id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT NOT NULL UNIQUE, category TEXT NOT NULL, rating REAL NOT NULL DEFAULT 4, on_time_delivery_rate REAL NOT NULL DEFAULT 85, status TEXT NOT NULL DEFAULT 'ACTIVE');
    CREATE TABLE IF NOT EXISTS rfqs(id INTEGER PRIMARY KEY AUTOINCREMENT, rfq_number TEXT NOT NULL UNIQUE, title TEXT NOT NULL, description TEXT NOT NULL, deadline TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS rfq_items(id INTEGER PRIMARY KEY AUTOINCREMENT, rfq_id INTEGER NOT NULL REFERENCES rfqs(id), description TEXT NOT NULL, quantity REAL NOT NULL, unit TEXT NOT NULL DEFAULT 'Nos', expected_price REAL NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS quotations(id INTEGER PRIMARY KEY AUTOINCREMENT, rfq_id INTEGER NOT NULL REFERENCES rfqs(id), vendor_id INTEGER NOT NULL REFERENCES vendors(id), quotation_number TEXT NOT NULL, document_path TEXT NOT NULL, currency TEXT NOT NULL DEFAULT 'INR', subtotal REAL NOT NULL, discount REAL NOT NULL, tax REAL NOT NULL, shipping REAL NOT NULL, grand_total REAL NOT NULL, delivery_days INTEGER NOT NULL, warranty_months INTEGER NOT NULL, payment_terms TEXT NOT NULL, confidence REAL NOT NULL, verified INTEGER NOT NULL DEFAULT 1, extracted_json TEXT NOT NULL, UNIQUE(rfq_id, vendor_id));
    CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY AUTOINCREMENT, rfq_id INTEGER NOT NULL UNIQUE REFERENCES rfqs(id), vendor_id INTEGER NOT NULL REFERENCES vendors(id), comments TEXT, decided_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS purchase_orders(id INTEGER PRIMARY KEY AUTOINCREMENT, po_number TEXT NOT NULL UNIQUE, rfq_id INTEGER NOT NULL UNIQUE REFERENCES rfqs(id), vendor_id INTEGER NOT NULL REFERENCES vendors(id), total_amount REAL NOT NULL, pdf_path TEXT NOT NULL, created_at TEXT NOT NULL, received_at TEXT);
    CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, entity TEXT NOT NULL, details TEXT, created_at TEXT NOT NULL);
    
    CREATE TABLE IF NOT EXISTS inventory(id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT NOT NULL UNIQUE, current_stock REAL NOT NULL DEFAULT 0, reorder_level REAL NOT NULL DEFAULT 5, unit TEXT NOT NULL DEFAULT 'Nos', warehouse TEXT NOT NULL DEFAULT 'Main Warehouse', last_updated TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS finance_budgets(id INTEGER PRIMARY KEY AUTOINCREMENT, department TEXT NOT NULL UNIQUE, allocated_budget REAL NOT NULL, spent_budget REAL NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS finance_invoices(id INTEGER PRIMARY KEY AUTOINCREMENT, po_number TEXT NOT NULL UNIQUE REFERENCES purchase_orders(po_number), invoice_number TEXT NOT NULL UNIQUE, amount REAL NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', payment_date TEXT, due_date TEXT, department TEXT NOT NULL DEFAULT 'Procurement');
    """)
    if connection.execute("SELECT COUNT(*) FROM vendors").fetchone()[0] == 0:
        connection.executemany("INSERT INTO vendors(company_name,category,rating,on_time_delivery_rate,status) VALUES(?,?,?,?,?)", [
            ("Apex Industrial Systems", "Industrial Automation", 4.3, 91, "ACTIVE"),
            ("NovaTech Components", "Electronic Components", 4.7, 96, "ACTIVE"),
            ("Orion Supply Works", "Industrial Supplies", 3.9, 82, "ACTIVE"),
        ])
    if connection.execute("SELECT COUNT(*) FROM rfqs").fetchone()[0] == 0:
        cursor = connection.execute("INSERT INTO rfqs(rfq_number,title,description,deadline,status,created_at) VALUES(?,?,?,?,?,?)", ("RFQ-2026-001", "Smart Factory Sensor Package", "Supply of industrial temperature and proximity sensors for the assembly line upgrade.", "2026-09-05", "OPEN", datetime.now().isoformat()))
        connection.execute("INSERT INTO rfq_items(rfq_id,description,quantity,unit,expected_price) VALUES(?,?,?,?,?)", (cursor.lastrowid, "Industrial sensor package", 20, "Nos", 5000))
    if connection.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
        connection.executemany("INSERT INTO inventory(item_name,current_stock,reorder_level,unit,warehouse,last_updated) VALUES(?,?,?,?,?,?)", [
            ("Industrial sensor package", 4, 10, "Nos", "Warehouse A", datetime.now().isoformat()),
            ("Proximity Sensors", 25, 15, "Nos", "Warehouse B", datetime.now().isoformat()),
            ("Temperature Probes", 2, 8, "Nos", "Warehouse A", datetime.now().isoformat()),
            ("PLC Modules", 12, 5, "Nos", "Main Warehouse", datetime.now().isoformat()),
        ])
    if connection.execute("SELECT COUNT(*) FROM finance_budgets").fetchone()[0] == 0:
        connection.executemany("INSERT INTO finance_budgets(department,allocated_budget,spent_budget) VALUES(?,?,?)", [
            ("Procurement", 1000000.0, 0.0),
            ("Operations", 500000.0, 120000.0),
            ("R&D", 300000.0, 45000.0),
        ])
    connection.commit(); connection.close()


@app.on_event("startup")
def startup() -> None:
    init_db()


class VendorInput(BaseModel):
    company_name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=100)
    rating: float = Field(default=4, ge=1, le=5)


class RfqInput(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=3)
    deadline: str
    item_description: str
    quantity: float = Field(gt=0)
    expected_price: float = Field(ge=0)


class ApprovalInput(BaseModel):
    vendor_id: int
    comments: str = ""


def rows(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    connection = db(); result = [dict(row) for row in connection.execute(query, params).fetchall()]; connection.close(); return result


def one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    connection = db(); result = connection.execute(query, params).fetchone(); connection.close(); return dict(result) if result else None


def audit(connection: sqlite3.Connection, action: str, entity: str, details: str = "") -> None:
    connection.execute("INSERT INTO audit_log(action,entity,details,created_at) VALUES(?,?,?,?)", (action, entity, details, datetime.now().isoformat()))


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() != ".pdf":
        raise HTTPException(400, "Only PDF and TXT files are supported in the offline MVP")
    try:
        with fitz.open(path) as document:
            text = "\n".join(page.get_text() for page in document)
    except Exception as exc:
        raise HTTPException(400, f"Could not read PDF: {exc}") from exc
    if len(text.strip()) < 40:
        raise HTTPException(422, "The PDF has no readable text. Install Tesseract/OCR support or use the included sample PDFs.")
    return text


def field(text: str, name: str, default: str = "") -> str:
    match = re.search(rf"^{re.escape(name)}\s*:\s*(.+)$", text, flags=re.I | re.M)
    return match.group(1).strip() if match else default


def number(text: str, name: str, default: float = 0) -> float:
    value = re.sub(r"[^0-9.\-]", "", field(text, name, str(default)))
    try: return float(value)
    except ValueError: return default


def parse_quotation(text: str) -> dict[str, Any]:
    parsed = {
        "quotation_number": field(text, "QUOTATION NUMBER", field(text, "QUOTE NUMBER", f"AUTO-{datetime.now().strftime('%H%M%S')}")),
        "currency": field(text, "CURRENCY", "INR"), "subtotal": number(text, "SUBTOTAL"), "discount": number(text, "DISCOUNT"),
        "tax": number(text, "TAX"), "shipping": number(text, "SHIPPING"), "grand_total": number(text, "GRAND TOTAL"),
        "delivery_days": int(number(text, "DELIVERY DAYS", 30)), "warranty_months": int(number(text, "WARRANTY MONTHS", 0)),
        "payment_terms": field(text, "PAYMENT TERMS", "Not specified"), "items": []
    }
    for match in re.finditer(r"ITEM\s*:\s*(.*?)\s*\|\s*QTY\s*:\s*([\d.]+)\s*\|\s*UNIT\s*:\s*(.*?)\s*\|\s*UNIT_PRICE\s*:\s*([\d.]+)", text, flags=re.I):
        description, qty, unit, unit_price = match.groups(); parsed["items"].append({"description":description.strip(),"quantity":float(qty),"unit":unit.strip(),"unit_price":float(unit_price),"line_total":float(qty)*float(unit_price)})
    if not parsed["subtotal"] and parsed["items"]: parsed["subtotal"] = sum(item["line_total"] for item in parsed["items"])
    calculated = parsed["subtotal"] - parsed["discount"] + parsed["tax"] + parsed["shipping"]
    if not parsed["grand_total"]: parsed["grand_total"] = calculated
    present = sum(bool(parsed[key]) for key in ("quotation_number","subtotal","grand_total","delivery_days","payment_terms"))
    parsed["confidence"] = round(0.68 + present * 0.055, 2)
    return parsed


def save_quotation(rfq_id: int, vendor_id: int, path: Path) -> dict[str, Any]:
    if not one("SELECT id FROM rfqs WHERE id=?", (rfq_id,)): raise HTTPException(404, "RFQ not found")
    if not one("SELECT id FROM vendors WHERE id=?", (vendor_id,)): raise HTTPException(404, "Vendor not found")
    parsed = parse_quotation(extract_text(path)); connection = db()
    connection.execute("""INSERT INTO quotations(rfq_id,vendor_id,quotation_number,document_path,currency,subtotal,discount,tax,shipping,grand_total,delivery_days,warranty_months,payment_terms,confidence,verified,extracted_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?) ON CONFLICT(rfq_id,vendor_id) DO UPDATE SET quotation_number=excluded.quotation_number,document_path=excluded.document_path,currency=excluded.currency,subtotal=excluded.subtotal,discount=excluded.discount,tax=excluded.tax,shipping=excluded.shipping,grand_total=excluded.grand_total,delivery_days=excluded.delivery_days,warranty_months=excluded.warranty_months,payment_terms=excluded.payment_terms,confidence=excluded.confidence,verified=1,extracted_json=excluded.extracted_json""", (rfq_id,vendor_id,parsed["quotation_number"],str(path),parsed["currency"],parsed["subtotal"],parsed["discount"],parsed["tax"],parsed["shipping"],parsed["grand_total"],parsed["delivery_days"],parsed["warranty_months"],parsed["payment_terms"],parsed["confidence"],json.dumps(parsed)))
    connection.execute("UPDATE rfqs SET status='COMPARED' WHERE id=?", (rfq_id,)); audit(connection,"QUOTATION_PROCESSED","RFQ",f"RFQ {rfq_id}, vendor {vendor_id}"); connection.commit(); connection.close(); return parsed


@app.get("/")
def root(): return {"name":"ProcureAI API","docs":"/docs","health":"/api/v1/health"}


@app.get("/api/v1/health")
def health(): return {"status":"ok","database":str(DB_PATH.name)}


@app.get("/api/v1/dashboard")
def dashboard():
    connection=db(); result={"vendors":connection.execute("SELECT COUNT(*) FROM vendors WHERE status='ACTIVE'").fetchone()[0],"rfqs":connection.execute("SELECT COUNT(*) FROM rfqs").fetchone()[0],"quotations":connection.execute("SELECT COUNT(*) FROM quotations").fetchone()[0],"pending_approvals":connection.execute("SELECT COUNT(*) FROM rfqs WHERE status='PENDING_APPROVAL'").fetchone()[0],"purchase_orders":connection.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0],"procurement_value":connection.execute("SELECT COALESCE(SUM(total_amount),0) FROM purchase_orders").fetchone()[0]}; connection.close(); return result


@app.get("/api/v1/vendors")
def list_vendors(): return rows("SELECT * FROM vendors ORDER BY company_name")


@app.post("/api/v1/vendors", status_code=201)
def create_vendor(data: VendorInput):
    connection=db()
    try: cursor=connection.execute("INSERT INTO vendors(company_name,category,rating,on_time_delivery_rate,status) VALUES(?,?,?,?,?)",(data.company_name,data.category,data.rating,85,"ACTIVE")); audit(connection,"VENDOR_CREATED","VENDOR",data.company_name); connection.commit()
    except sqlite3.IntegrityError as exc: raise HTTPException(409,"Vendor already exists") from exc
    finally: connection.close()
    return {"id":cursor.lastrowid,**data.model_dump(),"status":"ACTIVE"}


@app.get("/api/v1/rfqs")
def list_rfqs(): return rows("SELECT r.*, COUNT(i.id) item_count FROM rfqs r LEFT JOIN rfq_items i ON i.rfq_id=r.id GROUP BY r.id ORDER BY r.id DESC")


@app.post("/api/v1/rfqs", status_code=201)
def create_rfq(data: RfqInput):
    connection=db(); number_value=f"RFQ-{datetime.now().year}-{connection.execute('SELECT COUNT(*)+1 FROM rfqs').fetchone()[0]:03d}"; cursor=connection.execute("INSERT INTO rfqs(rfq_number,title,description,deadline,status,created_at) VALUES(?,?,?,?,?,?)",(number_value,data.title,data.description,data.deadline,"OPEN",datetime.now().isoformat())); connection.execute("INSERT INTO rfq_items(rfq_id,description,quantity,unit,expected_price) VALUES(?,?,?,?,?)",(cursor.lastrowid,data.item_description,data.quantity,"Nos",data.expected_price)); audit(connection,"RFQ_CREATED","RFQ",number_value); connection.commit(); result={"id":cursor.lastrowid,"rfq_number":number_value}; connection.close(); return result


@app.get("/api/v1/rfqs/{rfq_id}/quotations")
def list_quotations(rfq_id:int): return rows("SELECT q.id,q.vendor_id,v.company_name vendor_name,q.quotation_number,q.grand_total,q.delivery_days,q.warranty_months,q.payment_terms,q.confidence,q.verified FROM quotations q JOIN vendors v ON v.id=q.vendor_id WHERE q.rfq_id=? ORDER BY q.id",(rfq_id,))


@app.post("/api/v1/rfqs/{rfq_id}/quotations", status_code=201)
async def upload_quotation(rfq_id:int, vendor_id:int=Form(...), file:UploadFile=File(...)):
    suffix=Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf",".txt"}: raise HTTPException(400,"Supported formats: PDF and TXT")
    content=await file.read()
    if len(content)>10*1024*1024: raise HTTPException(413,"Maximum file size is 10 MB")
    target=UPLOAD_DIR/f"rfq_{rfq_id}_vendor_{vendor_id}{suffix}"; target.write_bytes(content); parsed=save_quotation(rfq_id,vendor_id,target); return {"message":"Quotation processed","extracted":parsed}


@app.post("/api/v1/rfqs/{rfq_id}/load-demo")
def load_demo(rfq_id:int):
    files=[SAMPLE_DIR/"apex_quote.pdf",SAMPLE_DIR/"novatech_quote.pdf",SAMPLE_DIR/"orion_quote.pdf"]
    missing=[p.name for p in files if not p.exists()]
    if missing: raise HTTPException(500,f"Sample files missing: {', '.join(missing)}")
    for vendor_id,path in enumerate(files,start=1): save_quotation(rfq_id,vendor_id,path)
    return {"message":"Three demo quotations processed"}


@app.get("/api/v1/rfqs/{rfq_id}/comparison")
def comparison(rfq_id:int):
    quotes=list_quotations(rfq_id)
    if not quotes: return []
    lowest=min(q["grand_total"] for q in quotes if q["grand_total"]>0); fastest=min(q["delivery_days"] for q in quotes if q["delivery_days"]>0); max_warranty=max(max(q["warranty_months"] for q in quotes),1)
    vendor_map={v["id"]:v for v in list_vendors()}; scored=[]
    for q in quotes:
        v=vendor_map[q["vendor_id"]]; price=lowest/q["grand_total"]*100 if q["grand_total"] else 0; delivery=fastest/q["delivery_days"]*100 if q["delivery_days"] else 0; quality=v["rating"]/5*100; warranty=q["warranty_months"]/max_warranty*100; payment=90 if "30" in q["payment_terms"] else 75; compliance=100 if q["verified"] else 50; final=price*.40+delivery*.20+quality*.15+warranty*.10+payment*.10+compliance*.05
        scored.append({**q,"price_score":round(price,1),"delivery_score":round(delivery,1),"quality_score":round(quality,1),"warranty_score":round(warranty,1),"payment_score":payment,"compliance_score":compliance,"final_score":round(final,1)})
    scored.sort(key=lambda item:item["final_score"],reverse=True)
    for rank,item in enumerate(scored,start=1): item["rank"]=rank; item["recommendation"]=(f"{item['vendor_name']} balances a total cost of INR {item['grand_total']:,.0f}, {item['delivery_days']}-day delivery and {item['warranty_months']}-month warranty. The decision is based on visible weighted criteria and can be overridden by a manager.")
    return scored


@app.post("/api/v1/rfqs/{rfq_id}/approve")
def approve(rfq_id:int,data:ApprovalInput):
    valid=one("SELECT id FROM quotations WHERE rfq_id=? AND vendor_id=?",(rfq_id,data.vendor_id))
    if not valid: raise HTTPException(400,"The selected vendor has no quotation for this RFQ")
    connection=db(); connection.execute("INSERT INTO approvals(rfq_id,vendor_id,comments,decided_at) VALUES(?,?,?,?) ON CONFLICT(rfq_id) DO UPDATE SET vendor_id=excluded.vendor_id,comments=excluded.comments,decided_at=excluded.decided_at",(rfq_id,data.vendor_id,data.comments,datetime.now().isoformat())); connection.execute("UPDATE rfqs SET status='APPROVED' WHERE id=?",(rfq_id,)); audit(connection,"VENDOR_APPROVED","RFQ",f"RFQ {rfq_id}, vendor {data.vendor_id}"); connection.commit(); connection.close(); return {"message":"Vendor approved"}


@app.post("/api/v1/rfqs/{rfq_id}/purchase-order")
def generate_po(rfq_id:int):
    selected=one("SELECT a.vendor_id,v.company_name,q.* FROM approvals a JOIN vendors v ON v.id=a.vendor_id JOIN quotations q ON q.rfq_id=a.rfq_id AND q.vendor_id=a.vendor_id WHERE a.rfq_id=?",(rfq_id,))
    rfq=one("SELECT * FROM rfqs WHERE id=?",(rfq_id,))
    if not selected or not rfq: raise HTTPException(400,"Approve a vendor before generating the purchase order")
    
    # Budget Check
    budget = one("SELECT * FROM finance_budgets WHERE department = 'Procurement'")
    if budget and (budget["allocated_budget"] - budget["spent_budget"]) < selected["grand_total"]:
        raise HTTPException(400, f"Insufficient budget in Procurement department. Remaining: INR {budget['allocated_budget'] - budget['spent_budget']:,.2f}, Required: INR {selected['grand_total']:,.2f}")
        
    po_number=f"PO-{datetime.now().year}-{rfq_id:04d}"; path=GENERATED_DIR/f"{po_number}.pdf"; styles=getSampleStyleSheet(); doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm)
    story=[Paragraph("PROCUREAI",styles["Title"]),Paragraph("Purchase Order",styles["Heading1"]),Spacer(1,8),Table([["PO Number",po_number],["RFQ",rfq["rfq_number"]],["Supplier",selected["company_name"]],["Issue Date",datetime.now().strftime("%d %B %Y")],["Payment Terms",selected["payment_terms"]]],colWidths=[45*mm,110*mm]),Spacer(1,12),Table([["Description","Delivery","Warranty","Total"],[rfq["title"],f"{selected['delivery_days']} days",f"{selected['warranty_months']} months",f"INR {selected['grand_total']:,.2f}"]],colWidths=[75*mm,28*mm,28*mm,32*mm]),Spacer(1,18),Paragraph("Approved through ProcureAI's explainable supplier comparison workflow.",styles["BodyText"])]
    for element in story:
        if isinstance(element,Table): element.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.5,colors.HexColor("#CBD5E1")),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E8F5F0")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("PADDING",(0,0),(-1,-1),8)]))
    doc.build(story); connection=db(); connection.execute("INSERT INTO purchase_orders(po_number,rfq_id,vendor_id,total_amount,pdf_path,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(rfq_id) DO UPDATE SET vendor_id=excluded.vendor_id,total_amount=excluded.total_amount,pdf_path=excluded.pdf_path,created_at=excluded.created_at",(po_number,rfq_id,selected["vendor_id"],selected["grand_total"],str(path),datetime.now().isoformat()))
    
    # Auto-generate Invoice
    invoice_number = f"INV-{datetime.now().year}-{rfq_id:04d}"
    connection.execute("""
        INSERT INTO finance_invoices(po_number, invoice_number, amount, status, due_date, department)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(po_number) DO UPDATE SET amount=excluded.amount
    """, (po_number, invoice_number, selected["grand_total"], "PENDING", (datetime.now().date().replace(month=datetime.now().month + 1 if datetime.now().month < 12 else 12)).isoformat(), "Procurement"))
    
    connection.execute("UPDATE rfqs SET status='PO_GENERATED' WHERE id=?",(rfq_id,)); audit(connection,"PO_GENERATED","RFQ",po_number); connection.commit(); connection.close(); return FileResponse(path,media_type="application/pdf",filename=f"{po_number}.pdf")


# --- INVENTORY & FINANCE INTEGRATION ---

class InventoryInput(BaseModel):
    item_name: str = Field(min_length=2, max_length=120)
    current_stock: float = Field(ge=0)
    reorder_level: float = Field(ge=0)
    unit: str = "Nos"
    warehouse: str = "Main Warehouse"


class ReorderInput(BaseModel):
    item_name: str
    quantity: float


@app.get("/api/v1/inventory")
def list_inventory():
    return rows("SELECT * FROM inventory ORDER BY item_name")


@app.post("/api/v1/inventory", status_code=201)
def create_inventory(data: InventoryInput):
    connection = db()
    try:
        cursor = connection.execute(
            "INSERT INTO inventory(item_name,current_stock,reorder_level,unit,warehouse,last_updated) VALUES(?,?,?,?,?,?)",
            (data.item_name, data.current_stock, data.reorder_level, data.unit, data.warehouse, datetime.now().isoformat())
        )
        audit(connection, "INVENTORY_CREATED", "INVENTORY", data.item_name)
        connection.commit()
        result = {"id": cursor.lastrowid, **data.model_dump(), "last_updated": datetime.now().isoformat()}
    except sqlite3.IntegrityError:
        connection.execute(
            "UPDATE inventory SET current_stock=?, reorder_level=?, unit=?, warehouse=?, last_updated=? WHERE item_name=?",
            (data.current_stock, data.reorder_level, data.unit, data.warehouse, datetime.now().isoformat(), data.item_name)
        )
        audit(connection, "INVENTORY_UPDATED", "INVENTORY", data.item_name)
        connection.commit()
        result = one("SELECT * FROM inventory WHERE item_name=?", (data.item_name,))
    finally:
        connection.close()
    return result


@app.post("/api/v1/inventory/reorder", status_code=201)
def trigger_reorder(data: ReorderInput):
    connection = db()
    number_value = f"RFQ-{datetime.now().year}-{connection.execute('SELECT COUNT(*)+1 FROM rfqs').fetchone()[0]:03d}"
    target_date = (datetime.now().date().replace(month=datetime.now().month + 1 if datetime.now().month < 12 else 12)).isoformat()
    cursor = connection.execute(
        "INSERT INTO rfqs(rfq_number,title,description,deadline,status,created_at) VALUES(?,?,?,?,?,?)",
        (number_value, f"Reorder: {data.item_name}", f"Automated replenishment request for {data.item_name} based on low stock alerts.", target_date, "OPEN", datetime.now().isoformat())
    )
    connection.execute(
        "INSERT INTO rfq_items(rfq_id,description,quantity,unit,expected_price) VALUES(?,?,?,?,?)",
        (cursor.lastrowid, data.item_name, data.quantity, "Nos", 0.0)
    )
    audit(connection, "RFQ_REORDER_CREATED", "RFQ", number_value)
    connection.commit()
    result = {"id": cursor.lastrowid, "rfq_number": number_value}
    connection.close()
    return result


@app.post("/api/v1/rfqs/{rfq_id}/receive", status_code=200)
def receive_items(rfq_id: int):
    connection = db()
    po = connection.execute("SELECT * FROM purchase_orders WHERE rfq_id=?", (rfq_id,)).fetchone()
    if not po:
        connection.close()
        raise HTTPException(400, "Purchase order not generated yet")
    if po["received_at"]:
        connection.close()
        return {"message": "Items already received for this PO"}
        
    items = connection.execute("SELECT * FROM rfq_items WHERE rfq_id=?", (rfq_id,)).fetchall()
    for item in items:
        desc = item["description"]
        qty = item["quantity"]
        unit = item["unit"]
        
        inv_item = connection.execute("SELECT * FROM inventory WHERE LOWER(item_name) = LOWER(?)", (desc,)).fetchone()
        if inv_item:
            new_stock = inv_item["current_stock"] + qty
            connection.execute("UPDATE inventory SET current_stock=?, last_updated=? WHERE id=?", (new_stock, datetime.now().isoformat(), inv_item["id"]))
        else:
            connection.execute("INSERT INTO inventory(item_name,current_stock,reorder_level,unit,warehouse,last_updated) VALUES(?,?,?,?,?,?)", (desc, qty, 5.0, unit, "Main Warehouse", datetime.now().isoformat()))
            
    connection.execute("UPDATE purchase_orders SET received_at=? WHERE rfq_id=?", (datetime.now().isoformat(), rfq_id))
    connection.execute("UPDATE rfqs SET status='RECEIVED' WHERE id=?", (rfq_id,))
    audit(connection, "ITEMS_RECEIVED", "INVENTORY", f"Received items for PO {po['po_number']}")
    connection.commit()
    connection.close()
    return {"message": "Items received and inventory updated"}


@app.get("/api/v1/finance/budgets")
def list_budgets():
    return rows("SELECT * FROM finance_budgets ORDER BY department")


@app.get("/api/v1/finance/invoices")
def list_invoices():
    return rows("""
        SELECT fi.*, po.total_amount, po.created_at as po_created_at, v.company_name as vendor_name
        FROM finance_invoices fi
        JOIN purchase_orders po ON po.po_number = fi.po_number
        JOIN vendors v ON v.id = po.vendor_id
        ORDER BY fi.id DESC
    """)


@app.post("/api/v1/finance/invoices/{invoice_id}/pay")
def pay_invoice(invoice_id: int):
    connection = db()
    invoice = connection.execute("SELECT * FROM finance_invoices WHERE id=?", (invoice_id,)).fetchone()
    if not invoice:
        connection.close()
        raise HTTPException(404, "Invoice not found")
    if invoice["status"] == "PAID":
        connection.close()
        return {"message": "Invoice already paid"}
        
    dept = invoice["department"]
    budget = connection.execute("SELECT * FROM finance_budgets WHERE department=?", (dept,)).fetchone()
    if budget:
        new_spent = budget["spent_budget"] + invoice["amount"]
        connection.execute("UPDATE finance_budgets SET spent_budget=? WHERE department=?", (new_spent, dept))
        
    connection.execute("UPDATE finance_invoices SET status='PAID', payment_date=? WHERE id=?", (datetime.now().isoformat(), invoice_id))
    audit(connection, "INVOICE_PAID", "FINANCE", f"Invoice {invoice['invoice_number']} for INR {invoice['amount']}")
    connection.commit()
    connection.close()
    return {"message": "Invoice paid successfully"}


@app.get("/api/v1/purchase-orders")
def list_purchase_orders():
    return rows("""
        SELECT po.*, v.company_name as vendor_name, r.title as rfq_title, r.rfq_number, r.status as rfq_status
        FROM purchase_orders po
        JOIN vendors v ON v.id = po.vendor_id
        JOIN rfqs r ON r.id = po.rfq_id
        ORDER BY po.id DESC
    """)


@app.get("/api/v1/audit-logs")
def list_audit_logs():
    return rows("SELECT * FROM audit_log ORDER BY id DESC LIMIT 50")
