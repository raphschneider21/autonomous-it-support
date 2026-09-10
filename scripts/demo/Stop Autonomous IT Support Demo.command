#!/bin/bash
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
bash "$script_dir/stop_all_mac.sh"
status=$?
printf '\n'
if [[ "${DEMO_NO_PAUSE:-0}" != "1" ]]; then
  read -r -p "Press Return to close this window..." _response
fi
exit "$status"
