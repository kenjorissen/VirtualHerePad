import importlib.util
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "touch_stop", Path(__file__).resolve().parents[1] / "src/touch-stop.py"
)
touch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(touch)


def make_hold(slots=None):
    return touch.CornerHold(
        (100, 1100),
        (200, 2200),
        slots or {0: {"id": -1, "x": 100, "y": 200}, 1: {"id": -1, "x": 100, "y": 200}},
    )


def make_device():
    device = touch.Touchscreen.__new__(touch.Touchscreen)
    device.hold = make_hold()
    device.slot = 0
    device.dropped = False
    device.pending = False
    return device


class GestureTests(unittest.TestCase):
    def test_all_corners_with_nonzero_coordinate_minimum(self):
        for x, y in ((100, 200), (1100, 200), (100, 2200), (1100, 2200)):
            with self.subTest(x=x, y=y):
                hold = make_hold()
                hold.slots[0].update(id=5, x=x, y=y)
                hold.frame(10)
                self.assertFalse(hold.expired(11.99))
                self.assertTrue(hold.expired(12))

    def test_center_or_edge_is_not_a_corner(self):
        for x, y in ((600, 1200), (100, 1200), (600, 200), (0, 0)):
            hold = make_hold()
            hold.slots[0].update(id=5, x=x, y=y)
            hold.frame(0)
            self.assertFalse(hold.expired(5))

    def test_release_cancels(self):
        hold = make_hold()
        hold.slots[0]["id"] = 5
        hold.frame(0)
        hold.slots[0]["id"] = -1
        hold.frame(1.9)
        self.assertFalse(hold.expired(3))

    def test_motion_cancels_and_reentry_restarts_timer(self):
        hold = make_hold()
        hold.slots[0]["id"] = 5
        hold.frame(0)
        hold.slots[0]["x"] = 600
        hold.frame(1)
        self.assertFalse(hold.expired(5))
        hold.slots[0]["x"] = 100
        hold.frame(6)
        self.assertFalse(hold.expired(7.9))
        self.assertTrue(hold.expired(8))

    def test_new_contact_or_different_corner_restarts_timer(self):
        hold = make_hold()
        hold.slots[0]["id"] = 5
        hold.frame(0)
        hold.slots[0]["id"] = 6
        hold.frame(1)
        self.assertFalse(hold.expired(2))
        hold.slots[0].update(x=1100, y=2200)
        hold.frame(2)
        self.assertFalse(hold.expired(3))
        self.assertTrue(hold.expired(4))

    def test_multiple_fingers_require_full_release(self):
        hold = make_hold()
        hold.slots[0]["id"] = 5
        hold.frame(0)
        hold.slots[1]["id"] = 6
        hold.frame(1)
        hold.slots[1]["id"] = -1
        hold.frame(2)
        self.assertFalse(hold.expired(10))
        hold.slots[0]["id"] = -1
        hold.frame(11)
        hold.slots[0]["id"] = 7
        hold.frame(12)
        self.assertTrue(hold.expired(14))

    def test_preexisting_touch_must_lift(self):
        hold = make_hold({0: {"id": 7, "x": 100, "y": 200}})
        hold.frame(0)
        self.assertFalse(hold.expired(5))
        hold.slots[0]["id"] = -1
        hold.frame(6)
        hold.slots[0]["id"] = 8
        hold.frame(7)
        self.assertTrue(hold.expired(9))

    def test_idle_monitor_has_no_timer(self):
        device = make_device()
        self.assertIsNone(touch.wait_timeout([device], 0, 100))
        device.hold.slots[0]["id"] = 5
        device.hold.frame(100)
        self.assertEqual(touch.wait_timeout([device], 0, 100.5), 1.5)
        self.assertEqual(touch.wait_timeout([], 110, 100), 10)

    def test_frames_and_signed_release(self):
        device = make_device()
        encoded = touch.EVENT.pack(0, 0, touch.EV_ABS, touch.ABS_MT_TRACKING_ID, 5)
        _, _, kind, code, value = touch.EVENT.unpack(encoded)
        device.feed(kind, code, value, 0)
        self.assertIsNone(touch.wait_timeout([device], 0, 0))
        device.feed(touch.EV_SYN, touch.SYN_REPORT, 0, 0)
        self.assertEqual(touch.wait_timeout([device], 0, 0), 2)
        encoded = touch.EVENT.pack(0, 0, touch.EV_ABS, touch.ABS_MT_TRACKING_ID, -1)
        _, _, kind, code, value = touch.EVENT.unpack(encoded)
        device.feed(kind, code, value, 1)
        device.feed(touch.EV_SYN, touch.SYN_REPORT, 0, 1)
        self.assertFalse(device.hold.expired(5))

    def test_dropped_events_cancel_and_resync(self):
        device = make_device()
        device.hold.slots[0]["id"] = 5
        device.hold.frame(0)
        device.feed(touch.EV_SYN, touch.SYN_DROPPED, 0, 1)
        self.assertFalse(device.hold.expired(5))
        self.assertIsNone(touch.wait_timeout([device], 0, 5))
        with patch.object(device, "resync") as resync:
            device.feed(touch.EV_ABS, touch.ABS_MT_POSITION_X, 1100, 2)
            resync.assert_not_called()
            device.feed(touch.EV_SYN, touch.SYN_REPORT, 0, 2)
            resync.assert_called_once()

    def test_capability_detection_rejects_mouse_and_accepts_direct_multitouch(self):
        axes = sum(1 << c for c in (47, 53, 54, 57))

        def fake_ioctl(fd, number, size, initial=b""):
            if number == 0x09:
                return (2).to_bytes(size, "little")
            if number == 0x23:
                return axes.to_bytes(size, "little")
            info = {
                47: (0, 0, 1, 0, 0, 0),
                53: (100, 100, 1100, 0, 0, 0),
                54: (200, 200, 2200, 0, 0, 0),
            }
            if number >= 0x40:
                return struct.pack("=6i", *info[number - 0x40])
            code = struct.unpack("=i", initial)[0]
            values = {57: (-1, -1), 53: (100, 100), 54: (200, 200)}[code]
            return initial + struct.pack("=2i", *values)

        with patch.object(touch, "ioctl_read", side_effect=fake_ioctl):
            device = touch.Touchscreen(123)
            self.assertEqual(device.count, 2)
            self.assertFalse(device.hold.blocked)
        with patch.object(touch, "ioctl_read", return_value=bytes(16)):
            with self.assertRaises(ValueError):
                touch.Touchscreen(123)


if __name__ == "__main__":
    unittest.main()
