#!/bin/bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
helper="$project_dir/scripts/demo/mac_runtime.py"
runtime_dir="${DEMO_RUNTIME_DIR:-$project_dir/.demo-runtime}"

if [[ -n "${DEMO_PYTHON:-}" ]]; then
  python_bin="$DEMO_PYTHON"
elif [[ -x "$project_dir/.venv/bin/python" ]]; then
  python_bin="$project_dir/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  python_bin="$(command -v python)"
else
  printf 'DEMO NOT STOPPED: Python is unavailable, so PID ownership cannot be verified safely.\n' >&2
  exit 1
fi

printf '\nStopping Autonomous IT Support Demo...\n\n'

stop_one() {
  role="$1"
  label="$2"
  if output="$("$python_bin" "$helper" stop --role "$role" --runtime-dir "$runtime_dir" 2>&1)"; then
    case "$output" in
      STOPPED:*) printf '✓ %s stopped\n' "$label" ;;
      NOT-RUNNING:*) printf '✓ %s was not started by this launcher\n' "$label" ;;
      STALE:*) printf '✓ %s stale PID record cleaned\n' "$label" ;;
      FOREIGN:*) printf '✓ %s unrelated process left untouched; stale record cleaned\n' "$label" ;;
      *) printf '✓ %s: %s\n' "$label" "$output" ;;
    esac
  else
    printf 'DEMO NOT STOPPED: %s\n' "$output" >&2
    exit 1
  fi
}

stop_one endpoint "Endpoint"
stop_one service-desk "Service Desk"
rmdir "$runtime_dir/pids" 2>/dev/null || true
printf '✓ Launcher PID files cleaned; logs preserved at %s/logs\n' "$runtime_dir"

printf '\n==========================================\n'
printf '              DEMO STOPPED\n'
printf '==========================================\n'
