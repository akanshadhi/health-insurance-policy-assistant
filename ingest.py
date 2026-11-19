"""Steps 2 and 3: read the PDFs, clean the text, cut it into chunks.

Run from the project folder:  python ingest.py
Output: data/chunks.jsonl  (one chunk per line, with insurer, document and page)
"""
import json
import re
from collections import Counter
from pathlib import Path

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

RAW = Path("data/raw")
OUT = Path("data/chunks.jsonl")

# Label each file. Edit the keys if your file names are different.
DOCS = {
    "nivabupa_reassure3_wording.pdf": ("Niva Bupa", "ReAssure 3.0 policy wording"),
    "nivabupa_reassure3_cis.pdf": ("Niva Bupa", "ReAssure 3.0 customer information sheet"),
    "digit_supreme_wording.pdf": ("Go Digit", "Digit Supreme Care policy wording"),
    "digit_supreme_care_cis.pdf": ("Go Digit", "Digit Supreme Care customer information sheet"),
    "irdai_health_master_circular.pdf": ("IRDAI", "Master Circular on Health Insurance Business"),
}

CHUNK_WORDS = 220   # about 300 tokens
STEP_WORDS = 170    # so neighbouring chunks overlap by 50 words
EDGE_LINES = 3      # headers/footers live in the first and last few lines of a page


def normalise(line):
    """Turn 'Page 3 of 99' and 'Page 4 of 99' into the same string."""
    return re.sub(r"\d+", "#", line.strip().lower())


def read_pages(path):
    if pymupdf is not None:
        with pymupdf.open(path) as doc:
            return [page.get_text() for page in doc]
    from pypdf import PdfReader  # fallback if PyMuPDF is missing
    return [(p.extract_text() or "") for p in PdfReader(path).pages]


def edge_indexes(lines):
    """Positions of the first and last few non-empty lines of a page."""
    non_empty = [i for i, l in enumerate(lines) if l.strip()]
    return set(non_empty[:EDGE_LINES] + non_empty[-EDGE_LINES:])


def remove_repeated_lines(pages):
    """Drop headers and footers: lines at the top/bottom of many pages.

    Only the first and last few lines of each page are considered, so a real
    clause that happens to repeat in the body of the document is never removed.
    """
    if len(pages) < 5:
        return pages
    split = [text.splitlines() for text in pages]
    counts = Counter()
    for lines in split:
        counts.update({normalise(lines[i]) for i in edge_indexes(lines)})
    limit = 0.4 * len(pages)
    cleaned = []
    for lines in split:
        edges = edge_indexes(lines)
        keep = [l for i, l in enumerate(lines)
                if not (i in edges and counts[normalise(l)] > limit)]
        cleaned.append("\n".join(keep))
    return cleaned


def make_chunks(pages):
    words = []  # (word, page_number)
    for page_no, text in enumerate(pages, start=1):
        for w in text.split():
            words.append((w, page_no))
    chunks = []
    start = 0
    while start < len(words):
        window = words[start:start + CHUNK_WORDS]
        chunks.append({
            "text": " ".join(w for w, _ in window),
            "page_start": window[0][1],
            "page_end": window[-1][1],
        })
        if start + CHUNK_WORDS >= len(words):
            break
        start += STEP_WORDS
    return chunks


def main():
    pdfs = sorted(RAW.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found in data/raw/")
        return
    total = 0
    with OUT.open("w", encoding="utf-8") as f:
        for pdf in pdfs:
            insurer, doc_name = DOCS.get(pdf.name, ("Unknown", pdf.stem))
            pages = remove_repeated_lines(read_pages(pdf))
            chunks = make_chunks(pages)
            for i, c in enumerate(chunks):
                c.update({"id": f"{pdf.stem}-{i}", "insurer": insurer,
                          "document": doc_name, "file": pdf.name})
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
            total += len(chunks)
            print(f"{pdf.name}: {len(pages)} pages -> {len(chunks)} chunks")
    print(f"Done. {total} chunks saved to {OUT}")


if __name__ == "__main__":
    main()