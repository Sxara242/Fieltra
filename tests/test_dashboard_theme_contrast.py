from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel

from app import appearance_theme, dashboard
from app.database import Database
from app.main_window import STYLESHEET, build_app_palette


def contrast(first, second):
    def luminance(color):
        channels = [color.redF(), color.greenF(), color.blueF()]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
                  for c in channels]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    values = sorted((luminance(first), luminance(second)))
    return (values[1] + 0.05) / (values[0] + 0.05)


class DashboardThemeContrastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_real_kpi_labels_are_readable_dark_and_unchanged_light(self):
        original_style, original_palette = self.app.styleSheet(), self.app.palette()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(dashboard, "BASE_DIR", root), \
                 patch.object(appearance_theme, "_SETTINGS_FILE", root / "appearance.ini"):
                self.app.setStyleSheet(STYLESHEET)
                self.app.setPalette(build_app_palette())
                controller = appearance_theme.ThemeController(
                    self.app, STYLESHEET, build_app_palette())
                page = dashboard.DashboardPage(Database(root / "test.db"))
                unrelated_value = QLabel("Unrelated metric")
                unrelated_value.setObjectName("metricValue")
                cards = (page.production, page.income, page.expenses, page.balance)
                try:
                    controller.apply_saved_theme()
                    for _, label in cards:
                        label.ensurePolished()
                        self.assertEqual(QColor("#21483A"),
                                         label.palette().color(QPalette.ColorRole.WindowText))
                    controller.set_theme("dark", persist=False)
                    unrelated_value.ensurePolished()
                    self.assertEqual(QColor("#21483A"), unrelated_value.palette().color(
                        QPalette.ColorRole.WindowText))
                    for box, label in cards:
                        box.ensurePolished()
                        label.ensurePolished()
                        foreground = label.palette().color(QPalette.ColorRole.WindowText)
                        background = box.palette().color(QPalette.ColorRole.Window)
                        self.assertEqual(QColor("#20272C"), background)
                        self.assertGreaterEqual(contrast(foreground, background), 4.5)
                    controller.set_theme("light", persist=False)
                    for _, label in cards:
                        self.assertEqual(QColor("#21483A"),
                                         label.palette().color(QPalette.ColorRole.WindowText))
                finally:
                    self.app.removeEventFilter(controller)
                    page.close()
                    page.deleteLater()
                    unrelated_value.close()
                    unrelated_value.deleteLater()
                    controller.deleteLater()
                    self.app.setStyleSheet(original_style)
                    self.app.setPalette(original_palette)


if __name__ == "__main__":
    unittest.main()
