import os
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

IS_RENDER = os.getenv("RENDER") == "true"
if IS_RENDER:
    db.seed_demo_data()

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
    ollama_ok = False
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as r:
            ollama_ok = True
    except Exception:
        ollama_ok = False

    return {
        "status": "ok",
        "ollama": ollama_ok,
        "render": IS_RENDER
    }


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
                err_msg = str(e)
                if IS_RENDER and ("11434" in err_msg or "Connection refused" in err_msg or "WinError" in err_msg or "urlopen error" in err_msg):
                    err_msg = "Cloud Demo Mode: Local Ollama is unreachable on this cloud instance. LedgerLocal's architecture guarantees 100% data confidentiality by running Gemma 2 locally on your own laptop or local GPU server."
                errors.append({"file": f.filename, "error": err_msg})

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
