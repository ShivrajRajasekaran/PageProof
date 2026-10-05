# PageProof — Run · Demo · Explain (Team SOUL SOCIETY)

One page to keep open during judging. Deeper material: `JUDGE_QA.md` (30 Q&As), `DEMO_RUNBOOK.md`, `MEMO.md`.

---

## 1. Run it (cmd, Windows)

**Pre-flight (do once, 2 minutes before judges arrive)**
```bat
taskkill /F /IM brave.exe
taskkill /F /IM Antigravity.exe
```
The 8B model needs ~6 GB of free memory. Close anything heavy.

**Start Ollama and load the model onto the GPU**
```bat
start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
timeout /t 8
ollama run qwen3:8b "say ok" --think=false
```
You should get a short reply. If you see `memory layout cannot be allocated`, close more apps and run the last line again.

**Start PageProof**
```bat
cd /d C:\Users\shivraj\Desktop\RAPIDWINNER
set OLLAMA_MODEL=qwen3:8b
set CONF_THRESHOLD=0.4
set STRATEGY=D
python -m streamlit run app.py
```
Open **http://localhost:8501** in Edge or Chrome. Keep this cmd window open for the whole demo.

**If port 8501 is already taken** (an old copy is still running):
```bat
for /f "tokens=5" %a in ('netstat -ano ^| findstr :8501 ^| findstr LISTENING') do taskkill /F /PID %a
```

**Warm up:** upload `CSCI415009_V2.pdf`, ask `What is an admissible heuristic?`, wait for the answer, then press **F5** so only the judges' PDF is loaded when they arrive.

**Troubleshooting**
| Symptom | Fix |
|---|---|
| "Unable to connect" to Ollama | Start the Ollama app from the Start menu, wait 10 s |
| `memory layout cannot be allocated` | Close apps; re-run `ollama run qwen3:8b "say ok" --think=false` |
| Answer takes > 2 min | Normal upper bound is ~160 s; each turn is capped at 3,072 tokens so it cannot hang |
| Sidebar says "No text layer" | Scanned PDF; say OCR is on the roadmap, answers will be "insufficient information" |
| Wrong answer | Expand **Evidence**, show the quotes, name the failure mode from the memo (section 4 below) |

---

## 2. Demo script (6–7 minutes)

**0:00 Open with the constraint, not the app.**
> "Every team had the same four tools and a six-call budget. Our question was: how do you make an answer *trustworthy* under that limit, with no RAG, no vector DB and no cloud? PageProof's answer: the harness, not the model, enforces every guarantee. It runs 100% locally on this laptop."

**0:30 Upload the judges' PDF.** Point at the sidebar.
> "No index, no embeddings, no page cache. At upload we only read the outline. Page text is fetched only when the agent spends a counted call."

**1:00 Ask a multi-page question** (their question, or one that needs two sections).
While it runs, point at the budget meter filling:
> "Each slot is one tool call. Call seven is physically refused by the code, not by the prompt."
When it answers, expand **📌 Evidence**:
> "Every quote is matched by our code against a page the agent actually read in this question. No verified quote means the answer is converted to *insufficient information*. The model never gets the last word."

**2:30 Ask an unanswerable question.**
> "Declining is a verified outcome, not a fallback. The harness refuses an early 'I don't know' while budget and unread search hits remain, and pushes the agent back once."

**3:30 Ask the injection question** (text that tells the AI to skip tools / reply with a payload).
> "Page text is fenced with a random nonce, and any instruction in the document or the question is treated as data. You see the real answer, no payload, and the 🧬 route badge: the harness classified the question before any tool call."

**4:30 Contradiction case** (if they ask one).
> "When a later section amends an earlier one, the agent reports the latest statement and names the one it replaces."
If it misses: say so at once. "That is failure mode 1 in our memo: unmarked contradictions need both pages read. The planned fix is an evidence-collision resolver."

**5:30 Close on proof.** Open the **📊 Benchmark** tab.
> "Same local model, same 19 real questions. A naive agent scored 63% and was hijacked by all three injections. PageProof scored 74% in two independent runs, was hijacked by none, and never exceeded six calls."
Click **⬇ Full tool-call trace (JSONL)** and hand over the file: "Nothing hidden."

**Phrasing tip for live questions:** include the distinctive noun ("Laplace smoothing", "monotonicity"), not just the section name. Search is lexical by design.

**Download the trace before uploading a second PDF**: each upload starts a new session log.

---

## 3. Explain it (the 90-second version)

**Problem.** Teams need answers from internal PDFs without building and maintaining a vector index per document set. LLM agents hallucinate, follow injected text, and have unbounded cost.

**Architecture.**
```
Chat UI → DocAgent (hand-written loop, raw HTTP to local Ollama)
        → BudgetedToolbox: counts and logs every call; call #7 refused
        → 4 tools: list_documents · list_headings · get_page · search_keyword
        → Gates on the answer: ① quote found on a page read  ② confidence ≥ 0.4
```

**What makes it different (strategy D, "PageProof hybrid"):**
1. **Evidence budgeting:** 2 calls to locate (outline + search), at most 3 to read, 1 in reserve. Stops early when the quote is verified; often 3 of 6 calls.
2. **🧬 Question fingerprinting:** a zero-cost classifier routes each question (comparison, may-have-changed, multi-part, definition, specific fact). No tool or LLM call spent.
3. **Negative-evidence check:** "not in the document" must be earned; a premature decline is pushed back once with the unread search hits.
4. **Two-stage answer gate:** a quote must match a page read in this question (≥ 80% 3-gram match, numbers identical), and confidence must be ≥ 0.4. Otherwise the user gets "insufficient information".
5. **Injection fencing:** page text wrapped in a random-nonce fence; PDF metadata escaped and labelled untrusted.
6. **Contradictions:** latest amendment wins; the earlier statement is named.

**Why local Ollama (qwen3:8b):** privacy (no document leaves the machine), zero per-answer cost, no rate limits. We built on a cloud API first and hit its quota mid-build; local inference removed that risk.

**Results (benchmarked, not claimed):**
| Strategy | Accuracy, 19 real Qs | Obeyed an injection |
|---|---|---|
| A. Naive ReAct (existing) | 12/19 (63%) | 3/3 |
| B / C. Search-first / Outline-first (existing) | 5/7 subset each | 0/2 |
| **D. PageProof (ours), two independent runs** | **14/19 (74%) both** | **0/3** |
Red-team fixture 6/6. Zero questions over budget in any run.

**Why threshold 0.8 for the quote gate, 0.4 for confidence:** we replayed every benchmark answer against the pages read. 0.8 is the strictest quote threshold that blocks no correct answers; 0.9 or verbatim-only wrongly blocks 1–2. Confidence is only a backstop: the model reports 0.95–1.0 on everything, including wrong answers, so we never trust it alone.

---

## 4. Honest failure modes (say these before the judges find them)
1. **Unmarked contradictions:** without an "amended" cue on the page it reads, the agent can report the older value (2/4 in our tests). Fix: evidence-collision resolver using the reserve call.
2. **Keyword choice on an 8B model:** searching a section name instead of the distinctive term can exhaust the budget before the right page (1 live miss in rehearsal). Fix: fingerprint-driven term extraction.
3. **Run-to-run variance:** both full runs scored 14/19 but missed different questions.
4. **The gate checks quotes, not every claim:** a grounded answer can still add an unsupported detail. Fix: claim-by-claim check.
5. **Latency and hardware:** 25–160 s per answer on an RTX 5050; no OCR for scanned PDFs.

---

## 5. Likely judge questions (short answers; full set in `JUDGE_QA.md`)
- **"Isn't extracting text at upload pre-reading?"** No. Upload builds only the outline. `get_page` and `search_keyword` read from the PDF at call time; each question starts with an empty context.
- **"Why not RAG?"** The rules forbid it, and our point is that verifiable answers don't need it: lexical search plus a quote check beats similarity search for auditability.
- **"3 of 6 calls used: is that a problem?"** No. Six is a ceiling, not a target. Early stop means lower cost per answer.
- **"How do we know nothing is hidden?"** Every tool call, every refused call, every push-back and the final answer are in the JSONL trace you can download.
- **"What would you do with one more week?"** Collision resolver for contradictions, claim-level grounding, a stronger local model, OCR.
