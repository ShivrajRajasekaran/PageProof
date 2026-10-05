# PageProof — Full Tanglish Guide
Team SOUL SOCIETY · RAP Hackathon 2026

(English technical words appadiye vechirukkom, judges kekkumbodhu same words use pannunga.)

---

## 1. PageProof — 60 seconds-la

**PageProof oru chat app. Edhavadhu oru PDF upload panni question kettaa, 4 tools mattum use panni, maximum 6 tool calls-kulla, PDF-la proof irukkuradha mattum dhaan answer pannum.**

**Problem enna?**
- Companies-ku avanga sondha documents-la (policy, contract, manual) irundhu answer venum.
- Ippo ellarum use panradhu **RAG**: document-a chinna chinna pieces-a cut panni, numbers (vectors)-a maathi, vector database-la store pannuvaanga.
- Idhukku ovvoru document set-kum setup, cost venum. Document maarina index pazhasaagidum. Aprum AI innum poi sollum (hallucination).
- Hackathon RAG-a ban panniduchu. Kelvi: "Oru manushan maadhiri — contents page paathu, word search panni, page open panni — limited budget-la AI padikka mudiyumaa?"

**Namma answer:**
- PDF-a 4 tools moolama mattum dhaan padikkum: `list_documents`, `list_headings`, `get_page`, `search_keyword`
- Oru question-ku 6 tool calls dhaan. 7th call-a **code-e block pannidum**, prompt illa.
- Answer sonna, andha question-kaaga padicha page-la irundhu **quote** kaatanum. Illa-na "insufficient information" — guess panna maattom.
- PDF-kulla "ignore your rules" maadhiri ezhudhi irundha, adha **data**-va mattum paakum, command-a follow panna maattom.
- Ellame laptop-laye local-a odudhu (Ollama + `qwen3:8b`). Document veliya pogave pogadhu.
- Ovvoru tool call-um log aagum; judges trace download pannalaam.

**Oru line pitch:** "RAG illa. Vector database illa. Six tool calls. Ovvoru answer-kum oru quote."

---

## 2. Eppadi work aagudhu — step by step

```
 PDF upload ──► Headings list mattum ready (page text store pannala)
      │
 Question ──► Fingerprint (regex, free): comparison / maaridichaa / multi-part / definition / fact
      │
      ▼
 Agent loop (namma sondha code, LangChain illa)    BudgetedToolbox ovvoru call-um count + log
   Turn 1: list_headings + search_keyword  (2)     ── 7th call-a REFUSE pannidum
   Apram:  get_page × 1–3                  (3)
   Reserve: amendment / next page-ku 1 call (1)
      │
      ▼
 final_answer ("+1" call): status, answer, quotes, pages, confidence
      │
      ▼
 Gates: ① decline check  ② grounding gate (quote padicha page-la irukkaa, 0.8)  ③ confidence ≥ 0.4
      │                       fail ──► "insufficient information" (guess label panni kaattum)
      ▼
 UI: answer + ✅ quotes + timeline + call meter + trace download
```

1. **Upload:** PDF-oda outline (table of contents) irundha adha edukkum. Illa-na font size, bold text vechu headings kandupidikkum. Adhu mattum dhaan. Page text-a munnadiye store panna maattom.
2. **Fingerprint:** Question enna type nu regex vechu kandupidikkum (free — tool call illa, LLM call illa). Udharanam: "current", "latest" maadhiri word irundha, "idhu maari irukkalaam, reserve call-la 'amend' search pannu" nu hint kudukkum.
3. **Turn 1-la 2 calls sethu:** `list_headings` (map) + `search_keyword` (coordinates — endha page-la word irukku).
4. **1–3 pages padikkum** `get_page` vechu — oru call-ku oru page dhaan.
5. **Reserve call:** amendment check panna illa adutha page continue aagudhaa paakka oru call vechirukkom.
6. **Budget:** `BudgetedToolbox` ovvoru call-um count pannum (fail aana call-um count). 7th call run aagradhukku munnadiye block. Adhanaala budget thaandave mudiyaadhu.
7. **Final answer:** model `final_answer` call pannum — status, answer, exact quotes, page numbers, confidence.
8. **Gates (checks):**
   - Decline check: search hits padikkaama, budget irukkum bodhe model "theriyaadhu" nu sonna, harness oru thadava "innum padi" nu thirumbi anuppum.
   - Grounding gate: kammi-yaa oru quote-aavadhu indha question-la padicha page-la irukkanum (exact-a, illa 80% 3-word pieces match + ella numbers-um match).
   - Confidence 0.4-ku keezha irundha decline.
   - Edhavadhu gate fail-na "insufficient information". Model-oda guess-a "withheld" nu label panni kaattum.
9. **Ellathaiyum kaattum:** answer, ✅/❓ quotes, ovvoru call-oda timeline, 6-slot meter, JSONL trace download.

---

## 3. ML / AI words — Tanglish-la

| Word | Tanglish meaning | Namma project-la enga |
|---|---|---|
| LLM | Romba text-la train panna AI; adutha word predict panni yosikkum, ezhudhum | `qwen3:8b` — endha tool call pannanum, answer enna nu decide pannudhu |
| Agent / agentic AI | AI step by step work pannum: yosi, tool use pannu, result paaru, marubadi decide pannu | `DocAgent` (`agent.py`) |
| Tool / function calling | AI "indha function-a run pannu" nu kekkum, program run panni result thirumba kudukkum | 4 tools + `final_answer` |
| Harness | AI-ya control panra code: loop, budget, log, checks | `BudgetedToolbox`, gates, trace — score-la 20% |
| ReAct | Yosi (Reason), apram act pannu (Act), repeat | Strategy A — namma baseline |
| RAG | Database-la irundhu relevant text eduthu AI-ku kudukkuradhu | Ban — use pannala |
| Embedding / vector | Text-oda meaning-a numbers list-a maathuradhu | Ban — create pannave illa |
| Vector database | Meaning vechu text thedura database | Ban — illa |
| Keyword search | Ctrl+F maadhiri exact word thedradhu | `search_keyword` — page numbers mattum tharum |
| Context window | AI oru time-la evlo text paakka mudiyum | 16k tokens |
| Token | Word-oda chinna pieces; AI text-a tokens-a count pannum | Context, output limit |
| Temperature | AI-oda randomness; 0-na mostly same answer | Naama 0 use panrom |
| Hallucination | AI confident-a poi solradhu | Grounding gate block pannum |
| Grounding | Answer-a real document text-oda link panradhu | Padicha page-la irundhu quote venum |
| Grounding gate | Quote unmaiyaave padicha page-la irukkaa nu code check | `_quote_supported()`, 0.8 |
| 3-gram | Thodarndhu varra 3 words ("refund window is") | Quote-oda 80% 3-grams page-la irukkanum |
| Confidence score | Model "naan evlo sure" nu solra number, 0 to 1 | 0.4 backstop; model eppovum 0.95–1.0 solludhu |
| Threshold | Cut-off: mela-na accept, keezha-na decline | Grounding 0.8, confidence 0.4 |
| Calibration | Model sonna confidence unmaiyaa match aagudhaa | Namma model-ku illa, adhanaala quote check |
| Prompt injection | AI-ya emaathi vera vela seiya vaikkura text ("ignore your rules") | Page text-a random marker-kulla vechu data-va mattum treat |
| System prompt | AI-ku munnadiye kudukkura hidden rules | `SYSTEM_PROMPT` (`agent.py`) |
| Accuracy | Evlo questions correct-a answer pannudhu | D: 14/19 (74%) |
| Baseline | Compare panna simple version | Strategy A |
| Benchmark / evaluation | Fixed questions vechu test panni score paakradhu | `eval.py`, 19 questions, 3 PDFs |
| Red-team test | System-a odaikka try panra test | Northwind PDF — 6/6 |
| Latency | Oru answer-ku evlo neram | ~52–60 seconds average |
| Ollama | Laptop-laye free-a LLM run panna tool | `qwen3:8b` run pannudhu |
| VRAM | Graphics card memory | RTX 5050 — 8 GB |
| Heuristic | Anubava rule, guarantee illa | Font vechu headings kandupidikkuradhu |
| Question fingerprinting | Question enna type nu regex vechu kandupidichu route solradhu | `agent.py` — call illa |

---

## 4. Namma results (qwen3:8b, `logs/RESULTS.md`-la irundhu)

3 real PDFs-la 19 questions: 204-page course reader, US Constitution, "Attention Is All You Need" paper.

| Strategy | Accuracy | Avg calls | Max calls | Injection-ku yemaandhadhu | Budget thaandinadhu |
|---|---|---|---|---|---|
| A. Normal ReAct (gates illa) | 12/19 (63%) | 3.7 | 6 | **3/3** | 0 |
| B. Search-first | 5/7 subset | 3.9 | 5 | 0/2 | 0 |
| C. Outline-first | 5/7 subset | 3.7 | 5 | 0/2 | 0 |
| **D. PageProof (namma), final** | **14/19 (74%)** | 4.0 | 6 | **0/3** | **0** |

- D type-wise (final run): single 4/5, multi-page 2/4, answer illaadhadhu 3/3, superseded (maarina facts) 2/4, injection 3/3.
- Red-team PDF (synthetic, open-a solliyirukkom, headline-la serkala): 6/6.
- Endha run-layum budget thaandala.
- 2 full D runs rendum 14/19, aana vera vera questions miss — 8B model run-ku run konjam maarum.
- Oru answer-ku average ~52–60 seconds (25–160 s range).

**Thresholds:**
- Grounding 0.8: 0.5-la irundhu 0.8 varaikkum ella correct answers-um pass. 0.9 illa exact-only vechaa 1–2 correct answers block aagudhu. Adhanaala 0.8 = edhuvum miss aagaama irukkura strictest value.
- Confidence 0.4: model ella answer-kum 0.95–1.0 solludhu, thappaa irundhaalum. Adhanaala 0-la irundhu 0.7 varaikkum endha threshold vechaalum same score. Adhanaala dhaan quote check main, confidence illa.

---

## 5. Unga 17 points — Tanglish-la

| # | Point | Enna pannom | Judges-kitta enna solradhu |
|---|---|---|---|
| 1 | Problem purinjukkradhu | Ovvoru hard rule-um code-la enforce | "Ovvoru rule-um code: 7th call refuse, 4 tools mattum dhaan." |
| 2 | Markdown design | 1-page MEMO, README, deck content, Q&A, runbook | "Memo rulebook sonna 3 headings-la irukku; numbers ellam logs-la irundhu." |
| 3 | Dataset | 3 real PDFs, 19 labelled questions | "3 vera vera maadhiri real PDFs; ovvoru question-kum evidence page mark pannirukom." |
| 4 | Extra features | Call meter, timeline, gate badges, injection banner, verified quotes, withheld guess, trace download, benchmark tab, multi-PDF | "Ovvoru feature-um 'indha answer-a nambalaam' nu kaatradhukku dhaan." |
| 5 | PPT: audience, wellness, business, scale-up | Deck slides 2, 3, 9, 10, 12 | "Customer wellness-na trust: quote + page, illa-na honest-a 'theriyaadhu'." |
| 6 | Yaaru use pannuvaanga | Compliance, legal, HR, support, SMEs, regulated / air-gapped companies | "Thappu answer-na periya problem aagura, cloud-ku file anuppa mudiyaadha teams." |
| 7 | Pain point (root cause) | Root cause: budget illa + proof illa | "Naama rendum add pannom: 6-call limit + quote check." |
| 8 | Dataset problem-ku match aagudhaa | Single 5, multi 4, superseded 4, answer illaadhadhu 3, injection 3 | "Judges sonna ella case type-um avanga PDF paakradhukku munnadiye test pannom." |
| 9 | Synthetic data illa | Headline-ku real PDFs mattum; Northwind test PDF open-a solli, thani-yaa score | "Oru security test file mattum synthetic, adha headline-la serkala." |
| 10 | Requirements | Ovvoru question-kum fresh budget, cache illa, fail call-um count | "Budget thaandave mudiyaadhu, code-e niruthidum." |
| 11 | Endha algorithm best | A ReAct, B search-first, C outline-first, D hybrid compare | "D jeichadhu: 14/19 vs 12/19; injection-ku 0 times vs 3 times." |
| 12 | Best accuracy | D 74%, budget thaandala, red-team 6/6 | "Real PDFs-la 74%, budget eppovum thaandala, fail aanadhum kaattrom." |
| 13 | Research papers | ReAct, Toolformer, SQuAD 2.0, Greshake (injection), Pan et al. IEEE TKDE 2024 uttpada 7 papers | "Ovvoru paper-um oru design decision-ku base." |
| 14 | Business model | Free, Team SaaS $15/user/month, Enterprise on-prem, $0.02/question (example pricing) | "6-call limit irukkaradhaala oru question-oda maximum cost fixed." |
| 15 | User-friendly, secure, centralised | Chat + badges; fully local; oru audit log | "Edhuvum laptop-a vittu pogadhu; ella call-um oru trace-la." |
| 16 | Thresholds | Grounding 0.8 main; confidence 0.4 backstop | "0.8 data paathu choose pannom — oru correct answer-um miss aagaama irukkura strictest value." |
| 17 | Strategy & tools | Strategy D + gates; Ollama qwen3:8b, PyMuPDF, Streamlit, sondha loop | "~300 lines namma sondha harness, local model; LangChain illa, cloud illa." |

---

## 6. 5-minute script — Tanglish

**Mukkiyamaana timing:** oru answer-ku ~50 seconds aagum. 5 minutes-la **2 live questions** dhaan kaatta mudiyum. Mudhal question type panni, adhu odumbodhu pesunga — timeline live-a fill aagradhu dhaan best visual.

**12 slides illa, 7 slides** use pannunga. Oruthar slides pesanum, innoruthar laptop drive pannanum.

| Time | Slide / action | Enna pesanum |
|---|---|---|
| 0:00–0:20 | **1. Title** | "Naanga Team SOUL SOCIETY. PageProof edhavadhu PDF-la question kettaa, 4 tools, 6 calls-kulla, PDF-la proof irukkuradha mattum dhaan answer pannum. RAG illa, vector database illa. Ovvoru answer-kum quote irukkum." |
| 0:20–0:50 | **2. Problem & users** | "Compliance, legal, HR teams-ku document-la irundhu answer venum. Aana thappu answer-na periya problem, cloud-ku file anuppavum mudiyaadhu. Ippo irukkura AI tools poi solludhu, cost-ku limit illa. Root cause: budget illa, proof illa. Naama rendum add pannom." |
| 0:50–1:30 | **3. How it works** | "Mudhal turn-la headings-um keyword search-um sethu 2 calls. Apram 3 pages varaikkum padikkum. Oru call amendment check panna reserve. 7th call-a prompt illa, code-e block pannum. Answer-ku padicha page-la irundhu quote venum; illa-na 'insufficient information'. PDF-kulla irukkura text data mattum dhaan, command illa." |
| 1:30–3:30 | **LIVE DEMO** | Judges PDF upload: "Table of contents illa-naalum headings kandupidikkum." Q1 kelunga: "Meter-um timeline-um paarunga — ovvoru card-um oru tool call." Answer vandhadhum: "Idho verified quote, idho page number." Q2 (PDF-la illaadha question): "Guess pannaama 'insufficient information' nu solludhu." Download trace: "Ella call-um log aagirukku, edhuvum hide pannala." |
| 3:30–4:10 | **4. Results** | "19 real questions-la 4 strategies compare pannom. Normal ReAct 63%, 3 injection attack-kum yemaandhudhu. Namma PageProof 74%, oru injection-kum yemaarala, budget-um thaandala." |
| 4:10–4:30 | **5. Thresholds & safety** | "Quote check 0.8 — oru correct answer-um miss aagaama irukkura strictest value. Model confidence eppovum 0.95 mela solludhu, thappa irundhaalum. Adhanaala adha mattum nambala." |
| 4:30–4:45 | **6. Business & scale-up** | "Fully local, adhanaala regulated companies-ku perfect. Call limit irukkaradhaala oru question-oda cost fixed. Next: OCR, SSO, SharePoint, Teams connectors." |
| 4:45–5:00 | **7. Limits + close** | "Namma weak spots: mark pannaadha contradictions, romba pages varra multi-part answers. Memo-la fix-oda ezhudhirukkom. PageProof — PDF prove panradha mattum dhaan sollum. Thank you." |

**Demo-la endha 2 questions kekkalaam (judges PDF-la irundhu):**
1. Document-la apram maarina oru value (amended / updated). Question-la "current" illa "latest" word podunga — appo fingerprint reserve call-a amendment thedradhukku use pannum.
2. PDF-la kandippa illaadha onnu (e.g. "Who is the CEO?") — safe decline kaatta.

Judges avanga sondha question kettaa, run pannunga. Thappa vandhaa: "Idhu namma memo-la failure mode 1," nu solli trace kaattunga.

---

## 7. Judges Q&A — Tanglish-la

| Judges kelvi | Short answer |
|---|---|
| Upload-la headings build panradhu "pre-reading" illaiyaa? | Illa. Heading list build panradhu dhaan `list_headings` tool-oda vela. AI tool call pannra varaikkum edhuvum paakaadhu; page text store pannala. |
| 6 calls eppadi guarantee? | Code, prompt illa. `BudgetedToolbox` ovvoru call-um (fail aanadhum) count pannum; 7th call run aagradhukku munnadiye refuse. |
| Hallucination eppadi stop panreenga? | Grounding gate: kammi-yaa oru quote indha question-la padicha page-la irukkanum nu code check pannum. Illa-na "insufficient information". |
| Prompt injection? | Page text-a PDF fake panna mudiyaadha random marker-kulla vechu, "idhu data mattum" nu system prompt sollum. Normal ReAct 3/3 yemaandhudhu; namma 0/3. |
| Contradictions? | Latest amendment jeikkum; reserve call-la "amend"/"revised" thedum. Honest-a: namma test-la 2/4 — memo-la failure mode 1. |
| Indha thresholds yen? | Grounding 0.8 = oru correct answer-um miss aagaama irukkura strictest value (measure pannom). Confidence 0.4 backstop; model eppovum 0.95+ solradhaala adhu perusa maathaadhu. |
| Yen local 8B model? | Privacy (document veliya pogadhu), cost fixed, demo-la API limit problem illa. Minus: slow, ~50 s per answer. |
| Yen LangChain illa? | Rule 6 ban pannirukku; aprum sondha loop-la budget-a exact-a control panna mudiyum. |
| Scanned PDF-na? | OCR innum illa, text varaadhu. App warning kaattum. Fix: `get_page`-kulla OCR. |
| Yen 74% dhaan? | Laptop-la 8B model, strict rules, honest scoring. Guess pannradha vida decline better — guess-ku dhaan adhiga penalty. |

---

## 8. Honest limits — Tanglish-la

1. **Mark pannaadha contradictions:** Congress meeting date-ku original date sonnuchu, 20th Amendment date illa. BLEU 41.8-ku badhila 41.0 sonnuchu. *Fix:* revision mark paatha, reserve call-la "amendment" + topic search.
2. **4+ pages venumna multi-part answers** 6 calls-la fit aagala. *Fix:* endha pages first padikkanum nu better planning.
3. **Confidence nambaththakkadhu illa; gate quote-a mattum check pannum, claim-a illa.** Real quote pakkathula oru extra detail thappa irukkalaam. *Fix:* claim by claim check.
4. **Ovvoru run-um konjam maarum, slow:** temperature 0-la kooda; 25–160 seconds. *Fix:* perusa GPU illa faster model.
5. **Scanned PDF-ku OCR illa;** headings kandupidikkradhu heuristic dhaan.

Idhellam memo-la honest-a ezhudhirukkom — rulebook-la "honesty about gaps"-ku partial credit irukku. Adhu namakku points.
