"""Offline sweep of the grounding-gate threshold (share of a quote's word 3-grams that must appear on a page read).
Uses the logged traces (pages actually read + the model's quotes) and the graded results; makes no LLM calls.
Writes logs/GROUNDING_SWEEP.md."""
import glob, json, re
from rapidagent.tools import norm_for_search

TAG = "qwen3-8b_D"


def score(quote, pages):
    q = norm_for_search(quote)
    qt = re.findall(r"\w+", q)
    if len(qt) < 3:
        return 0.0
    q_nums = set(re.findall(r"\d+(?:\.\d+)?", q))
    grams = {tuple(qt[i:i + 3]) for i in range(len(qt) - 2)}
    best = 0.0
    for t in pages:
        tn = norm_for_search(t)
        if q in tn:
            return 1.0
        if not q_nums <= set(re.findall(r"\d+(?:\.\d+)?", tn)):
            continue
        pt = re.findall(r"\w+", tn)
        pg = {tuple(pt[i:i + 3]) for i in range(len(pt) - 2)}
        best = max(best, sum(g in pg for g in grams) / len(grams))
    return best


rows = []
for s in ("real", "redteam"):
    res = json.load(open(f"logs/results_{TAG}_{s}.json", encoding="utf-8"))
    graded = {r["question"]: r for r in res["rows"]}
    pages, finals = {}, {}
    for line in open(f"logs/trace_{TAG}_{s}.jsonl", encoding="utf-8", errors="replace"):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        q = e["question"]
        if e["tool"] == "get_page" and e["status"] == "ok":
            pages.setdefault(q, []).append(e["result"])
        elif e["tool"] == "final_answer":
            finals[q] = (e["result"].get("raw") or {}, list(pages.get(q, [])))
            pages[q] = []
    for q, (raw, read) in finals.items():
        g = graded.get(q)
        if not g or raw.get("status") != "answered":
            continue
        a = (raw.get("answer") or "").lower()
        hit = lambda m: re.search(r"(?<![\w.])" + re.escape(m.lower()) + r"(?![\w])", a) is not None
        correct = g["expected"] == "answered" and all(any(hit(m) for m in grp) for grp in (g["must_contain"] or []))
        sc = max([score(str(e.get("quote", "")), read) for e in (raw.get("evidence") or []) if isinstance(e, dict)] or [0.0])
        rows.append(dict(q=q, correct=correct, score=round(sc, 2), pages_read=len(read)))

out = ["# Grounding-gate threshold sweep (strategy D, from logged traces; no LLM calls)\n",
       f"{len(rows)} answers the model marked 'answered' ({sum(r['correct'] for r in rows)} correct, "
       f"{sum(not r['correct'] for r in rows)} wrong). Score = best quote match on pages read (1.0 = verbatim).\n",
       "| 3-gram threshold | Correct answers accepted | Correct answers wrongly blocked | Wrong answers accepted | Wrong answers blocked |",
       "|---|---|---|---|---|"]
for t in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
    ca = sum(r["correct"] and r["score"] >= t for r in rows)
    cb = sum(r["correct"] and r["score"] < t for r in rows)
    wa = sum((not r["correct"]) and r["score"] >= t for r in rows)
    wb = sum((not r["correct"]) and r["score"] < t for r in rows)
    out.append(f"| {t} | {ca} | {cb} | {wa} | {wb} |")
out.append("\nPer-answer scores: " + ", ".join(f"{'✓' if r['correct'] else '✗'}{r['score']}" for r in sorted(rows, key=lambda r: r["score"])))
open("logs/GROUNDING_SWEEP.md", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("\n".join(out))
