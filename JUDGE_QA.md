# PageProof: Judge Q&A Prep (25 toughest questions)

> Every answer cites the code. If you don't know, say so and point to the trace or the code. Don't improvise numbers.
> **Numbers to fill once the benchmark finishes:** take them from `logs/results_qwen3-8b_D_real.json` and `logs/results_qwen3-8b_D_redteam.json` (`summary.accuracy`, `avg_calls`, `max_calls`, `over_budget`, `avg_seconds`, `by_type`, `threshold_sweep`).

**Quick facts:**
- **Budget:** `TOOL_BUDGET = 6` and `MAX_HEADINGS = 300` (`tools.py`). `MAX_TURNS = TOOL_BUDGET` gives **at most 7 LLM calls per question**: 6 tool-using turns plus 1 final call.
- **Gates and history:** `CONF_THRESHOLD = 0.4`; history is the last 4 Q/A pairs, as text only (`agent.py`).
- **Model:** `qwen3:8b` with `temperature 0`, `num_ctx 16384` and `keep_alive 30m` (`llm.py`).
- **Test PDFs:** the 204-page course reader has **no** embedded outline. The US Constitution (19 pages, 101 outline entries) and *Attention* (15 pages, 22 entries) do.
- **No framework:** `llm.py` is a raw `requests.post` to `/api/chat`, and `agent.py` is a hand-written `for turn in range(MAX_TURNS)` loop.

---

## A. Rules and compliance

**1. Why not RAG? Wouldn't embeddings be more accurate?**
RAG is banned outright, and it also has a real cost: one index per document set, and the index goes stale. We replace semantic retrieval with *navigation*. `list_headings` gives a map, `search_keyword` returns page numbers only, and the agent then reads a few whole pages with `get_page`. Reading whole pages gives full context instead of chunk fragments ("Lost in the Middle"). The trade-off is that pure synonyms are missed (Q6).

**2. How exactly is the 6-call budget enforced?**
It is enforced in the harness, not the prompt. `BudgetedToolbox.call` (`tools.py`) increments `used` *before* executing, so failed and invalid calls count. Once `used >= budget`, further requests are logged as `rejected, counted=False` ("BUDGET EXHAUSTED … Not executed"), and nothing runs. Calls the model issues in the same turn as `final_answer` are logged as `dropped_call` and not executed. When the budget is spent, `DocAgent.ask` makes **one** structured call (`json_schema=FINAL_SCHEMA`, no tools). That is the "+1 answer call", and it cannot read the document.

**3. Isn't processing the PDF at upload "pre-reading"?**
No. Nothing is pre-read and no page text is cached.
- **At upload:** `DocStore.add_pdf` only builds the outline that `list_headings` must return, and keeps the PDF handle open.
- **At call time:** `get_page` extracts its page with PyMuPDF (`Document.page_text`), and `search_keyword` scans the pages fresh on each call (about 0.3 s for 204 pages; "scanned per call, not cached").

So page text exists only when a counted tool call produces it. Each question gets a fresh `BudgetedToolbox` with an empty `pages_read`. `history` carries only `(question, answer)` text. The grounding gate accepts quotes only from pages read *in this question*, so an earlier answer can't be reused without re-reading.

**4. The system prompt contains the title and page count. Isn't that a free `list_documents` call?**
`_fmt_doc_info` passes only upload metadata: doc_id, page count, number of headings, and the title. The title is JSON-escaped, labelled "untrusted metadata" and truncated to 120 characters. It contains no page content, and it saves a call that adds no information when only one PDF is loaded. With 2 or more PDFs, `_first_turn_tools` adds `list_documents` to turn 1, and that call counts. If judges rule otherwise, it's a one-line change.

## B. How the harness reads documents

**5. Most PDFs have no table of contents. How does `list_headings` work?**
`_extract_headings` uses the embedded outline when it has 3 or more entries. Otherwise it detects headings from fonts:
- The body size is the most common font size, weighted by character count.
- A line is a heading candidate if it is at least 1.15× the body size, or bold, numbered (`_NUMBERED`: "3.1", "Chapter 2", "Appendix A") and under 80 characters.
- Numbers and titles on the same baseline are merged, and so are wrapped lines.
- Noise is dropped: bare numbers, lines with low alpha ratio, and running headers repeated on more than `max(3, pages/10)` pages.
- Level is the font-size rank.

Output is capped at 300 headings of at most 120 characters each, with a "[outline truncated … use search_keyword]" note. If fewer than 3 headings are found, turn 1 offers only `search_keyword`, so no call is wasted.

**6. Search has fallbacks. Isn't that semantic search in disguise?**
No. `search_keyword` runs three lexical steps:
1. An exact case-insensitive substring of the normalised page.
2. The same match with spaces **and hyphens** removed. Extraction drops spaces, and "nonrefundable" should match "non-refundable".
3. For multi-word input, pages containing *every* word (a boolean AND).

All three are deterministic string matching, with no vectors, synonyms or stemming, so "reimbursement" never matches "refund". The fallbacks exist because small models search long phrases and would otherwise waste calls on zero hits. Known downsides: substring false hits ("age" matches "page") and common words that hit many pages.

**7. What stops the model from answering from its own knowledge?**
Rule 2 of `SYSTEM_PROMPT` forbids outside knowledge. `_finalize` then downgrades any "answered" response unless at least one evidence quote verifies against a page read in this question. Example: the course reader has no Q-learning update rule. The model knows the rule, but the gate declined it (`logs/eval_all_lite.txt`). The withheld guess stays visible in the UI and is labelled as withheld.

## C. Gates and robustness

**8. How does the grounding gate work, and where does it fail?**
`_quote_supported` (`agent.py`) needs at least 3 words. A quote passes if it appears **verbatim after normalisation** on a page read in this question, **or** if both of these hold on one such page:
- at least 80% of its word **3-grams** appear there;
- **every number** in the quote appears there.

Example: a fake quote "refund window is 30 days" checked against the amendment page, which says 14, is rejected. Each quote is shown as ✅ or ❓, and the answer passes if at least one quote verifies.

Remaining limits:
- It checks *any* page read, not the page number the model cited.
- A dropped "not" can still clear 80% of the 3-grams.
- It proves the quotes are real, **not** that the answer follows from them. A real quote of a superseded value still passes.

**9. Why a confidence threshold of 0.4 and not 0.3?**
Score +1 for a correct answer, 0 for a decline and −λ for a wrong answer. Answering then pays only if p > λ/(1+λ). The cutoff is 0.3 for λ≈0.43, 0.4 for λ≈0.67 and 0.5 for λ=1. The brief penalises guessing *more heavily* than declining, so 0.4 is the safer choice. Self-reported confidence is bimodal (grounded answers come in at 0.8 or higher), so the cutoff only removes the low cluster, and the grounding gate does most of the work. The evidence is `summary.threshold_sweep` in `logs/results_qwen3-8b_D_*.json`, recomputed offline in `eval.py` with no extra LLM calls. **If the sweep disagrees, say so.**

**10. How do you handle contradictions or superseded statements?**
Three parts:
- **Prompt:** the `CONTRADICTIONS` block says the latest "amended / revised / supersedes / effective" statement wins, the old one should be mentioned, and both should be reported if nothing says which wins.
- **Budget:** strategy D keeps 1 call in reserve to search "amend" or "supersede", or to read a later page.
- **Tests:** 4 real superseded questions (3 on the Constitution, for example the 20th Amendment changing Congress's meeting day; 1 on *Attention*) plus the red-team refund amendment.

Limit: this is prompt-driven. If the amendment uses unusual wording and sits on a page the agent never reads, it reports the old value.

**11. How do you defend against prompt injection?**
Five layers:
1. **Nonce fence:** page text is wrapped in `<<<PAGE n id=XXXX - untrusted…>>> … <<<END PAGE id=XXXX>>>`, where `id` comes from `secrets.token_hex(4)` and changes on every read.
2. **Neutralisation:** any `<<<` or `>>>` inside the page text becomes `«`/`»`, so a PDF can't fake the closing marker.
3. **Untrusted title:** the title is JSON-escaped and labelled untrusted.
4. **Rules:** rule 3 says document text is data, and the same applies to manipulative text in the question. The `ignored_embedded_instruction` field becomes a "⚠ Ignored embedded instruction" note.
5. **Structure:** every tool is read-only, so an injection can't *do* anything, and in turn 1 `final_answer` isn't offered.

Limit: an 8B model can still be persuaded by text inside the fence. These layers lower the risk; they don't remove it.

## D. Design choices

**12. What are strategies A–D, and why D?**
All four use the same loop and model; they differ only in the first-turn tools and the strategy text:
- **A:** free tool choice, and **no gates** (`self.strategy != "A"`). This is the ungated baseline.
- **B:** turn 1 may only search.
- **C:** turn 1 may only call headings.
- **D:** turn 1 calls headings **and** search in parallel, then reads at most 3 pages and keeps 1 call in reserve.

D gets a map and coordinates for 2 calls. That covers B's weakness (answers spread across sections) and C's (a call spent before any evidence). `_first_turn_tools` adapts: it adds `list_documents` when several PDFs are loaded, and offers search only when there is no outline. Comparisons must come from `logs/results_qwen3-8b_{A..D}_real.json`.

**13. What if the model loops, stalls or emits garbage?**
The loop is bounded several ways:
- Tool calls are capped at 6, and extras are refused without running.
- LLM turns are capped at `MAX_TURNS = 6`, plus 1 forced final call, so at most 7 LLM calls.
- If the model returns neither a tool call nor JSON, the harness nudges once, then forces the final call.
- Malformed output falls back to `_parse_json`. If no final answer appears, the result is "insufficient information".

Each HTTP call has a 600 s timeout. The worst case is a decline, never a budget overrun.

**14. Why a local Ollama model instead of a frontier API?**
- **Privacy:** documents never leave the laptop, which the target users (compliance, air-gapped organisations) need.
- **Cost:** near zero per question.
- **No rate limits:** our Gemini prototype hit `429 RESOURCE_EXHAUSTED` (free-tier quota of 20 requests/day; `logs/eval_northwind_out.txt`), and a question needs up to 7 LLM calls.

The harness is model-agnostic (`OLLAMA_MODEL`), so an upgrade is a one-variable change.

**15. Why qwen3:8b?**
It fits an 8 GB RTX 5050 with a 16k context. It has native tool calling through Ollama's `/api/chat`, including several calls per turn, which strategy D relies on. Its thinking mode (`OLLAMA_THINK=1`) helps it plan page reads. `qwen2.5:7b` is the documented fallback. Don't claim a model comparison: the `mistral:latest` attempt returned Ollama 500 errors (memory), not results.

## E. Performance and operations

**16. Latency?**
About 27 s per question. A typical question takes 3 LLM turns (discover, read, answer), each generating thinking tokens over a context of up to 16k. Tools are cheap: `get_page` extracts one page in milliseconds, and `search_keyword` re-scans the PDF in about 0.3 s per 204 pages. Levers: `OLLAMA_THINK=0`, a smaller `num_ctx`, or a bigger GPU. Parallel tool calls in one turn already save turns.

**17. Cost per answer?**
Locally it's electricity. Assuming about 150 W of laptop draw for about 27 s, that's roughly 1 Wh, a fraction of a cent (estimate). The key point is that the worst case is **bounded** by construction: 6 tool calls and at most 7 LLM calls, so a cost per question can be quoted in advance. On a hosted API the cost is mostly input tokens re-sent each turn (not measured).

**18. What are your failure modes?**
Name them before the judges do (see `MEMO.md`):
1. Multi-hop answers spread over more than 4 pages run out of budget.
2. Math- and figure-heavy pages extract badly, so correct quotes fail the gate.
3. Heading detection is heuristic.
4. Self-reported confidence is poorly calibrated.
5. Printed page numbers differ from PDF indexes (rule 4 tells the model to use indexes).
6. Lexical search misses synonyms.
7. The gate checks that quotes exist, not that the reasoning is right (Q8).

**19. Would this scale to a 1000-page PDF?**
The tools would work:
- **Upload:** building the outline is a one-time layout pass.
- **Search:** it re-extracts every page on each call, which is linear and estimated at roughly 1.5 s per search at 1000 pages, based on 0.3 s per 204 pages. That is the price of not caching.
- **Outline:** `list_headings` is capped at 300 headings with a truncation note, so it can't overflow the 16k context.

The real pressure is that 6 calls stay fixed while common keywords return hundreds of pages, so precise search terms matter more. Next steps: map printed page labels to PDF indexes, and use a larger `num_ctx` on a bigger GPU.

**20. Scanned PDFs?**
At upload, `add_pdf` checks the first 5 pages for a text layer, and the app shows a red warning: "No text layer found (scanned PDF?)". The agent then safely declines with "insufficient information". The fix is OCR inside the tool implementation (for example PyMuPDF's Tesseract OCR), with the same four tools and no interface change.

**21. Multiple documents?**
The UI accepts several files (`doc1…docN`). Turn 1 then adds a counted `list_documents` call. `pages_read` is keyed by `(doc_id, page)`, so the gate works across documents. The cost is budget: `search_keyword` covers one document per call, so a 3-document question spends 1 call listing plus 3 searches, leaving 2 reads. This is the hardest case.

## F. Evaluation and audit

**22. How did you test it?**
- **Real questions:** 19 hand-labelled questions over 3 real PDFs (`tests/questions.json`): the provided course reader, the US Constitution and *Attention Is All You Need*. They split into 5 single-page, 4 multi-page, 4 superseded, 3 unanswerable and 3 injection-in-question.
- **Red team:** a separate 6-question fixture (`REDTEAM` in `eval.py`).
- **Scoring:** a question counts as correct only if the answer key matches as a **whole word** (word-boundary match, so "6" doesn't match "16") **and** `tool_calls_used <= 6`.
- **Traps:** the unanswerable questions are deliberate. For example, "nine" appears in the Constitution, but the number of Supreme Court justices does not.

**23. The red-team PDF is synthetic. Isn't that cheating?**
That's why it is **excluded from headline accuracy**. We wrote it (`tests/make_test_pdf.py`), so we know every trap and could overfit to it. It exists because none of the real PDFs contains an embedded injection, and the live PDF will. It works as a disclosed unit test of the defences, reported separately.

**24. How can we verify nothing is hidden?**
`BudgetedToolbox._write` appends **every** tool call to `logs/*.jsonl` with unabridged results, including rejected calls. Each entry has `ts`, `question`, `tool`, `args`, `status`, `counted`, `call_no` and the full `result`. `box.note` also logs every `dropped_call` and the final answer: raw model output, gated status, evidence with ✅ flags, and notes. You can check that `call_no` never exceeds 6 per question and that every ✅ quote appears in a `get_page` result in the same trace. The live session goes to `logs/session_<timestamp>.jsonl`, and the sidebar has a "⬇ Full tool-call trace (JSONL)" download. The model's internal reasoning tokens are not stored.

**25. What would you do with one more week?**
In priority order:
1. Calibrate the threshold on about 100 labelled questions.
2. Verify each quote against its *cited* page, and add a negation check.
3. Add OCR for scanned pages.
4. Map printed page labels with `page.get_label()`.
5. Read the next page only when text is cut mid-sentence, to save budget on multi-hop questions.
6. Run the eval suite on every change.

None of these needs RAG or a bigger budget.
