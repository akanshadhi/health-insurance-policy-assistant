"""Step 7: run every test question through the app and score the results.

Usage:
  python run_eval.py baseline            run all questions, save data/results_baseline.csv
  python run_eval.py baseline 5          run only the first 5 questions (quick test)
  python run_eval.py score baseline      re-score after you fill the 'correct' column (y/n)

Input:  eval_questions.csv  (id, type, insurer, question, expected_behavior,
                             expected_answer, expected_pages)
Scores:
  retrieval hit rate : did a retrieved chunk contain an expected page?
  refusal accuracy   : did the app refuse exactly when it should?
  correctness        : your own y/n judgement, in the 'correct' column of the results file
"""
import csv
import re
import sys
import time
from pathlib import Path

import answer as app   # answer.py: retrieve, build_prompt, ask_llm

QUESTIONS = Path("eval_questions.csv")
REFUSAL_TEXT = "i could not find this in the policy documents"
PAUSE = 1.0   # seconds between questions, to stay inside free-tier limits


def parse_pages(text):
    """'30' -> {30};  '30-31' -> {30,31};  '12, 45-46' -> {12,45,46}"""
    pages = set()
    for part in re.split(r"[;,]", text or ""):
        part = part.strip()
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if m:
            pages.update(range(int(m.group(1)), int(m.group(2)) + 1))
        elif part.isdigit():
            pages.add(int(part))
    return pages


def retrieved_pages(hits):
    pages = set()
    for _, meta in hits:
        pages.update(range(meta["page_start"], meta["page_end"] + 1))
    return pages


def run(label, limit=None):
    app.load_env_file()
    with QUESTIONS.open(encoding="utf-8-sig", newline="") as f:
        questions = list(csv.DictReader(f))
    if limit:
        questions = questions[:limit]

    results = []
    for i, q in enumerate(questions, start=1):
        insurer = q["insurer"].strip() or None
        started = time.time()
        hits = app.retrieve(q["question"], insurer)
        try:
            reply = app.ask_llm(app.build_prompt(q["question"], hits)).strip()
        except SystemExit as e:           # ask_llm gives up with sys.exit
            reply = f"ERROR: {e}"
        refused = REFUSAL_TEXT in reply.lower()

        expected = parse_pages(q["expected_pages"])
        if expected and insurer:
            hit = "yes" if expected & retrieved_pages(hits) else "no"
        else:
            hit = ""                      # nothing to check (refuse rows, comparisons)

        behavior = q["expected_behavior"].strip().lower()
        should_refuse = behavior == "refuse"
        refusal_ok = "yes" if refused == should_refuse else "no"

        results.append({
            "id": q["id"], "type": q["type"], "insurer": q["insurer"],
            "question": q["question"], "expected_behavior": behavior,
            "expected_answer": q["expected_answer"], "expected_pages": q["expected_pages"],
            "app_answer": reply, "refused": "yes" if refused else "no",
            "refusal_ok": refusal_ok, "retrieval_hit": hit,
            "correct": "", "seconds": f"{time.time() - started:.1f}",
        })
        print(f"[{i}/{len(questions)}] {q['id']}  refusal_ok={refusal_ok}  hit={hit or '-'}")
        time.sleep(PAUSE)

    out = Path("data") / f"results_{label}.csv"
    save(out, results)
    print(f"\nSaved {out}")
    summarise(results)


def save(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def pct(num, den):
    return f"{num}/{den} = {100 * num / den:.0f}%" if den else "n/a"


def summarise(rows):
    hits = [r for r in rows if r["retrieval_hit"]]
    refusal = [r for r in rows if r["refusal_ok"]]
    graded = [r for r in rows if r.get("correct", "").strip().lower() in ("y", "n")]
    print("\n===== SCORES =====")
    print("Retrieval hit rate :", pct(sum(r["retrieval_hit"] == "yes" for r in hits), len(hits)))
    print("Refusal accuracy   :", pct(sum(r["refusal_ok"] == "yes" for r in refusal), len(refusal)))
    print("Correct answers    :", pct(sum(r["correct"].strip().lower() == "y" for r in graded), len(graded)),
          "(only rows you graded)")
    types = sorted({r["type"] for r in rows})
    print("\nBy type (refusal accuracy):")
    for t in types:
        sub = [r for r in rows if r["type"] == t]
        print(f"  {t:13s}", pct(sum(r["refusal_ok"] == "yes" for r in sub), len(sub)))
    avg = sum(float(r["seconds"]) for r in rows) / len(rows)
    print(f"\nAverage time per question: {avg:.1f}s")


def rescore(label):
    path = Path("data") / f"results_{label}.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        summarise(list(csv.DictReader(f)))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "score" and len(args) > 1:
        rescore(args[1])
    else:
        run(args[0], int(args[1]) if len(args) > 1 else None)