"""Step 5: search the policies, then let Gemini write a plain-language answer.

Usage:
  python answer.py "Is cataract surgery covered in the first year?"
  python answer.py "What is the room rent limit?" "Go Digit"      (only that insurer)

Needs:  pip install google-genai
Key:    put  GEMINI_API_KEY=your_key_here  in a file called .env (same folder)
"""
import os
import sys
import time
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]
TOP_K = 8            # chunks fetched when one insurer is chosen
PER_INSURER_K = 4    # chunks fetched from EACH insurer when none is chosen
INSURERS = ["Niva Bupa", "Go Digit"]

SYSTEM_PROMPT = """You help people understand Indian health insurance policies.
You are given numbered excerpts from policy documents. Follow these rules strictly:
1. Answer ONLY from the excerpts. Never use outside knowledge and never guess.
2. Use simple words that a person with no insurance knowledge can follow.
3. After each fact, cite the excerpt in square brackets, like [2]. Name the insurer when it matters.
4. If different insurers say different things, say what each one says separately.
5. If the excerpts answer only part of the question, give the part they answer and say clearly what is missing (for example: "the number of months is not in the policy wording, it is in your Policy Schedule"). Only if the excerpts contain nothing relevant, reply exactly:
   "I could not find this in the policy documents I have." and stop. Do not guess.
6. Numbers (days, months, percentages, rupee amounts) must be copied exactly from the excerpts.
7. Keep the answer short: at most 6 sentences.
End every answer with: "This is information from the documents, not insurance or legal advice. Please confirm with your insurer."
"""


def load_env_file():
    """Read GEMINI_API_KEY from a .env file so the key never goes into the code."""
    env = Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def page_label(meta):
    if meta["page_start"] == meta["page_end"]:
        return str(meta["page_start"])
    return f'{meta["page_start"]}-{meta["page_end"]}'



def retrieve(question, insurer=None):
    client = chromadb.PersistentClient(path="data/chroma")
    collection = client.get_collection(
        "policies", embedding_function=embedding_functions.DefaultEmbeddingFunction()
    )
    # With no insurer chosen, search each insurer separately so comparison
    # questions get excerpts from both policies, not just the closest one.
    searches = [(insurer, TOP_K)] if insurer else [(name, PER_INSURER_K) for name in INSURERS]
    wanted = []
    for name, k in searches:
        result = collection.query(query_texts=[question], n_results=k, where={"insurer": name})
        # Add the chunk before and after every hit, so a list and the sentence that
        # explains it are never separated by a chunk boundary.
        for chunk_id in result["ids"][0]:
            stem, number = chunk_id.rsplit("-", 1)
            for n in (int(number) - 1, int(number), int(number) + 1):
                neighbour = f"{stem}-{n}"
                if n >= 0 and neighbour not in wanted:
                    wanted.append(neighbour)
    found = collection.get(ids=wanted)
    by_id = dict(zip(found["ids"], zip(found["documents"], found["metadatas"])))
    return [by_id[i] for i in wanted if i in by_id]
    


def build_prompt(question, hits):
    parts = []
    for n, (doc, meta) in enumerate(hits, start=1):
        parts.append(
            f'[{n}] {meta["insurer"]} - {meta["document"]} (page {page_label(meta)})\n{doc}'
        )
    excerpts = "\n\n".join(parts)
    return f"EXCERPTS:\n{excerpts}\n\nQUESTION: {question}"


def ask_llm(prompt):
    try:
        from google import genai
        from google.genai import errors, types
    except ImportError:
        sys.exit("Missing library. Run:  pip install google-genai")

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("No API key found. Create a file named .env containing:\n"
                 "GEMINI_API_KEY=your_key_here")

    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(
            timeout=60000,  # give up after 30 seconds (the value is in milliseconds)
            retry_options=types.HttpRetryOptions(attempts=1),  # no hidden retries
        ),
    )
    last_error = None
    for attempt in range(3):
        for model in MODELS:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.1,
                    ),
                )
                print(f"(answered by {model})")
                return response.text
            except errors.APIError as e:
                last_error = e
                if e.code in (404, 429, 500, 503, 504):   # overloaded or unknown: try the next model
                    print(f"({model} unavailable: {e.code}, trying next)")
                    continue
                raise
            except Exception as e:                        # timeouts and network problems
                last_error = e
                print(f"({model} failed: {type(e).__name__}, trying next)")
                continue
        time.sleep(5)
    sys.exit(f"All models failed. Last error: {last_error}")
    


def main():
    if len(sys.argv) < 2:
        sys.exit('Usage: python answer.py "your question" ["Niva Bupa" | "Go Digit" | "IRDAI"]')
    question = sys.argv[1]
    insurer = sys.argv[2] if len(sys.argv) > 2 else None

    load_env_file()
    t0 = time.time()
    hits = retrieve(question, insurer)
    t1 = time.time()
    answer = ask_llm(build_prompt(question, hits))
    t2 = time.time()

    print(f"\nQuestion: {question}" + (f"   [{insurer} only]" if insurer else ""))
    print("\n" + answer.strip())
    print("\nSources:")
    for n, (_, meta) in enumerate(hits, start=1):
        print(f'  [{n}] {meta["insurer"]} - {meta["document"]}, page {page_label(meta)}')
    print(f"\nTime: search {t1 - t0:.1f}s, Gemini {t2 - t1:.1f}s")

if __name__ == "__main__":
    main()