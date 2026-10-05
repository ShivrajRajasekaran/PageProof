#!/bin/bash
# usage: ask.sh "question" screenshot.png  — asks in the open PageProof browser tab, waits for the answer, screenshots
cd /c/Users/shivraj/Desktop/RAPIDWINNER
before=$(cat logs/session_*.jsonl 2>/dev/null | grep -c '"tool": "final_answer"')
playwright-cli fill "getByPlaceholder('Ask a question about the document…')" "$1" --submit >/dev/null 2>&1
for i in $(seq 1 100); do
  n=$(cat logs/session_*.jsonl 2>/dev/null | grep -c '"tool": "final_answer"')
  [ "$n" -gt "$before" ] && break; sleep 3
done
sleep 7
playwright-cli screenshot --filename="demo_screens/$2" >/dev/null 2>&1
tail -n 1 "$(ls -t logs/session_*.jsonl | head -1)" | python -c "import sys,json; r=json.loads(sys.stdin.read())['result']; print(r['status'], '|', r['tool_calls_used'], 'calls |', r['answer'][:160], '| notes:', r['notes'])"
