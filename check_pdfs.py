from pathlib import Path

try:
    import fitz  # PyMuPDF

    def pages_text(path):
        with fitz.open(path) as doc:
            return [page.get_text() for page in doc]

except ImportError:
    from pypdf import PdfReader

    def pages_text(path):
        return [(p.extract_text() or "") for p in PdfReader(path).pages]


RAW = Path("data/raw")
pdfs = sorted(RAW.glob("*.pdf"))
if not pdfs:
    print("No PDFs found in data/raw/. Download them there first.")

for pdf in pdfs:
    texts = pages_text(pdf)
    total = len(texts)
    with_text = sum(1 for t in texts if len(t.strip()) > 100)
    pct = 100 * with_text / total if total else 0
    status = "OK" if pct >= 90 else "CHECK (possibly scanned)"
    print(f"{pdf.name}: {total} pages, {with_text} with text ({pct:.0f}%) -> {status}")
    if texts:
        sample = " ".join(texts[min(2, total - 1)].split())[:200]
        print(f"   sample: {sample}")