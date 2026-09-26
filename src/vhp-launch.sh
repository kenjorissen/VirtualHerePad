#!/usr/bin/env bash
# The one installed Steam target; no privilege or checkout dependency here.
set -euo pipefail
unset LD_PRELOAD
base=$(dirname -- "$(readlink -f -- "$0")")
mode=${1:-}
if [[ $# -gt 1 ]]; then
  echo 'Usage: vhp-launch.sh [--keyboard|--terminal]' >&2
  exit 1
fi
if [[ -z $mode ]]; then
  mode=terminal
  if [[ -f $base/launch-mode ]]; then read -r mode <"$base/launch-mode"; fi
  mode="--$mode"
fi
case "$mode" in
  --keyboard | --terminal) ;;
  *)
    echo 'Usage: vhp-launch.sh [--keyboard|--terminal]' >&2
    exit 1
    ;;
esac
exec 9>"$base/session.lock"
flock -n 9 || {
  echo 'VirtualHerePad is already open.' >&2
  exit 1
}
if [[ $mode == --terminal ]]; then exec "$base/vhp-gui.sh"; fi
exec /usr/bin/python3 -I "$base/vhp_session.py"
