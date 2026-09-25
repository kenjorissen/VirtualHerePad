#!/usr/bin/env bash
# Read-only diagnostics. Never launch/stop VHP or display private config contents.
set -u -o pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
issues=0
section() { printf '\n== %s ==\n' "$1"; }
warn() {
  echo "WARNING: $*"
  issues=$((issues + 1))
}

section 'Platform and tools'
uname -sm
for cmd in sudo systemctl systemd-inhibit curl konsole python3; do
  if command -v "$cmd" >/dev/null; then
    echo "OK: $cmd"
  else
    warn "Missing $cmd (python3 is needed for touchscreen exit and Steam shortcut creation)"
  fi
done

section 'Installed files and ownership'
for path in /home/.vhp /home/.vhp/bin /home/.vhp/bin/vhp-root /home/.vhp/bin/vhusbdx86_64 /home/.vhp/bin/touch-stop.py /etc/systemd/system/vhp.service /home/.vhp/data; do
  if [[ -e $path ]]; then
    stat -c '%U:%G %a %n' "$path"
    [[ ! -L $path ]] || warn "Unexpected symlink: $path"
    if [[ $path == /home/.vhp/data && $(stat -c '%a' "$path") != 700 ]]; then
      warn 'Settings directory should have mode 700'
    fi
    owner=$(stat -c '%u' "$path")
    mode=$(stat -c '%a' "$path")
    if [[ $owner != 0 ]] || (((8#$mode & 8#022) != 0)); then
      warn "Not root-owned or writable by group/others: $path"
    fi
  else
    warn "Missing $path; rerun ./setup.sh"
  fi
done
for path in /home/.vhp/bin/vhp-root /home/.vhp/bin/vhusbdx86_64; do
  [[ -x $path ]] || warn "Not executable: $path"
done

section 'Installed user tools (independent of the checkout)'
user_root="${HOME:?HOME must be set}/.local/share/VirtualHerePad"
for name in vhp.sh doctor.sh uninstall.sh steam-shortcut.py; do
  if [[ -r "$user_root/$name" ]]; then
    echo "OK: $user_root/$name"
  else
    warn "Missing user tool: $user_root/$name; rerun setup.sh"
  fi
done
[[ -x "$user_root/vhp.sh" ]] || warn 'Installed user launcher is not executable'

section 'Installed version (not the current checkout)'
if [[ -r /home/.vhp/bin/build-info.txt ]]; then
  head -n 3 /home/.vhp/bin/build-info.txt
else
  warn 'Installed version metadata is missing; rerun ./setup.sh to record it'
fi
if [[ -r /home/.vhp/bin/vhusbdx86_64 ]]; then
  echo 'Actual installed VirtualHere SHA-256 (compare with VIRTUALHERE_SHA256 above):'
  sha256sum /home/.vhp/bin/vhusbdx86_64
fi

section 'Passwordless sudo authentication (harmless probe, no cached credentials)'
if sudo -k -n /home/.vhp/bin/vhp-root check; then
  echo 'OK: harmless helper check succeeded without cached authentication'
else
  warn 'Passwordless helper check failed; rerun setup and inspect sudo rule ordering'
fi

section 'Listed sudo permissions (does not start or stop VHP)'
for action in start stop keepalive; do
  if sudo -n -l /home/.vhp/bin/vhp-root "$action"; then
    echo "Listed permission: $action (listing alone does not prove passwordless access)"
  else
    warn "Cannot confirm $action authorization; rerun ./setup.sh"
  fi
done

section 'Service state (inactive is normal when not playing)'
systemctl --no-pager status vhp.service || true
systemctl show vhp.service -p LoadState -p ActiveState -p SubState -p Result

section 'Backlight and sleep'
echo 'Brightness preference: /home/.vhp/data/brightness-percent (integer 0-100, default 10).'
echo 'Galileo + max 599000 uses measured OLED steps; other models/ranges use generic gamma 2.2.'
if [[ -r /sys/class/dmi/id/product_name ]]; then
  printf 'Device model: '
  head -n 1 /sys/class/dmi/id/product_name
fi
echo 'Use sudoedit to change it; restart VHP to apply. Saved/target values appear in the journal.'
echo 'Steam adaptive brightness: not queried or changed by VHP.'
echo 'It may override one-time dimming; check Steam > Settings > Display if the screen relights.'
if [[ -r /sys/class/backlight/amdgpu_bl0/brightness ]]; then
  printf 'Current brightness: '
  head -n 1 /sys/class/backlight/amdgpu_bl0/brightness
else
  warn 'amdgpu_bl0 is unavailable; automatic dimming will be skipped'
fi
systemctl is-enabled sleep.target suspend.target hibernate.target hybrid-sleep.target || true
systemd-inhibit --list --no-pager || true

section 'Recent service logs (review before sharing)'
journalctl -u vhp.service -n 40 --no-pager || true
echo 'If logs are unavailable, run: sudo journalctl -u vhp.service -n 40 --no-pager'
printf '\nDiagnostics complete: %s warning(s). No settings were changed.\n' "$issues"
((issues == 0))
