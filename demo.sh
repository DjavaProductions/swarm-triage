#!/usr/bin/env bash
# Swarm Triage — end-to-end demo on a single CVE (Log4Shell).
# Runs the pipeline offline (stdlib only, no network, no scanning) and
# shows the resulting triage report.
#
# Usage: ./demo.sh
#   Uses a temp directory by default; set DEMO_OUT to keep the output.
set -euo pipefail

cd "$(dirname "$0")"

OUT="${DEMO_OUT:-$(mktemp -d /tmp/swarm-triage-demo.XXXXXX)}"
CVE="${DEMO_CVE:-CVE-2021-44228}"

echo "== Swarm Triage demo =="
echo "CVE:    $CVE"
echo "Output: $OUT"
echo

echo "--- 1. Validate the dataset ---"
python3 triage.py --check
echo

echo "--- 2. Triage $CVE ---"
python3 triage.py --cve "$CVE" --out "$OUT"
echo

echo "--- 3. Report: $OUT/$CVE.md ---"
cat "$OUT/$CVE.md"
echo

echo "--- 4. Machine-readable summary ---"
python3 -c "import json; d=json.load(open('$OUT/summary.json')); print(json.dumps(d['results'][0], indent=2, sort_keys=True))"
echo
echo "Demo done. Reports are in: $OUT"
