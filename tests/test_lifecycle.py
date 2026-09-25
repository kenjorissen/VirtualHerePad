"""Exercise the actual shell runner with temporary paths and a fake USB server."""

import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LifecycleTests(unittest.TestCase):
    def test_launcher_sigkill_expires_lease_and_restores_brightness(self):
        self.exercise(kill_launcher=True)

    def test_service_term_restores_brightness(self):
        self.exercise(kill_launcher=False)

    def test_touch_request_stops_service_and_restores_brightness(self):
        self.exercise(kill_launcher=False, touch_exit=True)

    def exercise(self, kill_launcher, touch_exit=False):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            runtime = folder / "runtime"
            runtime.mkdir()
            brightness = folder / "brightness"
            brightness.write_text("73\n")
            brightness.chmod(0o640)
            server = folder / "server"
            # Ignore TERM to verify bounded shutdown and escalation too.
            server.write_text(
                "#!/usr/bin/env python3\nimport signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nwhile True: time.sleep(1)\n"
            )
            server.chmod(0o755)
            monitor = folder / "touch-stop.py"
            monitor.write_text("import time\nwhile True: time.sleep(60)\n")
            helper = folder / "helper"
            source = (ROOT / "vhp-root").read_text()
            source = source.replace("[[ $EUID == 0 && $# == 1 ]]", "[[ $# == 1 ]]")
            source = source.replace("/run/vhp", str(runtime))
            source = source.replace("/sys/class/backlight/amdgpu_bl0/brightness", str(brightness))
            source = source.replace("/home/.vhp/bin/vhusbdx86_64", str(server))
            source = source.replace("/home/.vhp/bin/touch-stop.py", str(monitor))
            source = source.replace('exec /usr/bin/systemctl "$1" vhp.service', "exit 0")
            helper.write_text(source)
            helper.chmod(0o755)
            # sudo and systemctl mocks let the unmodified launcher loop run unprivileged.
            sudo = folder / "sudo"
            sudo.write_text('#!/bin/bash\nshift\nexec "$@"\n')
            sudo.chmod(0o755)
            systemctl = folder / "systemctl"
            systemctl.write_text("#!/bin/bash\nexit 0\n")
            systemctl.chmod(0o755)
            launcher = folder / "launcher"
            launcher.write_text(
                (ROOT / "vhp.sh")
                .read_text()
                .replace("/home/.vhp/bin/vhp-root", str(helper))
                .replace("/usr/bin/systemctl", str(systemctl))
            )
            launcher.chmod(0o755)
            service = subprocess.Popen(
                [str(helper), "run"],
                start_new_session=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            client = None
            try:
                # Bounded readiness check for this local test fixture.
                deadline = time.monotonic() + 3
                while brightness.read_text().strip() != "0":
                    if time.monotonic() > deadline or service.poll() is not None:
                        self.fail("Mock service failed to dim brightness")
                    time.sleep(0.02)
                if kill_launcher:
                    env = dict(os.environ, PATH=f"{folder}:" + os.environ["PATH"])
                    client = subprocess.Popen(
                        [str(launcher)],
                        env=env,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    time.sleep(1.2)
                    self.assertIsNone(client.poll())
                    client.kill()  # No EXIT trap can run.
                    client.wait(timeout=2)
                elif touch_exit:
                    (runtime / "touch-stop").touch()
                else:
                    service.send_signal(signal.SIGTERM)
                output, _ = service.communicate(timeout=17)
                self.assertEqual(service.returncode, 0, output)
                if kill_launcher:
                    self.assertIn("heartbeat expired", output)
                if touch_exit:
                    self.assertIn("Touchscreen requested shutdown.", output)
                self.assertIn("Saved backlight brightness=73", output)
                self.assertIn("Restored backlight brightness=73", output)
                self.assertEqual(brightness.read_text().strip(), "73")
                self.assertEqual(brightness.stat().st_mode & 0o777, 0o640)
            finally:
                for process in (client, service):
                    if process is not None:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait(timeout=3)
                if service.stdout:
                    service.stdout.close()


if __name__ == "__main__":
    unittest.main()
