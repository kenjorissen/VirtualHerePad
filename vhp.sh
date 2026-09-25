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
clock_time='--:--'
local_ip='Unavailable'
client_ips='Unavailable'
client_count=0
client_status='Status unavailable'
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

sample_network() {
  local route='' sockets='' field previous='' _recv _send _local_endpoint peer _rest
  local -A seen=()
  local -a peers=()
  local_ip='Unavailable'
  # Kernel route lookups only: no packets are sent to these destinations.
  route=$(timeout 1 ip -o -4 route get 1.1.1.1 2>/dev/null) ||
    route=$(timeout 1 ip -o -6 route get 2606:4700:4700::1111 2>/dev/null) || route=''
  for field in $route; do
    if [[ $previous == src && $field =~ ^[0-9A-Fa-f:.]+(%[a-zA-Z0-9_.-]+)?$ ]]; then
      local_ip=$field
      break
    fi
    previous=$field
  done
  client_count=0
  client_ips='Unavailable'
  client_status='Status unavailable'
  # Unprivileged TCP connection metadata; never inspect payloads or private config.
  if ! sockets=$(timeout 1 ss -Hnt state established '( sport = :7575 )' 2>/dev/null); then
    return 0
  fi
  while read -r _recv _send _local_endpoint peer _rest; do
    [[ -n $peer ]] || continue
    peer=${peer%:*}
    peer=${peer#\[}
    peer=${peer%\]}
    # Reject unexpected output, especially control sequences, rather than render it.
    if [[ ! $peer =~ ^[0-9A-Fa-f:.]+(%[a-zA-Z0-9_.-]+)?$ ]]; then continue; fi
    if [[ -z ${seen[$peer]+present} ]]; then
      seen[$peer]=1
      peers+=("$peer")
    fi
  done <<<"$sockets"
  client_count=${#peers[@]}
  client_ips='None'
  client_status='Waiting for client'
  if ((client_count > 0)); then
    # Stable ordering prevents redraws when ss changes socket enumeration order.
    client_ips=''
    while IFS= read -r peer; do
      client_ips+="${client_ips:+, }$peer"
    done < <(printf '%s\n' "${peers[@]}" | LC_ALL=C sort)
    client_status="TCP clients: $client_count"
  fi
}

text_at() {
  local row=$1 column=$2 text=$3
  if ((row < 1 || row > rows || column < 1 || column > cols)); then return 0; fi
  printf '\033[%s;%sH%s' "$row" "$column" "${text:0:cols-column+1}"
}

paint_dashboard() {
  local left top row char line title='VIRTUALHEREPAD' battery_color=37 connection_color=33
  local key="$battery_percent|$battery_status|$clock_time|$local_ip|$client_ips|$client_status|$rows|$cols"
  if [[ $key == "$last_display" && $ui_dirty == false ]]; then return 0; fi
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
    [A]=' # |# #|###|# #|# #'
    [D]='## |# #|# #|# #|## '
    [E]='###|#  |## |#  |###'
    [H]='# #|# #|###|# #|# #'
    [I]='###| # | # | # |###'
    [L]='#  |#  |#  |#  |###'
    [P]='## |# #|## |#  |#  '
    [R]='## |# #|## |# #|# #'
    [T]='###| # | # | # | # '
    [U]='# #|# #|# #|# #|###'
    [V]='# #|# #|# #|# #| # '
  )
  last_display=$key
  ui_dirty=false
  if ! "$ui_active"; then
    printf 'VirtualHerePad | Server running | %s | Battery: %s%% (%s) | Local IP: %s | %s | Clients: %s\n' \
      "$clock_time" "$battery_percent" "$battery_status" "$local_ip" "$client_status" "$client_ips"
    return 0
  fi
  if [[ $battery_percent != -- ]]; then
    if ((battery_percent <= 15)); then
      battery_color=31
    elif ((battery_percent <= 30)); then
      battery_color=33
    else battery_color=32; fi
  fi
  if ((client_count > 0)); then connection_color=32; fi
  printf '\033[0;37;40m\033[2J'
  if ((rows < 24 || cols < 72)); then
    printf '\033[1;36m'
    text_at 1 1 'VirtualHerePad - Server running'
    printf '\033[0;37;40m'
    text_at 2 1 "Local time: $clock_time"
    printf '\033[%sm' "$battery_color"
    text_at 3 1 "Battery: $battery_percent% ($battery_status)"
    printf '\033[%sm' "$connection_color"
    text_at 4 1 "$client_status"
    printf '\033[0;37;40m'
    text_at 5 1 "Local IP: $local_ip"
    text_at 6 1 "Clients: $client_ips"
    text_at 8 1 'Hold any corner for 2s to stop.'
    text_at 9 1 'Local keyboard: Ctrl+C'
    return 0
  fi
  left=$(((cols - 64) / 2 + 1))
  top=$(((rows - 24) / 2 + 1))
  printf '\033[36m'
  text_at 1 1 '+ HOLD 2s'
  text_at 1 "$((cols - 8))" 'HOLD 2s +'
  text_at "$rows" 1 '+ HOLD 2s'
  text_at "$rows" "$((cols - 8))" 'HOLD 2s +'
  printf '\033[1m'
  for ((row = 0; row < 5; row++)); do
    line=''
    for ((char = 0; char < ${#title}; char++)); do
      IFS='|' read -r -a cells <<<"${glyph[${title:char:1}]}"
      line+="${cells[row]} "
    done
    text_at "$((top + 2 + row))" "$((left + 4))" "$line"
  done
  printf '\033[0;37;40m'
  text_at "$((top + 8))" "$left" 'BATTERY'
  printf '\033[1;%sm' "$battery_color"
  for ((row = 0; row < 5; row++)); do
    line=''
    for ((char = 0; char < ${#battery_percent}; char++)); do
      IFS='|' read -r -a cells <<<"${glyph[${battery_percent:char:1}]}"
      line+="${cells[row]}  "
    done
    IFS='|' read -r -a cells <<<"${glyph['%']}"
    text_at "$((top + 10 + row))" "$left" "$line${cells[row]}"
  done
  printf '\033[0;37;40m'
  text_at "$((top + 16))" "$left" "$battery_status"
  printf '\033[1;32m'
  text_at "$((top + 8))" "$((left + 32))" 'SERVER RUNNING'
  printf '\033[0;%s;40m' "$connection_color"
  text_at "$((top + 10))" "$((left + 32))" "$client_status"
  printf '\033[0;37;40m'
  text_at "$((top + 12))" "$((left + 32))" 'LOCAL TIME'
  printf '\033[1;35m'
  text_at "$((top + 13))" "$((left + 32))" "$clock_time"
  printf '\033[0;36;40m'
  text_at "$((top + 17))" "$left" "Local IP: $local_ip"
  text_at "$((top + 18))" "$left" "Clients: $client_ips"
  printf '\033[0;37;40m'
  text_at "$((top + 20))" "$left" 'Hold one finger in any corner for 2 seconds to exit.'
  text_at "$((top + 21))" "$left" 'Local keyboard: Ctrl+C | TCP link only; device use not checked'
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
next_network_check=0
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
  fi
  if ((SECONDS >= next_network_check)); then
    sample_network
    next_network_check=$((SECONDS + 5))
  fi
  # Bash's builtin clock formatting adds no subprocess and displays no seconds.
  printf -v clock_time '%(%H:%M)T' -1
  paint_dashboard
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
