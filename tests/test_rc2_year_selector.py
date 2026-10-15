"""Synthetic active-year selector, keyboard confirmation and lock regressions."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QDate, QEvent, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QComboBox, QMessageBox, QSpinBox
from app.database import Database
from app import year_context as context
from app.year_context_ui import YearContextBar
from tests.language_fixture import scoped_language


class FixedDate(QDate):
    @staticmethod
    def currentDate():
        return QDate(2026, 10, 12)


class YearSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.enterContext(scoped_language(self.app, 'el'))
        self.enterContext(patch('app.year_context_ui.QDate', FixedDate))
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.db = Database(root / 'selector.db')
        context.set_active_working_year(self.db, 2027, audit=False)
        self.bar = YearContextBar(self.db, initial_installation_year=2026)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        context.finish_year_correction(self.db)
        self.bar.close()
        self.bar.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def select(self, year):
        self.bar.year_selector.setEditText(str(year))
        self.bar._apply_year()

    def snapshot(self):
        with self.db.connect() as connection:
            return tuple(connection.iterdump())

    def test_one_editable_selection_with_compact_installation_year_range(self):
        self.assertEqual([self.bar.year_selector], self.bar.findChildren(QComboBox))
        self.assertEqual([], self.bar.findChildren(QSpinBox))
        self.assertTrue(self.bar.year_selector.isEditable())
        self.assertEqual([2024, 2025, 2026, 2027], [self.bar.year_selector.itemData(i) for i in range(4)])
        self.assertEqual(4, self.bar.year_selector.count())
        self.assertEqual(6, self.bar.year_selector.maxVisibleItems())
        self.assertEqual(QComboBox.InsertPolicy.NoInsert, self.bar.year_selector.insertPolicy())
        self.assertEqual('Ενεργό έτος εργασίας:', self.bar.year_selector.accessibleName())

    def test_refresh_and_same_year_do_not_request_confirmation_or_write(self):
        before = self.snapshot()
        with patch('app.year_context_ui._message') as dialog:
            self.bar.refresh()
            self.select(2027)
            dialog.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_cancel_restores_selection_and_never_refreshes_pages(self):
        before = self.snapshot()
        with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.No), \
                patch.object(self.bar, '_notify_window') as refresh:
            self.select(2028)
            refresh.assert_not_called()
        self.assertEqual(2027, self.bar.year_selector.currentData())
        self.assertEqual(before, self.snapshot())

    def test_accept_refreshes_once_after_persisting_and_preserves_lock(self):
        context.is_year_physically_locked(self.db, 2026)
        self.db.execute('INSERT INTO year_locks(year,is_locked) VALUES(2026,1)')
        with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.Yes), \
                patch.object(self.bar, '_notify_window',
                             side_effect=lambda: self.assertEqual(2026, context.active_working_year(self.db))) as refresh:
            self.select(2026)
            refresh.assert_called_once()
        self.assertTrue(context.is_year_write_blocked(self.db, 2026))
        self.assertIn('Μόνο προβολή', self.bar.warning_label.text())

    def test_failed_write_restores_selection_without_success(self):
        self.bar.year_selector.setEditText('2028')
        before = self.snapshot()
        with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.Yes) as dialog, \
                patch('app.year_context_ui.set_active_working_year', side_effect=RuntimeError('synthetic write failure')):
            with self.assertRaises(RuntimeError):
                self.bar._apply_year()
        self.assertEqual(1, dialog.call_count)
        self.assertEqual(2027, self.bar.year_selector.currentData())
        self.assertEqual(before, self.snapshot())

    def test_correction_hides_selector_and_blocks_even_direct_activation(self):
        context.is_year_physically_locked(self.db, 2026)
        self.db.execute('INSERT INTO year_locks(year,is_locked) VALUES(2026,1)')
        context.begin_year_correction(self.db, 2026, 'synthetic correction')
        self.bar.refresh()
        before = self.snapshot()
        with patch('app.year_context_ui._message') as dialog:
            self.select(2028)
            dialog.assert_not_called()
        self.assertTrue(self.bar.year_selector.isHidden())
        self.assertEqual(2027, self.bar.year_selector.currentData())
        self.assertEqual(before, self.snapshot())
        self.assertEqual(2026, context.effective_working_year(self.db))

    def test_keyboard_navigation_opens_confirmation_before_database_change(self):
        self.bar.show()
        edit = self.bar.year_selector.lineEdit()
        edit.setFocus()
        edit.selectAll()
        QTest.keyClicks(edit, '2040')
        self.assertEqual(2027, context.active_working_year(self.db))
        errors, observed = [], []
        before = self.snapshot()
        def reject_dialog():
            box = self.app.activeModalWidget()
            try:
                self.assertIsInstance(box, QMessageBox)
                self.assertEqual(2027, context.active_working_year(self.db))
                observed.append(box.text())
            except BaseException as error:
                errors.append(error)
            finally:
                if isinstance(box, QMessageBox):
                    box.done(QMessageBox.StandardButton.No)
        QTimer.singleShot(0, reject_dialog)
        QTest.keyClick(edit, Qt.Key.Key_Return)
        if errors:
            raise errors[0]
        self.assertEqual(1, len(observed))
        self.assertIn('2040', observed[0])
        self.assertEqual(2027, self.bar.year_selector.currentData())
        self.assertEqual(before, self.snapshot())

    def test_selector_inherits_light_and_dark_styles_without_inline_colours(self):
        from app.main_window import STYLESHEET
        from app.appearance_theme import DARK_STYLESHEET
        for stylesheet in (STYLESHEET, DARK_STYLESHEET):
            self.bar.setStyleSheet(stylesheet)
            self.bar.refresh()
            self.assertEqual('', self.bar.year_selector.styleSheet())
            self.assertEqual('active', self.bar.property('yearContextState'))
            self.assertEqual(2027, self.bar.year_selector.currentData())

    def test_manual_past_and_future_not_limited_by_dropdown_or_inserted(self):
        with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.Yes):
            for year in (1000, 1800, 1903, 2040, 9999):
                self.select(year)
                self.assertEqual(year, context.active_working_year(self.db))
                self.assertEqual(str(year), self.bar.year_selector.currentText())
                self.assertEqual(-1, self.bar.year_selector.findData(year))
                from app.widgets import date_input
                edit = date_input(self.db)
                self.assertEqual(year, edit.date().year())
                edit.deleteLater()
        self.assertEqual(4, self.bar.year_selector.count())

    def test_invalid_values_never_confirm_or_change_state(self):
        before = self.snapshot()
        for value in ('', '20', '20265', '0000', '0999', '-2026', '202x', '２０２６'):
            with self.subTest(value=value), patch('app.year_context_ui._message') as dialog:
                self.select(value)
                self.assertEqual('warning', dialog.call_args.args[1])
                self.assertEqual(before, self.snapshot())
                self.assertEqual('2027', self.bar.year_selector.currentText())

    def test_calendar_rollover_extends_end_without_moving_start(self):
        with patch.object(FixedDate, 'currentDate', return_value=QDate(2027, 1, 1)):
            self.bar.refresh()
        self.assertEqual(2024, self.bar.year_selector.itemData(0))
        self.assertEqual(2028, self.bar.year_selector.itemData(4))

    def test_unknown_or_very_old_date_uses_manual_entry_without_huge_list(self):
        for first in (None, 1903):
            self.bar.initial_installation_year = first
            self.bar.refresh()
            self.assertEqual(0, self.bar.year_selector.count())
            with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.Yes):
                self.select(1903)
            self.assertEqual(1903, context.active_working_year(self.db))

    def test_dropdown_activation_and_normal_row_height(self):
        with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.Yes):
            selector = self.bar.year_selector
            index = selector.findData(2025)
            selector.setCurrentIndex(index)
            selector.activated.emit(index)
        self.assertEqual(2025, context.active_working_year(self.db))
        self.assertLess(selector.view().sizeHintForRow(0), 2 * self.bar.fontMetrics().height() + 12)

    def display_themes(self, font_pixels=14):
        """Use the application's combined/scoped skins, without saving preferences."""
        from app.appearance_theme import ThemeController
        from app.main_window import STYLESHEET, build_app_palette
        # Windows offscreen QPA does not enumerate system fonts automatically.
        font_path = Path('C:/Windows/Fonts/segoeui.ttf')
        if font_path.is_file():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            self.assertGreaterEqual(font_id, 0)
            self.addCleanup(QFontDatabase.removeApplicationFont, font_id)
        self.addCleanup(self.app.setStyleSheet, self.app.styleSheet())
        self.addCleanup(self.app.setPalette, self.app.palette())
        sheet = STYLESHEET.replace('font-size: 14px;', f'font-size: {font_pixels}px;')
        theme = ThemeController(self.app, sheet, build_app_palette())
        self.addCleanup(self.app.removeEventFilter, theme)
        self.addCleanup(theme.deleteLater)
        theme.apply_saved_theme()
        self.bar.show()
        for skin in ('light', 'dark'):
            theme.set_theme(skin, persist=False)
            self.bar.refresh()
            self.app.processEvents()
            # Exercise the narrowest layout Qt permits, not only a roomy window.
            self.bar.resize(self.bar.minimumSizeHint())
            self.app.processEvents()
            yield skin

    def assert_four_digits_visible(self, expected):
        edit = self.bar.year_selector.lineEdit()
        self.app.processEvents()
        self.assertEqual(str(expected), edit.text())
        metrics = edit.fontMetrics()
        # QLineEdit needs internal text margins and caret space beyond glyph width.
        self.assertGreaterEqual(edit.contentsRect().width(), metrics.horizontalAdvance(edit.text()) + 6)
        origin = None
        for position in (len(edit.text()), 0, 1, 2, 3, len(edit.text())):
            edit.setCursorPosition(position)
            self.app.processEvents()
            current = edit.cursorRect().x() - metrics.horizontalAdvance(edit.text()[:position])
            if origin is None:
                origin = current
            self.assertLessEqual(abs(current - origin), 1, 'Cursor movement horizontally scrolled the year')

    def test_all_digits_visible_on_initial_load_and_dropdown_confirmation(self):
        context.set_active_working_year(self.db, 2026, audit=False)
        for skin in self.display_themes():
            with self.subTest(theme=skin):
                self.assert_four_digits_visible(2026)
                selector = self.bar.year_selector
                with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.Yes):
                    index = selector.findData(2025)
                    selector.setCurrentIndex(index)
                    selector.activated.emit(index)
                self.assert_four_digits_visible(2025)
                context.set_active_working_year(self.db, 2026, audit=False)

    def test_all_digits_visible_after_keyboard_edit_accept_cancel_and_invalid_input(self):
        for skin in self.display_themes():
            with self.subTest(theme=skin):
                edit = self.bar.year_selector.lineEdit()
                edit.setFocus()
                edit.selectAll()
                QTest.keyClicks(edit, '2040')
                self.assert_four_digits_visible(2040)
                with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.Yes):
                    QTest.keyClick(edit, Qt.Key.Key_Return)
                self.assert_four_digits_visible(2040)
                with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.No):
                    self.select(1000)
                self.assert_four_digits_visible(2040)
                with patch('app.year_context_ui._message'):
                    self.select('20')
                self.assert_four_digits_visible(2040)

    def test_all_digits_visible_after_theme_and_font_size_change(self):
        for skin in self.display_themes(font_pixels=20):
            with self.subTest(theme=skin):
                self.assert_four_digits_visible(2027)
                with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.Yes):
                    self.select(9999)
                self.assert_four_digits_visible(9999)
                context.set_active_working_year(self.db, 2027, audit=False)
