#!/bin/bash
set -e

cd /app

apt-get update -qq && apt-get install -y -qq tesseract-ocr

cat > document_processor.py << 'PYEOF'
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "numpy==2.3.2",
#     "opencv-python==4.11.0.86",
#     "packaging==25.0",
#     "pandas==2.3.2",
#     "pillow==11.3.0",
#     "pymupdf==1.25.2",
#     "pytesseract==0.3.13",
#     "python-dateutil==2.9.0.post0",
#     "pytz==2025.2",
#     "six==1.17.0",
#     "tzdata==2025.2",
# ]
# ///

import csv
import re
from pathlib import Path
from typing import Union

import fitz  # PyMuPDF
import pytesseract
from PIL import Image


DOCUMENTS_DIR = Path("/app/documents")
INVOICES_DIR = Path("/app/invoices")
OTHER_DIR = Path("/app/other")

STRONG_INVOICE_PATTERNS = [
    r"invoice\s+no[:\s]",
    r"invoice\s+number[:\s]",
    r"^invoice$",
    r"date\s+of\s+issue[:\s]",
    r"total\s+\$",
    r"totalprice",
    r"vat\s+\[%\]",
    r"gross\s+worth",
    r"net\s+worth",
    r"seller[:\s].*client[:\s]",
]

NON_INVOICE_PATTERNS = [
    r"memorandum",
    r"stock\s+report",
    r"purchase\s+order",
    r"interoffice",
    r"secret",
    r"confidential",
    r"category\s*:\s*produce",
]

FINANCIAL_INDICATORS = [
    "total", "amount", "price", "cost", "tax", "vat",
    "qty", "quantity", "payment", "due",
]

FINANCIAL_INDICATOR_THRESHOLD = 4


def extract_text_from_image(image_path: Path) -> str:
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image, config="--psm 6")
    return text.strip()


def extract_text_from_pdf(pdf_path: Path) -> str:
    doc = fitz.open(str(pdf_path))
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


def extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in (".jpg", ".jpeg", ".png", ".tiff", ".bmp"):
        return extract_text_from_image(file_path)
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    return ""


def classify_document(text: str) -> str:
    text_lower = text.lower()

    for pattern in STRONG_INVOICE_PATTERNS:
        if re.search(pattern, text_lower):
            return "invoice"

    for pattern in NON_INVOICE_PATTERNS:
        if re.search(pattern, text_lower):
            return "other"

    indicator_count = sum(
        1 for indicator in FINANCIAL_INDICATORS if indicator in text_lower
    )
    if indicator_count >= FINANCIAL_INDICATOR_THRESHOLD:
        return "invoice"

    return "other"


def parse_european_amount(raw: str) -> float:
    return float(raw.replace(" ", "").replace(",", "."))


def extract_financial_data(text: str) -> dict[str, Union[float, str]]:
    total_amount: Union[float, str] = ""
    vat_amount: Union[float, str] = ""

    # Pattern: "Total $ 5 640,17 $ 564,02 $ 6 204,19" (net, vat, gross)
    total_line_match = re.search(
        r"Total\s+\$\s*([0-9\s]+,\d{2})\s+\$\s*([0-9\s]+,\d{2})\s+\$\s*([0-9\s]+,\d{2})",
        text,
    )
    if total_line_match:
        try:
            vat_amount = parse_european_amount(total_line_match.group(2))
            total_amount = parse_european_amount(total_line_match.group(3))
        except (ValueError, IndexError):
            pass

    # Pattern: "Total: $9963" or "Total $9963"
    if not total_amount:
        simple_total_match = re.search(
            r"Total[:]*\s*\$\s*([0-9,]+\.?\d{0,2})", text, re.IGNORECASE
        )
        if simple_total_match:
            try:
                total_amount = float(simple_total_match.group(1).replace(",", ""))
            except ValueError:
                pass

    # Pattern: "TotalPrice\n440.0"
    if not total_amount:
        totalprice_match = re.search(
            r"TotalPrice\s*\n?\s*([0-9,]+\.?\d{0,2})", text, re.IGNORECASE
        )
        if totalprice_match:
            try:
                total_amount = float(totalprice_match.group(1).replace(",", ""))
            except ValueError:
                pass

    # VAT from summary line: "10% 5 640,17 564,02 6 204,19"
    if not vat_amount:
        summary_match = re.search(
            r"10%\s+([0-9\s]+,\d{2})\s+([0-9\s]+,\d{2})\s+([0-9\s]+,\d{2})", text
        )
        if summary_match:
            try:
                vat_amount = parse_european_amount(summary_match.group(2))
                if not total_amount:
                    total_amount = parse_european_amount(summary_match.group(3))
            except (ValueError, IndexError):
                pass

    # Special case: both "Total" and "Amount Due" present — prefer Total
    if re.search(r"total.*amount\s+due", text, re.IGNORECASE | re.DOTALL):
        total_match = re.search(
            r"Total[:]*\s*\$\s*([0-9,]+\.?\d{0,2})", text, re.IGNORECASE
        )
        if total_match:
            try:
                total_amount = float(total_match.group(1).replace(",", ""))
            except ValueError:
                pass

    return {"total_amount": total_amount, "vat_amount": vat_amount}


def process_documents() -> list[dict]:
    INVOICES_DIR.mkdir(exist_ok=True)
    OTHER_DIR.mkdir(exist_ok=True)

    results: list[dict] = []

    for file_path in DOCUMENTS_DIR.iterdir():
        if not file_path.is_file():
            continue

        print(f"Processing {file_path.name}...")
        text = extract_text(file_path)
        doc_type = classify_document(text)

        if doc_type == "invoice":
            dest_path = INVOICES_DIR / file_path.name
            financial_data = extract_financial_data(text)
            results.append(
                {
                    "filename": file_path.name,
                    "type": "invoice",
                    "total_amount": financial_data["total_amount"],
                    "vat_amount": financial_data["vat_amount"],
                }
            )
        else:
            dest_path = OTHER_DIR / file_path.name
            results.append({"filename": file_path.name, "type": "other"})

        file_path.rename(dest_path)

    return results


def create_summary_csv(results: list[dict]) -> None:
    invoice_results = [r for r in results if r["type"] == "invoice"]
    csv_path = INVOICES_DIR / "summary.csv"

    total_sum = 0.0
    vat_sum = 0.0

    with open(csv_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["filename", "total_amount", "vat_amount"])

        for result in invoice_results:
            total_amount = result["total_amount"]
            vat_amount = result["vat_amount"]

            writer.writerow([result["filename"], total_amount, vat_amount])

            if isinstance(total_amount, float):
                total_sum += total_amount
            if isinstance(vat_amount, float):
                vat_sum += vat_amount

        writer.writerow(["total", round(total_sum, 2), round(vat_sum, 2)])


def main() -> None:
    results = process_documents()
    create_summary_csv(results)

    invoice_count = sum(1 for r in results if r["type"] == "invoice")
    other_count = sum(1 for r in results if r["type"] == "other")
    print(f"Processed {len(results)} documents: {invoice_count} invoices, {other_count} other")


if __name__ == "__main__":
    main()
PYEOF

uv run document_processor.py
