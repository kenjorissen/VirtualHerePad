"""USB HID key state and initial PC keyboard layouts (no GUI dependencies)."""

LAYOUT_NAMES = {"us": "English (US)", "uk": "English (UK)", "de": "Deutsch", "fr": "Français"}
ALLOWED_KEYS = set(range(4, 70)) | {76, 79, 80, 81, 82, 100} | set(range(224, 232))


class KeyState:
    def __init__(self):
        self.keys = set()

    def update(self, code, down):
        if type(code) is not int or code not in ALLOWED_KEYS or type(down) is not bool:
            raise ValueError("Unsupported key event")
        if down:
            if code < 224 and code not in self.keys and sum(k < 224 for k in self.keys) >= 6:
                raise ValueError("Maximum six simultaneous non-modifier keys")
            self.keys.add(code)
        else:
            self.keys.discard(code)
        return self.report()

    def clear(self):
        self.keys.clear()
        return self.report()

    def report(self):
        modifiers = sum(1 << (key - 224) for key in self.keys if key >= 224)
        keys = sorted(key for key in self.keys if key < 224)
        return bytes([modifiers, 0, *keys, *([0] * (6 - len(keys)))])


def layout_rows(layout):
    """Labels describe the matching PC layout; reports always contain HID usages."""
    if layout not in LAYOUT_NAMES:
        raise ValueError("Unknown keyboard layout")
    labels = {code: (chr(code + 93), chr(code + 61), "") for code in range(4, 30)}
    for code, normal, shifted in zip(range(30, 40), "1234567890", "!@#$%^&*()"):
        labels[code] = (normal, shifted, "")
    labels.update(
        {
            45: ("-", "_", ""),
            46: ("=", "+", ""),
            47: ("[", "{", ""),
            48: ("]", "}", ""),
            49: ("\\", "|", ""),
            50: ("#", "~", ""),
            51: (";", ":", ""),
            52: ("'", '"', ""),
            53: ("`", "~", ""),
            54: (",", "<", ""),
            55: (".", ">", ""),
            56: ("/", "?", ""),
            100: ("\\", "|", ""),
        }
    )
    if layout == "uk":
        labels.update(
            {31: ("2", '"', ""), 32: ("3", "£", ""), 52: ("'", "@", ""), 53: ("`", "¬", "¦")}
        )
    elif layout == "de":
        labels.update(
            {
                28: ("z", "Z", ""),
                29: ("y", "Y", ""),
                31: ("2", '"', "²"),
                32: ("3", "§", "³"),
                35: ("6", "&", ""),
                36: ("7", "/", "{"),
                37: ("8", "(", "["),
                38: ("9", ")", "]"),
                39: ("0", "=", "}"),
                45: ("ß", "?", "\\"),
                46: ("´", "`", ""),
                47: ("ü", "Ü", ""),
                48: ("+", "*", "~"),
                50: ("#", "'", ""),
                51: ("ö", "Ö", ""),
                52: ("ä", "Ä", ""),
                53: ("^", "°", ""),
                54: (",", ";", ""),
                55: (".", ":", ""),
                56: ("-", "_", ""),
                100: ("<", ">", "|"),
                8: ("e", "E", "€"),
                20: ("q", "Q", "@"),
                16: ("m", "M", "µ"),
            }
        )
    elif layout == "fr":
        labels.update(
            {
                4: ("q", "Q", ""),
                20: ("a", "A", ""),
                26: ("z", "Z", ""),
                29: ("w", "W", ""),
                8: ("e", "E", "€"),
                30: ("&", "1", ""),
                31: ("é", "2", "~"),
                32: ('"', "3", "#"),
                33: ("'", "4", "{"),
                34: ("(", "5", "["),
                35: ("-", "6", "|"),
                36: ("è", "7", "`"),
                37: ("_", "8", "\\"),
                38: ("ç", "9", "^"),
                39: ("à", "0", "@"),
                45: (")", "°", "]"),
                46: ("=", "+", "}"),
                47: ("^", "¨", ""),
                48: ("$", "£", "¤"),
                50: ("*", "µ", ""),
                51: ("m", "M", ""),
                52: ("ù", "%", ""),
                53: ("²", "", ""),
                16: (",", "?", ""),
                54: (";", ".", ""),
                55: (":", "/", ""),
                56: ("!", "§", ""),
                100: ("<", ">", ""),
            }
        )
    special = {
        40: "Enter",
        41: "Esc",
        42: "⌫",
        43: "Tab",
        44: "Space",
        57: "Caps",
        76: "Del",
        79: "→",
        80: "←",
        81: "↓",
        82: "↑",
        224: "Ctrl",
        225: "Shift",
        226: "Alt",
        227: "Super",
        228: "Ctrl",
        229: "Shift",
        230: "AltGr",
    }
    special.update({code: f"F{code - 57}" for code in range(58, 70)})
    codes = [
        [53, *range(30, 40), 45, 46, 42],
        [43, 20, 26, 8, 21, 23, 28, 24, 12, 18, 19, 47, 48, 49 if layout == "us" else 50],
        [57, 4, 22, 7, 9, 10, 11, 13, 14, 15, 51, 52, 40],
        [225, *([] if layout == "us" else [100]), 29, 27, 6, 25, 5, 17, 16, 54, 55, 56, 229],
        [224, 227, 226, 230, 44, 80, 81, 82, 79, 228],
        [41, *range(58, 70)],
    ]
    rows = []
    for row in codes:
        keys = []
        for code in row:
            normal, shift, altgr = labels.get(code, (special.get(code, "?"), "", ""))
            weight = 5 if code == 44 else 1.6 if code in (40, 42, 57, 225, 229) else 1
            keys.append(
                {
                    "code": code,
                    "normal": normal,
                    "shift": shift or normal,
                    "altgr": altgr,
                    "weight": weight,
                    "letter": len(normal) == len(shift) == 1
                    and normal.isalpha()
                    and shift.isalpha(),
                }
            )
        rows.append(keys)
    return rows


MODIFIERS = set(range(224, 232))
# Shift and AltGr apply to exactly one following key; the rest stay latched until
# tapped again, which is what makes shortcuts usable one finger at a time.
ONE_SHOT = {225, 229, 230}
STICKY = {224, 226, 227, 228, 231}
CAPS = 57


class TouchKeys:
    """Turn touch down/up events into the exact key events to send to the PC.

    Pure logic: it never touches hardware, so the awkward parts (one-shot versus
    latched modifiers, caps display, releasing everything on disconnect) are
    directly testable.
    """

    def __init__(self):
        self.held = set()
        self.sticky = set()
        self.oneshot = set()
        self.temporary = set()
        self.used = set()
        self.caps = False
        self.applied = set()

    # -- state exposed to the UI ------------------------------------------
    @property
    def active(self):
        """Every modifier the user has engaged, including latched one-shots."""
        return self.held | self.sticky | self.oneshot | self.temporary

    @property
    def wire(self):
        """Modifiers that must currently be held down on the PC.

        A latched one-shot is deliberately absent until the next real key press,
        so tapping Shift does not leave Shift down on the remote machine.
        """
        return self.held | self.sticky | self.temporary

    @property
    def shift_active(self):
        return bool(self.active & {225, 229})

    @property
    def altgr_active(self):
        return 230 in self.active

    def label(self, key):
        """The character this key would produce right now, for display only.

        The PC's own layout decides what is actually typed; this is a preview.
        Shift+AltGr combinations are not modelled.
        """
        if self.altgr_active and key["altgr"]:
            return key["altgr"]
        if self.shift_active:
            return key["shift"]
        if self.caps and key["letter"]:
            return key["shift"]
        return key["normal"]

    def decorated(self, key):
        return {
            "code": key["code"],
            "span": key["span"],
            "label": self.label(key),
            "active": key["code"] in self.active or (key["code"] == CAPS and self.caps),
        }

    # -- input ------------------------------------------------------------
    def press(self, code):
        if code in MODIFIERS:
            self.held.add(code)
            self.used.discard(code)
            return self.sync()
        if code == CAPS:
            # A tap, not a hold: the PC latches caps itself.
            self.caps = not self.caps
            return [(CAPS, True), (CAPS, False)]
        self.temporary = set(self.oneshot)
        self.used |= self.held
        return [*self.sync(), (code, True)]

    def release(self, code):
        if code in MODIFIERS:
            self.held.discard(code)
            if code in self.used:
                self.used.discard(code)
            elif code in ONE_SHOT:
                self.oneshot.symmetric_difference_update({code})
            else:
                self.sticky.symmetric_difference_update({code})
            return self.sync()
        if code == CAPS:
            return []
        self.temporary.clear()
        self.oneshot.clear()
        return [(code, False), *self.sync()]

    def sync(self):
        """Emit only the modifier transitions needed to match the desired state."""
        desired = self.wire
        events = [(code, True) for code in sorted(desired - self.applied)]
        events += [(code, False) for code in sorted(self.applied - desired)]
        self.applied = set(desired)
        return events

    def release_all(self):
        self.held.clear()
        self.sticky.clear()
        self.oneshot.clear()
        self.temporary.clear()
        self.used.clear()
        events = [(code, False) for code in sorted(self.applied)]
        self.applied = set()
        return events


def largest_remainder(weights, total):
    """Split `total` integer cells across weights, never giving a key zero cells."""
    if total < len(weights):
        raise ValueError("not enough cells for every key")
    exact = [weight * total / sum(weights) for weight in weights]
    spans = [int(value) for value in exact]
    remaining = total - sum(spans)
    order = sorted(range(len(weights)), key=lambda index: (-(exact[index] - spans[index]), index))
    for index in order[:remaining]:
        spans[index] += 1
    return spans


def layout_grid(layout, columns=1000):
    """Lay every row out across the same number of cells.

    A large cell count keeps key widths visually proportional while keeping touch
    hit-testing exact integer arithmetic: cell = x * columns // width.
    """
    grid = []
    for row in layout_rows(layout):
        spans = largest_remainder([key["weight"] for key in row], columns)
        grid.append([{**key, "span": span} for key, span in zip(row, spans)])
    return grid
