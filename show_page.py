"""Print the text of one PDF page, exactly as our code reads it.

Usage:
  python show_page.py digit_supreme_wording.pdf 68
"""
import sys
from pathlib import Path

if len(sys.argv) < 3:
    sys.exit("Usage: python show_page.py <file name in data/raw> <page number>")

path = Path("data/raw") / sys.argv[1]
page_no = int(sys.argv[2])

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

if pymupdf is not None:
    with pymupdf.open(path) as doc:
        text = doc[page_no - 1].get_text()
else:
    from pypdf import PdfReader
    text = PdfReader(path).pages[page_no - 1].extract_text() or ""

print(f"----- {sys.argv[1]}, page {page_no} -----")
print(text)