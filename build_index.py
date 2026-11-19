"""Step 4: turn every chunk into numbers (embeddings) and store them in Chroma.

Run from the project folder:  python build_index.py
Needs:  pip install chromadb
Input:  data/chunks.jsonl   (made by ingest.py)
Output: data/chroma/        (the searchable index)

The first run downloads a small embedding model (about 80 MB). After that it
works offline. Safe to re-run: it rebuilds the index from scratch each time.
"""
import json
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

CHUNKS = Path("data/chunks.jsonl")
DB_DIR = "data/chroma"
COLLECTION = "policies"
BATCH = 64


def main():
    if not CHUNKS.exists():
        print("data/chunks.jsonl not found. Run python ingest.py first.")
        return

    rows = [json.loads(line) for line in CHUNKS.open(encoding="utf-8")]
    print(f"Loaded {len(rows)} chunks")

    client = chromadb.PersistentClient(path=DB_DIR)
    try:
        client.delete_collection(COLLECTION)  # start fresh on every run
    except Exception:
        pass
    collection = client.create_collection(
        name=COLLECTION,
        embedding_function=embedding_functions.DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )

    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        collection.add(
            ids=[r["id"] for r in batch],
            documents=[r["text"] for r in batch],
            metadatas=[{
                "insurer": r["insurer"],
                "document": r["document"],
                "file": r["file"],
                "page_start": r["page_start"],
                "page_end": r["page_end"],
            } for r in batch],
        )
        print(f"  indexed {min(i + BATCH, len(rows))}/{len(rows)}")

    print(f"Done. {collection.count()} chunks stored in {DB_DIR}")


if __name__ == "__main__":
    main()