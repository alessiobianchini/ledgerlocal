import json
import logging
import re
import urllib.request
from pathlib import Path
from pypdf import PdfReader

log = logging.getLogger("ledgerlocal.parser")

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "phi4-mini:latest"

CATEGORIES = [
    "Software & Subscriptions",
    "Hosting & Cloud Infrastructure",
    "Hardware & Office Supplies",
    "Travel & Transportation",
    "Meals & Client Entertainment",
    "Professional & Legal Services",
    "Marketing & Advertising",
    "Utilities & Internet",
    "Other"
]

EXTRACTION_PROMPT = """Extract the financial fields from this invoice or receipt into a single JSON object.

Allowed categories:
- Software & Subscriptions
- Hosting & Cloud Infrastructure
- Hardware & Office Supplies
- Travel & Transportation
- Meals & Client Entertainment
- Professional & Legal Services
- Marketing & Advertising
- Utilities & Internet
- Other

Rules:
- date: YYYY-MM-DD format if clearly present, otherwise null.
- total_amount: float (e.g. 42.50). Remove currency signs.
- tax_amount: float for VAT/tax/IVA if listed, otherwise null.
- currency: ISO 3-letter code (EUR, USD, GBP, etc.).
- invoice_number: invoice, order, or fiscal receipt (RT) code, or null.
- category: pick the best matching category from the list above.
- summary: one brief phrase describing what was bought.

Return only valid JSON matching this schema:
{
  "vendor": "Company name",
  "date": "YYYY-MM-DD",
  "invoice_number": "INV-123",
  "currency": "EUR",
  "total_amount": 0.0,
  "tax_amount": 0.0,
  "category": "Software & Subscriptions",
  "summary": "Monthly server subscription"
}

DOCUMENT TEXT:
"""


def extract_text(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(str(file_path))
        pages = [p.extract_text() or "" for p in reader.pages]
        return "\n".join(pages).strip()
    
    if ext in {".txt", ".md", ".csv", ".json", ".log"}:
        return file_path.read_text(encoding="utf-8", errors="replace").strip()
    
    raise ValueError(f"Unsupported extension: {ext}")


def parse_with_ollama(text: str, filename: str, model: str = DEFAULT_MODEL) -> dict:
    if not text:
        raise ValueError(f"No text could be extracted from {filename}")

    # Truncate overly long documents to save context window
    truncated = text[:4000]
    payload = {
        "model": model,
        "prompt": EXTRACTION_PROMPT + truncated,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 350
        }
    }

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        raw = res.get("response", "{}")
        data = json.loads(raw)

    # Sanitize and normalize values
    date_val = data.get("date")
    if date_val and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date_val)):
        date_val = None

    try:
        total = float(data.get("total_amount") or 0.0)
    except (ValueError, TypeError):
        total = 0.0

    try:
        tax = float(data.get("tax_amount")) if data.get("tax_amount") is not None else None
    except (ValueError, TypeError):
        tax = None

    cat = data.get("category")
    if cat not in CATEGORIES:
        cat = "Other"

    return {
        "filename": filename,
        "vendor": data.get("vendor") or Path(filename).stem,
        "date": date_val,
        "invoice_number": data.get("invoice_number"),
        "currency": (data.get("currency") or "EUR").upper(),
        "total_amount": round(total, 2),
        "tax_amount": round(tax, 2) if tax is not None else None,
        "category": cat,
        "summary": data.get("summary") or filename,
        "raw_text": truncated[:1000]
    }
