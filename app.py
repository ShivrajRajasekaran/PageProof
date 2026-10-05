"""PageProof chat UI: upload a PDF, ask questions, watch the budgeted agent work. Run: streamlit run app.py"""
import glob, html, json, os, tempfile, time, warnings
warnings.filterwarnings("ignore")
import streamlit as st
from rapidagent.agent import CONF_THRESHOLD, STRATEGY, TOOL_BUDGET, DocAgent
from rapidagent.llm import OLLAMA_MODEL
from rapidagent.tools import DocStore

st.set_page_config(page_title="PageProof", page_icon="📄", layout="wide")

st.markdown("""
<style>
:root { --pp-accent:#6366f1; --pp-ok:#10b981; --pp-warn:#f59e0b; --pp-bad:#ef4444; --pp-muted:#94a3b8; }
.block-container { padding-top: 1.6rem; max-width: 1200px; }
.pp-hero { background: linear-gradient(135deg,#1e1b4b 0%,#312e81 55%,#4338ca 100%); color:#fff; border-radius:16px;
           padding:22px 26px; margin-bottom:14px; }
.pp-hero h1 { margin:0; font-size:2.1rem; letter-spacing:-.02em; color:#fff; }
.pp-hero p { margin:.35rem 0 0; color:#c7d2fe; font-size:1rem; }
.pp-chips { margin-top:12px; display:flex; flex-wrap:wrap; gap:8px; }
.pp-chip { background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.22); padding:3px 10px; border-radius:999px;
           font-size:.8rem; color:#e0e7ff; }
.pp-meter { display:flex; gap:6px; align-items:center; margin:6px 0 10px; flex-wrap:wrap; }
.pp-slot { width:38px; height:38px; border-radius:9px; display:flex; align-items:center; justify-content:center;
           font-weight:700; font-size:.85rem; border:2px solid #cbd5e1; color:#94a3b8; background:transparent; }
.pp-slot.used { background:var(--pp-accent); border-color:var(--pp-accent); color:#fff; }
.pp-slot.err { background:var(--pp-warn); border-color:var(--pp-warn); color:#fff; }
.pp-slot.blocked { border-style:dashed; border-color:var(--pp-bad); color:var(--pp-bad); }
.pp-slot.final { width:auto; padding:0 10px; border-color:var(--pp-ok); color:var(--pp-ok); }
.pp-slot.final.done { background:var(--pp-ok); color:#fff; }
.pp-step { border-left:3px solid var(--pp-accent); padding:6px 12px; margin:6px 0; border-radius:0 8px 8px 0;
           background:rgba(99,102,241,.07); font-size:.9rem; }
.pp-step.err { border-left-color:var(--pp-warn); background:rgba(245,158,11,.08); }
.pp-step.info { border-left-color:var(--pp-muted); background:rgba(148,163,184,.10); }
.pp-step code { font-size:.82rem; }
.pp-gates { display:flex; gap:8px; flex-wrap:wrap; margin:8px 0; }
.pp-gate { padding:4px 10px; border-radius:8px; font-size:.82rem; font-weight:600; }
.pp-gate.pass { background:rgba(16,185,129,.14); color:#059669; }
.pp-gate.fail { background:rgba(239,68,68,.14); color:#dc2626; }
.pp-gate.na { background:rgba(148,163,184,.16); color:#64748b; }
.pp-inject { background:rgba(239,68,68,.12); border:1px solid rgba(239,68,68,.45); color:#b91c1c; border-radius:10px;
             padding:8px 12px; margin:8px 0; font-weight:600; }
.pp-quote { border-left:3px solid var(--pp-ok); padding:4px 10px; margin:6px 0; font-size:.9rem; }
.pp-quote.unv { border-left-color:var(--pp-muted); opacity:.75; }
@media (prefers-color-scheme: dark) { .pp-slot { border-color:#475569; } .pp-gate.pass{color:#34d399} .pp-gate.fail{color:#f87171}
  .pp-inject{color:#fca5a5} }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="pp-hero">
  <h1>📄 PageProof</h1>
  <p>Budget-bounded, evidence-verified document agent that answers only what the PDF proves.</p>
  <div class="pp-chips">
    <span class="pp-chip">🔒 100% local · {html.escape(OLLAMA_MODEL)} on Ollama</span>
    <span class="pp-chip">🧮 ≤ {TOOL_BUDGET} tool calls + 1 answer</span>
    <span class="pp-chip">🚫 no RAG · no embeddings · no page cache</span>
    <span class="pp-chip">✅ quote-verified answers</span>
    <span class="pp-chip">🛡️ injection-fenced pages</span>
  </div>
</div>""", unsafe_allow_html=True)

STRAT_NAMES = {"D": "D · PageProof hybrid (proposed)", "C": "C · Outline-first", "B": "B · Search-first", "A": "A · Naive ReAct (no gates)"}
with st.sidebar:
    st.header("Document")
    files = st.file_uploader("Upload PDF(s)", type="pdf", accept_multiple_files=True)
    model = st.text_input("Ollama model", OLLAMA_MODEL)
    strategy = st.selectbox("Agent strategy", ["D", "C", "B", "A"], index=["D", "C", "B", "A"].index(STRATEGY), format_func=STRAT_NAMES.get)
    st.caption(f"Confidence threshold {CONF_THRESHOLD} · no document leaves this machine.")


def meter_html(trace, final_done=False):
    used = [e for e in trace if e.get("counted")]
    blocked = [e for e in trace if e["status"] == "rejected"]
    slots = []
    for i in range(TOOL_BUDGET):
        if i < len(used):
            e = used[i]
            cls = "err" if e["status"] == "error" else "used"
            slots.append(f'<div class="pp-slot {cls}" title="{html.escape(e["tool"])}">{i + 1}</div>')
        else:
            slots.append(f'<div class="pp-slot">{i + 1}</div>')
    if blocked:
        slots.append(f'<div class="pp-slot blocked" title="refused, not executed">✕{len(blocked)}</div>')
    slots.append(f'<div class="pp-slot final {"done" if final_done else ""}">+1 answer</div>')
    return f'<div class="pp-meter">{"".join(slots)}</div>'


def step_html(e):
    if e["status"] == "info":
        if e["tool"] == "fingerprint":
            return f'<div class="pp-step info">🧬 Question fingerprint → route: <b>{html.escape(", ".join(e["result"]["types"]))}</b> (no tool call)</div>'
        label = {"decline_check": "🔁 Decline check: premature 'insufficient' pushed back once",
                 "grounding_check": "🔁 Grounding check: unverified quotes pushed back once",
                 "dropped_call": "⏭️ Call issued with final answer: dropped, not executed",
                 "final_answer": "🏁 Final answer submitted"}.get(e["tool"], e["tool"])
        return f'<div class="pp-step info">{label}</div>'
    args = ", ".join(f"{k}={v!r}" for k, v in e["args"].items() if k != "doc_id")
    res = e["result"]
    if e["status"] == "ok":
        brief = {"get_page": lambda r: f"{len(r)} chars of page text",
                 "list_headings": lambda r: f"{len(r)} headings",
                 "search_keyword": lambda r: f"pages {r[:12]}{'…' if len(r) > 12 else ''}" if r else "no pages",
                 "list_documents": lambda r: f"{len(r)} document(s)"}.get(e["tool"], lambda r: "")(res)
    else:
        brief = str(res)[:140]
    no = f"#{e['call_no']}" if e.get("counted") else "✕"
    cls = "err" if e["status"] in ("error", "rejected") else ""
    return f'<div class="pp-step {cls}"><b>{no}</b> <code>{html.escape(e["tool"])}({html.escape(args)})</code> → {html.escape(brief)}</div>'


def gates_html(r):
    if r["status"] == "answered":
        g = '<span class="pp-gate pass">✓ grounding gate</span>'
        g += f'<span class="pp-gate pass">✓ confidence {r["confidence"]:.2f} ≥ {CONF_THRESHOLD}</span>'
    else:
        notes = " ".join(r["notes"])
        g = ('<span class="pp-gate fail">✗ grounding gate</span>' if "grounding gate" in notes else
             '<span class="pp-gate fail">✗ confidence threshold</span>' if "threshold" in notes else
             '<span class="pp-gate na">declined by agent</span>')
    if r.get("fingerprint"):
        g = f'<span class="pp-gate na">🧬 {html.escape(", ".join(r["fingerprint"]))}</span>' + g
    g += f'<span class="pp-gate na">{r["used"]}/{TOOL_BUDGET} tool calls · {r["seconds"]}s</span>'
    return f'<div class="pp-gates">{g}</div>'


def render_result(r):
    inj = [n for n in r["notes"] if n.startswith("Ignored embedded instruction")]
    if inj:
        st.markdown(f'<div class="pp-inject">🛡️ Injection blocked: {html.escape(inj[0].split(":", 1)[1].strip()[:200])}</div>',
                    unsafe_allow_html=True)
    if r["status"] == "answered":
        st.success("**Answered**, grounded in pages read")
    else:
        st.warning("**Insufficient information**: the agent declines rather than guesses")
    st.markdown(r["answer"])
    st.markdown(meter_html(r["trace"], final_done=True) + gates_html(r), unsafe_allow_html=True)
    if r["evidence"]:
        with st.expander("📌 Evidence: verbatim quotes", expanded=r["status"] == "answered"):
            for ev in r["evidence"]:
                cls = "" if ev.get("verified") else "unv"
                badge = "✅ verified on a page read" if ev.get("verified") else "❓ not found on pages read"
                st.markdown(f'<div class="pp-quote {cls}"><b>p.{ev["page"]}</b> · {badge}<br>“{html.escape(ev["quote"])}”</div>',
                            unsafe_allow_html=True)
    if r.get("tentative"):
        with st.expander("Withheld tentative answer (failed a gate)"):
            st.write(r["tentative"])
    with st.expander(f"🧭 Tool-call timeline ({r['used']} counted calls)"):
        st.markdown("".join(step_html(e) for e in r["trace"]), unsafe_allow_html=True)


def benchmark_tab():
    files_ = sorted(glob.glob("logs/results_*_*_*.json"))
    if not files_:
        st.info("No benchmark results yet. Run `python eval.py all --strategy D`.")
        return
    rows = []
    for f in files_:
        try:
            sm = json.load(open(f, encoding="utf-8"))["summary"]
        except Exception:  # noqa: BLE001
            continue
        if f.endswith("_final.json"):
            qset = "real · all 19 · FINAL code (fingerprinting + all fixes)"
        elif "injfix" in f:
            qset = "real · injection Qs only, re-check with final code"
        elif sm["set"] == "redteam":
            qset = "red-team fixture (synthetic, not headline)"
        elif sm["n"] < 19:
            qset = f"real · {sm['n']}-question subset (every 3rd)"
        else:
            qset = "real · all 19 questions"
        rows.append({"model": sm["model"], "strategy": STRAT_NAMES.get(sm["strategy"], sm["strategy"]), "question set": qset,
                     "accuracy": f"{sm['correct']}/{sm['n']} ({sm['accuracy'] * 100:.0f}%)", "avg calls": sm["avg_calls"],
                     "max calls": sm["max_calls"], "over budget": sm["over_budget"], "avg s": sm["avg_seconds"]})
    st.subheader("Existing vs proposed strategies (same local model, real PDFs)")
    st.dataframe(rows, width="stretch", hide_index=True)
    if os.path.exists("logs/RESULTS.md"):
        with st.expander("Full report: per-type results, threshold sweep, failures"):
            st.markdown(open("logs/RESULTS.md", encoding="utf-8").read())


def build(files):
    store = DocStore()
    for f in files:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as t:
            t.write(f.getvalue())
        store.add_pdf(t.name, original_name=f.name)
    return store


tab_chat, tab_bench = st.tabs(["💬 Ask the document", "📊 Benchmark"])
with tab_bench:
    benchmark_tab()

sig = tuple((f.name, f.size) for f in files)
if files and st.session_state.get("sig") != sig:
    with st.spinner("Opening PDF and reading its outline (no embeddings, no page cache)…"):
        st.session_state.store = build(files)
    st.session_state.sig = sig
    st.session_state.chat = []
    st.session_state.history = []
    st.session_state.logfile = f"logs/session_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"

if not files:
    with tab_chat:
        st.info("⬅️ Upload a PDF in the sidebar to start.")
    st.stop()

store = st.session_state.store
with st.sidebar:
    for d in store.docs.values():
        st.success(f"**{d.doc_id}**: {d.title} · {d.meta['num_pages']} pages")
        st.caption(f"Outline: {len(d.headings)} headings ({d.heading_source})")
        if not d.meta.get("has_text_layer", True):
            st.error("No text layer found (scanned PDF?). OCR is not supported, so answers will be 'insufficient information'.")
        with st.expander("Detected headings"):
            st.text("\n".join(f"{'  ' * max(h['level'] - 1, 0)}{h['title']}  (p{h['page']})" for h in d.headings) or "none")
    if os.path.exists(st.session_state.logfile):
        st.download_button("⬇ Full tool-call trace (JSONL)", open(st.session_state.logfile, "rb").read(), "tool_calls_trace.jsonl",
                           width="stretch")

with tab_chat:
    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            if m["role"] == "user":
                st.write(m["content"])
            else:
                render_result(m["content"])

q = st.chat_input("Ask a question about the document…")
if q:
    with tab_chat:
        st.session_state.chat.append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.write(q)
        with st.chat_message("assistant"):
            meter = st.empty()
            live = st.status("Agent working…", expanded=True)
            steps: list = []

            def on_event(kind, e):
                if kind == "tool":
                    steps.append(e)
                    meter.markdown(meter_html(steps), unsafe_allow_html=True)
                    live.markdown(step_html(e), unsafe_allow_html=True)

            meter.markdown(meter_html([]), unsafe_allow_html=True)
            ok = False
            try:
                agent = DocAgent(store, model=model, log_path=st.session_state.logfile, strategy=strategy)
                r = agent.ask(q, history=st.session_state.history, on_event=on_event)
                live.update(label=f"Done · {r.tool_calls_used}/{TOOL_BUDGET} tool calls · {r.seconds}s", state="complete", expanded=False)
                res = dict(status=r.status, answer=r.answer, confidence=r.confidence, evidence=r.evidence, used=r.tool_calls_used,
                           trace=r.trace, notes=r.notes, tentative=r.tentative_answer, seconds=r.seconds, fingerprint=r.fingerprint)
                st.session_state.chat.append({"role": "assistant", "content": res})
                st.session_state.history.append((q, r.answer))
                ok = True
            except Exception as ex:  # noqa: BLE001
                live.update(label="Error", state="error")
                st.error(f"{type(ex).__name__}: {ex}")
    if ok:
        st.rerun()  # redraw: renders the result card and refreshes the sidebar trace download
