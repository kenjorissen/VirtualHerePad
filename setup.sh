#!/usr/bin/env bash
# Run as your normal Steam Deck user; sudo is used only for installation.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
cd -- "$(dirname -- "$(readlink -f -- "$0")")"

if [[ $EUID == 0 ]]; then
  echo 'Run ./setup.sh as your normal user, not with sudo.' >&2
  exit 1
fi
[[ $(uname -m) == x86_64 ]] || {
  echo 'An x86-64 Steam Deck is required.' >&2
  exit 1
}
USER_ROOT="${HOME:?HOME must be set}/.local/share/VirtualHerePad"
user=$(id -un)
[[ $user =~ ^[a-z_][a-z0-9_-]*\$?$ ]] || {
  echo 'Unsupported username.' >&2
  exit 1
}
echo '== Preflight checks =='
for cmd in curl sudo systemctl systemd-inhibit visudo install sha256sum konsole python3; do
  command -v "$cmd" >/dev/null || {
    echo "Missing dependency: $cmd" >&2
    exit 1
  }
done
if [[ -n ${VHP_SHA256:-} && ! $VHP_SHA256 =~ ^[[:xdigit:]]{64}$ ]]; then
  echo 'Invalid VHP_SHA256.' >&2
  exit 1
fi
[[ -d /run/systemd/system ]] || {
  echo 'A running systemd system is required.' >&2
  exit 1
}
# Check the user-side install location without using sudo.
user_parent=$USER_ROOT
while [[ ! -d "$user_parent" ]]; do user_parent=$(dirname "$user_parent"); done
user_probe=$(mktemp "$user_parent/.vhp-write-check.XXXXXX")
rm -f -- "$user_probe"
echo 'Checking sudo access (set a password with passwd first if needed)...'
sudo -v
# Probe the nearest existing install directories without creating installation data.
sudo bash <<'VHP_PREFLIGHT'
set -euo pipefail
for target in /home/.vhp/bin /home/.vhp/data /etc/systemd/system /etc/sudoers.d; do
  directory=$target
  while [[ ! -d "$directory" ]]; do directory=$(dirname "$directory"); done
  if ! probe=$(mktemp "$directory/.vhp-write-check.XXXXXX"); then
    echo "Cannot write installation path: $target. Check filesystem permissions/mounts." >&2
    exit 1
  fi
  rm -f -- "$probe"
done
VHP_PREFLIGHT
if ! python3 steam-shortcut.py --check; then
  echo 'WARNING: Steam account setup needs attention; installation can continue without a shortcut.'
  echo 'Log into Steam once, or use --account ID with steam-shortcut.py if prompted.'
fi
echo 'Preflight passed. No Steam processes were stopped.'
echo 'Display note: Steam adaptive brightness may override VHP screen dimming.'
echo 'Its current setting is not checked or changed. You can leave it enabled.'

tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
url=https://www.virtualhere.com/sites/default/files/usbserver/vhusbdx86_64
echo "Downloading VirtualHere from $url"
curl --fail --location --proto '=https' --proto-redir '=https' \
  --retry 3 --connect-timeout 20 --max-time 180 \
  --output "$tmp/vhusbdx86_64" "$url"
[[ -s "$tmp/vhusbdx86_64" ]] || {
  echo 'Empty download.' >&2
  exit 1
}
if [[ -n ${VHP_SHA256:-} ]]; then
  printf '%s  %s\n' "$VHP_SHA256" "$tmp/vhusbdx86_64" | sha256sum --check -
else
  echo 'Download SHA-256 (HTTPS trusted; no pinned checksum supplied):'
  sha256sum "$tmp/vhusbdx86_64"
fi

commit=unknown
if command -v git >/dev/null && [[ $(git rev-parse --show-toplevel 2>/dev/null || true) == "$PWD" ]]; then
  commit=$(git rev-parse --verify HEAD 2>/dev/null || echo unknown)
  if [[ -n $(git status --porcelain) ]]; then commit="${commit}-dirty"; fi
fi
binary_hash=$(sha256sum "$tmp/vhusbdx86_64")
printf 'VHP_COMMIT=%s\nVIRTUALHERE_SHA256=%s\nINSTALLED_UTC=%s\n' \
  "$commit" "${binary_hash%% *}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$tmp/build-info.txt"

printf '%s ALL=(root) NOPASSWD: /home/.vhp/bin/vhp-root start, /home/.vhp/bin/vhp-root stop, /home/.vhp/bin/vhp-root keepalive, /home/.vhp/bin/vhp-root check\n' "$user" >"$tmp/sudoers"
visudo -cf "$tmp/sudoers"
sudo -v
# Reinstalling stops the old instance first so it can restore brightness.
if systemctl is-active --quiet vhp.service; then
  sudo systemctl stop vhp.service
fi
# Persistent SteamOS code/data lives on /home, outside the user's writable home.
sudo bash <<'VHP_DATA_SETUP'
set -euo pipefail
base=/home/.vhp
data=$base/data
# Refuse pre-existing user-controlled paths rather than taking ownership of them.
for directory in "$base" "$base/bin" "$data"; do
  if [[ -L "$directory" ]] || { [[ -e "$directory" ]] &&
    [[ ! -d "$directory" || $(stat -c '%u' "$directory") != 0 ]]; }; then
    echo "Refusing unsafe installation directory: $directory" >&2
    exit 1
  fi
  if [[ -d "$directory" ]]; then
    mode=$(stat -c '%a' "$directory")
    if (( (8#$mode & 8#022) != 0 )); then
      echo "Refusing group/other-writable directory: $directory" >&2
      exit 1
    fi
  fi
done
for config in "$base/config.ini" "$data/config.ini" "$data/brightness-percent"; do
  if [[ -L "$config" ]]; then
    echo "Refusing symlinked config: $config" >&2
    exit 1
  fi
  if [[ -f "$config" ]]; then
    chown root:root "$config"
    chmod 600 "$config"
  fi
done
install -d -o root -g root -m 755 "$base" "$base/bin"
install -d -o root -g root -m 700 "$data"
# User preference: create once, never overwrite on setup/update.
if [[ ! -e "$data/brightness-percent" ]]; then
  printf '10\n' > "$data/brightness-percent"
  chmod 600 "$data/brightness-percent"
fi
for previous in "$base/config.ini" /var/lib/vhp/config.ini; do
  if [[ ! -e "$data/config.ini" && -f "$previous" ]]; then
    install -o root -g root -m 600 "$previous" "$data/config.ini"
    echo "Migrated settings to $data; original retained at $previous."
  fi
done
VHP_DATA_SETUP
sudo install -o root -g root -m 755 "$tmp/vhusbdx86_64" /home/.vhp/bin/vhusbdx86_64
sudo install -o root -g root -m 755 vhp-root /home/.vhp/bin/vhp-root
sudo install -o root -g root -m 644 touch-stop.py /home/.vhp/bin/touch-stop.py
sudo install -o root -g root -m 644 "$tmp/build-info.txt" /home/.vhp/bin/build-info.txt
sudo install -o root -g root -m 644 vhp.service /etc/systemd/system/vhp.service
# Preserve any existing license/settings. Never automatically import checkout files.
# SteamOS's general password-required rule must come before this override.
sudo install -o root -g root -m 440 "$tmp/sudoers" /etc/sudoers.d/zz-vhp
sudo rm -f -- /etc/sudoers.d/vhp
sudo systemctl daemon-reload
sudo visudo -c
# -k ignores cached authentication for this invocation; -n never prompts.
# A real harmless invocation catches rule-order problems that sudo -l misses.
if ! sudo -k -n /home/.vhp/bin/vhp-root check; then
  echo 'ERROR: passwordless VHP access failed. Inspect sudo -l for later overriding rules.' >&2
  exit 1
fi

# BEGIN USER_INSTALL
# No runtime tool should depend on this checkout remaining in place.
install -d -m 755 "$USER_ROOT"
install -m 755 vhp.sh vhp-gui.sh doctor.sh uninstall.sh "$USER_ROOT/"
install -m 644 steam-shortcut.py "$USER_ROOT/steam-shortcut.py"
install -d -m 700 "$USER_ROOT/konsole/config" "$USER_ROOT/konsole/data/kxmlgui5/konsole"
install -m 600 konsole/config/konsolerc "$USER_ROOT/konsole/config/konsolerc"
install -m 600 konsole/data/kxmlgui5/konsole/*.rc "$USER_ROOT/konsole/data/kxmlgui5/konsole/"
# GUI state is disposable: do not let an older saved toolbar layout override XML.
rm -f -- "$USER_ROOT/konsole/state/konsolestaterc"
# END USER_INSTALL

echo 'VirtualHerePad components installed successfully.'
echo "User tools: $USER_ROOT"
echo 'Settings: /home/.vhp/data/config.ini (created by VirtualHere on first run).'
echo 'Logs: journalctl -u vhp.service'
echo
shortcut_status='skipped (not requested)'
if [[ -t 0 ]]; then
  echo 'If Steam is running, the shortcut helper will offer to shut it down gracefully.'
  if read -r -p 'Add/update the VirtualHerePad Steam shortcut now? [y/N] ' answer; then
    case "$answer" in
      y | Y | yes | YES)
        if python3 "$USER_ROOT/steam-shortcut.py"; then
          shortcut_status='ready (added, updated, or already current)'
        else
          shortcut_status='not updated (see error above)'
          echo 'VirtualHerePad installation succeeded, but the Steam shortcut was not updated.'
          printf 'Follow the message above, then rerun: python3 "%s/steam-shortcut.py"\n' "$USER_ROOT"
        fi
        ;;
      *) printf 'Skipped. Add it later with: python3 "%s/steam-shortcut.py"\n' "$USER_ROOT" ;;
    esac
  fi
else
  shortcut_status='skipped (noninteractive setup)'
  printf 'Noninteractive setup: shortcut skipped. Run python3 "%s/steam-shortcut.py" to add it.\n' "$USER_ROOT"
fi

printf '\n== Setup complete ==\n'
echo "Installation: successful ($commit)"
echo "Steam shortcut: $shortcut_status"
echo 'Settings: /home/.vhp/data/config.ini (preserved on reinstall)'
echo 'VirtualHerePad is not started or enabled at boot.'
case "$shortcut_status" in
  ready*)
    echo 'Next: in Gaming Mode, open Library > Non-Steam > VirtualHerePad > Play.'
    echo 'A new shortcut may not appear on Home / Recently Played until first launch.'
    echo 'Then connect from the other machine using the VirtualHere client.'
    ;;
  *) printf 'Next: run python3 "%s/steam-shortcut.py", then find VirtualHerePad under Library > Non-Steam.\n' "$USER_ROOT" ;;
esac
printf 'Diagnostics: "%s/doctor.sh"\n' "$USER_ROOT"
printf 'Manual launcher test: "%s/vhp.sh"\n' "$USER_ROOT"
if [[ $shortcut_status == ready* ]]; then
  echo 'The shortcut uses installed files; the checkout can be moved or deleted.'
else
  echo 'Before deleting the checkout, update any old Steam shortcut to use the installed launcher.'
fi
echo 'Display: defaults to 10%; edit /home/.vhp/data/brightness-percent (0-100) with sudo.'
echo 'Galileo OLED with max 599000 uses measured steps; other models/ranges use generic gamma 2.2.'
echo 'Existing brightness preferences are preserved. VHP does not fight Steam adaptive brightness.'
echo 'If the screen relights, check Steam > Settings > Display > Enable Adaptive Brightness.'
echo 'That setting is yours to change; setup leaves it untouched.'
echo 'Tip: keep the launcher open; hold one finger in any screen corner for 2 seconds to stop.'
echo 'Fallback: use a local keyboard and Ctrl+C to stop.'
echo 'The Deck Steam button may be forwarded to the VirtualHere client.'
