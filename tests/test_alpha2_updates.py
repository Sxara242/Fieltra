from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from app.update_manager import UpdateError, download_windows_update, parse_manifest
from app.version import (
    ANDROID_APK_NAME,
    APP_VERSION,
    GIT_TAG,
    WINDOWS_INSTALLER_NAME,
    is_newer_version,
)


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            data = self.payload[self.offset :]
            self.offset = len(self.payload)
            return data
        data = self.payload[self.offset : self.offset + size]
        self.offset += len(data)
        return data


def _manifest(**overrides) -> bytes:
    data = {
        "schema": 1,
        "product": "Fieltra",
        "version": "1.0.0-rc.3",
        "channel": "rc",
        "release_url": "https://example.invalid/releases/v0.40.0-alpha.3",
        "notes": "UI hotfix",
        "windows": {
            "filename": "Fieltra-0.40.0-alpha.3-Setup.exe",
            "url": None,
            "sha256": None,
        },
        "android": None,
    }
    data.update(overrides)
    return json.dumps(data).encode("utf-8")


class Alpha2UpdateTests(unittest.TestCase):
    def test_clean_release_naming_contract(self) -> None:
        self.assertEqual("1.0.0", APP_VERSION)
        self.assertEqual("v1.0.0", GIT_TAG)
        self.assertEqual(
            "Fieltra-1.0.0-Setup.exe",
            WINDOWS_INSTALLER_NAME,
        )
        self.assertEqual(
            "MastixaManager-0.40.0-alpha.2-Android.apk",
            ANDROID_APK_NAME,
        )

    def test_prerelease_version_ordering(self) -> None:
        self.assertTrue(is_newer_version("0.40.0-alpha.3", "0.40.0-alpha.2"))
        self.assertTrue(is_newer_version("0.40.0-beta.1", "0.40.0-alpha.99"))
        self.assertTrue(is_newer_version("0.40.0-rc.1", "0.40.0-beta.9"))
        self.assertTrue(is_newer_version("0.40.0", "0.40.0-rc.9"))
        self.assertFalse(is_newer_version("0.40.0-alpha.1", "0.40.0-alpha.2"))

    def test_manifest_requires_https_and_checksum_for_direct_download(self) -> None:
        info = parse_manifest(_manifest())
        self.assertEqual("1.0.0-rc.3", info.version)
        self.assertTrue(info.is_newer)

        with self.assertRaises(UpdateError):
            parse_manifest(
                _manifest(
                    windows={
                        "filename": "Fieltra-0.40.0-alpha.3-Setup.exe",
                        "url": "http://example.invalid/update.exe",
                        "sha256": "0" * 64,
                    }
                )
            )

        with self.assertRaises(UpdateError):
            parse_manifest(
                _manifest(
                    windows={
                        "filename": "Fieltra-0.40.0-alpha.3-Setup.exe",
                        "url": "https://example.invalid/update.exe",
                        "sha256": None,
                    }
                )
            )

    def test_download_verifies_sha256_before_promoting_installer(self) -> None:
        payload = b"trusted installer bytes"
        sha = hashlib.sha256(payload).hexdigest()
        info = parse_manifest(
            _manifest(
                windows={
                    "filename": "Fieltra-0.40.0-alpha.3-Setup.exe",
                    "url": "https://example.invalid/update.exe",
                    "sha256": sha,
                }
            )
        )

        def opener(_request, timeout=0):
            return _Response(payload)

        with tempfile.TemporaryDirectory() as tmp:
            installer = download_windows_update(
                info,
                destination_dir=Path(tmp),
                opener=opener,
            )
            self.assertEqual(payload, installer.read_bytes())
            self.assertEqual(
                "Fieltra-0.40.0-alpha.3-Setup.exe",
                installer.name,
            )

    def test_download_rejects_checksum_mismatch(self) -> None:
        info = parse_manifest(
            _manifest(
                windows={
                    "filename": "Fieltra-0.40.0-alpha.3-Setup.exe",
                    "url": "https://example.invalid/update.exe",
                    "sha256": "0" * 64,
                }
            )
        )

        def opener(_request, timeout=0):
            return _Response(b"tampered")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(UpdateError, "SHA-256"):
                download_windows_update(info, destination_dir=root, opener=opener)
            self.assertFalse(list(root.glob("*.exe")))


if __name__ == "__main__":
    unittest.main()
