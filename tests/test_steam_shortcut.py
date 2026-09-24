import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('shortcut', Path(__file__).resolve().parents[1] / 'steam-shortcut.py')
shortcut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shortcut)


def entries(data):
    return shortcut.decode(data)[0][2]


def fields(entry):
    return {key: value for _, key, value in entry[2]}


class ShortcutTests(unittest.TestCase):
    def test_new_and_idempotent(self):
        path = Path('/home/deck/my vhp')
        data = shortcut.update(b'', path)
        self.assertEqual(shortcut.update(data, path), data)
        self.assertEqual(len(entries(data)), 1)
        values = fields(entries(data)[0])
        self.assertEqual(values[b'exe'], b'"/usr/bin/env"')
        self.assertEqual(values[b'LaunchOptions'], b'-u LD_PRELOAD konsole --fullscreen -e "/home/deck/my vhp/vhp.sh"')
        self.assertEqual(values[b'AllowOverlay'], struct.pack('<I', 1))

    def test_adopts_manual_entry_and_preserves_others(self):
        other = (0, b'0', [shortcut.text('appname', 'Other'),
                          (7, b'custom', b'12345678'), (3, b'float', b'abcd')])
        manual = (0, b'1', [shortcut.text('appname', 'env'),
                           shortcut.text('LaunchOptions', '-u LD_PRELOAD konsole --fullscreen -e /home/deck/vhp/vhp.sh'),
                           shortcut.number('appid', 123),
                           shortcut.text('icon', '/my/art.png'),
                           (0, b'tags', [shortcut.text('0', 'Controllers')])])
        data = shortcut.encode([(0, b'shortcuts', [other, manual])])
        updated = entries(shortcut.update(data, Path('/new/vhp')))
        self.assertEqual(len(updated), 2)
        self.assertEqual(updated[0], other)
        values = fields(updated[1])
        self.assertEqual(values[b'appid'], struct.pack('<I', 123))
        self.assertEqual(values[b'icon'], b'/my/art.png')
        self.assertEqual(values[b'tags'], manual[2][-1][2])

    def test_rejects_duplicates(self):
        data = shortcut.encode([(0, b'shortcuts', [
            (0, str(i).encode(), [shortcut.text('appname', 'VHP')]) for i in range(2)])])
        with self.assertRaises(ValueError):
            shortcut.update(data, Path('/vhp'))

    def test_rejects_malformed_data(self):
        for data in (b'\0shortcuts\0', b'\x05bad\0\x08', b'\x08junk', b'\x02x\0a', b'\x01unterminated'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                shortcut.decode(data)

    def test_rejects_unsafe_launch_path(self):
        with self.assertRaises(ValueError):
            shortcut.update(b'', Path('/home/deck/$HOME'))

    def test_backup_and_atomic_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'shortcuts.vdf'
            path.write_bytes(b'original')
            shortcut.save(path, b'new')
            self.assertEqual(path.read_bytes(), b'new')
            backups = list(path.parent.glob('shortcuts.vdf.bak-*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), b'original')
            self.assertFalse(list(path.parent.glob('.vhp-shortcuts-*')))

    def test_refuses_running_steam(self):
        with patch('sys.argv', ['steam-shortcut.py']), patch.object(shortcut.os, 'geteuid', return_value=1000), patch.object(shortcut, 'steam_running', return_value=True), patch.object(shortcut, 'save') as save:
            with self.assertRaises(SystemExit):
                shortcut.main()
            save.assert_not_called()

    def test_multiple_accounts_requires_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            userdata = home / '.local/share/Steam/userdata'
            for account in ('123', '456'):
                (userdata / account / 'config').mkdir(parents=True)
            with patch.object(shortcut.Path, 'home', return_value=home), patch.object(shortcut.os, 'geteuid', return_value=1000), patch.object(shortcut, 'steam_running', return_value=False):
                with patch('sys.argv', ['steam-shortcut.py']), self.assertRaises(SystemExit):
                    shortcut.main()
                self.assertFalse(list(userdata.glob('*/config/shortcuts.vdf')))
                with patch('sys.argv', ['steam-shortcut.py', '--account', '456']):
                    shortcut.main()
                self.assertTrue((userdata / '456/config/shortcuts.vdf').exists())
                self.assertFalse((userdata / '123/config/shortcuts.vdf').exists())


if __name__ == '__main__':
    unittest.main()
