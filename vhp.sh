#!/usr/bin/env bash
set -euo pipefail

HELPER=/home/.vhp/bin/vhp-root
if [[ ! -x "$HELPER" ]]; then
  echo 'VHP is not installed. Run ./setup.sh from the checkout first.' >&2
  exit 1
fi

POWER_SUPPLY_ROOT=/sys/class/power_supply
battery_percent='--'
battery_status='Unavailable'
ui_active=false
ui_dirty=true
last_display=''
rows=24
cols=80

# BEGIN DASHBOARD_FUNCTIONS
sample_battery() {
  local supply kind scope value state
  battery_percent='--'
  battery_status='Unavailable'
  for supply in "$POWER_SUPPLY_ROOT"/*; do
    [[ -r "$supply/type" ]] || continue
    kind=$(<"$supply/type") || continue
    [[ $kind == Battery ]] || continue
    scope=''
    if [[ -r "$supply/scope" ]]; then scope=$(<"$supply/scope") || continue; fi
    [[ $scope != Device && -r "$supply/capacity" ]] || continue
    value=$(<"$supply/capacity") || continue
    if [[ ! $value =~ ^[0-9]{1,3}$ ]] || ((10#$value > 100)); then continue; fi
    battery_percent=$((10#$value))
    state='Unknown'
    if [[ -r "$supply/status" ]]; then state=$(<"$supply/status") || state='Unknown'; fi
    case "$state" in
      Charging | Discharging | Full | 'Not charging') battery_status=$state ;;
      *) battery_status='Unknown' ;;
    esac
    return 0
  done
}

text_at() { printf '\033[%s;%sH%s' "$1" "$2" "$3"; }

paint_dashboard() {
  local left top row char line key="$battery_percent|$battery_status|$rows|$cols"
  local -a cells
  local -A glyph=(
    [0]=' ### |#   #|#   #|#   #| ### '
    [1]='  #  | ##  |  #  |  #  | ### '
    [2]='#### |    #| ### |#    |#####'
    [3]='#### |    #| ### |    #|#### '
    [4]='#   #|#   #|#####|    #|    #'
    [5]='#####|#    |#### |    #|#### '
    [6]=' ### |#    |#### |#   #| ### '
    [7]='#####|    #|   # |  #  | #   '
    [8]=' ### |#   #| ### |#   #| ### '
    [9]=' ### |#   #| ####|    #| ### '
    ['%']='##  #|## # |  #  | # ##|#  ##'
    ['-']='     |     |#####|     |     '
  )
  if [[ $key == "$last_display" && $ui_dirty == false ]]; then return 0; fi
  last_display=$key
  ui_dirty=false
  if ! "$ui_active"; then
    printf 'VirtualHerePad | Server running | Battery: %s%% (%s)\n' "$battery_percent" "$battery_status"
    return 0
  fi
  printf '\033[0;37;40m\033[2J'
  if ((rows < 20 || cols < 60)); then
    text_at 1 1 'VirtualHerePad - Server running'
    text_at 3 1 "Battery: $battery_percent% ($battery_status)"
    text_at 5 1 'Hold any corner for 2 seconds to stop.'
    text_at 6 1 'Fallback: local keyboard Ctrl+C'
    return 0
  fi
  left=$(((cols - 52) / 2 + 1))
  top=$(((rows - 18) / 2 + 2))
  printf '\033[36m'
  text_at 1 1 '+ HOLD 2s'
  text_at 1 "$((cols - 8))" 'HOLD 2s +'
  text_at "$rows" 1 '+ HOLD 2s'
  text_at "$rows" "$((cols - 8))" 'HOLD 2s +'
  printf '\033[1m'
  text_at "$top" "$left" 'V I R T U A L H E R E P A D'
  printf '\033[0;37;40m'
  text_at "$((top + 2))" "$left" 'BATTERY'
  printf '\033[1;37m'
  for ((row = 0; row < 5; row++)); do
    line=''
    for ((char = 0; char < ${#battery_percent}; char++)); do
      IFS='|' read -r -a cells <<<"${glyph[${battery_percent:char:1}]}"
      line+="${cells[row]}  "
    done
    IFS='|' read -r -a cells <<<"${glyph['%']}"
    text_at "$((top + 4 + row))" "$left" "$line${cells[row]}"
  done
  printf '\033[0;37;40m'
  text_at "$((top + 10))" "$left" "$battery_status"
  printf '\033[32m'
  text_at "$((top + 12))" "$left" 'SERVER RUNNING'
  printf '\033[0;37;40m'
  text_at "$((top + 14))" "$left" 'Hold one finger in any corner for 2 seconds to exit.'
  text_at "$((top + 15))" "$left" 'Fallback: local Bluetooth keyboard + Ctrl+C'
  text_at "$((top + 16))" "$left" 'Connect with the VirtualHere client on your PC.'
}

resize_dashboard() {
  local size
  if "$ui_active" && size=$(stty size 2>/dev/null) && [[ $size =~ ^[0-9]+\ [0-9]+$ ]]; then
    read -r rows cols <<<"$size"
  fi
  ui_dirty=true
}
# END DASHBOARD_FUNCTIONS

# Invoked by the EXIT trap, including after INT/TERM.
# shellcheck disable=SC2329
cleanup() {
  local status=$?
  trap - EXIT INT TERM WINCH
  if "$ui_active"; then printf '\033[0m\033[?25h\033[?1049l'; fi
  if ((status != 0)); then
    echo "VHP exited with code $status. Inspect logs: journalctl -u vhp.service" >&2
  fi
  echo 'Stopping VHP...'
  sudo -n "$HELPER" stop || true
}
trap cleanup EXIT
trap 'exit 0' INT TERM

sudo -n "$HELPER" start
if [[ -t 1 && ${TERM:-dumb} != dumb ]]; then
  ui_active=true
  printf '\033[?1049h\033[?25l'
fi
resize_dashboard
trap 'ui_dirty=true' WINCH
next_battery_check=0
while /usr/bin/systemctl is-active --quiet vhp.service; do
  if ! sudo -n "$HELPER" keepalive; then
    # A touch request may have stopped the service between these two calls.
    if ! /usr/bin/systemctl is-active --quiet vhp.service; then break; fi
    echo 'ERROR: could not refresh the VHP heartbeat.' >&2
    exit 1
  fi
  # Reuse the existing heartbeat loop; no extra polling processes or animations.
  if "$ui_dirty"; then resize_dashboard; fi
  if ((SECONDS >= next_battery_check)); then
    sample_battery
    next_battery_check=$((SECONDS + 30))
    paint_dashboard
  elif "$ui_dirty"; then
    paint_dashboard
  fi
  # Keep a foreground input loop for the Konsole/Steam input context.
  if [[ -t 0 ]]; then
    read -rsn1 -t 1 _ || true
  else
    sleep 1
  fi
done
if /usr/bin/systemctl is-failed --quiet vhp.service; then
  echo 'VHP failed. Inspect logs with: journalctl -u vhp.service' >&2
  exit 1
fi
echo 'VHP stopped.'
