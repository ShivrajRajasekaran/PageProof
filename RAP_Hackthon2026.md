# Problem Statement: Budgeted Document-Answering Agent

**Duration:** 6 hours
**Team size:** 2 members
**Track:** AI/ML — Agentic Systems and Harness Design

---

## Background

Organizations increasingly need systems that can answer questions from internal documents without maintaining a separate vector database or embedding pipeline for every document set. This challenge asks you to build an agent that reads documents directly and reasons over them under strict operating constraints, closer to how an agent would need to work in a lightweight or resource-constrained deployment.

---

## What You Are Given

- **Sample PDFs.** These are for you to build and test against during the event. They are representative of the kind of documents your app will be evaluated on, but are not the documents used for judging.
- Tool interface constraints (you need to write the code for this yourself), which is the only way to access document content:
  - `list_documents()` — returns titles and metadata for all documents (nothing else)
  - `list_headings(doc_id)` — returns the table of contents / list of all headings for a document (nothing else)
  - `get_page(doc_id, page_number)` — returns the text of one page (only one page, no page ranges)
  - `search_keyword(doc_id, keyword)` — returns page numbers where a keyword appears (only page numbers, nothing else)
- A small set of sample questions with expected answers, based on the sample PDFs.

---

## The Task

Build an app with a chat interface that takes a PDF uploaded directly by the user and lets them ask questions about it. The app must answer questions correctly using only the tool interface described above. Your architecture, not just your code, will be evaluated.

### Hard Constraints

1. **No RAG, no embeddings, no vector database.** Any submission using semantic/vector search over the documents will be disqualified.
2. **No direct access to raw document text.** All reading must go through the tool interface listed. You may not design your own additional tools.
3. **Total tool call budget: 6 tool calls per question**, plus 1 final answer call. Exceeding this on a question marks that question as failed, regardless of whether the answer given was correct.
4. **The agent must be able to say "insufficient information."** Guessing when the document doesn't contain an answer is penalized more heavily than correctly declining to answer.
5. You may use any GenAI tools for coding. There is no restriction on this.
6. You may not use any agentic frameworks for this task, including LangChain, LangGraph, CrewAI, AutoGen, or similar. Allowed:
   - Any LLM provider or open-source model inference (OpenAI, Ollama, Vertex AI, Together AI, Gemini, Anthropic, etc.)
   - Any PDF-reading method of your choice
   - Any UI framework to build the chat interface

---



## Live Demonstration

At judging time, you will be given a **new PDF you have not seen before** and asked to run it through your app live in front of the judges. Your app must accept this PDF directly through your chat interface and answer questions about it on the spot, using the same tool interface and call budget as during development. Your solution must generalize to any PDF, not just the samples provided.

---

## Deliverables

Submit all of the following by the end of the 6-hour window:

1. **Working code** for your agent on OneDrive, including the required call-logging wrapper (provided) so that every tool call your agent makes is recorded.
2. **A short written memo (1 page)** covering:
   - Architecture of your agent design (a diagram is not required if time does not permit; a verbal explanation is fine)
   - What you did and why (you must be able to justify any design choice or feature present in your code)

   - Any known failure mode you did not have time to fix (explain the problem and your intended solution verbally)
3. **Full trace of your agent's tool calls** for the live demonstration. Nothing hidden.

---

## Evaluation Criteria

| Component | Weight |
|---|---|
| Overall agent harness design and architecture | 20% |
| Accuracy on the live, unseen PDF, within the call budget | 30% |
| Quality of your written memo (reasoning, honesty about gaps) | 30% |
| Your ability to explain and justify your solution when questioned | 20% |

The live demonstration PDF will include cases such as: answers requiring information from multiple pages, content that contradicts or supersedes an earlier statement in the same document, questions with no answer in the document, and text that attempts to redirect the agent's behavior (the correct response is to ignore such text and answer the user's actual question).

---

## Notes

- You are expected to test your solution against the sample PDFs and sample questions before relying on it.
- The 6-call budget applies per question. Reading pages ahead of time and caching them locally to bypass this limit during a question does not satisfy the intent of the constraint and will be treated as a violation.
- Partial credit is given for correctly identifying a failure mode in your memo even if you were unable to fully fix it in time.
