#!/usr/bin/env bash
set -euo pipefail

HELPER=/usr/local/lib/vhp/vhp-root
if [[ ! -x "$HELPER" ]]; then
  echo 'VHP is not installed. Run ./setup.sh from the checkout first.' >&2
  exit 1
fi

# Invoked by the EXIT trap, including after INT/TERM.
# shellcheck disable=SC2329
cleanup() {
  trap - EXIT INT TERM
  echo 'Stopping VHP...'
  sudo -n "$HELPER" stop || true
}
trap cleanup EXIT
trap 'exit 0' INT TERM

sudo -n "$HELPER" start
echo 'VHP is running. Leave this window open; use Steam > Exit Game to stop.'
while /usr/bin/systemctl is-active --quiet vhp.service; do
  sudo -n "$HELPER" keepalive
  # Keep a foreground input loop for the Konsole/Steam input context.
  if [[ -t 0 ]]; then
    read -rsn1 -t 1 _ || true
  else
    sleep 1
  fi
done
echo 'VHP stopped. Inspect logs with: journalctl -u vhp.service' >&2
exit 1
