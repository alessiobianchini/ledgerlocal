import csv
import io
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_FILE = Path(__file__).parent / "ledger.db"


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                vendor TEXT NOT NULL,
                date TEXT,
                invoice_number TEXT,
                currency TEXT NOT NULL,
                total_amount REAL NOT NULL,
                tax_amount REAL,
                category TEXT NOT NULL,
                summary TEXT NOT NULL,
                raw_text TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON receipts(date)")


def insert_receipt(data: dict) -> dict:
    rec_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO receipts (
                id, filename, vendor, date, invoice_number, currency,
                total_amount, tax_amount, category, summary, raw_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rec_id,
            data["filename"],
            data["vendor"],
            data.get("date"),
            data.get("invoice_number"),
            data["currency"],
            data["total_amount"],
            data.get("tax_amount"),
            data["category"],
            data["summary"],
            data.get("raw_text"),
            now
        ))
    data["id"] = rec_id
    data["created_at"] = now
    return data


def all_receipts() -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM receipts ORDER BY date DESC, created_at DESC")
        return [dict(r) for r in cur.fetchall()]


def update_receipt(rec_id: str, fields: dict) -> bool:
    allowed = {"vendor", "date", "invoice_number", "currency", "total_amount", "tax_amount", "category", "summary"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [rec_id]

    with get_conn() as conn:
        cur = conn.execute(f"UPDATE receipts SET {set_clause} WHERE id = ?", values)
        return cur.rowcount > 0


def delete_receipt(rec_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM receipts WHERE id = ?", (rec_id,))
        return cur.rowcount > 0


def dump_csv() -> str:
    rows = all_receipts()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Date", "Vendor", "Category", "Total", "Tax", "Currency", "Invoice #", "Summary", "Filename"])
    for r in rows:
        w.writerow([
            r["date"] or "",
            r["vendor"],
            r["category"],
            f"{r['total_amount']:.2f}",
            f"{r['tax_amount']:.2f}" if r["tax_amount"] is not None else "",
            r["currency"],
            r["invoice_number"] or "",
            r["summary"],
            r["filename"]
        ])
    return out.getvalue()


def stats() -> dict:
    rows = all_receipts()
    by_curr = {}
    by_cat = {}
    total = 0.0
    for r in rows:
        c = r["currency"]
        by_curr[c] = by_curr.get(c, 0.0) + r["total_amount"]
        cat = r["category"]
        by_cat[cat] = by_cat.get(cat, 0.0) + r["total_amount"]
        total += r["total_amount"]

    return {
        "count": len(rows),
        "total": round(total, 2),
        "currencies": {k: round(v, 2) for k, v in by_curr.items()},
        "categories": {k: round(v, 2) for k, v in by_cat.items()}
    }


def seed_demo_data():
    if all_receipts():
        return
    samples = [
        {
            "filename": "invoice_digitalocean.txt",
            "vendor": "DigitalOcean, LLC",
            "date": "2026-10-01",
            "invoice_number": "IN-DO-883921",
            "currency": "USD",
            "total_amount": 48.00,
            "tax_amount": 0.00,
            "category": "Hosting & Cloud",
            "summary": "Droplets & Managed Databases - October 2026",
            "raw_text": "Sample DigitalOcean Invoice"
        },
        {
            "filename": "invoice_github.txt",
            "vendor": "GitHub, Inc.",
            "date": "2026-09-28",
            "invoice_number": "GH-2026-9812",
            "currency": "USD",
            "total_amount": 21.00,
            "tax_amount": 0.00,
            "category": "Software & Subscriptions",
            "summary": "GitHub Copilot & Team Plan Seats",
            "raw_text": "Sample GitHub Invoice"
        },
        {
            "filename": "receipt_uber_trip.txt",
            "vendor": "Uber B.V.",
            "date": "2026-10-05",
            "invoice_number": "UBER-TRIP-7491",
            "currency": "EUR",
            "total_amount": 28.50,
            "tax_amount": 2.59,
            "category": "Travel & Transport",
            "summary": "Trip to client office / Central Station",
            "raw_text": "Sample Uber Receipt"
        },
        {
            "filename": "receipt_bistrot.txt",
            "vendor": "Antico Bistrot Milano S.r.l.",
            "date": "2026-10-09",
            "invoice_number": "RT-04829104",
            "currency": "EUR",
            "total_amount": 42.00,
            "tax_amount": 3.82,
            "category": "Meals & Entertainment",
            "summary": "Client meeting lunch (2 persons)",
            "raw_text": "Sample Bistrot Receipt"
        }
    ]
    for s in samples:
        insert_receipt(s)

