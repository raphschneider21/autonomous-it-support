#!/bin/bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
helper="$project_dir/scripts/demo/mac_runtime.py"
runtime_dir="${DEMO_RUNTIME_DIR:-$project_dir/.demo-runtime}"
log_dir="$runtime_dir/logs"
pid_dir="$runtime_dir/pids"
launch_complete=0
started_endpoint=0
started_service_desk=0
python_bin=""

banner() {
  printf '\n==========================================\n'
  printf ' AUTONOMOUS IT SUPPORT — DEMO LAUNCHER\n'
  printf '==========================================\n\n'
}

not_ready() {
  printf '\n==========================================\n' >&2
  printf '             DEMO NOT READY\n' >&2
  printf '==========================================\n' >&2
  printf '%s\n' "$1" >&2
  printf 'Logs: %s\n' "$log_dir" >&2
  exit 1
}

on_exit() {
  exit_status=$?
  trap - EXIT
  if [[ "$exit_status" -ne 0 && "$launch_complete" -ne 1 ]]; then
    if [[ "$started_endpoint" -eq 1 ]]; then
      "$python_bin" "$helper" stop --role endpoint --runtime-dir "$runtime_dir" >/dev/null 2>&1 || true
    fi
    if [[ "$started_service_desk" -eq 1 ]]; then
      "$python_bin" "$helper" stop --role service-desk --runtime-dir "$runtime_dir" >/dev/null 2>&1 || true
    fi
  fi
  exit "$exit_status"
}
trap on_exit EXIT

python_works() {
  candidate="$1"
  [[ -n "$candidate" && -x "$candidate" ]] || return 1
  "$candidate" -c 'import sys; assert sys.version_info >= (3, 10); import fastapi, pydantic, uvicorn' >/dev/null 2>&1
}

choose_python() {
  if [[ -n "${DEMO_PYTHON:-}" ]]; then
    if python_works "$DEMO_PYTHON"; then
      python_bin="$DEMO_PYTHON"
    else
      not_ready "DEMO_PYTHON cannot import the project dependencies: $DEMO_PYTHON"
    fi
  elif python_works "$project_dir/.venv/bin/python"; then
    python_bin="$project_dir/.venv/bin/python"
  else
    login_shell="${SHELL:-/bin/zsh}"
    login_python3="$("$login_shell" -lc 'command -v python3' 2>/dev/null || true)"
    login_python="$("$login_shell" -lc 'command -v python' 2>/dev/null || true)"
    path_python3="$(command -v python3 2>/dev/null || true)"
    path_python="$(command -v python 2>/dev/null || true)"
    for candidate_path in "$login_python3" "$login_python" "$path_python3" "$path_python"; do
      if python_works "$candidate_path"; then
        python_bin="$candidate_path"
        break
      fi
    done
    if [[ -z "$python_bin" ]]; then
      not_ready "No Python 3.10+ interpreter with the project dependencies was found. Create .venv or set DEMO_PYTHON."
    fi
  fi
  printf '✓ Python environment: %s\n' "$python_bin"
}

start_or_reuse() {
  role="$1"
  label="$2"
  log_file="$3"
  set +e
  probe_output="$("$python_bin" "$helper" probe --role "$role" 2>&1)"
  probe_status=$?
  set -e

  if [[ "$probe_status" -eq 0 ]]; then
    printf '✓ %s already healthy; reusing it without taking ownership\n' "$label"
    return
  fi
  if [[ "$probe_status" -ne 10 ]]; then
    not_ready "$label cannot start: $probe_output"
  fi

  printf '\n[%s] Starting %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$label" >>"$log_file"
  nohup "$python_bin" "$helper" run --role "$role" >>"$log_file" 2>&1 &
  service_pid=$!
  disown "$service_pid" 2>/dev/null || true
  "$python_bin" "$helper" record --role "$role" --pid "$service_pid" --runtime-dir "$runtime_dir" >/dev/null
  if [[ "$role" == "endpoint" ]]; then
    started_endpoint=1
  else
    started_service_desk=1
  fi
  if ! wait_output="$("$python_bin" "$helper" wait --role "$role" --timeout 20 2>&1)"; then
    not_ready "$label failed health verification: $wait_output"
  fi
  printf '✓ %s started (PID %s)\n' "$label" "$service_pid"
}

banner
cd "$project_dir"
mkdir -p "$log_dir" "$pid_dir"
choose_python

# Frozen single-Mac graded profile. Existing shell or .env values cannot change
# the execution boundary used by the launched endpoint.
export DEMO_MODE=1
export EXECUTOR=mock
export AGENT_MODE=deterministic
export RUNBOOK_STORE=ubuntu-26.04
export MONITORING_ENABLED=1
export MONITORING_URL=http://127.0.0.1:8001
export ENDPOINT_NAME=ubuntu-demo-01
export ENDPOINT_HOSTNAME=ubuntu-demo-01
export DEMO_ENDPOINT_URL=http://127.0.0.1:8000

if ! environment_output="$("$python_bin" scripts/demo/preflight.py --endpoint-url "$DEMO_ENDPOINT_URL" --environment-only 2>&1)"; then
  not_ready "Safe demo configuration was rejected: $environment_output"
fi
printf '✓ Deterministic mock configuration forced\n'

start_or_reuse "service-desk" "Service Desk :8001" "$log_dir/service-desk.log"
start_or_reuse "endpoint" "Endpoint runtime :8000" "$log_dir/endpoint.log"

if ! preflight_output="$("$python_bin" scripts/demo/preflight.py --endpoint-url "$DEMO_ENDPOINT_URL" 2>&1)"; then
  not_ready "Integrated preflight failed: $preflight_output"
fi
printf '✓ Simulated endpoint reset\n'
printf '✓ Service Desk connected\n'
printf '✓ EXECUTOR=mock and AGENT_MODE=deterministic confirmed by runtime health\n'

if ! surface_output="$("$python_bin" "$helper" check-surfaces 2>&1)"; then
  not_ready "Presentation surface check failed: $surface_output"
fi
printf '✓ Employee Support reachable\n'
printf '✓ Demo Lab reachable\n'
printf '✓ Service Desk UI reachable\n'

employee_url=http://127.0.0.1:8000
lab_url=http://127.0.0.1:8000/static/demo.html
desk_url=http://127.0.0.1:8001
if [[ "${DEMO_OPEN_BROWSER:-1}" == "1" ]]; then
  browser_ok=1
  if command -v open >/dev/null 2>&1; then
    open "$employee_url" || browser_ok=0
    open "$lab_url" || browser_ok=0
    open "$desk_url" || browser_ok=0
  else
    "$python_bin" -m webbrowser -t "$employee_url" || browser_ok=0
    "$python_bin" -m webbrowser -t "$lab_url" || browser_ok=0
    "$python_bin" -m webbrowser -t "$desk_url" || browser_ok=0
  fi
  if [[ "$browser_ok" -eq 1 ]]; then
    printf '✓ Opened Employee Support, Demo Lab and Service Desk\n'
  else
    printf '⚠ Browser launch failed; services remain healthy. Open these URLs manually:\n'
    printf '  %s\n  %s\n  %s\n' "$employee_url" "$lab_url" "$desk_url"
  fi
else
  printf 'Browser opening disabled. Presentation URLs:\n'
  printf '  %s\n  %s\n  %s\n' "$employee_url" "$lab_url" "$desk_url"
fi

launch_complete=1
printf '\n==========================================\n'
printf '               DEMO READY\n'
printf '==========================================\n'
printf 'Logs: %s\n' "$log_dir"
printf 'Stop with: %s\n' "$project_dir/scripts/demo/Stop Autonomous IT Support Demo.command"
