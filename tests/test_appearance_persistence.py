from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app import appearance_theme as theme


class AppearancePersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Native Windows temp paths may use an 8.3 alias (RUNNER~1). Production
        # runtime paths resolve that alias; compare the same canonical path.
        self.root = Path(self.temp.name).resolve()
        self.new = self.root / "user" / "data" / "appearance.ini"
        self.install = self.root / "install"
        self.legacy = self.install / "_internal" / "data" / "appearance.ini"
        for name, value in (("_SETTINGS_FILE", self.new),):
            mock = patch.object(theme, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        self.palette = self.app.palette()
        self.style = self.app.styleSheet()
        self.addCleanup(self.app.setPalette, self.palette)
        self.addCleanup(self.app.setStyleSheet, self.style)

    def controller(self):
        controller = theme.ThemeController(self.app, self.style, self.palette)
        self.addCleanup(controller.deleteLater)
        self.addCleanup(self.app.removeEventFilter, controller)
        return controller

    def write(self, path, value):
        settings = QSettings(str(path), QSettings.Format.IniFormat)
        settings.setValue("appearance/theme", value)
        settings.sync()
        self.assertEqual(QSettings.Status.NoError, settings.status())

    def test_frozen_path_uses_canonical_user_root_outside_install(self):
        # A fresh import verifies the actual production path assignment.
        code = """
import sys
from PySide6.QtCore import QSettings
sys.frozen = True
from app.appearance_theme import _SETTINGS_FILE
from app.runtime_paths import BASE_DIR
assert _SETTINGS_FILE == BASE_DIR / 'data' / 'appearance.ini'
print(_SETTINGS_FILE)
"""
        env = dict(os.environ, LOCALAPPDATA=str(self.root / "local"))
        env.pop("MASTIXA_DATA_HOME", None)
        result = subprocess.run([sys.executable, "-c", code], env=env,
                                capture_output=True, text=True, check=True)
        actual = Path(result.stdout.strip())
        self.assertEqual(self.root / "local" / "Fieltra" / "data" /
                         "appearance.ini", actual)
        self.assertFalse(actual.is_relative_to(self.install))

    def test_source_path_honors_runtime_override(self):
        env = dict(os.environ, MASTIXA_DATA_HOME=str(self.root / "override"))
        result = subprocess.run(
            [sys.executable, "-c",
             "from app.appearance_theme import _SETTINGS_FILE; print(_SETTINGS_FILE)"],
            env=env, capture_output=True, text=True, check=True,
        )
        self.assertEqual(self.root / "override" / "data" / "appearance.ini",
                         Path(result.stdout.strip()))

    def test_default_is_light_without_creating_preference(self):
        self.assertEqual("light", self.controller().theme)
        self.assertFalse(self.new.exists())

    def test_write_and_recreate_preserves_dark_then_light(self):
        controller = self.controller()
        controller.set_theme("dark")
        self.assertTrue(self.new.is_file())
        recreated = self.controller()
        self.assertEqual("dark", recreated.theme)
        recreated.set_theme("light")
        self.assertEqual("light", self.controller().theme)

    def test_existing_new_preference_wins_over_legacy(self):
        self.write(self.new, "light")
        self.write(self.legacy, "dark")
        before = self.new.read_bytes()
        self.assertEqual("light", self.controller().theme)
        self.assertEqual(before, self.new.read_bytes())

    def test_existing_new_file_without_value_is_not_overwritten(self):
        self.new.parent.mkdir(parents=True)
        self.new.write_text("[other]\nvalue=1\n", encoding="utf-8")
        self.write(self.legacy, "dark")
        before = self.new.read_bytes()
        self.assertEqual("light", self.controller().theme)
        self.assertEqual(before, self.new.read_bytes())

    def test_developer_theme_is_ignored_and_preserved(self):
        self.write(self.legacy, "dark")
        before = self.legacy.read_bytes()
        self.assertEqual("light", self.controller().theme)
        self.assertFalse(self.new.exists())
        self.assertEqual(before, self.legacy.read_bytes())


if __name__ == "__main__":
    unittest.main()
