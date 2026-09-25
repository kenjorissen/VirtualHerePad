#!/usr/bin/env python3
"""Download the private Qt runtime used by the optional on-screen keyboard UI.

Stock SteamOS has no pip requirement and no writable system Python, so the
PySide6 wheels are unpacked into a private directory that `vhp_ui.py` reaches
through PYTHONPATH. Nothing is installed system-wide and nothing is executed
during download.

Integrity note: each wheel's SHA-256 is checked against the digest published by
the same PyPI JSON API that supplied the URL. That detects truncated or corrupted
transfers, but it is not independent provenance.
"""

import argparse
import hashlib
import json
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

PACKAGES = ("shiboken6", "PySide6-Essentials")
API = "https://pypi.org/pypi/{package}/json"
TRUSTED_HOST = "files.pythonhosted.org"
MINIMUM_PYTHON = (3, 10)


def compatible(python_tags, python_version):
    """True if any of a wheel's compressed python tags fits this interpreter."""
    for tag in python_tags.split("."):
        if tag in ("py3", "py2"):
            return True
        if not tag.startswith("cp"):
            continue
        digits = tag[2:]
        if not digits.isdigit():
            return True  # e.g. cp3x; treat as permissive rather than skipping.
        required = (int(digits[0]), int(digits[1:]))
        if required <= python_version:
            return True
    return False


def select_wheel(package, python_version):
    """Pick the newest manylinux x86-64 wheel compatible with this interpreter.

    Wheel filenames end in ``-{python}-{abi}-{platform}.whl``; the python tag is
    the third field from the end, never the first.
    """
    with urllib.request.urlopen(API.format(package=package), timeout=60) as response:
        data = json.load(response)
    version = data["info"]["version"]
    candidates = []
    for entry in data["releases"].get(version, []):
        name = entry["filename"]
        if not name.endswith(".whl"):
            continue
        fields = name[: -len(".whl")].split("-")
        if len(fields) < 5:
            continue
        python_tag, abi, platform = fields[-3], fields[-2], fields[-1]
        if "manylinux" not in platform or "x86_64" not in platform:
            continue
        if "abi3" not in abi and "none" not in abi and python_tag not in ("py3", "py2.py3"):
            continue
        if not compatible(python_tag, python_version):
            continue
        candidates.append(entry)
    if not candidates:
        raise SystemExit(f"No compatible manylinux x86-64 wheel for {package}")
    # Prefer abi3 wheels, then the shortest filename for stable tie-breaking.
    candidates.sort(key=lambda entry: ("abi3" not in entry["filename"], entry["filename"]))
    return version, candidates[0]


def download(entry, destination):
    url = entry["url"]
    if not url.startswith("https://") or urllib.parse.urlsplit(url).hostname != TRUSTED_HOST:
        raise SystemExit(f"Refusing untrusted download host for {entry['filename']}")
    expected = entry["digests"]["sha256"]
    digest = hashlib.sha256()
    target = destination / entry["filename"]
    with urllib.request.urlopen(url, timeout=300) as response, target.open("wb") as stream:
        while chunk := response.read(65536):
            digest.update(chunk)
            stream.write(chunk)
    if digest.hexdigest() != expected:
        target.unlink(missing_ok=True)
        raise SystemExit(f"Checksum mismatch for {entry['filename']}")
    return target


def extract(wheel, destination):
    """Unpack a wheel, refusing any member that tries to escape the directory."""
    root = destination.resolve()
    with zipfile.ZipFile(wheel) as archive:
        for member in archive.infolist():
            name = member.filename
            if name.startswith("/") or ".." in Path(name).parts:
                raise SystemExit(f"Refusing unsafe wheel member: {name}")
            if stat.S_ISLNK(member.external_attr >> 16):
                raise SystemExit(f"Refusing symlink in wheel: {name}")
            if not (root / name).resolve().is_relative_to(root):
                raise SystemExit(f"Refusing wheel member outside destination: {name}")
        archive.extractall(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch the optional Qt runtime")
    parser.add_argument(
        "--destination", type=Path, default=Path.home() / ".local/share/VirtualHerePad/pylib"
    )
    parser.add_argument(
        "--keep-wheels",
        action="store_true",
        help="keep the downloaded .whl files next to the runtime",
    )
    options = parser.parse_args(argv)

    if sys.version_info < MINIMUM_PYTHON:
        raise SystemExit(
            f"Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}+ is required for PySide6; "
            f"this is {sys.version.split()[0]}"
        )
    destination = options.destination.expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    wheels = destination / ".wheels"
    wheels.mkdir(exist_ok=True)

    total = 0
    for package in PACKAGES:
        version, entry = select_wheel(package, sys.version_info[:2])
        print(f"{package} {version}: {entry['filename']}")
        wheel = download(entry, wheels)
        extract(wheel, destination)
        total += wheel.stat().st_size
        if not options.keep_wheels:
            wheel.unlink()
    if not options.keep_wheels:
        wheels.rmdir()
    print(f"Qt runtime ready in {destination} ({total // (1024 * 1024)} MiB)")
    print(f"Run the UI with: PYTHONPATH={destination} python3 vhp_ui.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
