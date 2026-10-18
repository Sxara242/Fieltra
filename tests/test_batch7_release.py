"""Source release contracts; no installer build or outbound requests."""
from pathlib import Path
import json
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QTabWidget, QWidget

from app.version import APP_VERSION
from app import update_manager, update_integration
from tests.test_alpha2_updates import _manifest, _Response


ROOT = Path(__file__).resolve().parents[1]


class Batch7ReleaseTests(unittest.TestCase):
    def test_windows_branding_and_numeric_string_versions(self):
        # Retained packaging inputs describe accepted v1.0.0, not this unbuilt
        # development checkout. Release preflight separately refuses that drift.
        packaged_version = json.loads((ROOT / "packaging/windows-rc.json").read_text())['version']
        self.assertEqual("1.0.0", packaged_version)
        text = (ROOT / "packaging/version_info.txt").read_text(encoding="utf-8")
        for key, value in {"FileDescription": "Fieltra - Farm Management", "ProductName": "Fieltra",
                           "InternalName": "Fieltra", "OriginalFilename": "Fieltra.exe",
                           "FileVersion": packaged_version, "ProductVersion": packaged_version}.items():
            self.assertIn(f"StringStruct('{key}', '{value}')", text)
        numbers = (*map(int, packaged_version.split(".")), 0)
        self.assertIn(f"filevers={numbers}", text)
        self.assertIn(f"prodvers={numbers}", text)
        iss = (ROOT / "installer/MastixaManager.iss").read_text(encoding="utf-8")
        self.assertIn(f'#define MyAppVersion "{packaged_version}"', iss)
        self.assertIn("VersionInfoVersion=" + ".".join(map(str, numbers)), iss)
        spec = (ROOT / "packaging/MastixaManager.spec").read_text(encoding="utf-8")
        self.assertIn('version=str(repo_root / "packaging" / "version_info.txt")', spec)
        self.assertIn('"app/locales"', spec)

    def test_download_rejects_unsafe_windows_filenames_before_io(self):
        for filename in ("../bad.exe", r"..\bad.exe", r"C:\bad.exe", "CON.exe", "NUL.exe",
                         "COM1.exe", "good.exe:stream.exe", "bad?.exe", "bad\x01.exe"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as root:
                info = update_manager.parse_manifest(_manifest(windows={
                    "filename": filename, "url": "https://example.invalid/file.exe", "sha256": "0" * 64}))
                opener = Mock(side_effect=AssertionError("Unsafe name reached network"))
                with self.assertRaisesRegex(update_manager.UpdateError, "Unsafe Windows installer filename"):
                    update_manager.download_windows_update(info, destination_dir=Path(root), opener=opener)
                opener.assert_not_called()
                self.assertEqual([], list(Path(root).iterdir()))

    def test_manifest_invalid_json_version_release_url_and_sha(self):
        for payload in (b"bad JSON", _manifest(version="invalid"), _manifest(release_url="http://example.invalid"),
                        _manifest(windows={"filename": "update.exe", "url": "https://example.invalid/update.exe", "sha256": "g" * 64})):
            with self.subTest(payload=payload), self.assertRaises(update_manager.UpdateError):
                update_manager.parse_manifest(payload)

    def test_feed_is_https_get_with_no_uploaded_data(self):
        opener = Mock(return_value=_Response(_manifest()))
        update_manager.fetch_update_info("https://example.invalid/feed.json", opener=opener)
        request = opener.call_args.args[0]
        self.assertIsNone(request.data)
        self.assertEqual("GET", request.get_method())
        opener.reset_mock()
        with self.assertRaises(update_manager.UpdateError):
            update_manager.fetch_update_info("http://example.invalid/feed.json", opener=opener)
        opener.assert_not_called()

    def test_update_ui_does_not_check_until_user_clicks(self):
        app = QApplication.instance() or QApplication([])
        page = QWidget()
        page.tabs = QTabWidget(page)
        page._composed_text = lambda label, text, **values: label.setText(text.format(**values))
        self.addCleanup(page.deleteLater)
        self.addCleanup(page.close)
        info = update_manager.parse_manifest(_manifest(
            version=APP_VERSION, channel=update_manager.RELEASE_CHANNEL))
        def thread(*, target, **_kwargs):
            return SimpleNamespace(start=target)
        with patch.object(update_integration, "fetch_update_info", return_value=info) as fetch, \
             patch.object(update_integration.threading, "Thread", side_effect=thread) as start:
            update_integration._add_updates_tab(page)
            app.processEvents()
            fetch.assert_not_called()
            start.assert_not_called()
            self.assertTrue(page._mastixa_install_update_button.isHidden())
            page._mastixa_check_updates_button.click()
            fetch.assert_called_once_with()
            self.assertIn(APP_VERSION, page._mastixa_update_status.text())
            self.assertTrue(page._mastixa_check_updates_button.isEnabled())
            self.assertTrue(page._mastixa_install_update_button.isHidden())
