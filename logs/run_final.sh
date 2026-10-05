#!/bin/bash
# wait for strategy A to finish, kill the old loop's C/B runs, then run the final sequence
cd /c/Users/shivraj/Desktop/RAPIDWINNER
export PYTHONIOENCODING=utf-8
until [ -f logs/results_qwen3-8b_A_real.json ]; do sleep 5; done
for i in $(seq 1 90); do   # for ~3 min, kill any eval.py run with strategy C or B started by the old loop
  powershell -NoProfile -c "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ? { \$_.CommandLine -match 'eval.py real --strategy (C|B)' } | % { Stop-Process -Id \$_.ProcessId -Force }" >/dev/null 2>&1
  grep -q "^done" logs/bench_qwen3.txt && break
  sleep 2
done
{
echo "=== FINAL D (real) ==="; python -W ignore -u eval.py real --strategy D
echo "=== FINAL D (redteam) ==="; python -W ignore -u eval.py redteam --strategy D
echo "=== FINAL C (real, every 3rd) ==="; python -W ignore -u eval.py real --strategy C --every 3
echo "=== FINAL B (real, every 3rd) ==="; python -W ignore -u eval.py real --strategy B --every 3
echo "FINAL_DONE"
} > logs/bench_final.txt 2>&1
