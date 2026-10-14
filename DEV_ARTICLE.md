---
title: "I was tired of manual bookkeeping, so I wrote an offline receipt parser with Ollama"
published: true
tags: hf26challenge, opensource, python, ai
cover_image: https://raw.githubusercontent.com/alessiobianchini/ledgerlocal/main/screenshot.png
canonical_url: https://github.com/alessiobianchini/ledgerlocal
---

Last weekend was tax prep weekend. 

Like every quarter, I found myself sitting at my desk with an iced coffee, staring at a Downloads folder with 40-something random files: AWS invoices, Uber rides, railway tickets, client coffee receipts, and software subscriptions. And like every quarter, I was manually opening each PDF, finding the total amount, locating the VAT percentage, and typing it into a spreadsheet like a caveman.

I looked at commercial receipt scanners. They all have the same two problems:
1. They want $25 to $40 a month. I do my bookkeeping four times a year; I'm not paying a recurring \$360/year subscription for something I touch once a quarter.
2. They make you upload everything to their servers. My freelance invoices contain NDA-protected project scopes, client corporate names, and my personal card details. I am not sending all of that to an unvetted cloud API.

When I saw the Hacktoberfest Week 2 challenge theme (**"Side Hustle"**—build something with open-source AI that solves a real problem someone would actually pay for), I realized this was the perfect weekend project.

The tool is called **LedgerLocal**. It's a small local app that extracts dates, vendors, tax/VAT rates, and deduction categories from your receipts using an open-weight model running on your own machine. Zero cloud calls, zero token bills.

---

### Why this only works with open-source models

If you build this with closed APIs (like OpenAI or Claude), the product doesn't make sense:

* **The privacy wall:** The moment you tell a freelancer or a small business accountant *"just upload your client invoices to our cloud backend"*, anyone dealing with serious NDAs will say no. With a local open-weight model running through Ollama, data privacy isn't a legal promise in a privacy policy—it's physically impossible for data to leak because the packets never leave `localhost`.
* **The unit economics:** If you want to sell a utility like this as a one-time purchase (say, $20 on Gumroad) or release it as a free tool with optional paid add-ons, you can't pay \$0.03 per API call. If a user processes a backlog of 500 invoices from the past two years, cloud API fees would kill you. With local inference, processing 10 receipts or 10,000 receipts costs the exact same: $0.
* **Offline reliability:** I often do admin work while traveling on trains or flights where connection drops constantly. A local model doesn't care if you have WiFi or not.

---

### How I built it (without framework bloat)

I didn't use LangChain, LlamaIndex, or any heavy agent framework for this. For a tool like this, you don't need 15 layers of abstractions; you just need clean parsing and reliable JSON.

The pipeline is simple:

1. **Text Extraction:** When you upload a PDF or text file, `pypdf` extracts the raw text. If it's an image, it base64-encodes it.
2. **Local Inference:** It posts the raw text to Ollama running `phi4-mini:latest` (or `llama3.2-vision` if you want multimodal). `phi4-mini` is roughly 3.8B parameters, fits comfortably in 4GB of RAM, and parses an invoice on my laptop in about 2-3 seconds.
3. **Structured Output:** I used Ollama's native `format: "json"` with a strict prompt specifying standard accounting deduction categories (Software, Hosting, Meals, Travel, etc.) and explicit rules for VAT and ISO dates.
4. **Validation & Storage:** A Pydantic v2 schema validates the output and saves it into a local SQLite file (`ledger.db`).
5. **UI:** I didn't want a 500MB `node_modules` folder, so the web UI is a single `index.html` file using standard system fonts, responsive CSS, and vanilla JavaScript `fetch()`.

![LedgerLocal Dashboard](https://raw.githubusercontent.com/alessiobianchini/ledgerlocal/main/screenshot.png)

Here is the core Ollama caller from `parser.py`—just clean Python:

```python
def call_ollama(prompt: str, model: str = "phi4-mini:latest") -> dict:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.1,  # Keep it deterministic
            "num_predict": 512,
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return json.loads(res.get("response", "{}"))
```

---

### The messy reality of invoice parsing (and how I fixed it)

Building the happy path took two hours. Handling real-world receipts took the rest of the weekend:

1. **Ambiguous Dates:** Depending on where the receipt comes from, `05/06/2026` could be May 6th or June 5th. I added a regex validation check in the pipeline; if the model can't determine the date with high confidence, it falls back to `null` so you can manually select it instead of silently logging the wrong tax quarter.
2. **Italian "Documento Commerciale":** Local Italian restaurant and taxi receipts don't have an "Invoice Number"; they have an `RT` (Registratore Telematico) code like `RT: 99M102391024`. The model was initially returning `null` for invoice IDs on these. I tuned the prompt instructions to recognize fiscal printer IDs as valid document references.
3. **Multi-currency headaches:** I had receipts in USD (DigitalOcean, GitHub) and receipts in EUR (trains, lunches). My first prototype summed all numbers into one total. That obviously makes no sense, so I updated SQLite queries to separate balances by currency (`EUR: 86.33`, `USD: 69.68`).
4. **Human-in-the-loop:** No LLM is 100% accurate on messy documents. The UI includes an inline "Edit" button on every row so you can tweak any field in two seconds before exporting.

---

### Testing it on a real freelancer

To test if someone would actually use this, I sent the repo to Ale, a freelance consultant friend. I had him drop 15 of his Q3 receipts into the dashboard.

**What worked:**
* It parsed 15 invoices (PDFs and text receipts) in under 4 minutes.
* Digital invoices from Google Cloud, GitHub, and Adobe were recognized with 100% accuracy on tax rates and totals.

**What he asked for:**
* *"Can you add a CLI command? Sometimes I just want to run a terminal script against a folder without opening a browser."*
  -> Added `python -m src.cli import ./folder` and `python -m src.cli export -o expenses.csv`.
* *"Would I pay for this?"*
  His exact answer: *"I would never pay a monthly subscription for this, but if this was packaged as a standalone desktop app for €25, I'd buy it immediately just so I never have to manually type VAT numbers into Excel again."*

---

### Running it yourself

The code is completely open-source (MIT license):

👉 **GitHub:** [github.com/alessiobianchini/ledgerlocal](https://github.com/alessiobianchini/ledgerlocal)

Setup takes about 2 minutes:

```bash
git clone https://github.com/alessiobianchini/ledgerlocal.git
cd ledgerlocal
pip install -r requirements.txt

# Run the web dashboard:
python run.py

# Or use the CLI:
python -m src.cli import ./sample_data
python -m src.cli list
```

Open `http://localhost:8000`, drag your receipts in, and hit **Export CSV**.

If you're a freelancer dealing with quarterly receipts, give it a spin. If it breaks on a receipt format from your country, open an issue or submit a PR on GitHub.
