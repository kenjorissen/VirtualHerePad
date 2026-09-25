"""Test install layout/migration without sudo or real system paths."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SettingsTests(unittest.TestCase):
    def run_setup(self, folder):
        source = (ROOT / "setup.sh").read_text()
        block = source.split("sudo bash <<'VHP_DATA_SETUP'\n", 1)[1].split("\nVHP_DATA_SETUP", 1)[0]
        block = block.replace("/home/.vhp", str(folder / "base"))
        block = block.replace("/var/lib/vhp", str(folder / "old"))
        block = block.replace(
            "$(stat -c '%u' \"$directory\") != 0",
            f"$(stat -c '%u' \"$directory\") != {os.getuid()}",
        )
        block = block.replace("-o root -g root ", "")
        block = block.replace("chown root:root", f"chown {os.getuid()}:{os.getgid()}")
        return subprocess.run(["bash", "-c", block], capture_output=True, text=True, timeout=3)

    def test_fresh_setup(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            result = self.run_setup(folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name, mode in [("base", 0o755), ("base/bin", 0o755), ("base/data", 0o700)]:
                self.assertEqual((folder / name).stat().st_mode & 0o777, mode)
            self.assertFalse((folder / "base/data/config.ini").exists())
            preference = folder / "base/data/brightness-percent"
            self.assertEqual(preference.read_text(), "5\n")
            self.assertEqual(preference.stat().st_mode & 0o777, 0o600)

    def test_reinstall_preserves_brightness_preference(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            self.assertEqual(self.run_setup(folder).returncode, 0)
            preference = folder / "base/data/brightness-percent"
            for content in ("0\n", "33\n", "invalid-but-user-owned-content\n"):
                preference.write_text(content)
                result = self.run_setup(folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(preference.read_text(), content)

    def test_copy_preserves_original_and_never_overwrites(self):
        for source in ("old", "base"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                (folder / source).mkdir(mode=0o700)
                old = folder / source / "config.ini"
                old.write_text("test fixture settings")
                result = self.run_setup(folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                new = folder / "base/data/config.ini"
                self.assertEqual(new.read_text(), old.read_text())
                self.assertEqual(new.stat().st_mode & 0o777, 0o600)
                new.write_text("newer settings")
                result = self.run_setup(folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(new.read_text(), "newer settings")
                self.assertEqual(old.read_text(), "test fixture settings")
                if source == "base":
                    self.assertEqual(old.stat().st_mode & 0o777, 0o600)

    def test_rejects_unsafe_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "base").mkdir()
            (folder / "base").chmod(0o777)
            self.assertNotEqual(self.run_setup(folder).returncode, 0)

    def test_rejects_symlinks(self):
        for name in (
            "base",
            "base/bin",
            "base/data",
            "base/config.ini",
            "base/data/config.ini",
            "base/data/brightness-percent",
        ):
            with self.subTest(path=name), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                link = folder / name
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(folder / "missing")
                self.assertNotEqual(self.run_setup(folder).returncode, 0)
                self.assertFalse((folder / "missing").exists())

    def test_no_protected_usr_install_paths(self):
        for name in ("setup.sh", "uninstall.sh", "vhp-root", "vhp.sh", "vhp.service", "doctor.sh"):
            self.assertNotIn("/usr/local", (ROOT / name).read_text())
        self.assertIn("RequiresMountsFor=/home/.vhp", (ROOT / "vhp.service").read_text())


if __name__ == "__main__":
    unittest.main()
