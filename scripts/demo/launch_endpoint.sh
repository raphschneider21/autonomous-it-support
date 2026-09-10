#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_dir"

# Frozen, safe demo profile. Existing shell values cannot silently switch the
# launcher to real commands or an external model.
export DEMO_MODE=1
export EXECUTOR=mock
export AGENT_MODE=deterministic
export MONITORING_ENABLED=1
export ENDPOINT_NAME=ubuntu-demo-01
export ENDPOINT_HOSTNAME=ubuntu-demo-01
export RUNBOOK_STORE=ubuntu-26.04
# Read the configured Mac address from the shell or .env, using the same rules
# as the endpoint. The launcher binds port 8000 and checks that exact port.
MONITORING_URL="$(python -c 'from src import config; from src.integrations.monitoring_client import monitoring_url; print(monitoring_url())')"
export MONITORING_URL
export DEMO_ENDPOINT_URL=http://127.0.0.1:8000

python scripts/demo/preflight.py \
  --endpoint-url "$DEMO_ENDPOINT_URL" \
  --environment-only \
  --check-bind

python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1 &
endpoint_pid=$!
cleanup() {
  kill "$endpoint_pid" 2>/dev/null || true
  wait "$endpoint_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for _attempt in 1 2 3 4 5 6 7 8 9 10; do
  if ! kill -0 "$endpoint_pid" 2>/dev/null; then
    echo "NOT READY: endpoint exited during startup" >&2
    exit 1
  fi
  if python -c 'import os, urllib.request; urllib.request.urlopen(os.environ["DEMO_ENDPOINT_URL"] + "/api/health", timeout=.5)' 2>/dev/null; then
    break
  fi
  sleep 0.5
done

python scripts/demo/preflight.py --endpoint-url "$DEMO_ENDPOINT_URL"
echo "Demo endpoint ready: $DEMO_ENDPOINT_URL"
echo "Demo Lab API: $DEMO_ENDPOINT_URL/api/demo/state"
if [[ "${DEMO_OPEN_BROWSER:-1}" == "1" ]]; then
  python -m webbrowser -t "$DEMO_ENDPOINT_URL" || echo "Open the Employee Support URL above manually."
fi
wait "$endpoint_pid"
