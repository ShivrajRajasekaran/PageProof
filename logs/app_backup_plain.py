"""Chat UI: upload a PDF, ask questions. Run: streamlit run app.py"""
import json, os, tempfile, time, warnings
warnings.filterwarnings("ignore")
import streamlit as st
from rapidagent.agent import CONF_THRESHOLD, STRATEGY, TOOL_BUDGET, DocAgent
from rapidagent.llm import OLLAMA_MODEL
from rapidagent.tools import DocStore

st.set_page_config(page_title="PageProof", page_icon="📄", layout="wide")
st.title("📄 PageProof")
st.markdown("**Budget-bounded, evidence-verified document agent — answers only what the PDF proves.** Runs fully local (Ollama).")
st.caption(f"Answers only from the uploaded PDF through 4 tools (list_documents, list_headings, get_page, search_keyword) · "
           f"max {TOOL_BUDGET} tool calls per question · no RAG / embeddings.")

with st.sidebar:
    st.header("Document")
    files = st.file_uploader("Upload PDF(s)", type="pdf", accept_multiple_files=True)
    model = st.text_input("Ollama model", OLLAMA_MODEL)
    strategy = st.selectbox("Agent strategy", ["D", "C", "B", "A"], index=["D", "C", "B", "A"].index(STRATEGY),
                            format_func=lambda k: {"D": "D · PageProof hybrid (proposed)", "C": "C · Outline-first", "B": "B · Search-first", "A": "A · Naive ReAct (no gates)"}[k])
    st.caption(f"Confidence threshold: {CONF_THRESHOLD} · local inference, no document leaves this machine.")

def build(files):
    store = DocStore()
    for f in files:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as t:
            t.write(f.getvalue())
        store.add_pdf(t.name, original_name=f.name)
    return store

sig = tuple((f.name, f.size) for f in files)
if files and st.session_state.get("sig") != sig:
    with st.spinner("Opening PDF and reading its outline (no embeddings, no page cache)…"):
        st.session_state.store = build(files)
    st.session_state.sig = sig
    st.session_state.chat = []
    st.session_state.history = []
    st.session_state.logfile = f"logs/session_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"

if not files:
    st.info("Upload a PDF in the sidebar to start.")
    st.stop()

store = st.session_state.store
with st.sidebar:
    for d in store.docs.values():
        st.success(f"**{d.doc_id}**: {d.title} — {d.meta['num_pages']} pages")
        st.caption(f"Outline: {len(d.headings)} headings ({d.heading_source})")
        if not d.meta.get("has_text_layer", True):
            st.error("No text layer found (scanned PDF?). OCR is not supported, so answers will be 'insufficient information'.")
        with st.expander("Detected headings"):
            st.text("\n".join(f"{'  ' * (h['level'] - 1)}{h['title']}  (p{h['page']})" for h in d.headings) or "none")
    if os.path.exists(st.session_state.logfile):
        st.download_button("⬇ Full tool-call trace (JSONL)", open(st.session_state.logfile, "rb").read(), "tool_calls_trace.jsonl")

def render_trace(trace):
    for e in trace:
        if e["status"] == "info":
            st.markdown(f"ℹ️ `{e['tool']}` (not a tool call, logged for audit)")
            continue
        res = e["result"]
        brief = (f"{len(res)} chars" if e["tool"] == "get_page" and e["status"] == "ok"
                 else f"{len(res)} headings" if e["tool"] == "list_headings" and e["status"] == "ok" else res)
        tag = f"**#{e['call_no']}**" if e.get("counted") else "**✗ (not counted)**"
        st.markdown(f"{tag} `{e['tool']}({', '.join(f'{k}={v!r}' for k, v in e['args'].items())})` → `{e['status']}` {brief}")

def render_result(r):
    if r["status"] == "answered":
        st.success(f"Answered · confidence {r['confidence']:.2f} · tool calls {r['used']}/{TOOL_BUDGET}")
    else:
        st.warning(f"Insufficient information · tool calls {r['used']}/{TOOL_BUDGET}")
    st.markdown(r["answer"])
    for n in r["notes"]:
        st.caption("⚠ " + n)
    if r["evidence"]:
        with st.expander("Evidence (verbatim quotes)"):
            for ev in r["evidence"]:
                st.markdown(f"- p.{ev['page']} {'✅' if ev.get('verified') else '❓'} “{ev['quote']}”")
    if r.get("tentative"):
        with st.expander("Withheld tentative answer"):
            st.write(r["tentative"])
    with st.expander(f"Tool-call trace ({r['used']} calls, {r['seconds']}s)"):
        render_trace(r["trace"])

for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        if m["role"] == "user":
            st.write(m["content"])
        else:
            render_result(m["content"])

if q := st.chat_input("Ask a question about the document…"):
    st.session_state.chat.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.write(q)
    with st.chat_message("assistant"):
        live = st.status("Working…", expanded=True)
        def on_event(kind, e):
            if kind == "tool":
                live.write(f"{'#' + str(e.get('call_no')) if e.get('counted') else '✗'} `{e['tool']}({', '.join(f'{k}={v!r}' for k, v in e['args'].items())})` → {e['status']}")
        try:
            agent = DocAgent(store, model=model, log_path=st.session_state.logfile, strategy=strategy)
            r = agent.ask(q, history=st.session_state.history, on_event=on_event)
            live.update(label=f"Done · {r.tool_calls_used}/{TOOL_BUDGET} tool calls", state="complete", expanded=False)
            res = dict(status=r.status, answer=r.answer, confidence=r.confidence, evidence=r.evidence, used=r.tool_calls_used,
                       trace=r.trace, notes=r.notes, tentative=r.tentative_answer, seconds=r.seconds)
            render_result(res)
            st.session_state.chat.append({"role": "assistant", "content": res})
            st.session_state.history.append((q, r.answer))
            ok = True
        except Exception as ex:  # noqa: BLE001
            ok = False
            live.update(label="Error", state="error")
            st.error(f"{type(ex).__name__}: {ex}")
    if ok:
        st.rerun()  # redraw so the sidebar trace download includes this question
