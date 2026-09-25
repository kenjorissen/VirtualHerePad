#!/usr/bin/env bash
# Temporary test harness for the touch-keyboard UI.
#
# Not part of setup.sh and not installed anywhere: it exists so the whole
# prototype can be started and stopped with one command while it is being
# evaluated on real hardware.
#
#   ./vhp-gui-sandbox.sh          start everything, Ctrl+C stops everything
#   ./vhp-gui-sandbox.sh --stop   force-clean anything left behind
set -euo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")"

HELPER=/home/.vhp/bin/vhp-root
RUNTIME="$HOME/.local/share/VirtualHerePad/pylib"
SOCKET="/run/user/$(id -u)/vhp-gui.sock"
backend=''
keepalive=''

say() { printf '%s\n' "$*"; }

remove_gadget() {
  sudo bash -c '
    set -euo pipefail
    gadget=/sys/kernel/config/usb_gadget/vhp_keyboard
    [[ -d $gadget ]] || exit 0
    printf "\n" >"$gadget/UDC" 2>/dev/null || true
    rm -f -- "$gadget/configs/c.1/hid.usb0"
    rmdir -- "$gadget/functions/hid.usb0" "$gadget/configs/c.1" \
      "$gadget/strings/0x409" "$gadget" 2>/dev/null || true
  '
}

stop_everything() {
  trap - EXIT INT TERM
  [[ -z $keepalive ]] || kill "$keepalive" 2>/dev/null || true
  [[ -z $backend ]] || sudo kill "$backend" 2>/dev/null || true
  wait 2>/dev/null || true
  remove_gadget
  rm -f -- "$SOCKET"
  sudo -n "$HELPER" stop 2>/dev/null || true
  say 'Stopped: UI closed, backend stopped, USB gadget removed.'
}

if [[ ${1:-} == --stop ]]; then
  sudo -v
  backend=''
  keepalive=''
  stop_everything
  say 'VHP service stopped. Nothing from the sandbox should be running now.'
  exit 0
fi

say '== Checks =='
[[ -x $HELPER ]] || {
  say 'VHP is not installed yet. Run ./setup.sh first (it installs the helper).' >&2
  exit 1
}
[[ -d $RUNTIME ]] || {
  say "Qt runtime missing. Run: python3 vhp-gui-deps.py" >&2
  exit 1
}
if [[ -z ${WAYLAND_DISPLAY:-} && -z ${DISPLAY:-} ]]; then
  say 'No graphical session found. Run this from Konsole in Desktop Mode, not over SSH.' >&2
  exit 1
fi
say 'Checking sudo access...'
sudo -v

say '== Installing the service unit from this checkout =='
say "   (/etc/systemd/system/vhp.service)"
sudo install -o root -g root -m 644 vhp.service /etc/systemd/system/vhp.service
sudo systemctl daemon-reload

say '== Starting VHP (VirtualHere server) =='
sudo -n "$HELPER" start
# The launcher normally refreshes the heartbeat; here the sandbox does it.
(
  while sudo -n "$HELPER" keepalive 2>/dev/null; do sleep 2; done
) &
keepalive=$!
trap stop_everything EXIT INT TERM

say '== Starting the touch-keyboard backend (root) =='
sudo python3 vhp_backend.py --owner "$USER" --socket "$SOCKET" &
backend=$!

for _ in $(seq 1 100); do
  [[ -S $SOCKET ]] && break
  sleep 0.1
done
[[ -S $SOCKET ]] || {
  say 'The backend never created its socket. Output above should say why.' >&2
  exit 1
}
say 'Backend ready.'

say '== Starting the touch UI =='
say 'On the PC, use "VHP Touch Keyboard" in the VirtualHere client.'
say 'Press Ctrl+C here to stop everything.'
say ''
PYTHONPATH="$RUNTIME" python3 vhp_ui.py --socket "$SOCKET"
say 'UI closed.'
