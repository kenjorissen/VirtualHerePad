#!/usr/bin/env python3
"""Root-side backend for the VHP touch keyboard and brightness buttons.

Runs as root. Owns the USB gadget, the volume-key grab, and brightness. The Qt
UI is a normal user process and talks to this over a Unix socket; it can only
send a known operation name, an HID key code, and a boolean.

This is a standalone development entry point: it is started manually for now and
is not yet wired into the systemd unit.
"""

import argparse
import grp
import os
import select
import signal
import socket
import stat
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vhp_ipc  # noqa: E402
from vhp_hardware import Brightness, Gadget, VolumeBridge  # noqa: E402
from vhp_keyboard import KeyState  # noqa: E402

STATUS_INTERVAL = 2.0  # Only while a UI client is connected.


class Hardware:
    """Bundle of privileged adapters, injectable so the backend is testable."""

    def __init__(self, gadget, brightness, volume):
        self.gadget = gadget
        self.brightness = brightness
        self.volume = volume


def default_hardware(options):
    gadget = Gadget()
    try:
        brightness = Brightness()
        volume = None if options.no_volume_keys else VolumeBridge(brightness)
    except Exception:
        gadget.close()
        raise
    return Hardware(gadget, brightness, volume)


class Backend:
    def __init__(self, options, hardware=None):
        self.options = options
        self.hardware = hardware if hardware is not None else default_hardware(options)
        self.gadget = self.hardware.gadget
        self.brightness = self.hardware.brightness
        self.volume = self.hardware.volume
        self.keys = KeyState()
        self.layout = options.layout
        self.stopping = False
        self.shared = False
        self.connection = None
        self.next_status = 0.0
        self.quiet = bool(getattr(options, "quiet", False))

    def notice(self, message):
        """Print unless the caller asked for silence (tests, embedded use)."""
        if not self.quiet:
            print(message, flush=True)

    # -- reporting ---------------------------------------------------------
    def status(self):
        return {
            "op": "status",
            "shared": self.shared,
            "stopping": Path("/run/vhp/stopping").exists(),
            "percent": self.brightness.percent,
            "layout": self.layout,
            "keys": len(self.keys.keys),
        }

    def send(self, message):
        if self.connection is None:
            return
        try:
            self.connection.sendall(vhp_ipc.encode(message))
        except OSError:
            self.disconnect()

    # -- protocol ----------------------------------------------------------
    def handle(self, message):
        op = message["op"]
        if op == "ping":
            self.send({"op": "pong"})
        elif op == "status":
            self.send(self.status())
        elif op == "key":
            self.press(message["code"], message["down"])
        elif op == "clear":
            if self.gadget.fd is not None:
                os.write(self.gadget.fd, self.keys.clear())
        elif op == "layout":
            self.layout = message["layout"]
            self.send(self.status())
        elif op == "stop":
            self.stopping = True

    def press(self, code, down):
        # Typing is only meaningful once the PC has bound the keyboard, and it
        # must never be possible for a report to land on the Deck's own desktop.
        if self.gadget.fd is None or not self.shared:
            return
        try:
            report = self.keys.update(code, down)
        except ValueError:
            return  # Ignore, never crash: a bad press must not drop the session.
        try:
            os.write(self.gadget.fd, report)
        except OSError:
            self.disconnect()

    # -- connection --------------------------------------------------------
    def accept(self, server):
        connection, _ = server.accept()
        credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        pid, uid, gid = (
            int.from_bytes(credentials[index : index + 4], "little") for index in (0, 4, 8)
        )
        del pid, gid
        if uid != self.options.owner_uid:
            # Never explain to a rejected peer, and never log its identity.
            connection.close()
            return None
        connection.setblocking(False)
        self.connection = connection
        self.shared = self.gadget.shared()
        self.send(self.status())
        # Re-arm the periodic report so a fresh client is not answered twice.
        self.next_status = time.monotonic() + STATUS_INTERVAL
        return connection

    def disconnect(self):
        if self.connection is not None:
            try:
                self.connection.close()
            except OSError:
                pass
            self.connection = None
        # Release on the wire as well as locally: the PC must not keep a key down.
        if self.gadget.fd is not None:
            try:
                os.write(self.gadget.fd, self.keys.clear())
            except OSError:
                pass

    # -- main loop ---------------------------------------------------------
    def run(self):
        server = self.bind()
        reader = vhp_ipc.Reader()
        try:
            while not self.stopping:
                watches = [server]
                if self.connection is not None:
                    watches.append(self.connection)
                ready, _, _ = select.select(watches, [], [], 0.5)
                for item in ready:
                    if item is server:
                        if self.connection is None:
                            self.accept(server)
                        else:
                            item.accept()[0].close()  # One UI at a time.
                    else:
                        self.read(reader)
                if self.connection is not None and time.monotonic() >= self.next_status:
                    self.next_status = time.monotonic() + STATUS_INTERVAL
                    shared = self.gadget.shared()
                    if shared != self.shared:
                        self.shared = shared
                        if self.gadget.fd is not None and not shared:
                            os.write(self.gadget.fd, self.keys.clear())
                    self.send(self.status())
        finally:
            self.close(server)

    def read(self, reader):
        try:
            data = self.connection.recv(4096)
        except OSError:
            self.disconnect()
            return
        if not data:
            self.disconnect()
            return
        try:
            lines = reader.feed(data)
            for line in lines:
                self.handle(vhp_ipc.decode(line))
        except vhp_ipc.ProtocolError:
            # A malformed or oversized frame is a hard error: drop that client.
            self.disconnect()

    def bind(self):
        path = self.options.socket
        if path.exists():
            if not stat.S_ISSOCK(path.lstat().st_mode):
                raise SystemExit(f"Refusing to replace non-socket: {path}")
            path.unlink()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(str(path))
            os.chown(path, self.options.owner_uid, self.options.owner_gid)
            os.chmod(path, 0o600)
            server.listen(1)
            server.setblocking(False)
        except OSError:
            # Never leave a stale socket that a later run would have to trust.
            server.close()
            try:
                path.unlink()
            except OSError:
                pass
            raise
        # Announced only once the socket is actually accepting connections.
        self.notice(f"backend ready: {path} (owner uid {self.options.owner_uid})")
        return server

    def close(self, server):
        self.disconnect()
        server.close()
        try:
            self.options.socket.unlink()
        except OSError:
            pass
        self.brightness.save()
        if self.volume is not None:
            self.volume.close()
        self.gadget.close()


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description="VHP root backend (development entry point)")
    parser.add_argument("--socket", type=Path, default=Path("/run/vhp/gui.sock"))
    parser.add_argument("--owner", required=True, help="user allowed to connect")
    parser.add_argument("--group", help="group to own the socket (default: user's primary group)")
    parser.add_argument("--layout", default="us", choices=vhp_ipc.LAYOUTS)
    parser.add_argument(
        "--no-volume-keys", action="store_true", help="do not take over the Deck volume buttons"
    )
    parser.add_argument(
        "--allow-unverified-gadget",
        action="store_true",
        help="skip the root/hardware safety checks (test environments only)",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress the ready notice")
    options = parser.parse_args(argv)
    if os.geteuid() != 0 and not options.allow_unverified_gadget:
        parser.error("must run as root")
    import pwd

    try:
        record = pwd.getpwnam(options.owner)
    except KeyError:
        parser.error(f"no such user: {options.owner}")
    options.owner_uid = record.pw_uid
    options.owner_gid = record.pw_gid
    if options.group:
        try:
            options.owner_gid = grp.getgrnam(options.group).gr_gid
        except KeyError:
            parser.error(f"no such group: {options.group}")
    return options


def main(argv=None):
    options = parse_arguments(sys.argv[1:] if argv is None else argv)
    # Constructors clean up after themselves if any hardware step fails.
    backend = Backend(options)

    def stop(signum, frame):
        del signum, frame
        backend.stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    backend.run()  # run() releases keys, brightness, volume grab, and the gadget.
    return 0


if __name__ == "__main__":
    sys.exit(main())
