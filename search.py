"""Try the search without any LLM yet.

Usage:
  python search.py "what is the waiting period for cataract"
  python search.py "room rent limit" "Go Digit"      (only that insurer)

Insurer names: "Niva Bupa", "Go Digit", "IRDAI"
"""
import sys

import chromadb
from chromadb.utils import embedding_functions

TOP_K = 5

if len(sys.argv) < 2:
    print('Usage: python search.py "your question" ["Niva Bupa" | "Go Digit" | "IRDAI"]')
    sys.exit(1)

question = sys.argv[1]
insurer = sys.argv[2] if len(sys.argv) > 2 else None

client = chromadb.PersistentClient(path="data/chroma")
collection = client.get_collection(
    "policies", embedding_function=embedding_functions.DefaultEmbeddingFunction()
)

result = collection.query(
    query_texts=[question],
    n_results=TOP_K,
    where={"insurer": insurer} if insurer else None,
)

print(f"\nQuestion: {question}" + (f"   [{insurer} only]" if insurer else ""))
for rank, (doc, meta, dist) in enumerate(
    zip(result["documents"][0], result["metadatas"][0], result["distances"][0]), start=1
):
    pages = (str(meta["page_start"]) if meta["page_start"] == meta["page_end"]
             else f'{meta["page_start"]}-{meta["page_end"]}')
    print(f'\n#{rank}  distance {dist:.3f}  |  {meta["insurer"]} - {meta["document"]}  |  page {pages}')
    print("    " + doc[:350].replace("\n", " ") + " ...")