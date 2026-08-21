"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

type Vendor = { id:number; company_name:string; category:string; rating:number; on_time_delivery_rate:number; status:string };
type Rfq = { id:number; rfq_number:string; title:string; description:string; deadline:string; status:string; item_count:number };
type Quote = { id:number; vendor_id:number; vendor_name:string; quotation_number:string; grand_total:number; delivery_days:number; warranty_months:number; payment_terms:string; confidence:number; verified:boolean };
type Comparison = Quote & { price_score:number; delivery_score:number; quality_score:number; warranty_score:number; payment_score:number; compliance_score:number; final_score:number; rank:number; recommendation:string };
type Dashboard = { vendors:number; rfqs:number; quotations:number; pending_approvals:number; purchase_orders:number; procurement_value:number };

type InventoryItem = { id:number; item_name:string; current_stock:number; reorder_level:number; unit:string; warehouse:string; last_updated:string };
type Budget = { id:number; department:string; allocated_budget:number; spent_budget:number };
type Invoice = { id:number; po_number:string; invoice_number:string; amount:number; status:string; payment_date:string | null; due_date:string; department:string; total_amount:number; po_created_at:string; vendor_name:string };
type PurchaseOrder = { id:number; po_number:string; rfq_id:number; vendor_id:number; total_amount:number; pdf_path:string; created_at:string; received_at:string | null; vendor_name:string; rfq_title:string; rfq_number:string; rfq_status:string };
type AuditLog = { id:number; action:string; entity:string; details:string; created_at:string };

const money = (value:number) => new Intl.NumberFormat("en-IN", { style:"currency", currency:"INR", maximumFractionDigits:0 }).format(value || 0);

export default function Home() {
  const [tab, setTab] = useState("dashboard");
  const [dashboard, setDashboard] = useState<Dashboard>({vendors:0,rfqs:0,quotations:0,pending_approvals:0,purchase_orders:0,procurement_value:0});
  const [vendors, setVendors] = useState<Vendor[]>([]); 
  const [rfqs, setRfqs] = useState<Rfq[]>([]);
  const [quotes, setQuotes] = useState<Quote[]>([]); 
  const [comparison, setComparison] = useState<Comparison[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);

  const [selectedRfq, setSelectedRfq] = useState(1); 
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("Ready for quotation analysis");
  
  const [showVendorForm, setShowVendorForm] = useState(false); 
  const [showRfqForm, setShowRfqForm] = useState(false);
  const [showInventoryForm, setShowInventoryForm] = useState(false);
  
  const [reorderItemName, setReorderItemName] = useState("");
  const [reorderQty, setReorderQty] = useState(10);

  const request = async (path:string, options?:RequestInit) => {
    const response = await fetch(`${API}${path}`, options);
    if (!response.ok) throw new Error((await response.json().catch(()=>({detail:"Request failed"}))).detail || "Request failed");
    return (response.headers.get("content-type") || "").includes("application/json") ? response.json() : response.blob();
  };

  const refresh = async () => {
    try {
      const [d,v,r,inv,b,invs,pos,logs] = await Promise.all([
        request("/dashboard"), 
        request("/vendors"), 
        request("/rfqs"),
        request("/inventory"),
        request("/finance/budgets"),
        request("/finance/invoices"),
        request("/purchase-orders"),
        request("/audit-logs")
      ]);
      setDashboard(d); 
      setVendors(v); 
      setRfqs(r);
      setInventory(inv);
      setBudgets(b);
      setInvoices(invs);
      setPurchaseOrders(pos);
      setAuditLogs(logs);

      if (selectedRfq) { 
        try {
          setQuotes(await request(`/rfqs/${selectedRfq}/quotations`)); 
          setComparison(await request(`/rfqs/${selectedRfq}/comparison`)); 
        } catch {
          setQuotes([]);
          setComparison([]);
        }
      }
    } catch { 
      setNotice("Backend is offline — start it using the README instructions"); 
    }
  };

  useEffect(() => {
    let active = true;
    Promise.all([
      request("/dashboard"), 
      request("/vendors"), 
      request("/rfqs"),
      request("/inventory"),
      request("/finance/budgets"),
      request("/finance/invoices"),
      request("/purchase-orders"),
      request("/audit-logs")
    ])
      .then(async ([d,v,r,inv,b,invs,pos,logs]) => {
        let q = []; 
        let c = [];
        if (selectedRfq) {
          try {
            q = await request(`/rfqs/${selectedRfq}/quotations`);
            c = await request(`/rfqs/${selectedRfq}/comparison`);
          } catch {}
        }
        if (active) { 
          setDashboard(d); 
          setVendors(v); 
          setRfqs(r); 
          setInventory(inv);
          setBudgets(b);
          setInvoices(invs);
          setPurchaseOrders(pos);
          setAuditLogs(logs);
          setQuotes(q); 
          setComparison(c); 
        }
      })
      .catch(() => { 
        if (active) setNotice("Backend is offline — start it using the README instructions"); 
      });
    return () => { active = false; };
  }, [selectedRfq]);

  const winner = useMemo(() => comparison[0], [comparison]);

  const loadDemo = async () => { 
    setBusy(true); 
    setNotice("Analyzing three sample vendor quotations…"); 
    try { 
      await request(`/rfqs/${selectedRfq}/load-demo`, {method:"POST"}); 
      await refresh(); 
      setTab("comparison"); 
      setNotice("Analysis complete — three vendors ranked"); 
    } catch(e) { 
      setNotice(e instanceof Error ? e.message : "Could not load demo"); 
    } finally { 
      setBusy(false); 
    } 
  };

  const approveWinner = async () => { 
    if (!winner) return; 
    setBusy(true); 
    try { 
      await request(`/rfqs/${selectedRfq}/approve`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({vendor_id:winner.vendor_id, comments:"Approved from comparison dashboard"})}); 
      await refresh(); 
      setNotice(`${winner.vendor_name} approved. Purchase order is ready.`); 
    } catch(e) { 
      setNotice(e instanceof Error ? e.message : "Approval failed"); 
    } finally { 
      setBusy(false); 
    } 
  };

  const downloadPO = async () => { 
    if (!winner) return; 
    setBusy(true); 
    try { 
      const blob = await request(`/rfqs/${selectedRfq}/purchase-order`, {method:"POST"}); 
      const url=URL.createObjectURL(blob); 
      const a=document.createElement("a"); 
      a.href=url; 
      a.download=`PO-RFQ-${selectedRfq}.pdf`; 
      a.click(); 
      URL.revokeObjectURL(url); 
      await refresh(); 
      setNotice("Purchase order generated and downloaded"); 
    } catch(e) { 
      setNotice(e instanceof Error ? e.message : "Approve the selected vendor before generating a PO"); 
    } finally { 
      setBusy(false); 
    } 
  };

  const uploadQuote = async (event:FormEvent<HTMLFormElement>) => { 
    event.preventDefault(); 
    const form=new FormData(event.currentTarget); 
    setBusy(true); 
    setNotice("Extracting quotation fields…"); 
    try { 
      await request(`/rfqs/${selectedRfq}/quotations`, {method:"POST",body:form}); 
      await refresh(); 
      setNotice("Quotation extracted successfully"); 
      event.currentTarget.reset(); 
    } catch(e) { 
      setNotice(e instanceof Error ? e.message : "Upload failed"); 
    } finally { 
      setBusy(false); 
    } 
  };

  const createVendor = async (event:FormEvent<HTMLFormElement>) => { 
    event.preventDefault(); 
    const f=new FormData(event.currentTarget); 
    await request("/vendors", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(Object.fromEntries(f))}); 
    setShowVendorForm(false); 
    await refresh(); 
    setNotice("Vendor added"); 
  };

  const createRfq = async (event:FormEvent<HTMLFormElement>) => { 
    event.preventDefault(); 
    const f=new FormData(event.currentTarget); 
    const payload={...Object.fromEntries(f),quantity:Number(f.get("quantity")),expected_price:Number(f.get("expected_price"))}; 
    const result=await request("/rfqs", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}); 
    setSelectedRfq(result.id); 
    setShowRfqForm(false); 
    await refresh(); 
    setNotice("RFQ created"); 
  };

  const createInventoryItem = async (event:FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const f=new FormData(event.currentTarget);
    const payload = {
      item_name: f.get("item_name"),
      current_stock: Number(f.get("current_stock")),
      reorder_level: Number(f.get("reorder_level")),
      unit: f.get("unit"),
      warehouse: f.get("warehouse")
    };
    await request("/inventory", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
    setShowInventoryForm(false);
    await refresh();
    setNotice("Inventory item registered/updated");
  };

  const triggerReorder = async (event:FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await request("/inventory/reorder", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({item_name: reorderItemName, quantity: reorderQty})});
      setSelectedRfq(result.id);
      setTab("rfqs");
      await refresh();
      setNotice(`Reorder RFQ ${result.rfq_number} created for ${reorderItemName}`);
      setReorderItemName("");
    } catch(e) {
      setNotice(e instanceof Error ? e.message : "Reorder failed");
    } finally {
      setBusy(false);
    }
  };

  const receiveItems = async (rfqId: number) => {
    setBusy(true);
    try {
      await request(`/rfqs/${rfqId}/receive`, {method:"POST"});
      await refresh();
      setNotice("Items received! Stock levels updated.");
    } catch(e) {
      setNotice(e instanceof Error ? e.message : "Receive failed");
    } finally {
      setBusy(false);
    }
  };

  const payInvoice = async (invoiceId: number) => {
    setBusy(true);
    try {
      await request(`/finance/invoices/${invoiceId}/pay`, {method:"POST"});
      await refresh();
      setNotice("Invoice paid successfully!");
    } catch(e) {
      setNotice(e instanceof Error ? e.message : "Payment failed");
    } finally {
      setBusy(false);
    }
  };

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">P</span>
        <div><strong>ProcureAI</strong><small>Intelligent sourcing</small></div>
      </div>
      <nav aria-label="Main navigation">
        {[
          ["dashboard","Overview","01"],
          ["rfqs","RFQs","02"],
          ["quotations","Quotations","03"],
          ["comparison","Smart comparison","04"],
          ["vendors","Vendors","05"],
          ["inventory","Inventory","06"],
          ["finance","Finance","07"]
        ].map(([id,label,num])=>(
          <button key={id} className={tab===id?"nav-active":""} onClick={()=>setTab(id)}>
            <span>{num}</span>{label}
          </button>
        ))}
      </nav>
      <div className="sidebar-foot">
        <span className="status-dot"/>
        <div><b>Analysis engine</b><small>Local demo mode</small></div>
      </div>
    </aside>

    <main className="workspace">
      <header className="topbar">
        <div>
          <p className="eyebrow">PROCUREMENT WORKSPACE</p>
          <h1>{tab==="comparison"?"Vendor intelligence":tab==="rfqs"?"RFQs":tab.charAt(0).toUpperCase()+tab.slice(1)}</h1>
        </div>
        <div className="top-actions">
          <select value={selectedRfq} onChange={e=>setSelectedRfq(Number(e.target.value))} aria-label="Select RFQ">
            {rfqs.map(r=><option key={r.id} value={r.id}>{r.rfq_number} · {r.title}</option>)}
          </select>
          <button className="primary" onClick={loadDemo} disabled={busy}>{busy?"Working…":"Run demo analysis"}</button>
        </div>
      </header>

      <div className="notice"><span className="status-dot"/>{notice}</div>

      {tab==="dashboard"&&<>
        <section className="hero-card">
          <div>
            <p className="eyebrow light">DECISION BRIEF</p>
            <h2>Turn scattered quotations into a confident purchase decision.</h2>
            <p>Extract commercial terms, compare suppliers on transparent criteria, and move from RFQ to approved PO in minutes.</p>
          </div>
          <div className="hero-score">
            <span>{comparison.length?Math.round(comparison[0].final_score):"–"}</span>
            <small>top vendor score</small>
          </div>
        </section>

        <section className="metrics">
          <Metric label="Active vendors" value={dashboard.vendors}/>
          <Metric label="Open RFQs" value={dashboard.rfqs}/>
          <Metric label="Quotations" value={dashboard.quotations}/>
          <Metric label="Purchase value" value={money(dashboard.procurement_value)}/>
        </section>

        <section className="two-col">
          <div className="panel">
            <PanelTitle title="Procurement pipeline" detail="Live status across the selected RFQ"/>
            <div className="pipeline">
              {["RFQ created","Quotes received","AI analyzed","Manager approval","PO generated"].map((x,i)=><div key={x} className={i<(dashboard.purchase_orders?5:quotes.length?3:1)?"done":""}><span>{i+1}</span><p>{x}</p></div>)}
            </div>
          </div>
          <div className="panel">
            <PanelTitle title="Decision readiness" detail="Checks before approval"/>
            <Check label="Required suppliers" ok={quotes.length>=3}/>
            <Check label="Commercial fields extracted" ok={quotes.length>0}/>
            <Check label="Weighted ranking available" ok={comparison.length>0}/>
            <Check label="Purchase order generated" ok={dashboard.purchase_orders>0}/>
          </div>
        </section>

        <section className="dashboard-grid-enhanced">
          <div className="panel">
            <PanelTitle title="Finance & Department Budgets" detail="Remaining budget balances" action={<button className="secondary" onClick={()=>setTab("finance")}>Finance Ledger</button>}/>
            <div className="stack-form" style={{gap: "18px"}}>
              {budgets.map(b => {
                const pct = b.allocated_budget > 0 ? (b.spent_budget / b.allocated_budget) * 100 : 0;
                const barClass = pct >= 90 ? "danger" : pct >= 70 ? "warning" : "";
                return (
                  <div key={b.id}>
                    <div style={{display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: "4px"}}>
                      <b>{b.department}</b>
                      <span>{money(b.spent_budget)} / {money(b.allocated_budget)} ({pct.toFixed(0)}%)</span>
                    </div>
                    <div className="progress-bar-wrap">
                      <div className={`progress-bar-fill ${barClass}`} style={{width: `${Math.min(pct, 100)}%`}}/>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="panel">
            <PanelTitle title="Replenishment Alerts" detail="Inventory items below reorder points" action={<button className="secondary" onClick={()=>setTab("inventory")}>Stock Directory</button>}/>
            {inventory.filter(item => item.current_stock <= item.reorder_level).length === 0 ? (
              <Empty text="All inventory items are sufficiently stocked."/>
            ) : (
              <div className="quote-list">
                {inventory.filter(item => item.current_stock <= item.reorder_level).map(item => (
                  <article key={item.id} style={{padding: "10px 14px", borderLeft: "4px solid #ef4444"}}>
                    <div>
                      <b>{item.item_name}</b>
                      <small>In Stock: {item.current_stock} {item.unit} (Min: {item.reorder_level})</small>
                    </div>
                    <span className="badge low-stock">Low Stock</span>
                    <button className="action-link" onClick={() => { setReorderItemName(item.item_name); setReorderQty(Math.max(10, Math.round(item.reorder_level * 2))); setTab("inventory"); }} style={{background: "none", border: 0, padding: 0}}>
                      Replenish
                    </button>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="two-col" style={{marginTop: "20px"}}>
          <div className="panel">
            <PanelTitle title="Recent Workspace Activity" detail="Live log of procurement actions"/>
            <div className="timeline-feed">
              {auditLogs.slice(0, 5).map(log => (
                <div key={log.id} className="timeline-item">
                  <div className="timeline-dot active">✓</div>
                  <div className="timeline-content">
                    <p><strong>{log.action.replaceAll("_", " ")}</strong> · {log.details}</p>
                    <small>{new Date(log.created_at).toLocaleString()}</small>
                  </div>
                </div>
              ))}
              {auditLogs.length === 0 && <Empty text="No activity logged yet."/>}
            </div>
          </div>

          <div className="panel">
            <PanelTitle title="Pending Accounts Payable" detail="Invoices awaiting supplier payment"/>
            {invoices.filter(inv => inv.status === "PENDING").length === 0 ? (
              <Empty text="No pending invoices."/>
            ) : (
              <div className="quote-list">
                {invoices.filter(inv => inv.status === "PENDING").slice(0, 3).map(inv => (
                  <article key={inv.id} style={{padding: "12px"}}>
                    <div>
                      <b>{inv.vendor_name}</b>
                      <small>{inv.invoice_number} · Due {inv.due_date}</small>
                    </div>
                    <strong>{money(inv.amount)}</strong>
                    <button className="primary" style={{padding: "6px 12px", fontSize: "11px"}} onClick={() => payInvoice(inv.id)} disabled={busy}>
                      Pay
                    </button>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>
      </>}

      {tab==="vendors"&&<section className="panel">
        <PanelTitle title="Approved vendor directory" detail="Performance context used during evaluation" action={<button className="secondary" onClick={()=>setShowVendorForm(true)}>+ Add vendor</button>}/>
        <DataTable headers={["Vendor","Category","Rating","On-time","Status"]}>
          {vendors.map(v=><tr key={v.id}><td><b>{v.company_name}</b></td><td>{v.category}</td><td>{v.rating.toFixed(1)} / 5</td><td>{v.on_time_delivery_rate}%</td><td><Badge text={v.status}/></td></tr>)}
        </DataTable>
      </section>}

      {tab==="rfqs"&&<section className="panel">
        <PanelTitle title="Requests for quotation" detail="Create and monitor sourcing requests" action={<button className="secondary" onClick={()=>setShowRfqForm(true)}>+ New RFQ</button>}/>
        <DataTable headers={["RFQ","Requirement","Deadline","Items","Status"]}>
          {rfqs.map(r=><tr key={r.id} onClick={()=>setSelectedRfq(r.id)} className="clickable"><td><b>{r.rfq_number}</b></td><td>{r.title}</td><td>{r.deadline}</td><td>{r.item_count}</td><td><Badge text={r.status}/></td></tr>)}
        </DataTable>
      </section>}

      {tab==="quotations"&&<section className="two-col upload-layout">
        <div className="panel">
          <PanelTitle title="Upload quotation" detail="PDF documents up to 10 MB"/>
          <form className="stack-form" onSubmit={uploadQuote}>
            <label>Vendor
              <select name="vendor_id" required>
                {vendors.map(v=><option value={v.id} key={v.id}>{v.company_name}</option>)}
              </select>
            </label>
            <label className="file-drop">Quotation document
              <input type="file" name="file" accept=".pdf,.txt" required/>
              <span>Choose a PDF or text quotation</span>
            </label>
            <button className="primary" disabled={busy}>Extract quotation</button>
          </form>
        </div>
        <div className="panel">
          <PanelTitle title="Processed quotations" detail={`${quotes.length} documents ready`}/>
          {quotes.length===0?
            <Empty text="No quotations uploaded yet. Run the sample analysis or upload your own."/>:
            <div className="quote-list">
              {quotes.map(q=><article key={q.id}><div><b>{q.vendor_name}</b><small>{q.quotation_number}</small></div><strong>{money(q.grand_total)}</strong><span>{Math.round(q.confidence*100)}% confidence</span></article>)}
            </div>
          }
        </div>
      </section>}

      {tab==="comparison"&&<section className="panel comparison-panel">
        <PanelTitle title="Explainable supplier ranking" detail="Scores are deterministic; AI only extracts and explains" action={
          <div className="button-row">
            <button className="secondary" disabled={!winner||busy} onClick={approveWinner}>Approve winner</button>
            <button className="primary" disabled={!winner||busy} onClick={downloadPO}>Generate PO</button>
          </div>
        }/>
        {comparison.length===0?
          <Empty text="Load or upload at least one quotation to generate a comparison."/>:
          <>
            <div className="winner-card">
              <div>
                <span className="rank">#{winner.rank}</span>
                <div>
                  <small>RECOMMENDED SUPPLIER</small>
                  <h3>{winner.vendor_name}</h3>
                  <p>{winner.recommendation}</p>
                </div>
              </div>
              <div className="winner-score">
                <strong>{winner.final_score.toFixed(1)}</strong>
                <small>weighted score</small>
              </div>
            </div>
            <DataTable headers={["Rank","Vendor","Total","Delivery","Warranty","Price score","Final score"]}>
              {comparison.map(c=><tr key={c.id} className={c.rank===1?"highlight":""}><td><span className="rank">#{c.rank}</span></td><td><b>{c.vendor_name}</b></td><td>{money(c.grand_total)}</td><td>{c.delivery_days} days</td><td>{c.warranty_months} months</td><td>{c.price_score.toFixed(1)}</td><td><strong>{c.final_score.toFixed(1)}</strong></td></tr>)}
            </DataTable>
            <p className="formula-note">Default weighting: Price 40% · Delivery 20% · Quality 15% · Warranty 10% · Payment terms 10% · Compliance 5%</p>
          </>
        }
      </section>}

      {tab==="inventory"&&<section className="panel">
        <PanelTitle title="Inventory Stock Levels" detail="Physical items and spare parts stock" action={
          <button className="secondary" onClick={()=>setShowInventoryForm(true)}>+ Add Stock Item</button>
        }/>
        {reorderItemName && (
          <div className="notice" style={{background: "#fff3d6", padding: "14px", borderRadius: "10px", display: "block", color: "var(--navy)"}}>
            <form onSubmit={triggerReorder} className="form-row" style={{alignItems: "center", display: "flex", gap: "14px", justifyContent: "space-between"}}>
              <span>Auto-create replenishment RFQ for <strong>{reorderItemName}</strong>?</span>
              <div style={{display: "flex", gap: "10px", alignItems: "center"}}>
                <label style={{display:"flex", gap:"8px", alignItems:"center", fontSize:"11px", fontWeight:"bold"}}>
                  Qty:
                  <input type="number" value={reorderQty} onChange={e=>setReorderQty(Number(e.target.value))} min="1" style={{width:"80px"}} required/>
                </label>
                <button type="submit" className="primary" style={{padding:"8px 12px"}} disabled={busy}>Replenish Now</button>
                <button type="button" className="secondary" style={{padding:"8px 12px"}} onClick={()=>setReorderItemName("")}>Cancel</button>
              </div>
            </form>
          </div>
        )}
        <DataTable headers={["Item Name","Current Stock","Reorder Threshold","Warehouse","Status","Last Updated","Action"]}>
          {inventory.map(item => {
            const isLow = item.current_stock <= item.reorder_level;
            return (
              <tr key={item.id} className={isLow ? "highlight" : ""}>
                <td><b>{item.item_name}</b></td>
                <td>{item.current_stock} {item.unit}</td>
                <td>{item.reorder_level} {item.unit}</td>
                <td>{item.warehouse}</td>
                <td><span className={`badge ${isLow ? "low-stock" : "in-stock"}`}>{isLow ? "Low Stock" : "In Stock"}</span></td>
                <td>{new Date(item.last_updated).toLocaleDateString()}</td>
                <td>
                  <button className="action-link" style={{background:"none", border:0, padding:0}} onClick={() => { setReorderItemName(item.item_name); setReorderQty(Math.max(10, Math.round(item.reorder_level * 2))); }}>
                    Reorder
                  </button>
                </td>
              </tr>
            );
          })}
        </DataTable>
      </section>}

      {tab==="finance"&&<>
        <section className="panel" style={{marginBottom: "20px"}}>
          <PanelTitle title="Departmental Budget Ledger" detail="Corporate spend tracking per department"/>
          <DataTable headers={["Department","Allocated Budget","Spent Budget","Remaining Balance","Utilization"]}>
            {budgets.map(b => {
              const remaining = b.allocated_budget - b.spent_budget;
              const utilization = b.allocated_budget > 0 ? (b.spent_budget / b.allocated_budget) * 100 : 0;
              return (
                <tr key={b.id}>
                  <td><b>{b.department}</b></td>
                  <td>{money(b.allocated_budget)}</td>
                  <td>{money(b.spent_budget)}</td>
                  <td>{money(remaining)}</td>
                  <td>
                    <div style={{display: "flex", alignItems: "center", gap: "8px"}}>
                      <div className="progress-bar-wrap" style={{width: "100px", marginTop: 0}}>
                        <div className={`progress-bar-fill ${utilization >= 90 ? "danger" : utilization >= 70 ? "warning" : ""}`} style={{width: `${Math.min(utilization, 100)}%`}}/>
                      </div>
                      <span>{utilization.toFixed(0)}%</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </DataTable>
        </section>

        <section className="two-col">
          <div className="panel">
            <PanelTitle title="Supplier Invoices Ledger" detail="Accounts payable list from purchase orders"/>
            <DataTable headers={["Invoice #","Vendor","Amount","Due Date","Status","Action"]}>
              {invoices.map(inv => (
                <tr key={inv.id}>
                  <td><b>{inv.invoice_number}</b><br/><small style={{color: "var(--muted)"}}>{inv.po_number}</small></td>
                  <td>{inv.vendor_name}</td>
                  <td>{money(inv.amount)}</td>
                  <td>{inv.due_date}</td>
                  <td><span className={`badge ${inv.status.toLowerCase()}`}>{inv.status}</span></td>
                  <td>
                    {inv.status === "PENDING" ? (
                      <button className="primary" style={{padding: "6px 12px", fontSize: "11px"}} onClick={() => payInvoice(inv.id)} disabled={busy}>
                        Pay
                      </button>
                    ) : (
                      <span style={{color: "var(--muted)", fontSize: "11px"}}>Paid</span>
                    )}
                  </td>
                </tr>
              ))}
              {invoices.length === 0 && <tr><td colSpan={6} style={{textAlign: "center"}}><Empty text="No invoices generated yet."/></td></tr>}
            </DataTable>
          </div>

          <div className="panel">
            <PanelTitle title="Purchase Orders Delivery" detail="Goods receiving process for generated POs"/>
            <DataTable headers={["PO Number","Vendor","Amount","Status","Action"]}>
              {purchaseOrders.map(po => {
                const received = po.received_at !== null;
                return (
                  <tr key={po.id}>
                    <td><b>{po.po_number}</b><br/><small style={{color: "var(--muted)"}}>{po.rfq_title}</small></td>
                    <td>{po.vendor_name}</td>
                    <td>{money(po.total_amount)}</td>
                    <td><span className={`badge ${received ? "received" : "po-generated"}`}>{received ? "Received" : "Generated"}</span></td>
                    <td>
                      {!received ? (
                        <button className="secondary" style={{padding: "6px 12px", fontSize: "11px"}} onClick={() => receiveItems(po.rfq_id)} disabled={busy}>
                          Receive
                        </button>
                      ) : (
                        <span style={{color: "var(--muted)", fontSize: "11px"}}>Complete</span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {purchaseOrders.length === 0 && <tr><td colSpan={5} style={{textAlign: "center"}}><Empty text="No purchase orders created yet."/></td></tr>}
            </DataTable>
          </div>
        </section>
      </>}
    </main>

    {showVendorForm&&<Modal title="Add vendor" close={()=>setShowVendorForm(false)}>
      <form className="stack-form" onSubmit={createVendor}>
        <label>Company name<input name="company_name" required/></label>
        <label>Category<input name="category" defaultValue="Industrial Supplies" required/></label>
        <label>Rating<input name="rating" type="number" step="0.1" min="1" max="5" defaultValue="4.0" required/></label>
        <button className="primary">Save vendor</button>
      </form>
    </Modal>}

    {showRfqForm&&<Modal title="Create RFQ" close={()=>setShowRfqForm(false)}>
      <form className="stack-form" onSubmit={createRfq}>
        <label>RFQ title<input name="title" required/></label>
        <label>Description<textarea name="description" required/></label>
        <label>Deadline<input name="deadline" type="date" required/></label>
        <label>First item<input name="item_description" required/></label>
        <div className="form-row">
          <label>Quantity<input name="quantity" type="number" min="1" required/></label>
          <label>Expected unit price<input name="expected_price" type="number" min="0" required/></label>
        </div>
        <button className="primary">Create RFQ</button>
      </form>
    </Modal>}

    {showInventoryForm&&<Modal title="Register Stock Item" close={()=>setShowInventoryForm(false)}>
      <form className="stack-form" onSubmit={createInventoryItem}>
        <label>Item Name<input name="item_name" placeholder="e.g. Proximity Sensors" required/></label>
        <div className="form-row">
          <label>Current Stock<input name="current_stock" type="number" step="any" min="0" defaultValue="0" required/></label>
          <label>Reorder Point<input name="reorder_level" type="number" step="any" min="0" defaultValue="5" required/></label>
        </div>
        <div className="form-row">
          <label>Unit of Measure<input name="unit" defaultValue="Nos" required/></label>
          <label>Warehouse<input name="warehouse" defaultValue="Main Warehouse" required/></label>
        </div>
        <button className="primary">Register Item</button>
      </form>
    </Modal>}
  </div>;
}

function Metric({label,value}:{label:string,value:string|number}){return <article className="metric"><p>{label}</p><strong>{value}</strong><span>Live workspace total</span></article>}
function PanelTitle({title,detail,action}:{title:string,detail:string,action?:React.ReactNode}){return <div className="panel-title"><div><h2>{title}</h2><p>{detail}</p></div>{action}</div>}
function Badge({text}:{text:string}){return <span className={`badge ${text.toLowerCase().replaceAll("_","-")}`}>{text.replaceAll("_"," ")}</span>}
function Check({label,ok}:{label:string,ok:boolean}){return <div className="check"><span className={ok?"check-ok":""}>{ok?"✓":"·"}</span><p>{label}</p><b>{ok?"Ready":"Pending"}</b></div>}
function Empty({text}:{text:string}){return <div className="empty"><span>∷</span><p>{text}</p></div>}
function DataTable({headers,children}:{headers:string[],children:React.ReactNode}){return <div className="table-wrap"><table><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>}
function Modal({title,close,children}:{title:string,close:()=>void,children:React.ReactNode}){return <div className="modal-backdrop" onMouseDown={close}><div className="modal" onMouseDown={e=>e.stopPropagation()}><div className="modal-head"><h2>{title}</h2><button onClick={close} aria-label="Close">×</button></div>{children}</div></div>}
