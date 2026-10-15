"""Direct write-path and year-switch owner acceptance regressions."""
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QVBoxLayout
from app.database import Database
from app import year_context as context
from tests.language_fixture import scoped_language


class OwnerNativeCorrectionGestureTests(unittest.TestCase):
    """A real modal must finish before the accepted button gesture writes."""
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from app.fields import FieldsPage
        from app.year_context_ui import CorrectionMutationGuard
        self.enterContext(scoped_language(self.app, 'el'))
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.db = Database(self.root / 'gesture.db')
        context.set_active_working_year(self.db, 2027, audit=False)
        context.is_year_physically_locked(self.db, 2027)
        self.db.execute('INSERT INTO year_locks(year,is_locked) VALUES(2027,1)')
        context.begin_year_correction(self.db, 2027, 'Native modal regression')
        self.window = QDialog()
        self.page = FieldsPage(self.db)
        QVBoxLayout(self.window).addWidget(self.page)
        self.page.save_button.setDefault(True)
        self.guard = CorrectionMutationGuard(self.db, self.window)
        self.app.installEventFilter(self.guard)
        self.window.show()
        QTest.qWait(10)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.app.removeEventFilter(self.guard)
        context.finish_year_correction(self.db)
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def gesture(self, key=None):
        errors = []
        for answer in (QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes):
            self.page.name.setText('Native field')
            before = self.db.query_one('SELECT COUNT(*) n FROM fields')['n']
            dialogs = []
            def inspect():
                box = self.app.activeModalWidget()
                try:
                    self.assertIsInstance(box, QMessageBox)
                    self.assertIn('Native modal regression', box.text())
                    # Return must not execute the save before its warning.
                    self.assertEqual(before, self.db.query_one('SELECT COUNT(*) n FROM fields')['n'])
                    dialogs.append(box.text())
                except BaseException as error:
                    errors.append(error)
                finally:
                    if isinstance(box, QMessageBox):
                        QTest.mouseClick(box.button(answer), Qt.MouseButton.LeftButton)
            QTimer.singleShot(0, inspect)
            self.page.save_button.setFocus()
            if key is None:
                QTest.mouseClick(self.page.save_button, Qt.MouseButton.LeftButton)
            else:
                QTest.keyClick(self.page.save_button, key)
            self.app.processEvents()
            if errors:
                raise errors[0]
            self.assertEqual(1, len(dialogs))
            self.assertEqual(before + int(answer == QMessageBox.StandardButton.Yes),
                             self.db.query_one('SELECT COUNT(*) n FROM fields')['n'])
            self.assertTrue(context.is_year_physically_locked(self.db, 2027))

    def test_mouse_cancel_and_accept_real_modal(self):
        self.gesture()

    def test_space_cancel_and_accept_real_modal(self):
        self.gesture(Qt.Key.Key_Space)

    def test_return_cancel_and_accept_real_modal(self):
        self.gesture(Qt.Key.Key_Return)


class OwnerYearWriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.enterContext(scoped_language(self.app, 'el'))
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.db = Database(self.root / 'owner.db')
        context.set_active_working_year(self.db, 2027, audit=False)
        context.is_year_physically_locked(self.db, 2027)
        self.enterContext(patch('app.year_lock._message'))
        self.enterContext(patch.object(QMessageBox, 'warning'))
        self.enterContext(patch.object(QMessageBox, 'information'))
        self.pages = []
        self.addCleanup(self.close_pages)

    def close_pages(self):
        context.finish_year_correction(self.db)
        for page in self.pages:
            page.close()
            page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def page(self, module, cls):
        if module == 'partners':
            self.page('invoice_documents', 'InvoiceDocumentsPage')
            self.page('sales', 'SalesPage')
        page = getattr(importlib.import_module('app.' + module), cls)(self.db)
        self.pages.append(page)
        return page

    def lock(self, value=True):
        self.db.execute('INSERT OR REPLACE INTO year_locks(year,is_locked,reason) VALUES(2027,?,?)',
                        (int(value), 'Owner lock'))

    def snapshot(self):
        with self.db.connect() as connection:
            return tuple(connection.iterdump())

    def catalogs(self):
        return (
            ('fields', 'FieldsPage', 'fields', 'name', 'save_field', 'delete_field', 'selected_field_id'),
            ('labor', 'LaborPage', 'workers', 'worker_name', 'save_worker', 'delete_worker', 'selected_worker_id'),
            ('inventory', 'InventoryPage', 'inventory_items', 'item_name', 'save_item', 'delete_item', 'selected_item_id'),
            ('products', 'ProductsPage', 'products', 'name', 'save_product', 'toggle_status', 'selected_id'),
            ('partners', 'PartnersPage', 'business_partners', 'name', 'save_partner', 'delete_partner', 'selected_partner_id'),
            ('equipment', 'EquipmentPage', 'equipment', 'name', 'save_equipment', 'delete_equipment', 'selected_equipment_id'),
        )

    def fill(self, page, name_attr, name):
        getattr(page, name_attr).setText(name)
        if hasattr(page, 'unit') and page.__class__.__name__ == 'ProductsPage':
            page.unit.setEditText('kg')

    def test_direct_catalog_creates_lock_unlock_correction_and_relock(self):
        for module, cls, table, name, save, delete, selection in self.catalogs():
            with self.subTest(catalog=table):
                context.finish_year_correction(self.db)
                self.lock(False)
                page = self.page(module, cls)
                self.fill(page, name, 'Unlocked ' + table)
                getattr(page, save)()
                self.assertIsNotNone(self.db.query_one('SELECT id FROM ' + table + ' WHERE name=?', ('Unlocked ' + table,)))
                self.lock()
                self.fill(page, name, 'Blocked ' + table)
                before = self.snapshot()
                getattr(page, save)()  # Direct callable, independent of button state.
                self.assertEqual(before, self.snapshot())
                self.assertEqual('', getattr(page, name).text())
                context.begin_year_correction(self.db, 2027, 'Owner correction')
                self.fill(page, name, 'Correction ' + table)
                getattr(page, save)()
                self.assertIsNotNone(self.db.query_one('SELECT id FROM ' + table + ' WHERE name=?', ('Correction ' + table,)))
                self.assertTrue(context.is_year_physically_locked(self.db, 2027))
                context.finish_year_correction(self.db)
                self.fill(page, name, 'After correction ' + table)
                before = self.snapshot()
                getattr(page, save)()
                self.assertEqual(before, self.snapshot())

    def test_catalog_edit_delete_and_product_status_reject_direct_calls(self):
        for module, cls, table, name, save, delete, selection in self.catalogs():
            with self.subTest(catalog=table):
                context.finish_year_correction(self.db)
                self.lock(False)
                page = self.page(module, cls)
                self.fill(page, name, 'Existing ' + table)
                getattr(page, save)()
                record = self.db.query_one('SELECT id FROM ' + table + ' WHERE name=?', ('Existing ' + table,))
                setattr(page, selection, record['id'])
                self.fill(page, name, 'Edited ' + table)
                self.lock()
                before = self.snapshot()
                getattr(page, save)()
                with patch.object(page, 'confirm_delete', return_value=True):
                    getattr(page, delete)()
                self.assertEqual(before, self.snapshot())
                self.assertEqual('Edited ' + table, getattr(page, name).text())
                context.begin_year_correction(self.db, 2027, 'Correction')
                getattr(page, save)()
                self.assertIsNotNone(self.db.query_one('SELECT id FROM ' + table + ' WHERE name=?', ('Edited ' + table,)))
                setattr(page, selection, record['id'])
                with patch.object(page, 'confirm_delete', return_value=True):
                    getattr(page, delete)()
                if table == 'products':
                    self.assertEqual(0, self.db.query_one('SELECT is_active FROM products WHERE id=?', (record['id'],))['is_active'])
                else:
                    self.assertIsNone(self.db.query_one('SELECT id FROM ' + table + ' WHERE id=?', (record['id'],)))
                context.finish_year_correction(self.db)

    def test_inventory_zero_and_positive_initial_stock_both_reject(self):
        page = self.page('inventory', 'InventoryPage')
        self.lock()
        for quantity in ('0', '5'):
            page.item_name.setText('Blocked item')
            page.initial_stock.setText(quantity)
            before = self.snapshot()
            page.save_item()
            self.assertEqual(before, self.snapshot())
            self.assertEqual('', page.item_name.text())
            self.assertEqual('', page.initial_stock.text())

    def test_catalog_correction_for_another_year_does_not_unlock_active_year(self):
        page = self.page('fields', 'FieldsPage')
        self.lock()
        self.db.execute('INSERT INTO year_locks(year,is_locked,reason) VALUES(2026,1,?)', ('Old',))
        context.begin_year_correction(self.db, 2026, 'Old correction')
        page.name.setText('Correction-context field')
        page.save_field()
        self.assertIsNotNone(self.db.query_one('SELECT id FROM fields WHERE name=?', ('Correction-context field',)))
        self.assertTrue(context.is_year_write_blocked(self.db, 2027))
        context.finish_year_correction(self.db)
        page.name.setText('Blocked active year')
        before = self.snapshot()
        page.save_field()
        self.assertEqual(before, self.snapshot())

    def test_product_link_mutations_reject_locked_context(self):
        page = self.page('products', 'ProductsPage')
        field = self.db.execute("INSERT INTO fields(name) VALUES('Field')")
        product = self.db.execute("INSERT INTO products(name,unit,is_active) VALUES('Product','kg',1)")
        page.refresh()
        page.link_product.setCurrentIndex(page.link_product.findData(product))
        page.link_field.setCurrentIndex(page.link_field.findData(field))
        self.lock()
        before = self.snapshot()
        page.add_link()
        self.assertEqual(before, self.snapshot())
        context.begin_year_correction(self.db, 2027, 'Correction')
        page.add_link()
        self.assertIsNotNone(self.db.query_one('SELECT 1 FROM product_fields'))
        context.finish_year_correction(self.db)
        page.selected_link = (product, field)
        page.link_variety.setText('Blocked variety')
        before = self.snapshot()
        page.save_link_profile()
        with patch.object(page, 'confirm_delete', return_value=True):
            page.remove_link()
        self.assertEqual(before, self.snapshot())

    def test_work_blocked_create_resets_but_blocked_edit_preserves_selection(self):
        page = self.page('activities', 'ActivitiesPage')
        self.lock()
        page.notes.setText('Blocked work draft')
        page.responsible.setText('Owner')
        page.cost.setValue(42)
        before = self.snapshot()
        with patch('app.activities.warn_locked_year'):
            page.save_activity()
        self.assertEqual(before, self.snapshot())
        self.assertEqual('', page.notes.text())
        self.assertEqual('', page.responsible.text())
        self.assertEqual(0, page.cost.value())
        page.selected_activity_id = 123
        page.notes.setText('Existing edit')
        with patch('app.activities.warn_locked_year'):
            page.save_activity()
        self.assertEqual(123, page.selected_activity_id)
        self.assertEqual('Existing edit', page.notes.text())


class OwnerCorrectionPageRefreshTests(unittest.TestCase):
    """Correction transitions update the cached Year Lock page in place."""
    def setUp(self):
        from tests import test_ui_revamp_phase1 as fixture
        fixture.UiRevampTests.setUpClass()
        self.case = fixture.UiRevampTests('test_small_window_scroll_and_dark_palette')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        context.set_active_working_year(self.case.db, 2026, audit=False)
        context.is_year_physically_locked(self.case.db, 2026)
        self.case.db.execute('INSERT INTO year_locks(year,is_locked) VALUES(2026,1)')
        self.case.window.show()
        self.case.window._refresh_year_context_ui()
        QTest.qWait(20)
        self.case.nav.open('year_lock')
        QTest.qWait(20)
        self.holder = self.case.window.pages[self.case.nav.targets['year_lock'].page][1]
        self.page = self.holder.resolved_page()
        self.enterContext(patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.Yes))
        self.addCleanup(context.finish_year_correction, self.case.db)

    def enter_correction(self):
        self.page.correction_reason.setText('Owner refresh regression')
        QTest.mouseClick(self.page.edit_locked_button, Qt.MouseButton.LeftButton)
        self.assertIsNotNone(context.correction_state(self.case.db))
        self.assertTrue(self.page.finish_correction_button.isVisible())
        self.assertEqual('correction', self.case.window.year_context_bar.property('yearContextState'))

    def assert_normal(self):
        self.assertIsNone(context.correction_state(self.case.db))
        self.assertTrue(context.is_year_physically_locked(self.case.db, 2026))
        self.assertEqual(2026, context.active_working_year(self.case.db))
        self.assertTrue(self.page.edit_locked_button.isVisible())
        self.assertTrue(self.page.edit_locked_button.isEnabled())
        self.assertTrue(self.page.finish_correction_button.isHidden())
        self.assertFalse(self.page.finish_correction_button.isEnabled())
        self.assertTrue(self.page.correction_reason.isEnabled())
        self.assertTrue(self.page.unlock_button.isEnabled())
        self.assertFalse(self.page.lock_button.isEnabled())
        self.assertNotIn('ΠΡΟΣΟΧΗ:', self.page.correction_banner.text())
        self.assertEqual('active', self.case.window.year_context_bar.property('yearContextState'))
        self.assertTrue(self.case.window.year_context_bar.return_button.isHidden())
        self.assertEqual(self.case.nav.targets['year_lock'].page, self.case.window._current_page_index())
        self.assertEqual(self.case.nav.items['settings'].index(), self.case.nav.tree.currentIndex())
        self.assertIs(self.page, self.holder.resolved_page())

    def test_owner_top_return_refreshes_and_allows_immediate_reentry_and_finish(self):
        self.enter_correction()
        with patch.object(self.case.nav, 'open', side_effect=AssertionError('Unexpected navigation')):
            QTest.mouseClick(self.case.window.year_context_bar.return_button, Qt.MouseButton.LeftButton)
            self.assert_normal()  # Assert synchronously, before any leave/return.
            self.enter_correction()
            QTest.mouseClick(self.page.finish_correction_button, Qt.MouseButton.LeftButton)
            self.assert_normal()
        self.assertEqual('', self.page.correction_reason.text())

    def test_return_no_preserves_correction_then_yes_updates_controls(self):
        self.enter_correction()
        before = self.case.snapshot()
        with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.No):
            QTest.mouseClick(self.case.window.year_context_bar.return_button, Qt.MouseButton.LeftButton)
        self.assertEqual(before, self.case.snapshot())
        self.assertIsNotNone(context.correction_state(self.case.db))
        self.assertFalse(self.page.edit_locked_button.isVisible())
        self.assertTrue(self.page.finish_correction_button.isEnabled())
        QTest.mouseClick(self.case.window.year_context_bar.return_button, Qt.MouseButton.LeftButton)
        self.assert_normal()

    def test_finish_no_then_yes_immediately_reflects_locked_state(self):
        self.enter_correction()
        before = self.case.snapshot()
        with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.No):
            QTest.mouseClick(self.page.finish_correction_button, Qt.MouseButton.LeftButton)
        self.assertEqual(before, self.case.snapshot())
        self.assertIsNotNone(context.correction_state(self.case.db))
        QTest.mouseClick(self.page.finish_correction_button, Qt.MouseButton.LeftButton)
        self.assert_normal()
        self.enter_correction()
        QTest.mouseClick(self.case.window.year_context_bar.return_button, Qt.MouseButton.LeftButton)
        self.assert_normal()

    def test_context_transitions_do_not_construct_unvisited_lazy_pages(self):
        from app.startup_lazy_pages import LazyPage
        unloaded = [p for _, p in self.case.window.pages if isinstance(p, LazyPage) and not p.is_loaded]
        self.assertGreater(len(unloaded), 20)
        self.enter_correction()
        QTest.mouseClick(self.case.window.year_context_bar.return_button, Qt.MouseButton.LeftButton)
        self.assertTrue(all(not p.is_loaded for p in unloaded))

    def test_loaded_context_pages_follow_old_year_and_return_without_reconstruction(self):
        self.case.db.execute('INSERT INTO year_locks(year,is_locked) VALUES(2025,1)')
        pages = {}
        for key in ('crop_program', 'declaration'):
            self.case.nav.open(key)
            pages[key] = self.case.window.pages[self.case.nav.targets[key].page][1].resolved_page()
        self.case.nav.open('year_lock')
        self.page.year.setCurrentIndex(self.page.year.findData(2025))
        self.enter_correction()
        self.assertEqual(2025, pages['crop_program'].season_year.value())
        self.assertEqual(2025, pages['declaration'].year.currentData())
        QTest.mouseClick(self.case.window.year_context_bar.return_active_button, Qt.MouseButton.LeftButton)
        self.assert_normal()
        self.assertEqual(2025, self.page.year.currentData())
        self.assertEqual(2026, pages['crop_program'].season_year.value())
        self.assertEqual(2026, pages['declaration'].year.currentData())
        for key, page in pages.items():
            self.assertIs(page, self.case.window.pages[self.case.nav.targets[key].page][1].resolved_page())


class OwnerYearSwitchTests(unittest.TestCase):
    def fixture(self):
        from tests.test_ui_revamp_phase1 import UiRevampTests
        UiRevampTests.setUpClass()
        case = UiRevampTests('test_small_window_scroll_and_dark_palette')
        case.setUp()
        self.addCleanup(case.doCleanups)
        return case

    def test_cancel_preserves_year_draft_page_and_database(self):
        case = self.fixture()
        case.nav.open('income')
        page = case.window.pages[4][1].resolved_page()
        page.description.setText('Unsaved owner draft')
        before = case.snapshot()
        bar = case.window.year_context_bar
        bar.year_selector.setEditText('2028')
        with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.No) as dialog:
            bar._apply_year()
        self.assertEqual(2027, context.active_working_year(case.db))
        self.assertEqual(before, case.snapshot())
        self.assertEqual('Unsaved owner draft', page.description.text())
        self.assertEqual(4, case.window._current_page_index())
        self.assertEqual('2027', bar.year_selector.currentText())
        self.assertEqual(2027, dialog.call_args.kwargs['current_year'])
        self.assertEqual(2028, dialog.call_args.kwargs['destination_year'])
        self.assertEqual(QMessageBox.StandardButton.No, dialog.call_args.args[5])

    def test_confirm_changes_year_and_preserves_existing_refresh_behavior(self):
        case = self.fixture()
        case.nav.open('production')
        page = case.window.pages[3][1].resolved_page()
        bar = case.window.year_context_bar
        bar.year_selector.setEditText('2028')
        with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.Yes) as dialog:
            bar._apply_year()
        self.assertEqual(2028, context.active_working_year(case.db))
        self.assertEqual(2028, page.date.date().year())
        self.assertEqual('question', dialog.call_args_list[0].args[1])
        self.assertEqual('information', dialog.call_args_list[1].args[1])
