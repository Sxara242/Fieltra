from __future__ import annotations

import re
from dataclasses import dataclass


APP_NAME = "Fieltra"
APP_VERSION = "1.0.0"
RELEASE_CHANNEL = "stable"
APP_DESCRIPTOR = "Farm Management"
APP_LICENSE = "AGPL-3.0-only"
GIT_TAG = f"v{APP_VERSION}"
WINDOWS_INSTALLER_NAME = f"Fieltra-{APP_VERSION}-Setup.exe"
# Android has its own release checkpoint; this Windows batch does not bump it.
ANDROID_APK_NAME = "MastixaManager-0.40.0-alpha.2-Android.apk"

_VERSION_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<channel>alpha|beta|rc)\.(?P<serial>\d+))?$",
    re.IGNORECASE,
)
_CHANNEL_RANK = {"alpha": 0, "beta": 1, "rc": 2, "stable": 3}


@dataclass(frozen=True, order=True)
class ParsedVersion:
    major: int
    minor: int
    patch: int
    channel_rank: int
    serial: int


def parse_version(value: str) -> ParsedVersion:
    match = _VERSION_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Unsupported Fieltra version: {value!r}")

    channel = (match.group("channel") or "stable").lower()
    serial = int(match.group("serial") or 0)
    return ParsedVersion(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        _CHANNEL_RANK[channel],
        serial,
    )


def is_newer_version(candidate: str, current: str = APP_VERSION) -> bool:
    return parse_version(candidate) > parse_version(current)


def display_version(value: str = APP_VERSION) -> str:
    return value.removeprefix("v")
