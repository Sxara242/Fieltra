"""Batch 5 presentation contracts; synthetic profile data only."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractSpinBox, QMenu, QPlainTextEdit, QScrollArea, QStyle, QStyleOptionSpinBox
from shiboken6 import isValid

from app.database import Database
from app.money import MoneyPage
from app.production import ProductionPage
from app.products import ProductsPage
from app.date_preferences import format_iso_date, selected_date_format
from app.main_window import STYLESHEET, build_app_palette
from app.appearance_theme import DARK_STYLESHEET, _dark_palette
from app.crop_program_scheduling_ui import RuleDialog
from app.audit import AuditPage
from app import year_context
from tests.language_fixture import scoped_language
from tests.test_dashboard_theme_contrast import contrast


class Batch5UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.controller = self.enterContext(scoped_language(self.app, 'el'))
        keys = ('mastixaActiveWorkingYear', 'mastixaEffectiveWorkingYear', 'mastixaCorrectionYear', 'mastixaCorrectionReason')
        previous = {key: self.app.property(key) for key in keys}
        self.addCleanup(lambda: [self.app.setProperty(key, value) for key, value in previous.items()])
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.db = Database(self.root / 'ui.db')
        self.windows = []
        self.style, self.palette = self.app.styleSheet(), self.app.palette()
        self.addCleanup(self.cleanup_widgets)
        year_context.set_active_working_year(self.db, 2027, audit=False)

    def cleanup_widgets(self):
        for widget in reversed(self.windows):
            if isValid(widget):
                widget.close()
                widget.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.setStyleSheet(self.style)
        self.app.setPalette(self.palette)

    def keep(self, widget):
        self.windows.append(widget)
        return widget

    def snapshot(self):
        with self.db.connect() as con:
            return '\n'.join(con.iterdump())

    def test_money_cancel_dirty_pristine_and_no_write(self):
        for kind in ('income', 'expenses'):
            page = self.keep(MoneyPage(self.db, kind))
            before = self.snapshot()
            self.assertFalse(page.cancel_button.isEnabled())
            page.description.setText('draft')
            self.assertTrue(page.cancel_button.isEnabled())
            page.cancel_button.click()
            self.assertEqual('', page.description.text())
            self.assertFalse(page.cancel_button.isEnabled())
            self.assertIsNone(page.selected_money_id)
            self.assertEqual(before, self.snapshot())

    def test_money_all_meaningful_fields_enable_cancel(self):
        page = self.keep(MoneyPage(self.db, 'expenses'))
        field = self.db.execute("INSERT INTO fields(name) VALUES('A')")
        page.refresh()
        actions = [lambda: page.date.setDate(QDate(2027, 2, 3)),
                   lambda: page.field.setCurrentIndex(page.field.findData(field)),
                   lambda: page.category.setCurrentIndex(1),
                   lambda: page.partner.setEditText('raw partner'),
                   lambda: page.payment.setCurrentIndex(1),
                   lambda: page.amount.setValue(2), lambda: page.notes.setText('note')]
        for action in actions:
            page.clear_form()
            action()
            self.assertTrue(page.cancel_button.isEnabled())
        page.clear_form()
        page.description.setText('draft')
        page.description.clear()
        self.assertFalse(page.cancel_button.isEnabled())

    def test_money_sort_filter_identity_and_raw_dates(self):
        page = self.keep(MoneyPage(self.db, 'expenses'))
        ids = []
        for date, category, amount in [('2027-01-31','Άλλο',100),('2027-02-01','Εργασία',9),('2026-12-31','Άλλο',20),('2027-02-01','Άλλο',9)]:
            ids.append(self.db.execute("INSERT INTO expenses(entry_date,category,description,amount) VALUES(?,?,?,?)", (date,category,'needle',amount)))
        page.refresh()
        from app.year_lock import ensure_year_lock_schema
        ensure_year_lock_schema(self.db)
        before = self.snapshot()
        page.year_filter.setCurrentIndex(page.year_filter.findData(None))
        page.sort_order.setCurrentIndex(page.sort_order.findData('amount_asc'))
        shown = lambda: [page.table.item(i,0).data(Qt.ItemDataRole.UserRole) for i in range(page.table.rowCount()) if not page.table.isRowHidden(i)]
        self.assertEqual([ids[1],ids[3],ids[2],ids[0]], shown())
        page.sort_order.setCurrentIndex(page.sort_order.findData('date_asc'))
        self.assertEqual([ids[2],ids[0],ids[1],ids[3]], shown())
        page.category_filter.setCurrentIndex(page.category_filter.findData('Άλλο'))
        page.year_filter.setCurrentIndex(page.year_filter.findData('2027'))
        page.search.setText('needle')
        self.assertEqual([ids[0],ids[3]], shown())
        page.search.setText('absent')
        self.assertEqual([], shown())
        page.search.clear()
        page.category_filter.setCurrentIndex(0)
        page.load_selected(0,0)
        self.assertEqual(ids[0], page.selected_money_id)
        page.cancel_button.click()
        self.assertIsNone(page.selected_money_id)
        self.assertEqual(before,self.snapshot())

    def test_date_default_formats_legacy_and_iso_storage(self):
        self.assertEqual('DD/MM/YY', selected_date_format(self.db))
        for fmt, expected in [('DD/MM/YY','03/02/27'),('DD/MM/YYYY','03/02/2027'),('YYYY-MM-DD','2027-02-03')]:
            self.db.set_app_setting('date_display_format',fmt)
            page = self.keep(MoneyPage(self.db,'income'))
            page.date.setDate(QDate(2027,2,3))
            page.description.setText('raw')
            page.amount.setValue(9)
            page.save_money()
            self.assertEqual(expected,page.table.item(0,0).text())
            self.assertEqual('2027-02-03',self.db.query_one('SELECT entry_date FROM income ORDER BY id DESC')[0])
            self.assertEqual('legacy',format_iso_date('legacy',self.db))
            self.assertEqual('',format_iso_date('',self.db))

    def test_product_unit_requires_explicit_choice(self):
        page = self.keep(ProductsPage(self.db))
        self.assertEqual('',page.unit.currentText())
        page.name.setText('custom')
        before=self.snapshot()
        with patch('app.products.QMessageBox.warning') as warning:
            page.save_product()
        warning.assert_called_once()
        self.assertEqual(before,self.snapshot())

    def test_product_unit_typing_replaces_previous_unit(self):
        page = self.keep(ProductsPage(self.db))
        page.show()
        self.app.processEvents()
        page.unit.setCurrentText('τεμάχια')
        page.name.setFocus()
        self.app.processEvents()
        page.unit.lineEdit().setFocus()
        self.app.processEvents()
        QTest.keyClicks(page.unit.lineEdit(),'2')
        self.assertEqual('2',page.unit.currentText())

    def test_crop_arrows_have_clickable_geometry_both_themes(self):
        for dark in (False,True):
            self.app.setStyleSheet(STYLESHEET + (DARK_STYLESHEET if dark else ''))
            dialog=self.keep(RuleDialog())
            dialog.schedule_combo.setCurrentIndex(dialog.schedule_combo.findData('interval_window'))
            dialog.within_period_unit.setCurrentIndex(dialog.within_period_unit.findData('days'))
            dialog.show()
            self.app.processEvents()
            for spin in (dialog.base_year,dialog.every_years,dialog.every_days):
                option=QStyleOptionSpinBox();spin.initStyleOption(option)
                rect=spin.style().subControlRect(QStyle.ComplexControl.CC_SpinBox,option,QStyle.SubControl.SC_SpinBoxUp,spin)
                self.assertGreaterEqual(rect.height(),14)
                old=spin.value()
                QTest.mouseClick(spin,Qt.MouseButton.LeftButton,pos=rect.center())
                self.assertEqual(old+1,spin.value())
                QTest.keyClick(spin,Qt.Key.Key_Down)
                self.assertEqual(old,spin.value())

    def test_small_forms_have_reachable_scroll_content(self):
        for page in (MoneyPage(self.db,'income'),MoneyPage(self.db,'expenses'),ProductionPage(self.db)):
            self.keep(page)
            page.resize(640,400);page.show();self.app.processEvents()
            scroll=page.findChild(QScrollArea,'entryPageScroll')
            self.assertIsNotNone(scroll)
            self.assertGreater(scroll.verticalScrollBar().maximum(),0)
            for target in (page.save_button,page.table):
                scroll.ensureWidgetVisible(target)
                self.app.processEvents()
                self.assertTrue(target.isVisible())
            page.resize(1000,900);self.app.processEvents()
            page.resize(640,400);self.app.processEvents()
            self.assertGreater(scroll.verticalScrollBar().maximum(),0)

    def test_audit_empty_state_refresh_and_profile_isolation(self):
        page=self.keep(AuditPage(self.db))
        self.db.execute('DELETE FROM audit_events')
        page.refresh()
        self.assertEqual(0,page.table.rowCount())
        self.assertIn('Δεν υπάρχουν',page.empty_label.text())
        self.db.execute("INSERT INTO fields(name) VALUES('audit raw')")
        before=self.snapshot();page.refresh()
        self.assertGreater(page.table.rowCount(),0)
        self.assertTrue(page.empty_label.isHidden())
        self.assertEqual(before,self.snapshot())
        other=self.keep(AuditPage(Database(self.root/'other.db')))
        self.assertEqual(0,other.table.rowCount())

    def test_non_dashboard_metric_contrast(self):
        from app.inventory_report import InventoryReportPage
        for dark in (False,True):
            self.app.setPalette(_dark_palette() if dark else build_app_palette())
            self.app.setStyleSheet(STYLESHEET+(DARK_STYLESHEET if dark else ''))
            page=self.keep(InventoryReportPage(self.db))
            box,value=page.items_metric
            box.ensurePolished();value.ensurePolished()
            self.assertGreaterEqual(contrast(value.palette().color(QPalette.ColorRole.WindowText),box.palette().color(QPalette.ColorRole.Window)),4.5)

    def test_standard_coordinate_menu_disabled_contrast(self):
        self.app.setPalette(_dark_palette())
        self.app.setStyleSheet(STYLESHEET+DARK_STYLESHEET)
        editor=self.keep(QPlainTextEdit())
        menu=self.keep(editor.createStandardContextMenu())
        menu.ensurePolished()
        palette=menu.palette()
        self.assertGreaterEqual(contrast(palette.color(QPalette.ColorGroup.Disabled,QPalette.ColorRole.Text),palette.color(QPalette.ColorRole.Window)),3)

    def test_batch5_live_localization_and_raw_category(self):
        money = self.keep(MoneyPage(self.db, 'expenses'))
        products = self.keep(ProductsPage(self.db))
        audit = self.keep(AuditPage(self.db))
        for category in ('Εργασία', 'Παραγωγή <raw> {year}'):
            self.db.execute("INSERT INTO expenses(entry_date,category,description,amount) VALUES('2027-01-02',?,'raw',2)", (category,))
        money.refresh()
        self.db.execute('DELETE FROM audit_events')
        audit.refresh()
        before = self.snapshot()
        for code in ('el', 'en', 'el'):
            self.controller.set_language(code, persist=False)
            for page in (money, products, audit):
                self.controller.apply_to(page)
            english = code == 'en'
            self.assertEqual('Date: newest first' if english else 'Ημερομηνία: νεότερα πρώτα', money.sort_order.itemText(0))
            self.assertEqual('All categories' if english else 'Όλες οι κατηγορίες', money.category_filter.itemText(0))
            self.assertEqual('Select or enter a unit' if english else 'Επίλεξε ή γράψε μονάδα', products.unit.lineEdit().placeholderText())
            self.assertEqual('No history entries match the current filters.' if english else 'Δεν υπάρχουν εγγραφές ιστορικού με τα τρέχοντα φίλτρα.', audit.empty_label.text())
            index = money.category_filter.findData('Παραγωγή <raw> {year}')
            self.assertEqual('Παραγωγή <raw> {year}', money.category_filter.itemText(index))
            self.assertEqual(before, self.snapshot())

    def test_income_sort_and_filtered_delete_keep_record_identity(self):
        page = self.keep(MoneyPage(self.db, 'income'))
        from app.year_lock import ensure_year_lock_schema
        ensure_year_lock_schema(self.db)
        ids = [self.db.execute("INSERT INTO income(entry_date,description,amount) VALUES(?,?,?)", row)
               for row in [('2027-02-01', 'large', 100), ('2027-01-31', 'small', 9)]]
        page.refresh()
        for fmt in ('DD/MM/YY', 'DD/MM/YYYY', 'YYYY-MM-DD'):
            self.db.set_app_setting('date_display_format', fmt)
            page.refresh()
            page.sort_order.setCurrentIndex(page.sort_order.findData('date_asc'))
            self.assertEqual(ids[1], page.table.item(0, 0).data(Qt.ItemDataRole.UserRole))
            page.sort_order.setCurrentIndex(page.sort_order.findData('amount_desc'))
            self.assertEqual(ids[0], page.table.item(0, 0).data(Qt.ItemDataRole.UserRole))
        page.search.setText('small')
        visible = next(r for r in range(page.table.rowCount()) if not page.table.isRowHidden(r))
        page.load_selected(visible, 0)
        self.assertEqual(ids[1], page.selected_money_id)
        with patch.object(page, 'confirm_delete', return_value=True):
            page.delete_money()
        self.assertEqual([ids[0]], [r['id'] for r in self.db.query('SELECT id FROM income')])

    def test_core_table_dates_follow_preference_without_data_mutation(self):
        from app.sales import SalesPage
        from app.sales_report import SalesReportPage
        from app.activities import ActivitiesPage
        from app.labor import LaborPage
        from app.plantings import PlantingsPage
        from app.inventory import InventoryPage
        production = self.keep(ProductionPage(self.db))
        sales = self.keep(SalesPage(self.db))
        report = self.keep(SalesReportPage(self.db))
        activities = self.keep(ActivitiesPage(self.db))
        labor = self.keep(LaborPage(self.db))
        plantings = self.keep(PlantingsPage(self.db))
        inventory = self.keep(InventoryPage(self.db))
        products = self.keep(ProductsPage(self.db))
        field = self.db.execute("INSERT INTO fields(name) VALUES('Date field')")
        product = self.db.execute("INSERT INTO products(name,unit) VALUES('Date product','τεμάχια')")
        self.db.execute("INSERT INTO production(entry_date,field_id,product,product_id,quantity_kg) VALUES('2027-02-03',?,'Date product',?,10)", (field, product))
        self.db.execute("INSERT INTO production_sales(sale_date,buyer_name,product,product_id,quantity_kg,price_per_kg,total_amount) VALUES('2027-02-03','Buyer','Date product',?,2,3,6)", (product,))
        self.db.execute("INSERT INTO farm_activities(activity_date,category,status) VALUES('2027-02-03','Πότισμα','Προγραμματισμένη')")
        worker = self.db.execute("INSERT INTO workers(name) VALUES('Worker')")
        self.db.execute("INSERT INTO labor_entries(work_date,worker_id,work_type,hours,hourly_rate,cost) VALUES('2027-02-03',?,'Work',2,3,6)", (worker,))
        self.db.execute("INSERT INTO planting_batches(planting_date,field_id) VALUES('2027-02-03',?)", (field,))
        item = self.db.execute("INSERT INTO inventory_items(name,category,unit) VALUES('Input','Λιπάσματα','kg')")
        self.db.execute("INSERT INTO inventory_movements(movement_date,item_id,movement_type,quantity) VALUES('2027-02-03',?,'Παραλαβή',2)", (item,))
        self.db.execute("INSERT INTO product_fields(product_id,field_id,planting_date) VALUES(?,?,'2027-02-03')", (product, field))
        pages = [(production, production.table, 0), (sales, sales.table, 0), (report, report.detail_table, 0),
                 (activities, activities.table, 0), (labor, labor.entry_table, 0), (plantings, plantings.table, 0),
                 (inventory, inventory.movement_table, 0), (products, products.links_table, 5)]
        for page, _, _ in pages:
            page.refresh()
        for fmt, shown in [('DD/MM/YY', '03/02/27'), ('DD/MM/YYYY', '03/02/2027'), ('YYYY-MM-DD', '2027-02-03')]:
            self.db.set_app_setting('date_display_format', fmt)
            before = self.snapshot()
            for page, table, col in pages:
                with self.subTest(page=type(page).__name__, fmt=fmt):
                    page.refresh()
                    self.assertEqual(shown, table.item(0, col).text())
            self.assertEqual(before, self.snapshot())
        self.assertEqual('10 τεμάχια', production.table.item(0, 3).text())
        self.assertEqual('2 τεμάχια', sales.table.item(0, 3).text())

    def test_audit_installs_missing_table_triggers_on_later_refresh(self):
        from app.declaration import DeclarationPage
        page = self.keep(AuditPage(self.db))
        self.assertIsNone(self.db.query_one("SELECT name FROM sqlite_master WHERE name='cultivation_declarations'"))
        self.keep(DeclarationPage(self.db))
        page.refresh()
        self.assertIsNotNone(self.db.query_one("SELECT name FROM sqlite_master WHERE name='audit_declaration_insert'"))
        self.db.execute("INSERT INTO cultivation_declarations(declaration_year,status) VALUES(2027,'draft')")
        page.refresh()
        self.assertIsNotNone(self.db.query_one("SELECT id FROM audit_events WHERE table_name='cultivation_declarations' AND action='INSERT'"))

    def test_custom_unit_is_stored_exactly_and_reset_to_blank(self):
        page = self.keep(ProductsPage(self.db))
        raw = 'κιβώτια / XL 2'
        page.name.setText('Custom unit')
        page.unit.setCurrentText(raw)
        page.save_product()
        self.assertEqual(raw, self.db.query_one("SELECT unit FROM products WHERE name='Custom unit'")[0])
        self.assertEqual('', page.unit.currentText())

    def test_short_display_keeps_free_text_century_unambiguous(self):
        from app.date_preferences import date_placeholder, parse_user_date_to_iso
        self.assertEqual('DD/MM/YYYY', date_placeholder(self.db))
        self.assertEqual('1927-02-03', parse_user_date_to_iso('03/02/1927', self.db))
        self.assertEqual('2027-02-03', parse_user_date_to_iso('03/02/2027', self.db))
        with self.assertRaises(ValueError):
            parse_user_date_to_iso('03/02/27', self.db)

    def test_plant_text_date_round_trip_preserves_historical_year(self):
        from app import date_preferences
        from app.plant_tracking import PlantRecord
        from app.plant_tracking_ui import PlantDialog
        field = self.db.execute("INSERT INTO fields(name) VALUES('Historical field')")
        plant = PlantRecord(id='old-tree', field_id=str(field), label='Historical', planted_date='1927-02-03')
        with patch.object(PlantDialog, '__init__', PlantDialog.__init__), patch.object(PlantDialog, 'record', PlantDialog.record):
            date_preferences._install_plant_date_text_fix()
            for fmt, shown in [('DD/MM/YY', '03/02/1927'), ('DD/MM/YYYY', '03/02/1927'), ('YYYY-MM-DD', '1927-02-03')]:
                self.db.set_app_setting('date_display_format', fmt)
                before = self.snapshot()
                dialog = self.keep(PlantDialog(self.db, plant))
                self.assertEqual(shown, dialog.planted_date.text())
                self.assertEqual('1927-02-03', dialog.record().planted_date)
                self.assertEqual(before, self.snapshot())

    def test_settings_choices_persist_per_profile(self):
        from app import date_preferences
        from app.settings import SettingsPage
        from app.profile_manager import ProfileManager
        manager = ProfileManager(self.root / 'settings-profiles')
        args = (Mock(theme='light'), manager, self.controller)
        with patch.object(SettingsPage, '_build_general_tab', SettingsPage._build_general_tab), patch.object(SettingsPage, 'refresh', SettingsPage.refresh):
            date_preferences._install_settings_controls()
            settings = self.keep(SettingsPage(self.db, *args))
            combo = settings.date_format_combo
            self.assertEqual(['dd/MM/yy', 'dd/MM/yyyy', 'yyyy-MM-dd'], [combo.itemText(i) for i in range(combo.count())])
            combo.setCurrentIndex(combo.findData('YYYY-MM-DD'))
            reopened = self.keep(SettingsPage(Database(self.db.path), *args))
            self.assertEqual('YYYY-MM-DD', reopened.date_format_combo.currentData())
            other = self.keep(SettingsPage(Database(self.root/'other-settings.db'), *args))
            self.assertEqual('DD/MM/YY', other.date_format_combo.currentData())

    def test_report_alert_metric_caption_and_heading_contrast(self):
        from app import appearance_theme
        from app.alerts import AlertsPage
        from app.field_finance import FieldFinancePage
        from app.reports import ReportsPage
        from PySide6.QtWidgets import QLabel, QGroupBox
        with patch.object(appearance_theme, '_SETTINGS_FILE', self.root/'appearance.ini'):
            theme = appearance_theme.ThemeController(self.app, STYLESHEET, build_app_palette())
            try:
                pages = [self.keep(cls(self.db)) for cls in (AlertsPage, FieldFinancePage, ReportsPage)]
                for mode in ('light', 'dark', 'light'):
                    theme.set_theme(mode, persist=False)
                    for page in pages:
                        theme.apply_to(page)
                        cards = page.findChildren(QGroupBox, 'metricCard')
                        self.assertTrue(cards)
                        for card in cards:
                            card.ensurePolished()
                            for label in card.findChildren(QLabel):
                                label.ensurePolished()
                                minimum = 4.5 if mode == 'dark' or label.objectName() == 'metricValue' else 4.0
                                self.assertGreaterEqual(contrast(label.palette().color(QPalette.ColorRole.WindowText), card.palette().color(QPalette.ColorRole.Window)), minimum)
                        for box in page.findChildren(QGroupBox):
                            box.ensurePolished()
                            self.assertGreaterEqual(contrast(box.palette().color(QPalette.ColorRole.WindowText), box.palette().color(QPalette.ColorRole.Window)), 4.5)
            finally:
                self.app.removeEventFilter(theme)
                theme.deleteLater()

    def test_coordinate_menu_light_dark_normal_disabled_selected(self):
        from PySide6.QtGui import QColor
        for dark in (False, True):
            self.app.setPalette(_dark_palette() if dark else build_app_palette())
            self.app.setStyleSheet(STYLESHEET + (DARK_STYLESHEET if dark else ''))
            editor = self.keep(QPlainTextEdit('26.00000000 38.00000000'))
            menu = self.keep(editor.createStandardContextMenu())
            menu.ensurePolished()
            palette = menu.palette()
            self.assertTrue(any(not action.isEnabled() for action in menu.actions() if not action.isSeparator()))
            self.assertGreaterEqual(contrast(palette.color(QPalette.ColorRole.WindowText), palette.color(QPalette.ColorRole.Window)), 4.5)
            self.assertGreaterEqual(contrast(palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text), palette.color(QPalette.ColorRole.Window)), 3)
            # Actual selected-item stylesheet colors; disabled/normal use Qt palette.
            style = DARK_STYLESHEET if dark else STYLESHEET
            import re
            rule = re.search(r'QMenu::item:selected\s*\{([^}]+)', style).group(1)
            background = re.search(r'background:\s*([^;]+)', rule).group(1)
            foreground = re.search(r'(?<!-)color:\s*([^;]+)', rule).group(1)
            self.assertGreaterEqual(contrast(QColor(foreground), QColor(background)), 4.5)

    def test_scrolling_brings_actions_inside_viewport_after_restore(self):
        from PySide6.QtCore import QPoint, QRect
        for page in (MoneyPage(self.db, 'income'), MoneyPage(self.db, 'expenses'), ProductionPage(self.db)):
            self.keep(page)
            page.show()
            for width, height in ((640, 400), (1200, 900), (640, 400)):
                page.resize(width, height)
                self.app.processEvents()
                scroll = page.findChild(QScrollArea, 'entryPageScroll')
                for target in (page.date, page.save_button, page.cancel_button, page.table):
                    scroll.ensureWidgetVisible(target, 0, 0)
                    # QDateEdit.ensureWidgetVisible targets its cursor, not its
                    # full rectangle. Exercise both scrollbars as an owner can.
                    if target is not page.table:
                        center = target.mapTo(scroll.widget(), target.rect().center())
                        scroll.ensureVisible(center.x(), center.y(), target.width() // 2 + 1, target.height() // 2 + 1)
                    self.app.processEvents()
                    rectangle = QRect(target.mapTo(scroll.viewport(), QPoint()), target.size())
                    self.assertTrue(scroll.viewport().rect().intersects(rectangle))
                    if target is not page.table:
                        self.assertTrue(scroll.viewport().rect().contains(rectangle), (type(page).__name__, width, height, type(target).__name__, rectangle, scroll.viewport().rect()))
