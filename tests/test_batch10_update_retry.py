"""Updater failure recovery using mocked I/O and real Windows Qt buttons."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox, QTabWidget, QWidget

from app import update_integration, update_manager
from tests.test_alpha2_updates import _manifest


class UpdateRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_page(self):
        page = QWidget()
        page.tabs = QTabWidget(page)
        page._composed_text = lambda label, text, **values: label.setText(text.format(**values))
        update_integration._add_updates_tab(page)
        self.addCleanup(page.deleteLater)
        self.addCleanup(page.close)
        return page

    @staticmethod
    def immediate_thread(*, target, **kwargs):
        return SimpleNamespace(start=target)

    def available_update(self):
        return update_manager.parse_manifest(_manifest(windows={
            "filename": "Fieltra-0.40.0-alpha.3-Setup.exe",
            "url": "https://example.invalid/update.exe",
            "sha256": "0" * 64,
        }))

    def test_download_failure_allows_retry_without_restarting_or_launching(self):
        for detail in ("Could not download the update: timeout", "Downloaded installer failed SHA-256 verification"):
            with self.subTest(detail=detail):
                page = self.make_page()
                info = self.available_update()
                with patch.object(update_integration.threading, "Thread", side_effect=self.immediate_thread), \
                     patch.object(update_integration, "fetch_update_info", return_value=info), \
                     patch.object(update_integration, "download_windows_update", side_effect=[
                         update_manager.UpdateError(detail), Path("verified-update.exe")]) as download, \
                     patch.object(update_integration, "_message", return_value=QMessageBox.StandardButton.No) as prompt, \
                     patch.object(update_integration, "launch_windows_installer") as launch:
                    page._mastixa_check_updates_button.click()
                    page._mastixa_install_update_button.click()
                    self.assertEqual(1, download.call_count)
                    self.assertIn(detail, page._mastixa_update_status.text())
                    self.assertTrue(page._mastixa_install_update_button.isEnabled())
                    self.assertTrue(page._mastixa_check_updates_button.isEnabled())
                    prompt.assert_not_called()
                    launch.assert_not_called()
                    page._mastixa_install_update_button.click()
                    self.assertEqual(2, download.call_count)
                    prompt.assert_called_once()
                    launch.assert_not_called()
                    self.assertTrue(page._mastixa_install_update_button.isEnabled())
                    self.assertIn(info.version, page._mastixa_update_status.text())

    def test_failed_check_can_be_retried_and_no_update_keeps_install_hidden(self):
        page = self.make_page()
        current = update_manager.parse_manifest(_manifest(
            version=update_integration.APP_VERSION,
            channel=update_manager.RELEASE_CHANNEL))
        with patch.object(update_integration.threading, "Thread", side_effect=self.immediate_thread), \
             patch.object(update_integration, "fetch_update_info", side_effect=[
                 update_manager.UpdateError("offline"), current]) as fetch, \
             patch.object(update_integration, "download_windows_update") as download:
            page._mastixa_check_updates_button.click()
            self.assertIn("offline", page._mastixa_update_status.text())
            self.assertTrue(page._mastixa_check_updates_button.isEnabled())
            page._mastixa_check_updates_button.click()
            self.assertEqual(2, fetch.call_count)
            self.assertTrue(page._mastixa_install_update_button.isHidden())
            self.assertIn(current.version, page._mastixa_update_status.text())
            download.assert_not_called()
