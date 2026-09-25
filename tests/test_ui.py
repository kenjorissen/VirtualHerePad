"""Integration tests for the Qt UI bridge against a real backend.

These exercise the full path a key press takes: touch -> bridge -> socket ->
backend -> HID report. They run unprivileged by injecting fake hardware into the
backend, and are skipped entirely when PySide6 is not installed.
"""

import os
import sys
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from PySide6.QtCore import QCoreApplication, QUrl, qInstallMessageHandler
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from test_backend import Harness

    import vhp_ui

    HAVE_QT = True
except ImportError as error:  # pragma: no cover - depends on the environment
    HAVE_QT = False
    IMPORT_ERROR = error

KEY_A = bytes([0, 0, 4, 0, 0, 0, 0, 0])
SHIFT_A = bytes([0b00000010, 0, 4, 0, 0, 0, 0, 0])


def pump(seconds, until=None):
    """Run the Qt event loop for a while, optionally stopping early."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if until is not None and until():
            return True
        time.sleep(0.01)
    return until() if until is not None else True


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class QtTestCase(unittest.TestCase):
    """Shared Qt application and bridge construction."""

    @classmethod
    def setUpClass(cls):
        cls.application = QGuiApplication.instance() or QGuiApplication([])

    def bridge_for(self, harness):
        bridge = vhp_ui.Bridge(harness.options.socket)
        # Close the socket even if an assertion fails part-way through.
        self.addCleanup(bridge.drop)
        return bridge


class UiBackendTests(QtTestCase):
    def test_bridge_connects_and_reports_backend_state(self):
        with Harness() as harness:
            bridge = self.bridge_for(harness)
            self.assertTrue(pump(3, lambda: bridge.connected), "bridge never connected")
            self.assertTrue(pump(3, lambda: bridge.shared), "bridge never saw shared state")
            self.assertEqual(bridge.percent, 1)
            self.assertEqual(bridge.layout, "us")

    def test_typing_through_the_ui_reaches_the_usb_keyboard(self):
        with Harness() as harness:
            bridge = self.bridge_for(harness)
            self.assertTrue(pump(3, lambda: bridge.shared))
            bridge.press(4)
            self.assertEqual(harness.gadget.reports(1), [KEY_A])
            bridge.release(4)
            self.assertEqual(harness.gadget.reports(1), [bytes(8)])

    def test_latched_shift_travels_with_the_next_character(self):
        with Harness() as harness:
            bridge = self.bridge_for(harness)
            self.assertTrue(pump(3, lambda: bridge.shared))
            bridge.press(225)
            bridge.release(225)
            self.assertTrue(bridge.shiftActive)
            # Tapping a modifier is a momentary press on the wire, and it must be
            # released again rather than left down on the remote machine.
            self.assertEqual(
                harness.gadget.reports(2),
                [bytes([0b00000010, 0, 0, 0, 0, 0, 0, 0]), bytes(8)],
            )
            bridge.press(4)
            # Shift is re-applied for the next character, then cleared with it.
            reports = harness.gadget.reports(2)
            self.assertEqual(
                reports,
                [bytes([0b00000010, 0, 0, 0, 0, 0, 0, 0]), SHIFT_A],
            )
            bridge.release(4)
            self.assertFalse(bridge.shiftActive)

    def test_ctrl_stays_latched_across_several_keys(self):
        with Harness() as harness:
            bridge = self.bridge_for(harness)
            self.assertTrue(pump(3, lambda: bridge.shared))
            bridge.press(224)
            bridge.release(224)
            harness.gadget.reports(1)  # the momentary Ctrl press
            bridge.press(6)
            self.assertEqual(harness.gadget.reports(1)[0][0], 0b00000001)
            bridge.release(6)
            bridge.press(25)
            self.assertEqual(harness.gadget.reports(1)[0][0], 0b00000001)

    def test_layout_switch_changes_labels_and_reaches_the_backend(self):
        with Harness() as harness:
            bridge = self.bridge_for(harness)
            self.assertTrue(pump(3, lambda: bridge.shared))
            bridge.setLayout("de")
            self.assertEqual(bridge.layoutName, "Deutsch")
            labels = [key["label"] for row in bridge.rows for key in row]
            self.assertIn("ö", labels)
            self.assertIn("z", labels)
            self.assertTrue(pump(3, lambda: harness.backend.layout == "de"))

    def test_clear_releases_held_keys_and_resets_modifiers(self):
        with Harness() as harness:
            bridge = self.bridge_for(harness)
            self.assertTrue(pump(3, lambda: bridge.shared))
            bridge.press(225)
            harness.gadget.reports(1)
            bridge.clear()
            self.assertFalse(bridge.shiftActive)
            self.assertEqual(harness.gadget.reports(1), [bytes(8)])

    def test_stopping_the_backend_is_reported_and_the_ui_recovers(self):
        with Harness() as harness:
            bridge = self.bridge_for(harness)
            self.assertTrue(pump(3, lambda: bridge.shared))
            bridge.stop()
            harness.thread.join(timeout=3)
            self.assertFalse(harness.thread.is_alive())
            # The bridge must drop the connection rather than silently pretend.
            self.assertTrue(pump(3, lambda: not bridge.connected))
            self.assertFalse(bridge.shared)

    def test_layout_metadata_matches_the_protocol(self):
        with Harness() as harness:
            bridge = self.bridge_for(harness)
            names = [entry["id"] for entry in bridge.layoutNames]
            self.assertEqual(names, ["us", "uk", "de", "fr"])
            self.assertEqual(bridge.columns, 1000)

    def test_every_row_and_span_is_exposed_to_qml(self):
        with Harness() as harness:
            bridge = self.bridge_for(harness)
            rows = bridge.rows
            self.assertEqual(len(rows), 6)
            for row in rows:
                self.assertEqual(sum(key["span"] for key in row), bridge.columns)
                for key in row:
                    self.assertIn("code", key)
                    self.assertTrue(key["label"])


class QmlTests(QtTestCase):
    def test_qml_loads_without_errors_or_warnings(self):
        messages = []

        def handler(mode, context, message):
            del mode, context
            messages.append(message)

        previous = qInstallMessageHandler(handler)
        try:
            with Harness() as harness:
                bridge = self.bridge_for(harness)
                engine = QQmlApplicationEngine()
                engine.setInitialProperties({"vhp": bridge})
                engine.load(QUrl.fromLocalFile(str(ROOT / "vhp_ui.qml")))
                self.assertTrue(engine.rootObjects(), "QML produced no root object")
                pump(0.4)
                roots = engine.rootObjects()
        finally:
            qInstallMessageHandler(previous)
        problems = [
            message
            for message in messages
            if "TypeError" in message
            or "ReferenceError" in message
            or "is not defined" in message
            or "Unable to assign" in message
        ]
        self.assertEqual(problems, [])
        self.assertTrue(roots)

    def test_qml_declares_the_bridge_as_a_required_property(self):
        # Context properties are cleared before the object tree is destroyed,
        # which makes every binding re-evaluate against a null at shutdown.
        source = (ROOT / "vhp_ui.qml").read_text()
        self.assertIn("required property var vhp", source)
        self.assertNotIn("setContextProperty", (ROOT / "vhp_ui.py").read_text())


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class PlatformTests(unittest.TestCase):
    def test_wayland_is_preferred_when_nothing_was_requested(self):
        environment = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}
        self.assertTrue(vhp_ui.prefer_wayland(environment))
        self.assertEqual(environment["QT_QPA_PLATFORM"], "wayland")

    def test_an_explicit_platform_always_wins(self):
        for platform in ("offscreen", "xcb", "wayland", "minimal"):
            with self.subTest(platform=platform):
                environment = {"WAYLAND_DISPLAY": "wayland-0", "QT_QPA_PLATFORM": platform}
                self.assertFalse(vhp_ui.prefer_wayland(environment))
                self.assertEqual(environment["QT_QPA_PLATFORM"], platform)

    def test_nothing_changes_without_a_wayland_session(self):
        for environment in ({}, {"DISPLAY": ":0"}, {"WAYLAND_DISPLAY": ""}):
            with self.subTest(environment=environment):
                before = dict(environment)
                self.assertFalse(vhp_ui.prefer_wayland(environment))
                self.assertEqual(environment, before)

    def test_wayland_is_chosen_before_qt_picks_a_backend(self):
        # Setting QT_QPA_PLATFORM after QGuiApplication exists has no effect.
        source = (ROOT / "vhp_ui.py").read_text()
        self.assertLess(source.index("prefer_wayland()"), source.index("QGuiApplication(sys.argv"))


if __name__ == "__main__":
    unittest.main()
