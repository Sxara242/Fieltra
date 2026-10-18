"""Native legal/staging UI only; synthetic profiles, no real feed or launch."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QPushButton

from tests import test_ui_revamp_phase1 as ui_fixture
from app.version import APP_VERSION


class WindowsRcLegalUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ui_fixture.UiRevampTests.setUpClass()

    def setUp(self):
        self.fixture = ui_fixture.UiRevampTests('test_small_window_scroll_and_dark_palette')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.window = self.fixture.window
        self.window.resize(1050, 720)
        self.window.show()
        self.fixture.app.processEvents()
        self.fixture.nav.open('settings')
        self.page = self.window.pages[self.fixture.nav.targets['settings'].page][1].resolved_page()
        for _ in range(12):
            self.page.repaint()
            QTest.qWait(60)
            if self.page._secondary_construction.complete:
                break
        self.assertTrue(self.page._secondary_construction.complete)

    def test_legal_notice_links_are_accessible_in_el_en_light_dark_without_data_change(self):
        self.page.tabs.setCurrentIndex(2)
        before = self.fixture.snapshot()
        for theme in ('light', 'dark'):
            self.fixture.theme.set_theme(theme,persist=False)
            for code in ('el','en'):
                self.fixture.controller.set_language(code,persist=False)
                QTest.qWait(90)
                tab=self.page.tabs.currentWidget()
                labels=[label.text() for label in tab.findChildren(QLabel) if label.isVisible()]
                text='\n'.join(labels)
                self.assertIn('AGPL-3.0-only',text)
                self.assertIn('PySide6 / Qt',text)
                self.assertIn('without warranty' if code=='en' else 'χωρίς εγγύηση',text)
                buttons=[button for button in tab.findChildren(QPushButton) if button.isVisible()]
                legal=next(button for button in buttons if button.text()=='AGPL-3.0-only')
                with patch('PySide6.QtGui.QDesktopServices.openUrl',return_value=True) as open_url:
                    legal.click()
                    target=Path(open_url.call_args.args[0].toLocalFile())
                    self.assertTrue(target.is_file())
                    self.assertEqual('LICENSE',target.name)
                evidence=os.environ.get('MASTIXA_RC_EVIDENCE')
                if evidence:
                    self.window.grab().save(str(Path(evidence)/f'legal-{theme}-{code}.png'))
                self.assertEqual(before,self.fixture.snapshot())

    def test_staging_updates_show_installed_version_and_manual_offline_no_update(self):
        self.fixture.nav.open('updates')
        self.fixture.controller.set_language('en',persist=False)
        QTest.qWait(100)
        tab=self.page.tabs.currentWidget()
        text='\n'.join(label.text() for label in tab.findChildren(QLabel))
        self.assertIn(APP_VERSION,text)
        self.assertIn('local test feed',text)
        self.assertFalse(self.page._mastixa_install_update_button.isVisible())
        self.page._mastixa_check_updates_button.click()
        for _ in range(30):
            QTest.qWait(20)
            if self.page._mastixa_check_updates_button.isEnabled():
                break
        self.assertTrue(self.page._mastixa_check_updates_button.isEnabled())
        self.assertIn(APP_VERSION,self.page._mastixa_update_status.text())
        self.assertFalse(self.page._mastixa_install_update_button.isVisible())
        evidence=os.environ.get('MASTIXA_RC_EVIDENCE')
        if evidence:
            self.window.grab().save(str(Path(evidence)/'updates-staging-en.png'))
