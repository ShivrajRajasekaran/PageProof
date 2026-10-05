# PageProof — by Team SOUL SOCIETY

**A Budget-Bounded, Evidence-Verified Document Agent That Answers Only What the PDF Proves**

> *No RAG. No vector DB. Six tool calls. Every answer comes with a quote.*

PageProof is a chat app. You upload any PDF and ask questions about it. The agent can read the document only through four tools: `list_documents`, `list_headings`, `get_page` and `search_keyword`. It has a hard budget of **6 tool calls per question**, plus one structured final-answer call. The harness enforces the budget: call #7 is refused and never executed.

Every "answered" response must include verbatim quotes. These are checked against the pages the agent actually fetched for that question. If no quote can be verified, or the agent's confidence is below 0.4, the user gets **"insufficient information"** instead of a guess. Page text is fenced as untrusted data, so instructions embedded in the PDF are ignored and reported.

The LLM (`qwen3:8b`) runs fully locally through **Ollama** on a laptop GPU (RTX 5050, 8 GB), so no document leaves the machine. Every tool call is logged in full for audit.

---

## Quick start (Windows)

```powershell
# 1. Local model (Ollama must be installed and running)
ollama pull qwen3:8b

# 2. Python deps
pip install pymupdf streamlit requests

# 3. Configure (PowerShell)
$env:OLLAMA_MODEL  = "qwen3:8b"
$env:CONF_THRESHOLD = "0.4"

# 4. Run
streamlit run app.py
```

Open the URL Streamlit prints, upload a PDF in the sidebar and ask a question. The app also works with Wi-Fi turned off.

| Env var | Default | Meaning |
|---|---|---|
| `OLLAMA_MODEL` | `qwen3:8b` | Any tool-calling Ollama model (fallback: `qwen2.5:7b`) |
| `CONF_THRESHOLD` | `0.4` | Answers with self-reported confidence below this become "insufficient information" |
| `STRATEGY` | `D` | Agent strategy `A`–`D` (also selectable in the UI sidebar) |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server address |
| `OLLAMA_THINK` | `1` | qwen3 reasoning mode on/off |
| `OLLAMA_NUM_CTX` | `16384` | Context window |

---

## Architecture

```
 Streamlit chat (upload PDF, ask, live x/6 meter, ✅/❓ quotes, trace download)
        │
        ▼
 DocAgent.ask(question)    hand-written loop, no agent framework
        │  ◄──── raw HTTP POST /api/chat ────►  Ollama · qwen3:8b (local GPU)
        │  ≤ 6 tool calls, then 1 structured final_answer call
        ▼
 BudgetedToolbox           counts calls, refuses call #7 unexecuted, logs every call → logs/*.jsonl
        ▼
 DocTools                  list_documents · list_headings · get_page (1 page) · search_keyword (page numbers only)
        ▼
 DocStore                  PyMuPDF text, cleaned once at upload (ligatures, hyphenation, spacing)

 final_answer {status, answer, evidence[{page, quote}], confidence}
        ▼
 Gate 1: grounding   each quote must appear in a page fetched for THIS question  ── fail ─► insufficient information
        ▼
 Gate 2: threshold   confidence ≥ CONF_THRESHOLD (0.4)                           ── fail ─► insufficient information
        ▼
 Answer + verified quotes (+ injection / contradiction notes)
```

**Strategy D (PageProof hybrid, default):**
- Turn 1 calls `list_headings` and `search_keyword` in parallel, so the agent gets both a map and coordinates.
- It then reads at most 3 pages and keeps 1 call in reserve for a contradiction or a page continuation.
- **Decline check:** if it tries to decline while budget and unread search hits remain, the harness pushes back once and lists those pages.
- **Question fingerprinting:** before any tool call, a zero-cost regex classifier labels the question (comparison / may-have-changed / multi-part / definition / specific-fact) and adds the matching navigation route to the prompt. No LLM or tool call is spent. Measured effect: injection-style questions 1/3 → 3/3; headline accuracy unchanged at 14/19.
- **Grounding check:** if the first answer's quotes match no page read in this question, the harness pushes back once ("go and read") before converting it to a decline.
- Finally it answers through both gates.

---

## Hard constraint → how we comply

| Hard constraint | How PageProof complies |
|---|---|
| **No RAG, no embeddings, no vector DB** | `search_keyword` is a case-insensitive lexical substring match that returns page numbers only. If an exact phrase has no hit, it falls back to "pages containing every word". No embeddings, vectors or semantic index exist anywhere. |
| **Only the 4 given tools** | The model sees document content only through `list_documents`, `list_headings`, `get_page` (exactly one page) and `search_keyword` (page numbers only). No other tool exists. `final_answer` returns the answer and does not read the document. |
| **6 tool calls per question + 1 answer call** | `BudgetedToolbox` in `rapidagent/tools.py` enforces the budget in the harness. Failed or invalid calls count. **Call 7 is refused and never executed**, so a question cannot fail by going over budget. Once the budget is spent, the harness makes one final structured call (JSON-schema `format`, no tools). That is the "+1 answer call". |
| **Must say "insufficient information"** | This is a first-class `status`. On top of it, the grounding gate downgrades any answer whose quotes are not found in pages read, and the confidence threshold (0.4) downgrades low-confidence answers. The withheld tentative answer stays visible but is clearly labelled. |
| **No agentic frameworks** | A hand-written loop in `rapidagent/agent.py` plus raw `requests` HTTP to Ollama in `rapidagent/llm.py`. No LangChain, LangGraph, CrewAI, AutoGen or similar. |
| **Full call logging** | Every call is appended to `logs/*.jsonl` with its timestamp, question, tool, arguments, status, call number and the full, unabridged result. The UI offers a one-click "Full tool-call trace (JSONL)" download. |
| **No pre-reading or caching across questions** | Each question starts with an empty budget and no page text. Only pages returned by that question's own calls are visible to the model and to the grounding gate. Chat history carries earlier Q/A text only, never page text. |
| **Prompt injection must be ignored** | Page text is wrapped in `<<<PAGE n - untrusted document text>>>` markers. The system prompt states that document text is data, never instructions. Embedded instructions are reported in an "ignored embedded instruction" note. |
| **Generalise to an unseen PDF** | Headings come from the PDF outline if one exists. Otherwise they are detected from font size and weight relative to body text. Text cleaning fixes ligatures, end-of-line hyphens and lost spaces. |

---

## File map

| Path | Purpose |
|---|---|
| `app.py` | Streamlit chat UI: upload, live call meter, verified-quote evidence, trace panels, trace download |
| `rapidagent/agent.py` | `DocAgent`: system prompt, strategies A–D, hand-written tool loop, `final_answer` schema, grounding gate (`_quote_supported`), confidence threshold |
| `rapidagent/llm.py` | `OllamaBackend`: raw `requests` HTTP to the local Ollama `/api/chat` (tools, temperature 0, 16k context) |
| `rapidagent/tools.py` | `DocStore` (PyMuPDF + text cleaning), heading detection, the 4 `DocTools`, and the `BudgetedToolbox` budget and logging wrapper |
| `eval.py` | Evaluation runner: accuracy, calls per question, decline and injection results, threshold sweep |
| `run_q.py` | Ask a single question from the command line |
| `tests/real/` | Real public PDFs used for evaluation |
| `tests/northwind_test.pdf`, `tests/make_test_pdf.py` | Disclosed red-team fixture (planted injection and superseded values), scored separately |
| `CSCI415009_V2.pdf` | Provided sample PDF |
| `logs/` | JSONL call traces and `results_*.json` evaluation outputs |
| `MEMO.md` | 1-page design memo (architecture, rationale, failure modes) |
| `PITCH_DECK_CONTENT.md` | Slide content for the pitch deck |

---

## Running the evaluation

```powershell
python eval.py all --strategy D            # usage: eval.py [real|redteam|all] [--strategy A-D] [--model qwen3:8b] [--limit N]
```

- Writes per-question results, with status, confidence, calls used, latency and correctness, to `logs/results_<model>_<strategy>.json`.
- Every tool call is written to the JSONL trace.
- To compare against the baselines, run strategies `A`, `B` and `C` the same way.
- The 0.2–0.6 threshold sweep is recomputed offline from the logged confidences. It makes no extra LLM calls.

---

## Results

Model: `qwen3:8b` via Ollama on an RTX 5050 laptop (8 GB VRAM). Dataset: 19 hand-labelled questions on real PDFs. The injection fixture is reported separately.

|---|---|---|---|---|---|---|---|---|---|
| A | 12/19 (63%) | 3.7 | 6 | 3/3 | 1/3 | 3/3 | 0 | 0 | 54 s |
| B | 5/7 (71%) | 3.9 | 5 | n/a | 2/2 | 0/2 | 0 | 0 | 48 s |
| C | 5/7 (71%) | 3.7 | 5 | n/a | 2/2 | 0/2 | 0 | 0 | 78 s |
| D | 14/19 (74%) | 4.2 | 6 | 3/3 | 1/3 (+ red-team 1/1) | 0/3 | 2 | 0 | 60 s |
| D final (all fixes + question fingerprinting) | 14/19 (74%) | 4.0 | 6 | 3/3 | 3/3 | 0/3 | 0 | 0 | 52 s |
| D on the same 7-question subset as B/C | 5/7 | | | | | | | | |
| D, final code (stronger 'never skip tools' re-prompt), injection questions only | 2/3 | | | | | 0/3 | | | |

*Real PDFs: course reader, US Constitution, 'Attention Is All You Need'. B and C were run on an evenly spread subset (every 3rd question) for time.*

Threshold sweep (strategy D): 

| Threshold | Correct answers kept | Wrong answers let through | Correct declines | Net score |
|---|---|---|---|---|
| 0.0 | 11 | 2 | 3 | 10 |
| 0.2 | 11 | 2 | 3 | 10 |
| 0.3 | 11 | 2 | 3 | 10 |
| 0.4 | 11 | 2 | 3 | 10 |
| 0.5 | 11 | 2 | 3 | 10 |
| 0.6 | 11 | 2 | 3 | 10 |
| 0.7 | 11 | 2 | 3 | 10 |

Confidences reported on answered questions: [0.95, 0.95, 0.95, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]


---

## Known limits

See `MEMO.md` for details. In brief:
- Multi-hop answers that span more than 4 pages can exhaust the budget.
- Math- and figure-heavy pages extract poorly, so quotes from them may fail verification.
- Heading detection is heuristic, and scanned PDFs need OCR.
- Self-reported confidence is not well calibrated.
- Printed page numbers can differ from PDF page indexes.

---

## References

1. S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan, Y. Cao. *ReAct: Synergizing Reasoning and Acting in Language Models.* ICLR 2023. arXiv:2210.03629.
2. T. Schick, J. Dwivedi-Yu, R. Dessì, R. Raileanu, M. Lomeli, E. Hambro, L. Zettlemoyer, N. Cancedda, T. Scialom. *Toolformer: Language Models Can Teach Themselves to Use Tools.* NeurIPS 2023 (Advances in Neural Information Processing Systems 36).
3. P. Rajpurkar, R. Jia, P. Liang. *Know What You Don't Know: Unanswerable Questions for SQuAD.* ACL 2018 (ACL Anthology P18-2124).
4. K. Greshake, S. Abdelnabi, S. Mishra, C. Endres, T. Holz, M. Fritz. *Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection.* Proc. 16th ACM Workshop on Artificial Intelligence and Security (AISec '23), 2023. arXiv:2302.12173.
5. P. Manakul, A. Liusie, M. J. F. Gales. *SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models.* EMNLP 2023 (ACL Anthology 2023.emnlp-main.557).
6. N. F. Liu, K. Lin, J. Hewitt, A. Paranjape, M. Bevilacqua, F. Petroni, P. Liang. *Lost in the Middle: How Language Models Use Long Contexts.* TACL 12:157–173, 2024. doi:10.1162/tacl_a_00638.
7. S. Pan, L. Luo, Y. Wang, C. Chen, J. Wang, X. Wu. *Unifying Large Language Models and Knowledge Graphs: A Roadmap.* IEEE Transactions on Knowledge and Data Engineering 36(7):3580–3599, 2024. doi:10.1109/TKDE.2024.3352100.

**How each one shapes our design:**
- ReAct gives us the bounded act–observe loop.
- Toolformer led us to narrow, strictly-typed tools.
- SQuAD 2.0 makes abstention a first-class status.
- Greshake et al. is why we fence page text as untrusted data.
- SelfCheckGPT inspired our cheaper, deterministic grounding gate.
- Lost in the Middle is why we read a few targeted pages instead of stuffing the context.
- Pan et al. support grounding a black-box LLM in explicit external structure, which for us is the PDF's own headings and pages.
