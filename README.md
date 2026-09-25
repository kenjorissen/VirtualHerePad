# VirtualHerePad

Use a Steam Deck as a controller for another machine through the proprietary
[VirtualHere USB server](https://www.virtualhere.com/usb_server_software).
VirtualHerePad (VHP) starts the server, dims the Deck's screen, and prevents normal
sleep while sharing. Hold a screen corner to stop and restore brightness.
VirtualHere's own licensing terms apply.

## What is VirtualHere?

[VirtualHere](https://www.virtualhere.com/) shares **USB devices over a network**.
The receiving computer sees a shared device as though it were plugged into a
local USB port. This is controller sharing, not game/video streaming: your game
runs on the receiving computer, while the Deck supplies its controller input.

There are two parts:

- **Server — on the Steam Deck.** VirtualHerePad downloads and runs VirtualHere's
  USB server, then handles the Steam shortcut, screen dimming, and local exit
  gesture. You don't need to install the server yourself.
- **Client — on your gaming PC.** Install/run VirtualHere's USB client to connect
  to the Deck's controller. VirtualHerePad does not install this on the PC.

VirtualHere is separate, proprietary software—not part of VirtualHerePad's MIT
license. See its [official website](https://www.virtualhere.com/) for licensing,
trial limitations, pricing, and support. Existing server config/license files
can be [imported into VirtualHerePad](#config-and-license).

### Windows client quick start

1. On your Windows PC, open the official
   [VirtualHere USB Client download page](https://www.virtualhere.com/usb_client_software).
   Download **Windows x86_64** for a typical Intel/AMD PC, or **Windows ARM64**
   for an ARM-based Windows PC. Save and run the downloaded executable; follow
   any Windows permission or driver-installation prompts. Installing it as a
   Windows service is optional, not needed for this quick start.
2. Put the PC and Deck on the same trusted local network. Complete the Deck
   setup below and launch **VirtualHerePad** from Steam.
3. The client should discover the Deck's server and list its USB devices in a
   tree. Right-click the **Steam Controller** device (its label may include
   **Valve Software**) and select **Use**. Don't share the touchscreen—you need
   it locally for the corner-hold exit gesture.
4. Windows now sees the controller as a local USB device. Use Steam/Steam Input
   on the PC to configure it for your game as needed. When finished, stop using
   the device in the client or stop VHP with the Deck's corner-hold gesture.

If the Deck isn't discovered, check that VHP is running, both machines can reach
each other, and the network isn't a guest network with client isolation. Check
firewall rules too; the server uses TCP port **7575** by default. Don't expose
that port to the public internet. The client also supports manually specifying
a server address; see VirtualHere's client documentation for details.

## Quick start

All prerequisites are included on a stock Steam Deck. **No extra pacman or pip
packages, graphical toolkits, or virtual environment are needed.** Setup downloads
the VirtualHere server for you.

1. **Prepare the Deck.** Log into Steam once, switch to **Desktop Mode**, and open
   **Konsole**. Run as your normal user, not root. If you haven't set a sudo
   password yet, run `passwd`.
2. **Clone and install:**

   ```bash
   cd ~
   git clone https://github.com/kenjorissen/VirtualHerePad.git
   cd VirtualHerePad
   ./setup.sh
   ```

3. **Add the shortcut.** Accept setup's offer to add **VirtualHerePad** to Steam.
   Save games and finish downloads before allowing it to close Steam. Accept
   the offer to reopen Steam afterward, or open it yourself. If you already
   have a VirtualHere config/license, [import it](#config-and-license) before
   your first launch.
4. **Disable adaptive brightness.** In **Gaming Mode**, open **Steam > Settings >
   Display** and turn off **Enable Adaptive Brightness**. This prevents Steam's
   dynamic brightness control from relighting the screen while VHP runs. Setup
   does not change this setting; you can re-enable it after sharing.
5. **Find it explicitly.** In **Gaming Mode**, open **Library**, select
   the **Non-Steam** tab, then open **VirtualHerePad** and select **Play**.
   **Don't look only at Home / Recently Played:** a newly added shortcut may
   not appear there until it has actually been launched. In Desktop Mode, use
   Library search for `VirtualHerePad` with filters that include non-Steam games.
6. **Connect from the other machine.** Follow the [Windows client quick start](#windows-client-quick-start)
   above (clients are also available for macOS and Linux). Select **Use** on the
   Deck's controller and leave the Deck's launcher running.
7. **Stop when finished.** Hold **one finger in any screen corner for two
   seconds**. VHP stops sharing and restores brightness. A local Bluetooth
   keyboard and **Ctrl+C** are the fallback; the Deck's Steam button may be
   forwarded to the client rather than opening the local menu.

Setup installs the launcher and user tools into **`~/.local/share/VirtualHerePad`**.
Steam runs the installed `vhp.sh`, not the checkout. You do **not** need to run it
separately during installation. For a manual test in Konsole:

```bash
~/.local/share/VirtualHerePad/vhp.sh
```

This starts the same service and dims the screen. Once setup has updated the
shortcut, the checkout can be moved or deleted without affecting normal use.

## Update

From your checkout (normally `~/VirtualHerePad`):

```bash
cd ~/VirtualHerePad
git pull
./setup.sh
```

Setup stops the current instance, replaces installed code and user tools, and
preserves settings and license data. If you deleted the checkout, clone the
repository again and run its `setup.sh`. When upgrading from an older version,
accept shortcut creation so the existing entry is redirected from the checkout
to the installed launcher; its app ID and other settings are preserved.
Setup does not start VHP or enable it at boot. Normal SteamOS updates should preserve `/home`; if an update resets the service or sudo rule in
`/etc`, rerun setup to restore integration.

## Config and license

The active config is **`/home/.vhp/data/config.ini`**, created on the first server
run. It is **not** in `~/.vhp`, `/home/deck/.vhp`, or the Git checkout. The hidden
`.vhp` directory sits directly under `/home`; its root-only `data` directory has
mode `0700`. Check the file without displaying private contents:

```bash
sudo ls -l /home/.vhp/data/config.ini
```

To import a config from another VirtualHere installation, run setup first, then:

```bash
sudo -n /home/.vhp/bin/vhp-root stop
sudo install -o root -g root -m 600 /path/to/your/config.ini /home/.vhp/data/config.ini
```

Replace the source path with your actual file. This **replaces** the installed
config; the source is untouched. Launch VirtualHerePad from Steam afterward.
Setup also imports an existing `/var/lib/vhp/config.ini` if no current config
exists, retaining the old file as a fallback.

Config files can contain license and connection credentials. Keep them private;
don't commit them or paste them into public bug reports. Normal updates and
uninstall preserve the active config in place, without making a backup in your
user home. Keep a separate private backup for factory resets/reimaging.

## Using and stopping VHP

- Keep only one launcher open: all launchers control the same service.
- For touchscreen exit, hold within the outer **12% of both axes** in any corner.
  Releasing, moving out, or adding a finger cancels the hold. After multiple
  fingers, lift them all before retrying. A finger already down at startup must
  also lift before the gesture can arm. All corners work regardless of rotation.
- Touches remain available to other local apps. The touchscreen must stay local,
  not be forwarded through VirtualHere. Corner-hold exit and brightness
  restoration have been tested on a Steam Deck.
- The root-owned Python monitor detects direct type-B multitouch devices by
  capabilities, not event numbers. It makes no exclusive input grab and logs no
  coordinates. It blocks on input when idle; only an active hold needs a timer.
  Missing-device discovery retries every ten seconds. Battery impact has not
  been measured, but there is no graphical UI or continuous idle polling.
- A touch request is handled within the existing one-second service loop. If
  Steam kills the launcher instead, its heartbeat expires after about ten
  seconds and the service shuts down. A hung USB server gets up to three more
  seconds before being killed. Starting the service without the launcher also
  expires after ten seconds.

If touch exit fails, use local-keyboard **Ctrl+C**, or **Steam > Exit Game** if you
can reach the local Steam menu. From Konsole or SSH, you can always request:

```bash
sudo -n /home/.vhp/bin/vhp-root stop
```

### Screen brightness

VHP dims once and restores the saved value on normal exit without changing sysfs
permissions. **Steam adaptive brightness can relight the screen.** Setup warns
about this but neither checks nor changes that setting. You can leave it enabled;
if relighting is a problem, optionally disable **Steam > Settings > Display >
Enable Adaptive Brightness** while sharing.

The backlight path is currently `amdgpu_bl0`; dimming is skipped if unavailable.
Saved/restored values are logged. If brightness was already zero at startup,
VHP warns and restores zero rather than guessing a new level. Killing the
launcher is handled by the heartbeat, but a power loss or forced kill of the
privileged service itself can prevent restoration. Sleep inhibition does not
prevent privileged forced suspension.

## Shortcut reference and troubleshooting

Setup checks tools, sudo access, writable paths, and Steam account discovery
before downloading. Missing/ambiguous accounts produce a warning rather than
blocking installation without a shortcut. Read the final summary to see whether
shortcut creation succeeded or was skipped.

The shortcut helper asks before closing Steam with `steam -shutdown` and waits
up to 30 seconds after that command completes. It never force-kills Steam or
writes shortcuts while Steam is running. Declining shutdown or a shutdown
failure leaves shortcuts unchanged. Noninteractive setup skips shortcut prompts
and never closes or opens Steam automatically.

The installed shortcut helper works without a checkout:

```bash
python3 ~/.local/share/VirtualHerePad/steam-shortcut.py
# Check account discovery without editing files or stopping Steam:
python3 ~/.local/share/VirtualHerePad/steam-shortcut.py --check
# If multiple accounts exist, use the userdata ID listed by the helper:
python3 ~/.local/share/VirtualHerePad/steam-shortcut.py --account 12345678
```

Running the helper from a checkout also targets the installed launcher. Run
setup first; shortcut creation refuses a missing/non-executable launcher.

The helper backs up `shortcuts.vdf`, preserves other shortcuts, and updates an
existing VirtualHerePad/VHP/vhp.sh entry instead of duplicating it. Old VHP names
are renamed while app IDs and other settings are retained. Unsupported file
formats are left unchanged. It does not fabricate play history to promote the
shortcut into Steam's Home / Recently Played view.

Manual shortcut fields for the normal `deck` account:

| Field | Value |
| --- | --- |
| Name | `VirtualHerePad` |
| Target | `"/usr/bin/env"` |
| Start In | `"/home/deck/.local/share/VirtualHerePad"` |
| Launch Options | `-u LD_PRELOAD konsole --fullscreen -e "/home/deck/.local/share/VirtualHerePad/vhp.sh"` |
| Steam Overlay | On |
| Force Steam Play compatibility tool | Off (native Linux launcher) |

Setup resolves its own source directory and the invoking user's home; no checkout
name or username is assumed, and spaces are supported. User tools always install
under that home's `.local/share/VirtualHerePad` (not `$XDG_DATA_HOME`), so launching
from Steam or Konsole uses the same location. Existing `~/vhp` clones still work.
Moving or deleting the checkout no longer requires changing an installed shortcut.

## Diagnostics

```bash
~/.local/share/VirtualHerePad/doctor.sh
systemctl status vhp.service
journalctl -u vhp.service -n 100 --no-pager
```

`doctor.sh` is read-only: it checks tools, ownership, sudo access, service state,
backlight, sleep inhibitors, and logs. It reports installed commit/time and
recorded/actual VirtualHere binary hashes from `/home/.vhp/bin/build-info.txt`.
Modified checkouts record `-dirty`; non-Git installations record `unknown`.
It exits nonzero for warnings; an inactive service alone is normal. Use sudo
for the journal command if your account cannot read the logs. Review logs before
sharing; diagnostics do not read the private config contents.

## Installation and security details

Stock Steam Deck prerequisites are Git, Bash, Python 3, curl, sudo, systemd,
Konsole, and GNU utilities. Setup downloads the current x86-64 VirtualHere server
over HTTPS. To require a known trusted hash:

```bash
VHP_SHA256=<trusted-sha256> ./setup.sh
```

Without a pinned hash, HTTPS and the upstream host are trusted rather than an
independently verified release checksum. The proprietary binary is not in Git.

The launcher, shortcut helper, diagnostics, and uninstaller are user-owned under
`~/.local/share/VirtualHerePad`. Only these unprivileged tools live in the user's
writable home. Root-owned code stays in `/home/.vhp/bin`, settings in
`/home/.vhp/data`, and only the service and sudo rule go in `/etc` (normally writable through SteamOS's
overlay). Setup/uninstall do not write to `/usr` or require disabling SteamOS's
read-only protection. This layout has been tested on a Steam Deck.

`/etc/sudoers.d/zz-vhp` grants only fixed **start/stop/keepalive/check** operations
and sorts after SteamOS's general sudo rule. The harmless `check` operation
verifies passwordless access without cached authentication. Heartbeats and touch
exit requests use root-only `/run/vhp`; callers cannot supply arbitrary paths or
commands. The service never runs code or reads settings from the writable
checkout. Review changes before running setup, which installs trusted code using
your password-authorized sudo access.

VirtualHere still runs as root for device access. Root ownership is not a sandbox
against server vulnerabilities. Use a trusted network; VHP does not configure a
firewall or server authentication.

## Remove

Run as your normal user (not with `sudo`), from any directory:

```bash
~/.local/share/VirtualHerePad/uninstall.sh
```

The checkout's `./uninstall.sh` works too. This stops the service and removes
privileged code, the sudo rule, and the four installed user tools. Settings
remain at `/home/.vhp/data/config.ini` for reinstalling; nothing is moved to
`/home/deck`. Remove the non-Steam shortcut manually in Steam. The checkout and
old local files are left untouched.

**Only if you want to permanently delete settings/license without a backup:**

```bash
~/.local/share/VirtualHerePad/uninstall.sh --purge-settings
```

This additionally deletes `/home/.vhp` and any previous `/var/lib/vhp` data.

## License

Repository scripts and documentation are MIT licensed; see [LICENSE](LICENSE).
The separately downloaded VirtualHere binary is proprietary and is **not**
covered by that license.

## Development

There is no build step. On a Linux development machine, have **Python 3, Bash,
GNU make, ShellCheck, and [uv](https://docs.astral.sh/uv/)** available. `uvx`
(included with uv) downloads Ruff and shfmt into its tool cache on first use;
no project virtual environment is required. These tools are **development-only**:
Deck users still just run `setup.sh`, not these commands.

Run from the checkout:

```bash
make fmt    # Fix Python lint/import issues and format Python + shell files
make lint   # Check Ruff, formatting, ShellCheck, and Bash syntax; no source edits
make test   # Run the Python unittest suite
make check  # Run lint + tests (also the default for plain make)
```

Ruff settings live in `ruff.toml`. Shell formatting uses shfmt with two-space
indentation and indented case branches. `.github/workflows/check.yml` runs the
same `make check` on pushes, pull requests, and manual workflow dispatches.
CI currently uses Python 3.11; tools can be overridden locally, for example
`make check PYTHON=python3.13` or `make lint SHELLCHECK=/path/to/shellcheck`.

### Tool versions

The Makefile pins **Ruff** and the **shfmt-py** distribution (which supplies the
shfmt binary) to exact versions. Formatter releases can change output, so this
keeps local formatting consistent with CI. To upgrade, change the version in
the Makefile, run `make fmt` followed by `make check`, and review the diff.

Python, make, and ShellCheck are not exact-version pinned; CI uses its selected
Python minor version and the runner's packaged shell tools. This is a practical
development baseline, not a fully reproducible toolchain. If ShellCheck version
differences become a problem, it can be pinned too. None of these development
pins controls the separately downloaded VirtualHere server.

Tests use temporary files and mock services, not USB devices or root access;
they do not install or start VHP. Shortcut tests simulate a terminal and reject
unmocked input requests or process launches, so they cannot prompt or start Steam.
Test stdout/stderr is buffered and shown on failures. For hardware changes, test launch, client
connection, corner-hold exit, and forced launcher termination on the Deck;
confirm brightness and sleep return.
