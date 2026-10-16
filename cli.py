import argparse
import os
from pathlib import Path
import sentry_sdk


import db
import parser

SENTRY_DSN = os.getenv("SENTRY_DSN", "https://d1119d5c1aba5b3a09053e8ff629f481@o4512266577575936.ingest.de.sentry.io/4512266587471952")
if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=1.0, send_default_pii=True)

db.init_db()



def cmd_import(path: str):
    p = Path(path)
    files = [p] if p.is_file() else [f for f in p.iterdir() if f.is_file() and f.suffix.lower() in {".pdf", ".txt", ".md", ".csv"}]
    print(f"[*] Processing {len(files)} file(s)...")
    for f in files:
        try:
            text = parser.extract_text(f)
            data = parser.parse_with_ollama(text, f.name)
            db.insert_receipt(data)
            print(f"  [+] {data['vendor']} | {data['date'] or 'No date'} | {data['total_amount']:.2f} {data['currency']} | {data['category']}")
        except Exception as e:
            print(f"  [-] Failed {f.name}: {e}")


def cmd_list():
    rows = db.all_receipts()
    if not rows:
        print("No expenses recorded.")
        return
    for r in rows:
        print(f"{(r['date'] or '-'):<12} | {r['vendor'][:22]:<22} | {r['total_amount']:>7.2f} {r['currency']} | {r['category']}")


def cmd_export(output: str):
    csv_str = db.dump_csv()
    Path(output).write_text(csv_str, encoding="utf-8")
    print(f"[+] Wrote CSV to {output}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="ledgerlocal - local receipt parser")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_imp = sub.add_parser("import")
    p_imp.add_argument("path")

    sub.add_parser("list")

    p_exp = sub.add_parser("export")
    p_exp.add_argument("-o", "--output", default="expenses.csv")

    args = p.parse_args()
    if args.cmd == "import":
        cmd_import(args.path)
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "export":
        cmd_export(args.output)
