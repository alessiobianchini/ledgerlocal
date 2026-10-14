import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

import db
import parser

app = FastAPI(title="ledgerlocal")

db.init_db()

STATIC_DIR = Path(__file__).parent / "static"


class EditRequest(BaseModel):
    vendor: str
    date: str | None = None
    invoice_number: str | None = None
    currency: str = "EUR"
    total_amount: float
    tax_amount: float | None = None
    category: str = "Other"
    summary: str = ""


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/ping")
def ping():
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as r:
            return {"status": "ok", "ollama": True}
    except Exception:
        return {"status": "warning", "ollama": False}


@app.get("/api/receipts")
def list_receipts():
    return {
        "receipts": db.all_receipts(),
        "stats": db.stats(),
        "categories": parser.CATEGORIES
    }


@app.post("/api/upload")
async def upload(files: List[UploadFile] = File(...)):
    parsed = []
    errors = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for f in files:
            tmp_path = Path(tmpdir) / f.filename
            with open(tmp_path, "wb") as buffer:
                shutil.copyfileobj(f.file, buffer)

            try:
                text = parser.extract_text(tmp_path)
                data = parser.parse_with_ollama(text, f.filename)
                saved = db.insert_receipt(data)
                parsed.append(saved)
            except Exception as e:
                errors.append({"file": f.filename, "error": str(e)})

    return {"uploaded": parsed, "errors": errors}


@app.put("/api/receipts/{rec_id}")
def update(rec_id: str, req: EditRequest):
    ok = db.update_receipt(rec_id, req.model_dump())
    if not ok:
        raise HTTPException(404, "Receipt not found")
    return {"ok": True}


@app.delete("/api/receipts/{rec_id}")
def delete(rec_id: str):
    ok = db.delete_receipt(rec_id)
    if not ok:
        raise HTTPException(404, "Receipt not found")
    return {"ok": True}


@app.get("/api/export")
def export():
    csv_str = db.dump_csv()
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"}
    )
