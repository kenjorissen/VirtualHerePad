# VirtualHerePad

Use a Steam Deck as a controller for another machine through the proprietary
[VirtualHere USB server](https://www.virtualhere.com/usb_server_software).
VirtualHerePad (VHP) launches the server, turns down the Deck's backlight, and inhibits normal
system sleep until you exit. Install the VirtualHere client on the other machine
and select the Deck's controller there. VirtualHere's own licensing terms apply.

## Install

On the Deck, log into Steam once, switch to **Desktop Mode**, and open Konsole.
Run as your normal user (not root). If you haven't set a sudo password yet, run
`passwd` first.

```bash
cd ~
git clone https://github.com/kenjorissen/VirtualHerePad.git
cd VirtualHerePad
./setup.sh
```

Accept the offer to add the **VirtualHerePad** Steam shortcut. After setup,
launch **VirtualHerePad** from Steam's Library (the **Non-Steam** tab in Gaming
Mode). You do not need to run `vhp.sh` yourself for normal use.

Setup asks for your sudo password and downloads the current x86-64 VirtualHere
server directly from its publisher over HTTPS. All prerequisites—Git, Bash,
Python 3, curl, sudo, systemd, Konsole, and the standard GNU utilities—are already
included on a stock Steam Deck. **No extra package installation, pacman, pip,
or virtual environment is necessary.**

Before downloading, setup checks required tools, sudo access, writable install
paths, and Steam account discovery. Missing/ambiguous Steam accounts produce
warnings rather than blocking installation without a shortcut.
Preflight does not shut down Steam. The final summary reports installation and
shortcut status separately and tells you what to do next.

Setup leaves SteamOS's read-only system partition protected: binaries go under
`/home/.vhp/bin`, settings under `/home/.vhp/data`, and only the systemd unit and
sudo rule go into `/etc` (normally writable through SteamOS's overlay). No
`steamos-readonly disable` is needed on the expected stock layout. This has been
tested on a Steam Deck; setup will report errors on unsupported layouts.

Normal SteamOS updates should preserve `/home` data and binaries. If an update
resets the `/etc` service or sudo rule, rerun setup to restore integration.

## Update

From your checkout (normally `~/VirtualHerePad`):

```bash
cd ~/VirtualHerePad
git pull
./setup.sh
```

Setup is safe to rerun: it stops the current service, replaces installed code,
and keeps settings/license data in `/home/.vhp/data`. It does not start a service at
boot. Each setup fetches the latest upstream binary; to require a known hash:

```bash
VHP_SHA256=<trusted-sha256> ./setup.sh
```

Without this, HTTPS and the upstream host are trusted, not an independently
verified release checksum. The downloaded binary is not stored in Git.

## Steam

Run setup from **Desktop Mode**. It offers to add or update a **VirtualHerePad** non-Steam
shortcut. If Steam is running, the helper asks permission to close it with
`steam -shutdown`. Save games and finish downloads before accepting. It waits
up to 30 seconds after the shutdown command completes, never force-kills Steam,
and leaves shortcuts unchanged if you decline or shutdown fails. Noninteractive
runs never shut Steam down automatically.

You can also exit Steam yourself (**Steam > Exit**, not just closing its window).
After a successful shortcut update, the helper offers to reopen Steam. It never
launches Steam automatically in noninteractive runs. Python 3 is used for
shortcut creation and the local touchscreen exit monitor; setup checks for it.

You can also create/update the shortcut separately, as your normal user:

```bash
python3 steam-shortcut.py
# Check account discovery without editing shortcuts or stopping Steam:
python3 steam-shortcut.py --check
# If multiple accounts have userdata on this Deck, choose the ID it lists:
python3 steam-shortcut.py --account 12345678
```

The helper backs up `shortcuts.vdf` beside the original before changing it,
preserves unrelated shortcuts, and updates an existing VirtualHerePad, VHP, or
vhp.sh shortcut instead of duplicating it. Older VHP entries are renamed to
VirtualHerePad. Existing app IDs and other settings are preserved.
It refuses to write while Steam is running or if the file format is unsupported.
Leave Steam closed until it finishes. Noninteractive setup skips the prompt.

The generated shortcut uses your checkout's actual path:

- **Target:** `"/usr/bin/env"`
- **Name:** `VirtualHerePad`
- **Start In:** `"/home/deck/VirtualHerePad"` (or wherever you cloned it)
- **Launch Options:** `-u LD_PRELOAD konsole --fullscreen -e "/home/deck/VirtualHerePad/vhp.sh"`
- **Enable Steam Overlay:** on

`vhp.sh` is the launcher script used by this shortcut. For troubleshooting, you
can run `./vhp.sh` manually from your checkout in Konsole to see its output; this
starts the same service and dims the screen. It is not an extra installation step.

No specific checkout directory name is required; paths with spaces are supported.
Setup resolves its own location, and the shortcut helper uses that actual
path—not an assumed username or folder name. Existing `~/vhp` clones still work. After moving or
renaming a checkout, rerun `python3 /new/path/steam-shortcut.py` (or setup) to update
the shortcut. Installed privileged code/data stay at fixed, root-owned paths
under `/home/.vhp`, independently of the checkout name.

You can configure the shortcut fields manually instead. Keep the launcher open. To stop, **hold one finger in any screen corner for two
seconds** (within the outer 12% of both touchscreen axes). Releasing, moving out
of the corner, or adding another finger cancels the hold. After multiple fingers,
lift all fingers before trying again. All four corners work regardless of panel
rotation. The helper handles the request within its existing one-second loop.

The root-owned Python monitor detects direct type-B multitouch devices by
capabilities, not an event number or device name. It reads input non-exclusively
(no input grab), logs no coordinates, and requires the touchscreen to remain
local rather than forwarded through VirtualHere. Other local apps can still
receive the touches. A finger already down when monitoring starts must lift
before arming. Corner-hold exit and brightness restoration have been tested on
a Steam Deck; keep the keyboard fallback available when testing other hardware.

The monitor blocks on input while idle—no periodic polling of a connected idle
touchscreen. Only a potential hold schedules a timer. If the device is absent,
it retries discovery every ten seconds. This adds no graphical UI and should
have small overhead, but battery impact has not been measured.

A local Bluetooth keyboard can also stop it with **Ctrl+C**, including if touch
monitoring fails. The Deck's Steam button may be forwarded to the VirtualHere
client, so don't rely on it to open the local Steam menu. If you can access that
menu locally, **Steam > Exit Game** also stops VHP.

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
  backlight, sleep inhibitors, and recent logs. It also shows the installed VHP
  commit, installation time, and recorded/actual VirtualHere SHA-256 hashes.
  Local modifications at install time add `-dirty` to the commit; non-Git copies
  report `unknown`. Metadata lives in `/home/.vhp/bin/build-info.txt` and does not
  contain usernames, license data, or connection credentials.
  Review logs before sharing them; the script does not read private server
  configuration. It exits nonzero when
  it finds warnings. An inactive service alone is normal.

## Privileges and cleanup

Setup installs root-owned code under `/home/.vhp/bin`, a systemd service,
and `/etc/sudoers.d/zz-vhp`, allowing only fixed **start/stop/keepalive/check**
operations. The late-sorting filename places it after SteamOS's general sudo
rule. The `check` operation does nothing except exit successfully; setup and
diagnostics run it without cached authentication to verify passwordless access.
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
permissions. Dimming is a one-time write; VHP does not continuously override
Steam's brightness control. Adaptive brightness can relight the screen while
VHP runs. Setup warns about this but does **not** check or change the setting:
there is no verified shell interface for it. You can leave adaptive brightness
enabled. If relighting becomes a problem, check **Steam > Settings > Display >
Enable Adaptive Brightness** and optionally disable it while sharing.
The backlight
path is currently `amdgpu_bl0`; on hardware without it, dimming is skipped.
Saved and restored brightness values are logged in the service journal. If the
saved value is already zero, VHP warns and restores zero rather than guessing a
new level. This logging helps diagnose a screen that stays dark after exit.
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
