from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UninstallTests(unittest.TestCase):
    def run_uninstall(self, args=(), stop_failure=False):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            log = folder / 'commands'
            sudo = folder / 'sudo'
            sudo.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$COMMAND_LOG"\n'
                            'if [[ ${FAIL_STOP:-} == 1 && "$*" == "systemctl stop vhp.service" ]]; then exit 1; fi\n')
            sudo.chmod(0o755)
            systemctl = folder / 'systemctl'
            systemctl.write_text('#!/bin/bash\necho loaded\n')
            systemctl.chmod(0o755)
            script = folder / 'uninstall.sh'
            script.write_text((ROOT / 'uninstall.sh').read_text().replace(
                'export PATH=/usr/sbin:/usr/bin:/sbin:/bin', '# use mock commands'))
            env = dict(os.environ, PATH=f'{folder}:' + os.environ['PATH'],
                       COMMAND_LOG=str(log), FAIL_STOP='1' if stop_failure else '0')
            result = subprocess.run(['bash', str(script), *args], env=env,
                                    capture_output=True, text=True, timeout=3)
            return result, log.read_text() if log.exists() else ''

    def test_preserves_settings_by_default(self):
        result, commands = self.run_uninstall()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('/var/lib/vhp', commands)
        self.assertNotIn('rm -rf -- /home/.vhp /', commands)
        self.assertNotIn('/home/.vhp/data', commands)
        self.assertIn('rm -rf -- /home/.vhp/bin /run/vhp', commands)
        self.assertNotIn('/usr/local', commands)
        self.assertLess(commands.index('systemctl stop'), commands.index('rm -f'))
        self.assertIn('/etc/sudoers.d/vhp', commands)

    def test_purge_is_explicit(self):
        result, commands = self.run_uninstall(['--purge-settings'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('rm -rf -- /home/.vhp /var/lib/vhp', commands)

    def test_stop_failure_prevents_removal(self):
        result, commands = self.run_uninstall(stop_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('rm ', commands)

    def test_unknown_option_changes_nothing(self):
        result, commands = self.run_uninstall(['--purge'])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, '')


if __name__ == '__main__':
    unittest.main()
