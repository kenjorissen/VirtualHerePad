#!/usr/bin/env bash
# Run as your normal Steam Deck user; sudo is used only for installation.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
cd -- "$(dirname -- "$(readlink -f -- "$0")")"

if [[ $EUID == 0 ]]; then
  echo 'Run ./setup.sh as your normal user, not with sudo.' >&2
  exit 1
fi
[[ $(uname -m) == x86_64 ]] || { echo 'An x86-64 Steam Deck is required.' >&2; exit 1; }
user=$(id -un)
[[ $user =~ ^[a-z_][a-z0-9_-]*\$?$ ]] || { echo 'Unsupported username.' >&2; exit 1; }
for cmd in curl sudo systemctl systemd-inhibit visudo install sha256sum; do
  command -v "$cmd" >/dev/null || { echo "Missing dependency: $cmd" >&2; exit 1; }
done

tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
url=https://www.virtualhere.com/sites/default/files/usbserver/vhusbdx86_64
echo "Downloading VirtualHere from $url"
curl --fail --location --proto '=https' --proto-redir '=https' \
  --retry 3 --connect-timeout 20 --max-time 180 \
  --output "$tmp/vhusbdx86_64" "$url"
[[ -s "$tmp/vhusbdx86_64" ]] || { echo 'Empty download.' >&2; exit 1; }
if [[ -n ${VHP_SHA256:-} ]]; then
  [[ $VHP_SHA256 =~ ^[[:xdigit:]]{64}$ ]] || { echo 'Invalid VHP_SHA256.' >&2; exit 1; }
  printf '%s  %s\n' "$VHP_SHA256" "$tmp/vhusbdx86_64" | sha256sum --check -
else
  echo 'Download SHA-256 (HTTPS trusted; no pinned checksum supplied):'
  sha256sum "$tmp/vhusbdx86_64"
fi

printf '%s ALL=(root) NOPASSWD: /home/.vhp/bin/vhp-root start, /home/.vhp/bin/vhp-root stop, /home/.vhp/bin/vhp-root keepalive\n' "$user" > "$tmp/sudoers"
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
for config in "$base/config.ini" "$data/config.ini"; do
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
for previous in "$base/config.ini" /var/lib/vhp/config.ini; do
  if [[ ! -e "$data/config.ini" && -f "$previous" ]]; then
    install -o root -g root -m 600 "$previous" "$data/config.ini"
    echo "Migrated settings to $data; original retained at $previous."
  fi
done
VHP_DATA_SETUP
sudo install -o root -g root -m 755 "$tmp/vhusbdx86_64" /home/.vhp/bin/vhusbdx86_64
sudo install -o root -g root -m 755 vhp-root /home/.vhp/bin/vhp-root
sudo install -o root -g root -m 644 vhp.service /etc/systemd/system/vhp.service
# Preserve any existing license/settings. Never automatically import checkout files.
sudo install -o root -g root -m 440 "$tmp/sudoers" /etc/sudoers.d/vhp
sudo systemctl daemon-reload
sudo visudo -cf /etc/sudoers.d/vhp
sudo -n -l /home/.vhp/bin/vhp-root start

echo 'Installed. Run ./vhp.sh, or add it to Steam as a non-Steam game.'
echo 'Settings: /home/.vhp/data/config.ini (created by VirtualHere on first run).'
echo 'Logs: journalctl -u vhp.service'
echo
if ! command -v python3 >/dev/null; then
  echo 'Skipping Steam shortcut: python3 is unavailable.'
  echo 'Add vhp.sh manually in Steam, or install Python 3 and run python3 steam-shortcut.py.'
elif [[ -t 0 ]]; then
  echo 'Steam must be fully exited before its shortcut file can be updated.'
  if read -r -p 'Add/update the VHP Steam shortcut now? [y/N] ' answer; then
    case "$answer" in
      y|Y|yes|YES)
        if ! python3 steam-shortcut.py; then
          echo 'VHP installation succeeded, but the Steam shortcut was not updated.'
          echo 'Follow the message above, then rerun: python3 steam-shortcut.py'
        fi
        ;;
      *) echo 'Skipped. You can add it later with: python3 steam-shortcut.py' ;;
    esac
  fi
else
  echo 'Noninteractive setup: shortcut skipped. Run python3 steam-shortcut.py to add it.'
fi
