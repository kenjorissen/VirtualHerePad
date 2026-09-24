# VHP — VirtualHere Pad

Use a Steam Deck as a controller for another machine through the proprietary
[VirtualHere USB server](https://www.virtualhere.com/usb_server_software).
VHP launches the server, turns down the Deck's backlight, and inhibits normal
system sleep until you exit. Install the VirtualHere client on the other machine
and select the Deck's controller there. VirtualHere's own licensing terms apply.

## Install / update

On the Deck, clone this repository anywhere, then run as your normal user:

```bash
git pull
./setup.sh
./vhp.sh
```

The initial clone has no need for `git pull`. Setup asks for your sudo password
and downloads the current x86-64 server directly from VirtualHere over HTTPS.
Set a password with `passwd` first if your Deck doesn't have one.
Dependencies: Bash, curl, sudo, systemd, and standard GNU utilities.

Setup leaves SteamOS's read-only system partition protected: binaries go under
`/home/.vhp/bin`, settings under `/home/.vhp/data`, and only the systemd unit and
sudo rule go into `/etc` (normally writable through SteamOS's overlay). No
`steamos-readonly disable` is needed on the expected stock layout. This still
needs hardware verification; setup will report errors on unsupported layouts.

Normal SteamOS updates should preserve `/home` data and binaries. If an update
resets the `/etc` service or sudo rule, rerun setup to restore integration.

Setup is safe to rerun: it stops the current service, replaces installed code,
and keeps settings/license data in `/home/.vhp/data`. It does not start a service at
boot. Each setup fetches the latest upstream binary; to require a known hash:

```bash
VHP_SHA256=<trusted-sha256> ./setup.sh
```

Without this, HTTPS and the upstream host are trusted, not an independently
verified release checksum. The downloaded binary is not stored in Git.

## Steam

Setup offers to add or update a **VHP** non-Steam shortcut. First fully exit Steam
in Desktop Mode (**Steam > Exit**, not just closing its window). Restart Steam
after setup. Python 3 is required only for shortcut creation; no pip packages
are needed. If Python is missing, setup skips this step with a message.

You can also create/update the shortcut separately, as your normal user:

```bash
python3 steam-shortcut.py
# If multiple accounts have userdata on this Deck, choose the ID it lists:
python3 steam-shortcut.py --account 12345678
```

The helper backs up `shortcuts.vdf` beside the original before changing it,
preserves unrelated shortcuts, and updates an existing VHP/vhp.sh shortcut
instead of duplicating it. Existing app IDs and other settings are preserved.
It refuses to write while Steam is running or if the file format is unsupported.
Leave Steam closed until it finishes. Noninteractive setup skips the prompt.

The generated shortcut uses your checkout's actual path:

- **Target:** `"/usr/bin/env"`
- **Start In:** `"/home/deck/vhp"` (or wherever you cloned it)
- **Launch Options:** `-u LD_PRELOAD konsole --fullscreen -e "/home/deck/vhp/vhp.sh"`
- **Enable Steam Overlay:** on

You can keep your existing shortcut or configure those fields manually instead.
Keep the launcher open; use **Steam > Exit Game** to stop. Controller
sharing/input behavior still needs testing on your Deck and client machine.

Only one service instance is supported. Don't open multiple launchers: closing
one stops the shared service. The launcher sends a heartbeat every second.
If Steam force-kills it (even SIGKILL), the root-owned service detects the missing
heartbeat after about 10 seconds, restores brightness, and stops the server.
A hung server gets up to 3 additional seconds before being killed. Starting the
service directly without the launcher also expires after 10 seconds.
To stop it manually:

```bash
sudo -n /home/.vhp/bin/vhp-root stop
```

## Settings and diagnostics

- Server settings/license: `/home/.vhp/data/config.ini`, created on first run.
  This root-owned directory (mode `0700`) is on SteamOS's persistent home
  partition, outside the user-writable `/home/deck`. Normal SteamOS updates
  should preserve it; keep a separate backup for recovery/reimaging.
  Setup automatically copies an existing `/var/lib/vhp/config.ini` only if the
  new config does not exist, leaving the original untouched as a fallback.
- Logs: `journalctl -u vhp.service -n 100 --no-pager`
- Status: `systemctl status vhp.service`
- Read-only diagnostic report: `./doctor.sh` (run as your normal user).
  Checks tools, installed ownership/permissions, sudo authorization, service,
  backlight, sleep inhibitors, and recent logs. Review logs before sharing them;
  the script does not read private server configuration. It exits nonzero when
  it finds warnings. An inactive service alone is normal.

## Privileges and cleanup

Setup installs root-owned code under `/home/.vhp/bin`, a systemd service,
and a sudoers rule allowing only that service's fixed **start/stop/keepalive** operations.
Heartbeats contain only system uptime and live in root-only `/run/vhp`; no
caller-supplied paths or commands are accepted.
The running service never executes code or reads configuration from the writable
checkout. Editing the checkout requires another password-authorized setup to
change privileged installed code. Setup itself is trusted code: review updates
before running it.

The USB server still runs as root to access devices. Only use it on a trusted
network; VHP does not configure a firewall or server authentication. Root-owned
installation does not sandbox vulnerabilities in VirtualHere itself.

A temporary `systemd-inhibit` sleep lock prevents normal system sleep.
Backlight brightness is restored on normal stop without changing sysfs file
permissions. Steam can still adjust brightness while VHP runs. The backlight
path is currently `amdgpu_bl0`; on hardware without it, dimming is skipped.
A crash/power loss or forced kill of the privileged service itself may prevent
brightness restoration; killing only the launcher is handled by the heartbeat. Sleep
inhibitors don't prevent privileged forced suspension.

## Remove

```bash
./uninstall.sh
# Or explicitly delete the saved license/config too:
./uninstall.sh --purge-settings
```

By default settings remain in `/home/.vhp/data`. `--purge-settings` removes all
of `/home/.vhp` and any previous `/var/lib/vhp` data. Uninstall asks for sudo
access and stops the service before removing installed code and its sudo rule.
Neither installation nor removal writes to `/usr`.
Remove the non-Steam shortcut manually in Steam. The checkout is never deleted
by uninstall, even with `--purge-settings`.

## License

The scripts and documentation in this repository are MIT licensed; see
[LICENSE](LICENSE). The separately downloaded VirtualHere binary is proprietary
and is **not** covered by this license.

## Development checks

```bash
python3 -m unittest discover -s tests -v
shellcheck ./*.sh ./vhp-root
```

Tests use temporary files and mock services, not real USB devices or root access.
Before relying on VHP, test launch, client connection, normal Steam exit, and
forced launcher termination on the Deck; confirm brightness and sleep return.
