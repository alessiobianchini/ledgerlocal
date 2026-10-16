---
title: "I was tired of manual bookkeeping, so I wrote an offline receipt parser with Ollama"
published: true
tags: devchallenge, hf26challenge, opensource, python
cover_image: https://raw.githubusercontent.com/alessiobianchini/ledgerlocal/main/screenshot.png
canonical_url: https://github.com/alessiobianchini/ledgerlocal
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)*

## What I Built

Every quarter, freelancers and indie consultants go through the exact same nightmare: a Downloads folder filled with random files—AWS invoices, Uber trip slips, railway tickets, client coffee receipts, and software renewals. 

You end up sitting at your desk opening each file, finding the net amount, hunting down the VAT percentage, and manually typing it into a spreadsheet. 

Commercial scanners exist, but they have two dealbreakers:
1. **Subscription pricing:** They charge $25 to $40 a month. Freelancers only do bookkeeping four times a year; nobody wants to pay $360/year for something they use once a quarter.
2. **The privacy risk:** They require uploading every document to a third-party cloud. For freelancers working under client NDAs, uploading invoices with confidential project scopes and client company names to an unvetted cloud API is an immediate no-go.

I built **LedgerLocal**: a 100% offline invoice and receipt parser powered by local open-weight models running on your own machine. It extracts dates, vendors, tax/VAT rates, and tax deduction categories into a local SQLite database, lets you verify and edit anything in an interactive dashboard, and exports a clean CSV ready for your accountant.

Who would pay for it? Freelancers, contractors, and boutique agencies who want automated expense sorting without paying monthly SaaS subscriptions or exposing NDA-protected client data to cloud providers.

## Demo

![LedgerLocal Dashboard](https://raw.githubusercontent.com/alessiobianchini/ledgerlocal/main/screenshot.png)

The workflow is simple:
1. Drag and drop any folder of invoices or receipts (PDFs, text files, markdown) into the browser window.
2. The local model extracts the financial fields into a structured JSON payload in 2-3 seconds per file.
3. Review your expenses in a compact ledger table with inline edit buttons for quick human verification.
4. Click **Export CSV** to generate a clean, categorized ledger.

## Code

{% github alessiobianchini/ledgerlocal %}

👉 Direct GitHub link: [github.com/alessiobianchini/ledgerlocal](https://github.com/alessiobianchini/ledgerlocal)

The project is completely open source under the MIT license. You can run it locally with:

```bash
git clone https://github.com/alessiobianchini/ledgerlocal.git
cd ledgerlocal
pip install -r requirements.txt
python run.py
```

## How I Built It

I deliberately avoided large orchestration frameworks like LangChain or LlamaIndex. For an offline utility, you don't need heavyweight abstractions; you need predictable parsing and fast execution.

### Architecture
- **Inference Runtime:** [Ollama](https://ollama.ai) running Google's open-weight **Gemma 2 2B** (`gemma2:2b`). At just ~1.6GB of RAM, it runs blazingly fast on standard laptops and extracts structured financial data in ~1-2 seconds per invoice.
- **Text Extraction:** `pypdf` extracts text from digital invoices. Plain text and markdown files are read directly.
- **Backend:** Python + FastAPI for local endpoints (`/api/upload`, `/api/receipts`, `/api/export`).
- **Database:** Standard SQLite (`ledger.db`) via Python's native `sqlite3` module with zero ORM overhead.
- **Frontend:** A single-file `static/index.html` built with responsive, high-density CSS and vanilla JavaScript `fetch()`. No `node_modules` or build step required.

Here is the core extraction function from `parser.py`:

```python
def parse_with_ollama(text: str, filename: str, model: str = "gemma2:2b") -> dict:
    truncated = text[:5000]
    payload = {
        "model": model,
        "prompt": EXTRACTION_PROMPT + truncated,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.1,  # Keep output deterministic
            "num_predict": 512
        }
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return json.loads(res.get("response", "{}"))
```

### Real-World Parsing Challenges
Handling real invoices required several practical fixes:
* **Vendor vs. Buyer Ambiguity:** On European invoices, the model initially picked the customer name under *"Intestatario / Billed To"* instead of the actual vendor. I tuned the prompt rules to explicitly distinguish between issuer (*Cedente/Prestatore*) and client.
* **Date Formats:** To prevent misinterpreting `05/06/2026` (May vs. June), regex validation ensures dates strictly match `YYYY-MM-DD` or fall back to manual review.
* **Fiscal Printer Codes:** Italian receipts often lack standard "Invoice Numbers" and instead print a Registratore Telematico (`RT`) code. The prompt instructions were adjusted to treat fiscal printer codes as valid reference IDs.
* **Multi-Currency Totals:** Grouped summary calculations by currency (EUR, USD) so exchange rates don't distort accountant reports.

## Why Does Open Innovation Matter?

Open-source AI wasn't just an implementation choice; it is the entire foundation that makes this tool viable:

1. **Privacy as an Absolute Guarantee:** Invoices contain bank details, customer names, and project deliverables. Running open-weight models locally means data privacy isn't governed by a cloud provider's terms of service—it is physically guaranteed because packets never leave `localhost`.
2. **Sustainable Unit Economics:** A micro-utility sold as a one-time tool (e.g. $25 on Gumroad) cannot pay $0.02-$0.05 per API call. If a user imports 1,000 backlogged receipts, cloud API fees would instantly erase any profit margin. With local inference, processing 10 receipts or 10,000 receipts costs exactly $0.00.
3. **Offline Reliability:** Many freelancers work while traveling on trains or flights without reliable internet. A local model operates completely offline without network latency or rate limits.

## My First User

To test if someone would actually use this in the real world, I shared LedgerLocal with Ale, a freelance consultant.

I had him run 15 of his Q3 receipts through the system:
* **The Good:** It parsed all 15 invoices (DigitalOcean, GitHub, train tickets, client lunches) in under 4 minutes with 100% accuracy on digital PDF totals and tax rates.
* **The Feedback:** He requested a terminal workflow for fast scripting, which led to the creation of `cli.py` (`python cli.py import ./folder` and `python cli.py export`).
* **Would he pay?** His feedback: *"I'd never pay a monthly subscription because I only touch bookkeeping four times a year. But a €25 standalone offline desktop tool that spares me from manually typing VAT numbers into Excel? I'd buy that immediately."*

## Prize Categories

- **Best Use of Gemma**: LedgerLocal uses Google's open-weight Gemma 2 model (`gemma2:2b` via Ollama) as its core offline inference engine to parse sensitive invoices and receipts with zero API fees, sub-2-second latency, and total client data confidentiality.

