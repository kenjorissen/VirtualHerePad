import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ("vhp.sh", "doctor.sh", "uninstall.sh", "steam-shortcut.py")


class UserInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.checkout = self.root / "source checkout"
        self.checkout.mkdir()
        self.home = self.root / "user home"
        self.home.mkdir()
        self.installed = self.home / ".local/share/VirtualHerePad"
        self.env = dict(os.environ, HOME=str(self.home), USER_ROOT=str(self.installed))
        for name in TOOLS:
            shutil.copy2(ROOT / name, self.checkout / name)

    def install(self):
        source = (ROOT / "setup.sh").read_text()
        block = source.split("# BEGIN USER_INSTALL\n", 1)[1].split("# END USER_INSTALL", 1)[0]
        result = subprocess.run(
            ["bash", "-ec", block],
            cwd=self.checkout,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=3,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_copied_tools_survive_checkout_removal_and_helper_preflight_runs(self):
        self.install()
        for name in TOOLS:
            self.assertEqual(
                (self.installed / name).read_bytes(), (self.checkout / name).read_bytes()
            )
        self.assertTrue(os.access(self.installed / "vhp.sh", os.X_OK))
        self.assertTrue(os.access(self.installed / "uninstall.sh", os.X_OK))
        shutil.rmtree(self.checkout)
        (self.home / ".local/share/Steam/userdata/123").mkdir(parents=True)
        result = subprocess.run(
            ["python3", str(self.installed / "steam-shortcut.py"), "--check"],
            cwd=self.root,
            env=self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=3,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Steam account ready: 123", result.stdout)

    def test_installed_launcher_works_without_checkout(self):
        mocks = self.root / "mock commands"
        mocks.mkdir()
        helper = mocks / "helper"
        helper.write_text('#!/bin/bash\nprintf "%s\\n" "$1" >> "$CALLS"\n')
        helper.chmod(0o755)
        sudo = mocks / "sudo"
        sudo.write_text('#!/bin/bash\nshift\nexec "$@"\n')
        sudo.chmod(0o755)
        systemctl = mocks / "systemctl"
        systemctl.write_text("#!/bin/bash\nexit 1\n")  # Mock an already stopped service.
        systemctl.chmod(0o755)
        launcher = self.checkout / "vhp.sh"
        launcher.write_text(
            launcher.read_text()
            .replace("/home/.vhp/bin/vhp-root", shlex.quote(str(helper)))
            .replace("/usr/bin/systemctl", shlex.quote(str(systemctl)))
        )
        self.install()
        shutil.rmtree(self.checkout)
        calls = self.root / "calls"
        env = dict(self.env, PATH=str(mocks) + ":" + os.environ["PATH"], CALLS=str(calls))
        result = subprocess.run(
            [str(self.installed / "vhp.sh")],
            cwd=self.root,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=3,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls.read_text().splitlines(), ["start", "stop"])

    def test_installed_uninstaller_works_without_checkout_and_removes_itself(self):
        mocks = self.root / "mocks"
        mocks.mkdir()
        for name, content in (
            ("sudo", "#!/bin/bash\nexit 0\n"),
            ("systemctl", "#!/bin/bash\necho loaded\n"),
        ):
            command = mocks / name
            command.write_text(content)
            command.chmod(0o755)
        uninstaller = self.checkout / "uninstall.sh"
        uninstaller.write_text(
            uninstaller.read_text().replace(
                "export PATH=/usr/sbin:/usr/bin:/sbin:/bin", "# use test mocks"
            )
        )
        self.install()
        shutil.rmtree(self.checkout)
        result = subprocess.run(
            [str(self.installed / "uninstall.sh")],
            cwd=self.root,
            env=dict(self.env, PATH=str(mocks) + ":" + os.environ["PATH"]),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=3,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Uninstalled.", result.stdout)
        self.assertFalse(self.installed.exists())

    def test_reinstall_updates_user_tools_without_removing_other_files(self):
        self.install()
        extra = self.installed / "personal-note.txt"
        extra.write_text("keep")
        (self.installed / "vhp.sh").write_text("outdated launcher")
        self.install()
        self.assertEqual(
            (self.installed / "vhp.sh").read_bytes(), (self.checkout / "vhp.sh").read_bytes()
        )
        self.assertEqual(extra.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
