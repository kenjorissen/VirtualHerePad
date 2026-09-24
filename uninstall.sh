#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
purge=false
case "${1:-}" in
  '') [[ $# == 0 ]] || exit 1 ;;
  --purge-settings) [[ $# == 1 ]] || exit 1; purge=true ;;
  *) echo 'Usage: ./uninstall.sh [--purge-settings]' >&2; exit 1 ;;
esac

echo 'Removing the VHP service, installed code, and sudo rule.'
if "$purge"; then
  echo 'WARNING: --purge-settings permanently deletes /var/lib/vhp, including licenses/settings.'
fi
sudo -v
# Abort on stop failure: never delete files beneath a still-running service.
if [[ $(systemctl show -p LoadState --value vhp.service) != not-found ]]; then
  sudo systemctl stop vhp.service
fi
sudo rm -f -- /etc/sudoers.d/vhp /etc/systemd/system/vhp.service
sudo rm -rf -- /usr/local/lib/vhp /run/vhp
sudo systemctl daemon-reload
if "$purge"; then
  sudo rm -rf -- /var/lib/vhp
else
  echo 'Preserved settings/license in /var/lib/vhp.'
fi
echo 'Uninstalled. Remove the VHP non-Steam shortcut manually in Steam.'
echo 'The checkout and any old virtualhere/ files were left untouched.'
