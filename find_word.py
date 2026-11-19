"""Find every place a word appears in your chunks (exact text search, no AI).

Usage:
  python find_word.py cataract
  python find_word.py cataract "Go Digit"      (only that insurer)
"""
import json
import re
import sys
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit('Usage: python find_word.py word ["Niva Bupa" | "Go Digit" | "IRDAI"]')

word = sys.argv[1]
insurer = sys.argv[2] if len(sys.argv) > 2 else None
pattern = re.compile(re.escape(word), re.IGNORECASE)

found = 0
for line in Path("data/chunks.jsonl").open(encoding="utf-8"):
    c = json.loads(line)
    if insurer and c["insurer"] != insurer:
        continue
    m = pattern.search(c["text"])
    if m:
        found += 1
        pages = c["page_start"] if c["page_start"] == c["page_end"] else f'{c["page_start"]}-{c["page_end"]}'
        s = max(0, m.start() - 120)
        snippet = " ".join(c["text"][s:m.end() + 160].split())
        print(f'\n{c["insurer"]} | {c["document"]} | page {pages}\n   ...{snippet}...')

print(f'\n{found} chunk(s) contain "{word}"' + (f" for {insurer}" if insurer else ""))