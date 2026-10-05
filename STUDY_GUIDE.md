# PageProof — Study Guide & 5-Minute Pitch
Team SOUL SOCIETY · RAP Hackathon 2026 · 5 Oct 2026

Contents
1. PageProof in 60 seconds
2. How it works, step by step
3. ML and AI terms, explained simply
4. Our real results
5. Your 17 points, one by one
6. 5-minute script (English)
7. 5-minute script (Tanglish)
8. Judge Q&A cheat sheet
9. Honest limits and next fixes

---

## 1. PageProof in 60 seconds

**PageProof is a chat app that answers questions about any uploaded PDF, using only 4 tools, at most 6 tool calls per question, and only what the PDF proves.**

**The problem.** Companies want answers from their own documents (policies, contracts, manuals). The usual fix is RAG: cut every document into chunks, turn them into vectors, and store them in a vector database. That costs money and setup for every document set, goes stale when documents change, and the AI can still make answers up. The hackathon bans RAG and asks: can an agent read a document the way a person does (check the contents page, search a word, open a page) on a strict budget?

**Our answer.** PageProof:
- reads the PDF only through 4 tools: `list_documents`, `list_headings`, `get_page`, `search_keyword`
- stops at 6 tool calls per question, enforced in code: call 7 is refused
- accepts an answer only if it quotes a page it actually read for that question; otherwise it says "insufficient information"
- treats text inside the PDF as data, never as commands, so hidden instructions are ignored
- runs fully on the laptop (Ollama + `qwen3:8b`), so no document leaves the machine
- logs every tool call in a trace the judges can download

**One-line pitch:** "No RAG. No vector database. Six tool calls. Every answer comes with a quote."

**Tanglish:** Namma PageProof oru chat app. Neenga oru PDF upload panni question kekkalam. Adhu 4 tools mattum use pannum: headings paakum, keyword search pannum, page padikkum. Oru question-ku maximum 6 tool calls dhaan; 7th call-a code-e block pannidum. Answer sonna, adhu padicha page-la irundhu quote kaatanum. Quote illa-na "insufficient information" nu sollidum, guess panna maattom. PDF-kulla "ignore your rules" nu edhavadhu ezhudhi irundha, adha data-va mattum paakum, command-a follow panna maattom. Ellame laptop-laye local-a odudhu; document veliya pogadhu.

---

## 2. How it works, step by step

```
 Upload PDF ──► DocStore builds ONLY the heading list (no page text stored for the agent)
      │
 Question ──► Fingerprint (regex, free): comparison / may-have-changed / multi-part / definition / fact
      │
      ▼
 Agent loop (hand-written, no LangChain)          BudgetedToolbox counts + logs every call
   Turn 1: list_headings + search_keyword  (2)    ── call 7 is REFUSED before it runs
   Then:   get_page × 1–3                  (3)
   Reserve: 1 call for amendment / next page (1)
      │
      ▼
 final_answer (the "+1" call): status, answer, quotes, pages, confidence
      │
      ▼
 Gates:  ① decline check   ② grounding gate (quote on a page read, 0.8)   ③ confidence ≥ 0.4
      │                         fail ──► "insufficient information" (guess shown, labelled)
      ▼
 UI: answer + ✅ quotes + tool timeline + call meter + trace download
```

1. **Upload.** `DocStore` reads the PDF's outline. If there is none, it finds headings from font size and bold text. That is all it builds. No page text is cached for the agent.
2. **Fingerprint.** A free regex check labels the question type and adds a route hint, e.g. "may have changed → spend the reserve call searching for 'amend'". It uses no tool call and no LLM call.
3. **Turn 1, two calls at once.** `list_headings` (the map) and `search_keyword` (the coordinates).
4. **Read 1–3 pages** with `get_page`, one page per call.
5. **Reserve call.** One call is kept back for an amendment or a page that continues.
6. **Budget.** `BudgetedToolbox` counts every call, failed ones too, and logs it. Call 7 is refused before it runs, so a question can never go over budget.
7. **Final answer.** The model calls `final_answer` with status, answer, verbatim quotes, pages and confidence.
8. **Gates.**
   - Decline check: if the model gives up while unread search hits and budget remain, the harness pushes back once.
   - Grounding gate: at least one quote must be on a page fetched for this question (verbatim, or 80% of its 3-word runs with every number matching).
   - Confidence: below 0.4 → decline.
   - If a gate fails → "insufficient information". The withheld guess is still shown, clearly labelled.
9. **Show everything.** Answer, ✅/❓ quotes, a timeline of every call, a 6-slot meter, and a downloadable JSONL trace.

**Tanglish:** PDF upload pannumbodhu headings list mattum ready pannrom. Question vandha, mudhalla adhu enna type nu regex vechu kandupidippom (free, call illa). Apram 2 calls: headings + keyword search. Adhukkapram 1–3 pages padikkum. Oru call reserve-a vechirukkom (amendment check panna). 7th call vandha code-e block pannidum. Kadaisiya answer-oda quote varum; adha naama check pannuvom. Quote padicha page-la illa-na "insufficient information".

---

## 3. ML and AI terms, explained simply

| Term | Simple meaning | Tanglish | Where in PageProof |
|---|---|---|---|
| LLM (Large Language Model) | AI trained on huge text; predicts next words, can reason and write | Romba text-la train panna AI | `qwen3:8b` picks tools and writes the answer |
| Agent / agentic AI | LLM that works in steps: think, use a tool, look, decide again | Yosichu, tool use panni, result paathu decide pannum | `DocAgent` in `agent.py` |
| Tool / function calling | LLM asks the program to run a named function and gets the result | "Indha function run pannu" nu AI kekkum | Our 4 tools + `final_answer` |
| Harness | The code around the LLM: loop, budget, logging, checks | AI-ya control panra code | `BudgetedToolbox`, gates, trace (20% of score) |
| ReAct | Common pattern: Reason, then Act, repeat | Yosi, act pannu, repeat | Strategy A, our baseline |
| RAG | Retrieve chunks from a database, then answer from them | Database-la irundhu text eduthu AI-ku kudukkuradhu | Banned, not used |
| Embedding / vector | Numbers that represent meaning | Text meaning-a numbers-a maathuradhu | Banned, never created |
| Vector database | Finds text by meaning using embeddings | Meaning vechu thedura DB | Banned, not used |
| Keyword (lexical) search | Find pages containing the exact word, like Ctrl+F | Ctrl+F maadhiri | `search_keyword`, returns page numbers only |
| Context window | How much text the LLM sees at once | Oru time-la evlo text paakum | 16k tokens |
| Token | A piece of a word; LLMs count text in tokens | Word-oda pieces | Limits context and output |
| Temperature | Randomness; 0 = most repeatable | 0-na same answer varum | We use 0 |
| Hallucination | AI confidently says something false or not in the source | Confident-a poi solradhu | Blocked by grounding gate |
| Grounding | Tying an answer to real source text | Answer-a document text-oda link panradhu | Must quote a page it read |
| Grounding gate | Our check that a quote really appears on a page read | Quote unmaiyaa irukka check | `_quote_supported()`, 0.8 |
| n-gram (3-gram) | A run of n words; "refund window is" is one 3-gram | Thodarndhu varra 3 words | 80% of a quote's 3-grams must match |
| Confidence score | How sure the model says it is, 0 to 1 | "Evlo sure" nu solra number | 0.4 backstop; model says 0.95–1.0 always |
| Threshold | Cut-off: above accept, below decline | Cut-off value | Grounding 0.8, confidence 0.4 |
| Calibration | Does stated confidence match reality? | Confidence unmaiyaa match aagudha | Ours isn't, so we use quotes |
| Prompt injection | Text trying to hijack the AI ("ignore your rules") | AI-ya emaathura text | Page text fenced with a random marker |
| System prompt | Hidden rules given to the AI | Munnadiye kudukkura rules | `SYSTEM_PROMPT` in `agent.py` |
| Accuracy | Share of questions answered correctly | Evlo correct | D: 14/19 (74%) |
| Baseline | Simple version to compare against | Compare panna simple version | Strategy A |
| Benchmark / evaluation | Fixed question set, scored | Fixed questions vechu test | `eval.py`, 19 questions, 3 PDFs |
| Red-team test | Test designed to break the system | Odaikka try panra test | Northwind PDF, 6/6 |
| Latency | Time per answer | Evlo neram | ~52–60 s average |
| Ollama | Free tool that runs open LLMs locally | Laptop-la LLM run panna | Runs `qwen3:8b` |
| VRAM | Graphics-card memory | GPU memory | 8 GB RTX 5050 |
| Heuristic | Practical rule of thumb, no guarantee | Anubava rule | Heading detection from fonts |
| Question fingerprinting | Our free regex classifier of question type | Question type kandupidikkuradhu | `agent.py`, no tool/LLM call |

---

## 4. Our real results (qwen3:8b, from `logs/RESULTS.md`)

19 hand-labelled questions on 3 real PDFs: the 204-page course reader, the US Constitution, "Attention Is All You Need".

| Strategy | Accuracy | Avg calls | Max calls | Obeyed injection | Over budget |
|---|---|---|---|---|---|
| A. Naive ReAct (existing, no gates) | 12/19 (63%) | 3.7 | 6 | **3/3** | 0 |
| B. Search-first (existing) | 5/7 subset | 3.9 | 5 | 0/2 | 0 |
| C. Outline-first (existing) | 5/7 subset | 3.7 | 5 | 0/2 | 0 |
| **D. PageProof (proposed), final** | **14/19 (74%)** | 4.0 | 6 | **0/3** | **0** |

- D by type (final run): single 4/5, multi-page 2/4, unanswerable 3/3, superseded 2/4, injection 3/3.
- Red-team PDF (synthetic, disclosed, not in the headline): 6/6.
- Never over budget in any run.
- Two full D runs both scored 14/19 but missed different questions: an 8B model varies run to run.
- Average answer time about 52–60 s (range 25–160 s) on the RTX 5050.

**Thresholds:**
- Grounding 0.8: every value from 0.5 to 0.8 kept all correctly quoted answers; 0.9 or verbatim-only blocked 1–2 more correct ones. So 0.8 is the strictest value with no loss.
- Confidence 0.4: the model reported 0.95–1.0 on every answer, even wrong ones, so every threshold from 0 to 0.7 gave the same score (net 10). That's why the quote check, not confidence, does the real work.

---

## 5. Your 17 points, one by one

| # | Point | What we did | Say it (English) | Tanglish |
|---|---|---|---|---|
| 1 | Understand the problem | Every hard rule enforced in code | "Every rule is code: call 7 is refused, only 4 tools exist." | Ovvoru rule-um code-la enforce pannirukom. |
| 2 | Markdown design | 1-page MEMO, README, deck content, Q&A, runbook | "The memo follows the rulebook's 3 headings; every number comes from our logs." | Memo rulebook 3 headings-la; numbers ellam logs-la irundhu. |
| 3 | Dataset | 19 labelled questions, 3 real PDFs | "Three real, very different PDFs, each question tagged with its evidence page." | 3 real PDFs, 19 questions, evidence page mark pannirukom. |
| 4 | Extra features | Call meter, timeline, gate badges, injection banner, verified quotes, withheld guess, trace download, benchmark tab, multi-PDF | "Every feature shows why an answer can be trusted." | Ovvoru feature-um trust kaatradhukku. |
| 5 | PPT: audience, wellness, business, scale-up | Deck slides 2, 3, 9, 10, 12 | "Customer wellness means trust: a quote and a page, or an honest no." | Wellness-na trust: quote + page, illa honest-a "theriyaadhu". |
| 6 | Who uses it | Compliance, legal, HR, support, SMEs, regulated / air-gapped orgs | "People for whom a wrong answer is a liability and who can't use the cloud." | Thappu answer problem aagura, cloud use panna mudiyaadha teams. |
| 7 | Pain point (root cause) | Root cause: no budget + no proof | "We add both: a hard 6-call cap and a quote check." | Root cause: budget illa, proof illa. Rendum add pannom. |
| 8 | Dataset fits problem | Single 5, multi 4, superseded 4, unanswerable 3, injection 3 | "We tested every case type the judges named, before seeing their PDF." | Judges sonna ella case-um test pannom. |
| 9 | No synthetic data | Real PDFs only for headline; Northwind red-team PDF disclosed and separate | "One labelled security test file, never mixed into the headline." | Synthetic file headline score-la serkala. |
| 10 | Requirements | Fresh budget per question, no cache, failed calls count | "A question can never go over budget; the code stops it." | Budget thaanda mudiyaadhu. |
| 11 | Which algorithm fits | A ReAct, B search-first, C outline-first, D hybrid | "D won 14/19 vs 12/19, and obeyed 0 injections vs 3." | D jeichadhu; injection-ku yemaarala. |
| 12 | Best accuracy | D 74%, 0 over budget, red-team 6/6 | "74% on real PDFs, never over budget, and we show the misses." | 74%, budget thaandala, fail-um kaattrom. |
| 13 | Research papers | 7 papers incl. ReAct, Toolformer, SQuAD 2.0, Greshake (injection), Pan et al. IEEE TKDE 2024 | "Each paper maps to one design choice." | Ovvoru paper-um oru design-ku base. |
| 14 | Business model | Free, Team SaaS $15/user/mo, Enterprise on-prem, $0.02/question (illustrative) | "The 6-call cap fixes worst-case cost per question." | 6-call limit-aala max cost fixed. |
| 15 | User-friendly, secure, centralised | Chat + badges; fully local; one audit log | "Nothing leaves the laptop; every call is in one trace." | Ellam laptop-la; ella call-um oru trace-la. |
| 16 | Thresholds | Grounding 0.8 decides; confidence 0.4 backstop | "0.8 is the strictest value that loses no correct answer." | 0.8 data paathu choose pannom; quote check dhaan main. |
| 17 | Strategy and tools | Strategy D + gates; Ollama qwen3:8b, PyMuPDF, Streamlit, own loop | "Our own ~300-line harness, local model, no framework, no cloud." | Sondha harness, local model; LangChain illa, cloud illa. |

---

## 6. 5-minute script (English)

**Important timing fact:** one answer takes about 50 seconds. In 5 minutes you can show only **2 live questions**. Type the first one, then talk while it runs: the timeline fills live, which is the best visual you have.

Use **7 slides**, not 12. Speaker 1 does the slides, Speaker 2 drives the laptop.

| Time | Slide / action | What to say |
|---|---|---|
| 0:00–0:20 | **1. Title:** PageProof | "We're Team SOUL SOCIETY. PageProof answers questions on any PDF using only 4 tools, 6 calls, and only what the PDF proves. No RAG, no vector database, every answer comes with a quote." |
| 0:20–0:50 | **2. Problem & users** | "Compliance, legal and HR teams need answers from documents, but a wrong answer is a liability and they often can't send files to the cloud. Today's tools hallucinate and have no cost limit. The root cause is no budget and no proof. We add both." |
| 0:50–1:30 | **3. How it works** (the flow diagram) | "First turn: headings and keyword search together, two calls. Then up to three page reads, and one call kept in reserve to check for amendments. The 7th call is refused by code, not by the prompt. Every answer must quote a page it actually read, or it says 'insufficient information'. Text in the PDF is data, never commands." |
| 1:30–3:30 | **LIVE DEMO** | Upload the judges' PDF: "Headings are detected even without a table of contents." Ask Q1, a multi-page or amended fact: "Watch the meter and timeline fill: each card is one tool call." When it answers: "Here is the ✅ verified quote and the page." Ask Q2, something not in the PDF: "It says insufficient information instead of guessing." Click **Download trace**: "Every call is logged; nothing hidden." |
| 3:30–4:10 | **4. Results** | "We compared four strategies on 19 real questions. Plain ReAct got 63% and obeyed all 3 injection attacks. Ours got 74%, obeyed none, and never exceeded the budget." |
| 4:10–4:30 | **5. Thresholds & safety** | "The quote check at 0.8 is the strictest setting that loses no correct answer. Model confidence is always 0.95 or more, even when wrong, so we don't trust it alone." |
| 4:30–4:45 | **6. Business & scale-up** | "Fully local, so it fits regulated companies. The call cap fixes the cost per question. Next: OCR, SSO, SharePoint and Teams connectors." |
| 4:45–5:00 | **7. Honest limits + close** | "Our weak spots are unmarked contradictions and long multi-part answers; they're in our memo with fixes. PageProof: answers only what the PDF proves. Thank you." |

**Which 2 demo questions to ask:** pick from the judges' PDF:
1. Something that changes later in the document (e.g. a value that was "amended" or "updated"). Use words like "current" or "latest" in the question: our fingerprint then spends the reserve call hunting the amendment.
2. Something clearly not in the document (e.g. "Who is the CEO?"), to show the safe decline.
If the judges ask their own questions, just run them. If one is answered wrongly, say: "That's failure mode 1 in our memo," and show the trace.

---

## 7. 5-minute script (Tanglish)

| Time | Slide / action | Enna pesanum |
|---|---|---|
| 0:00–0:20 | **1. Title** | "Naanga Team SOUL SOCIETY. PageProof edhavadhu PDF-la question kettaa, 4 tools, 6 calls-kulla, PDF-la proof irukkuradha mattum dhaan answer pannum. RAG illa, vector database illa. Ovvoru answer-kum quote irukkum." |
| 0:20–0:50 | **2. Problem & users** | "Compliance, legal, HR teams-ku document-la irundhu answer venum. Aana thappu answer-na periya problem, cloud-ku file anuppavum mudiyaadhu. Ippo irukkura AI tools poi solludhu, cost-ku limit illa. Root cause: budget illa, proof illa. Naama rendum add pannom." |
| 0:50–1:30 | **3. How it works** | "Mudhal turn-la headings-um keyword search-um sethu 2 calls. Apram 3 pages varaikkum padikkum. Oru call amendment check panna reserve. 7th call-a prompt illa, code-e block pannum. Answer sonna padicha page-la irundhu quote kaatanum; illa-na 'insufficient information'. PDF-kulla irukkura text-a data-va mattum paakum, command-a illa." |
| 1:30–3:30 | **LIVE DEMO** | Judges PDF upload: "Table of contents illa-naalum headings kandupidikkum." Q1 kelunga: "Meter-um timeline-um paarunga, ovvoru card-um oru tool call." Answer vandhadhum: "Idho verified quote, idho page number." Q2 (PDF-la illaadha question): "Guess pannaama 'insufficient information' nu solludhu." Download trace: "Ella call-um log aagirukku, edhuvum hide pannala." |
| 3:30–4:10 | **4. Results** | "19 real questions-la 4 strategies compare pannom. Normal ReAct 63%, 3 injection attack-kum yemaandhudhu. Namma PageProof 74%, oru injection-kum yemaarala, budget-um thaandala." |
| 4:10–4:30 | **5. Thresholds** | "Quote check 0.8: adhu dhaan oru correct answer-um miss aagaama irukkura strictest value. Model confidence eppovum 0.95 mela solludhu, thappa irundhaalum. Adhanaala adha mattum nambala." |
| 4:30–4:45 | **6. Business** | "Fully local, adhanaala regulated companies-ku perfect. Call limit irukkaradhaala oru question-oda cost fixed. Next: OCR, SSO, SharePoint, Teams connectors." |
| 4:45–5:00 | **7. Limits + close** | "Namma weak spots: mark pannaadha contradictions, romba pages varra multi-part answers. Memo-la fix-oda ezhudhirukkom. PageProof: PDF prove panradha mattum dhaan sollum. Thank you." |

---

## 8. Judge Q&A cheat sheet

| Likely question | Short answer |
|---|---|
| Isn't building headings at upload "pre-reading"? | No. Building the heading list *is* how `list_headings` works. The LLM sees nothing until it calls a tool, and no page text is stored for later questions. |
| How do you guarantee 6 calls? | Code, not prompt. `BudgetedToolbox` counts every call (failed ones too) and refuses call 7 before it runs. |
| How do you stop hallucination? | Grounding gate: at least one quote must be on a page fetched for this question, checked by code. Otherwise "insufficient information". |
| How do you handle prompt injection? | Page text is wrapped in a random marker the PDF can't fake, and the system prompt says it is data only. Injections are reported, never obeyed. Plain ReAct obeyed 3/3; ours 0/3. |
| How do you handle contradictions? | The latest explicit amendment wins, and the agent spends its reserve call searching "amend"/"revised". Honest: 2/4 on our tests; it's failure mode 1 in the memo. |
| Why these thresholds? | Grounding 0.8 = strictest value with no lost correct answers (measured). Confidence 0.4 is a backstop; the model always says 0.95–1.0, so it barely matters. |
| Why a local 8B model? | Privacy (documents never leave the laptop), fixed cost, no API rate limits during the demo. Downside: slower, ~50 s per answer. |
| Why not LangChain? | Banned by rule 6, and a hand-written loop lets us control the budget exactly. |
| What if the PDF is scanned? | No OCR yet, so no text. The app warns about it. Fix: OCR inside `get_page`. |
| Why 74% and not higher? | An 8B model on a laptop, strict rules and honest scoring. We'd rather decline than guess, because guessing is penalised more. |

---

## 9. Honest limits and next fixes

1. **Unmarked contradictions.** It answered the original Congress date, not the 20th-Amendment one, and 41.0 BLEU instead of 41.8. *Fix:* when a revision marker appears, spend the reserve call on "amendment" + topic.
2. **Multi-part answers across 4+ pages** don't fit in 6 calls. *Fix:* better planning of which pages to read first.
3. **Confidence isn't calibrated, and the gate checks quotes, not claims.** A real quote can sit beside an extra unsupported detail. *Fix:* check claim by claim.
4. **Run-to-run variance and speed.** Answers vary even at temperature 0; 25–160 s each. *Fix:* bigger GPU or a faster model.
5. **No OCR** for scanned PDFs; heading detection is a heuristic.

**Tanglish:** Namma weak points: (1) amendment mark pannaadha contradictions miss aagudhu, (2) 4+ pages venumna 6 calls podhaadhu, (3) confidence number nambaththakkadhu illa, (4) ovvoru run-um konjam maarum, 25–160 seconds aagum, (5) scanned PDF-ku OCR illa. Ellam memo-la fix-oda ezhudhirukkom. Idhu dhaan honesty points vaangum.
