import os
from pathlib import Path

os.environ["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])

from fastapi.testclient import TestClient
from app.main import app, init_db

client = TestClient(app)


def setup_module():
    init_db()


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_seed_data():
    assert len(client.get("/api/v1/vendors").json()) >= 3
    assert len(client.get("/api/v1/rfqs").json()) >= 1


def test_demo_comparison_is_ranked():
    assert client.post("/api/v1/rfqs/1/load-demo").status_code == 200
    comparison = client.get("/api/v1/rfqs/1/comparison").json()
    assert len(comparison) == 3
    assert comparison[0]["rank"] == 1
    assert comparison[0]["final_score"] >= comparison[1]["final_score"]


def test_approval_and_po():
    comparison = client.get("/api/v1/rfqs/1/comparison").json()
    vendor_id = comparison[0]["vendor_id"]
    approval = client.post("/api/v1/rfqs/1/approve", json={"vendor_id": vendor_id, "comments": "QA approval"})
    assert approval.status_code == 200
    po = client.post("/api/v1/rfqs/1/purchase-order")
    assert po.status_code == 200
    assert po.headers["content-type"] == "application/pdf"


def test_inventory_flow():
    inv = client.get("/api/v1/inventory").json()
    assert len(inv) >= 4
    
    new_item = {
        "item_name": "Test Actuator",
        "current_stock": 2.0,
        "reorder_level": 5.0,
        "unit": "Nos",
        "warehouse": "Warehouse A"
    }
    resp = client.post("/api/v1/inventory", json=new_item)
    assert resp.status_code == 201
    assert resp.json()["item_name"] == "Test Actuator"
    
    reorder_payload = {"item_name": "Test Actuator", "quantity": 10.0}
    reorder_resp = client.post("/api/v1/inventory/reorder", json=reorder_payload)
    assert reorder_resp.status_code == 201
    assert "rfq_number" in reorder_resp.json()


def test_finance_flow():
    budgets = client.get("/api/v1/finance/budgets").json()
    assert len(budgets) >= 3
    
    invoices = client.get("/api/v1/finance/invoices").json()
    assert len(invoices) >= 1
    assert invoices[0]["status"] == "PENDING"
    
    invoice_id = invoices[0]["id"]
    pay_resp = client.post(f"/api/v1/finance/invoices/{invoice_id}/pay")
    assert pay_resp.status_code == 200
    
    invoices_after = client.get("/api/v1/finance/invoices").json()
    assert invoices_after[0]["status"] == "PAID"
    
    budgets_after = client.get("/api/v1/finance/budgets").json()
    proc_budget = next(b for b in budgets_after if b["department"] == "Procurement")
    assert proc_budget["spent_budget"] > 0


def test_receive_items():
    recv_resp = client.post("/api/v1/rfqs/1/receive")
    assert recv_resp.status_code == 200
    
    inv = client.get("/api/v1/inventory").json()
    sensor_item = next(i for i in inv if i["item_name"] == "Industrial sensor package")
    assert sensor_item["current_stock"] == 24.0

