import sys, json, warnings
warnings.filterwarnings("ignore")
from rapidagent.tools import DocStore
from rapidagent.agent import DocAgent
store = DocStore(); store.add_pdf("CSCI415009_V2.pdf")
agent = DocAgent(store, log_path="logs/tool_calls.jsonl")
for q in sys.argv[1:]:
    r = agent.ask(q)
    print("="*90); print("Q:", q)
    for e in r.trace:
        res = e["result"]; res = res if not isinstance(res,(list,str)) else (res[:12] if isinstance(res,list) else res[:60].replace("\n"," "))
        print(f"  [{e.get('call_no','-')}] {e['tool']}({e['args']}) -> {e['status']} {res}")
    print(f"STATUS={r.status} conf={r.confidence} calls={r.tool_calls_used} turns={r.llm_turns} {r.seconds}s")
    print("ANSWER:", r.answer); print("NOTES:", r.notes)
    for ev in r.evidence: print("  EV p", ev["page"], ev.get("verified"), ev["quote"][:100].replace("\n"," "))
