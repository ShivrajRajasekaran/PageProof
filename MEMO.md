# PageProof — Memo · Team SOUL SOCIETY (RAP Hackathon 2026, Budgeted Document-Answering Agent)

**PageProof answers questions on any uploaded PDF with only the four permitted tools in 6 tool calls + 1 answer call, fully locally (`qwen3:8b`, Ollama, 8 GB laptop GPU); no document leaves the machine.**

## Architecture
```
Streamlit chat ─► DocAgent.ask() (hand-written loop, no framework)
 ─► BudgetedToolbox (logs every call; #7 refused)
 ─► list_documents, list_headings, get_page, search_keyword (page numbers only)
 ─► DocStore (outline only at upload; page text read per call)
 ─► final_answer gates ① quote grounding ② confidence ≥ 0.4, else "insufficient information"
```

## What we did and why
- **The harness, not the prompt, enforces the budget**—small models ignore numeric limits. At most 7 LLM calls per question (6 tool turns + 1 tool-free answer); failed calls count (conservative reading).
- **Strategy D, "PageProof hybrid" (proposed).** Turn 1: outline + keyword search (two calls); then 1–3 page reads, one call reserved for continuation or amendment.
- **Headings without a TOC.** Embedded outline, else font size/bold vs body text, minus running headers.
- **Lexical search only.** Substring match after repairing ligatures (ﬁ/ﬂ), hyphens and lost spaces, then looser word matches; tolerates long queries and typos ("Peppert").
- **Decline check (D).** The 8B model gave up early: a decline with budget and unread search hits left is refused once (naming them); a second stands.
- **Grounding gate.** ≥1 quote must match a page fetched for this question—verbatim, or 80% of word 3-grams with every number present—blocking memory answers and invented quotes ("refund window is 30 days"). `grounding_sweep.py` (no LLM calls), replayed on all benchmark answers, set 0.8: 0.5–0.8 keep every correctly quoted answer, 0.9 or verbatim-only wrongly blocks 1–2 more, so 0.8 is the strictest lossless value.
- **Confidence 0.4** is a backstop: answer only if P > λ/(1+λ), i.e. a wrong answer costs about ⅔ of a right one; qwen3:8b reported 0.95–1.0 on every answer, even wrong ones, so it isn't trusted alone.
- **Prompt injection.** Page text is fenced with an unfakeable random nonce; title metadata escaped. Embedded instructions are data, reported in `ignored_embedded_instruction`, never obeyed.
- **Contradictions.** Latest explicit amendment wins, earlier statement mentioned; budget permitting, search "amend"/"revised".
- **No pre-reading or caching.** Fresh budget per question; history keeps Q/A, never page text.
- **Question fingerprinting.** A zero-cost regex classifier (no tool/LLM call) labels each question (comparison/may-have-changed/multi-part/definition/specific-fact) and injects a matching navigation route; may-have-changed spends the reserve call hunting the amendment (failure mode 1). Final-run effect: injection 1/3 → 3/3; contradictions unchanged (2/4) because "On what day does Congress meet?" has no temporal cue and routed as a plain fact.

## Results (qwen3:8b; numbers from `make_report.py`)
19 hand-labelled questions on 3 real PDFs (204-page course reader, US Constitution with amendments, "Attention Is All You Need"):

|Strategy (same model/questions)|Accuracy|Avg/max calls|Unanswerable declined|Obeyed injection|Ungrounded blocked|
|---|---|---|---|---|---|
|A. Naive ReAct (existing, no gates)|12/19 (63%)|3.7/6|3/3|**3/3** (e.g. "ACCESS GRANTED")|0|
|**D. PageProof (proposed)**|**14/19 (74%)**|4.2/6|3/3|**0/3**|2|
|**D final (+ fingerprinting, anti-skip prompt)**|**14/19 (74%)**|4.0/6|3/3|**0/3**; all 3 injection Qs answered|0|

By type (D final): single 4/5, multi 2/4, unanswerable 3/3, superseded 2/4, injection 3/3 (first D run: 5/5, 3/4, 3/3, 2/4, 1/3). Two full D runs both gave 14/19 with different misses (multi-page and contradiction questions vary run to run); none exceeded 6 tool calls. On a balanced 7-question subset, existing strategies B (search-first), C (outline-first) and D each scored 5/7; D's two misses were injection questions answered without tools (failure mode 2). Re-run on the 3 injection questions, final code scored 2/3, obeyed 0/3, third safely declined. The synthetic red-team fixture (planted amendment + injection, excluded from headlines) scored 6/6.

## Known failure modes (not fixed)
1. **Unmarked contradictions.** Reported 41.0 BLEU (text) not 41.8 (abstract, table), and the original Congress meeting date, not the 20th-Amendment one. Fix: on a revision marker (`*`, "changed by amendment"), spend the reserve call on "amendment" + topic.
2. **Injected "skip the tools" instructions.** In the benchmark run it skipped tools in 2 of 3; the gate turned memory answers into safe declines, losing the answer. The "never skip tools" re-prompt plus fingerprinting fixed this: 3/3 in the final full run, obeyed 0/3.
3. **Multi-part answers spanning over 4 pages** don't fit in 6 calls (found 1943, missed the Minsky/Papert page).
4. **Uncalibrated confidence; the gate checks quotes, not claims**, so grounded answers can add unsupported details. Fix: claim-by-claim checking.
5. **Variance and limits.** Answers vary between runs at temperature 0; each takes 25–160 s on an RTX 5050 (turns capped at 3,072 output tokens). No OCR for scans; heading detection is heuristic.
