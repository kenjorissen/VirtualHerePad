import fcntl
import os
import pty
import resource
import select
import signal
import struct
import subprocess
import tempfile
import termios
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def functions(name, marker):
    return (
        (ROOT / name).read_text().split(f"# BEGIN {marker}\n", 1)[1].split(f"# END {marker}", 1)[0]
    )


class BrightnessTests(unittest.TestCase):
    def apply(self, preference, maximum="599000", original="400000"):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            level = folder / "brightness"
            level.write_text(original + "\n")
            (folder / "max_brightness").write_text(maximum + "\n")
            setting = folder / "percent"
            if preference is not None:
                setting.write_text(preference)
            env = dict(os.environ, BRIGHTNESS_FILE=str(level), BRIGHTNESS_PERCENT_FILE=str(setting))
            result = subprocess.run(
                [
                    "bash",
                    "-euc",
                    functions("vhp-root", "BRIGHTNESS_FUNCTIONS")
                    + '\nbrightness=""; apply_brightness; printf "saved=%s\\n" "$brightness"',
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=3,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return level.read_text().strip(), result

    def test_percentage_conversion_and_original_preservation(self):
        for percent, expected in (
            ("0", "0"),
            ("5", "29950"),
            ("25", "149750"),
            ("100", "599000"),
            ("005", "29950"),
        ):
            with self.subTest(percent=percent):
                actual, result = self.apply(percent + "\n")
                self.assertEqual(actual, expected)
                self.assertIn("saved=400000", result.stdout)

    def test_rounds_to_nearest_hardware_step(self):
        actual, _ = self.apply("5", maximum="255", original="200")
        self.assertEqual(actual, "13")

    def test_missing_invalid_and_injection_values_fall_back(self):
        for value in (None, "", "101", "-1", "5%", "5.5", "5\n6", "$(exit 77)", "9999999999999999"):
            with self.subTest(value=value):
                actual, result = self.apply(value)
                self.assertEqual(actual, "29950")
                self.assertIn("using 5%", result.stderr)

    def read_preference(self, path):
        def limit_memory():
            resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))

        source = functions("vhp-root", "BRIGHTNESS_FUNCTIONS") + "\nread_brightness_percent"
        return subprocess.run(
            ["bash", "-euc", source],
            env=dict(os.environ, BRIGHTNESS_PERCENT_FILE=str(path)),
            capture_output=True,
            text=True,
            timeout=3,
            preexec_fn=limit_memory,
        )

    def test_one_gibibyte_file_is_rejected_under_small_memory_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "percent"
            with path.open("wb") as stream:
                stream.write(b"5\n")
                stream.truncate(1024**3)  # Sparse: do not allocate a gigabyte of data.
            result = self.read_preference(path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "5\n")
            self.assertIn("missing/invalid", result.stderr)

    def test_binary_junk_and_extra_lines_are_rejected_but_crlf_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "percent"
            for data, expected in ((b"25\x00", "5\n"), (b"25\n\n", "5\n"), (b"25\r\n", "25\n")):
                with self.subTest(data=data):
                    path.write_bytes(data)
                    result = self.read_preference(path)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, expected)

    def test_fifo_directory_and_symlink_are_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            target = folder / "valid"
            target.write_text("25\n")
            link = folder / "link"
            link.symlink_to(target)
            fifo = folder / "fifo"
            os.mkfifo(fifo)
            for path in (folder, link, fifo):
                with self.subTest(path=path):
                    result = self.read_preference(path)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "5\n")
                    self.assertIn("missing/invalid", result.stderr)

    def test_bad_maximum_or_original_leaves_backlight_unchanged(self):
        for maximum, original in (("0", "400000"), ("invalid", "400000"), ("599000", "invalid")):
            actual, result = self.apply("5", maximum=maximum, original=original)
            self.assertEqual(actual, original)
            self.assertIn("leaving backlight unchanged", result.stderr)


class DashboardTests(unittest.TestCase):
    def run_dashboard(self, supplies, commands):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name, values in supplies.items():
                supply = folder / name
                supply.mkdir()
                for key, value in values.items():
                    (supply / key).write_text(value + "\n")
            env = dict(os.environ, POWER_SUPPLY_ROOT=str(folder))
            source = functions("vhp.sh", "DASHBOARD_FUNCTIONS")
            init = "\nui_active=false; ui_dirty=true; last_display=''; rows=24; cols=80; sample_battery\n"
            result = subprocess.run(
                ["bash", "-euc", source + init + commands],
                env=env,
                capture_output=True,
                text=True,
                timeout=3,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

    def test_battery_percentage_and_status(self):
        for status in ("Charging", "Discharging", "Full", "Not charging"):
            text = self.run_dashboard(
                {"BAT1": {"type": "Battery", "capacity": "87", "status": status}}, "paint_dashboard"
            )
            self.assertIn(f"87% ({status})", text)
            self.assertNotIn("\033", text)

    def test_peripherals_are_ignored_and_missing_data_is_safe(self):
        supplies = {
            "mouse": {"type": "Battery", "scope": "Device", "capacity": "99"},
            "bad": {"type": "Battery", "capacity": "$(exit 77)"},
            "charger": {"type": "Mains"},
        }
        text = self.run_dashboard(supplies, "paint_dashboard")
        self.assertIn("--% (Unavailable)", text)

    def test_does_not_redraw_unchanged_values(self):
        supplies = {"BAT0": {"type": "Battery", "capacity": "50", "status": "Charging"}}
        text = self.run_dashboard(supplies, "paint_dashboard; sample_battery; paint_dashboard")
        self.assertEqual(text.count("Server running"), 1)

    def test_full_dashboard_and_compact_terminal(self):
        supplies = {"BAT0": {"type": "Battery", "capacity": "100", "status": "Full"}}
        text = self.run_dashboard(supplies, "ui_active=true; paint_dashboard")
        self.assertIn("SERVER RUNNING", text)
        self.assertEqual(text.count("HOLD 2s"), 4)
        self.assertIn("#", text)
        text = self.run_dashboard(supplies, "ui_active=true; rows=10; cols=40; paint_dashboard")
        self.assertIn("Battery: 100% (Full)", text)

    def test_ctrl_c_restores_terminal_and_stops_service(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            helper = folder / "helper"
            helper.write_text('#!/bin/bash\nprintf "%s\\n" "$1" >> "$CALLS"\n')
            sudo = folder / "sudo"
            sudo.write_text('#!/bin/bash\nshift\nexec "$@"\n')
            systemctl = folder / "systemctl"
            systemctl.write_text("#!/bin/bash\n[[ $1 == is-active ]]\n")
            for command in (helper, sudo, systemctl):
                command.chmod(0o755)
            launcher = folder / "launcher"
            launcher.write_text(
                (ROOT / "vhp.sh")
                .read_text()
                .replace("/home/.vhp/bin/vhp-root", str(helper))
                .replace("/usr/bin/systemctl", str(systemctl))
                .replace("/sys/class/power_supply", str(folder / "no-battery"))
            )
            launcher.chmod(0o755)
            calls = folder / "calls"
            env = dict(
                os.environ,
                PATH=str(folder) + ":" + os.environ["PATH"],
                TERM="xterm-256color",
                CALLS=str(calls),
            )
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
            process = subprocess.Popen(
                [str(launcher)],
                env=env,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                start_new_session=True,
            )
            os.close(slave)
            output = b""
            try:
                deadline = time.monotonic() + 3
                while b"SERVER RUNNING" not in output:
                    self.assertLess(time.monotonic(), deadline, output.decode(errors="replace"))
                    if select.select([master], [], [], 0.1)[0]:
                        output += os.read(master, 65536)
                process.send_signal(signal.SIGINT)
                process.wait(timeout=3)
                while select.select([master], [], [], 0.1)[0]:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output += chunk
                self.assertEqual(process.returncode, 0, output.decode(errors="replace"))
                self.assertIn(b"\x1b[?1049h", output)
                self.assertIn(b"\x1b[?25h\x1b[?1049l", output)
                self.assertEqual(calls.read_text().splitlines()[-1], "stop")
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)
                os.close(master)

    def test_resize_forces_redraw(self):
        text = self.run_dashboard({}, "paint_dashboard; cols=100; ui_dirty=true; paint_dashboard")
        self.assertEqual(text.count("Server running"), 2)


if __name__ == "__main__":
    unittest.main()
