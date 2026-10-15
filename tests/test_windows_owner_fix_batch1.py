"""Windows owner acceptance regressions, using disposable profiles only."""
import importlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.database import Database
from app import year_context as context
from tests.language_fixture import scoped_language


class OwnerFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from PySide6.QtGui import QFontDatabase
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')

    def setUp(self):
        self.enterContext(scoped_language(self.app, 'el'))
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.db = Database(self.root / 'owner.db')
        context.set_active_working_year(self.db, 2025, audit=False)
        self.pages = []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        context.finish_year_correction(self.db)
        for page in self.pages:
            page.close()
            page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def page(self, module, name, *args):
        page = getattr(importlib.import_module('app.' + module), name)(self.db, *args)
        self.pages.append(page)
        return page

    def test_empty_active_year_default_and_managed_years(self):
        context.is_year_physically_locked(self.db, 2024)
        self.db.execute('INSERT INTO year_locks(year,is_locked) VALUES(2024,0)')
        for module, cls, args, attr in (
            ('production', 'ProductionPage', (), 'year_filter'),
            ('money', 'MoneyPage', ('income',), 'year_filter'),
            ('money', 'MoneyPage', ('expenses',), 'year_filter'),
            ('sales', 'SalesPage', (), 'year_filter'),
            ('activities', 'ActivitiesPage', (), 'year_filter'),
            ('labor', 'LaborPage', (), 'year_filter'),
            ('plantings', 'PlantingsPage', (), 'year_filter'),
            ('plant_protection', 'PlantProtectionPage', (), 'year_filter'),
            ('inventory', 'InventoryPage', (), 'year_filter'),
            ('reports', 'ReportsPage', (), 'year'),
            ('farm_calendar', 'FarmCalendarPage', (), 'year'),
            ('field_finance', 'FieldFinancePage', (), 'year'),
            ('sales_report', 'SalesReportPage', (), 'year_filter'),
            ('annual_report', 'AnnualFarmReportPage', (), 'year_filter'),
            ('upload_center', 'UploadCenterPage', (), 'year'),
            ('equipment', 'EquipmentPage', (), 'year_filter'),
        ):
            with self.subTest(page=module, args=args):
                page = self.page(module, cls, *args)
                combo = getattr(page, attr)
                self.assertEqual('2025', str(combo.currentData()))
                self.assertIn('2024', [str(combo.itemData(i)) for i in range(combo.count())])
                combo.setCurrentIndex(combo.findText('2024'))
                page.refresh()
                self.assertEqual('2024', str(combo.currentData()))
                context.set_active_working_year(self.db, 2023, audit=False)
                page.refresh_year_context_ui()
                self.assertEqual('2023', str(combo.currentData()))
                context.set_active_working_year(self.db, 2025, audit=False)

    def test_master_data_visible_across_years(self):
        specs = (
            ('fields', 'FieldsPage', 'fields', "INSERT INTO fields(name) VALUES('Field')", 'table'),
            ('products', 'ProductsPage', 'products', "INSERT INTO products(name,unit) VALUES('Product','kg')", 'table'),
            ('labor', 'LaborPage', 'workers', "INSERT INTO workers(name) VALUES('Worker')", 'worker_table'),
            ('equipment', 'EquipmentPage', 'equipment', "INSERT INTO equipment(name) VALUES('Machine')", 'equipment_table'),
            ('partners', 'PartnersPage', 'business_partners', "INSERT INTO business_partners(name,partner_type) VALUES('Buyer','buyer')", 'table'),
        )
        self.page('sales', 'SalesPage')
        self.page('invoice_documents', 'InvoiceDocumentsPage')
        for module, cls, table, insert, table_attr in specs:
            page = self.page(module, cls)
            record = self.db.execute(insert)
            for year in (2023, 2025, 2027):
                context.set_active_working_year(self.db, year, audit=False)
                page.refresh_year_context_ui()
                widget = getattr(page, table_attr)
                self.assertGreater(widget.rowCount(), 0, module)
                self.assertIsNotNone(self.db.query_one(f'SELECT * FROM {table} WHERE id=?', (record,)))
        product = self.db.query_one('SELECT id FROM products')[0]
        field = self.db.query_one('SELECT id FROM fields')[0]
        self.db.execute('INSERT INTO product_fields(product_id,field_id) VALUES(?,?)', (product, field))
        self.db.execute("UPDATE producer SET name='Owner profile' WHERE id=1")
        context.set_active_working_year(self.db, 2022, audit=False)
        self.assertIsNotNone(self.db.query_one('SELECT * FROM product_fields WHERE product_id=? AND field_id=?', (product, field)))
        self.assertEqual('Owner profile', self.db.query_one('SELECT name FROM producer')[0])

    def test_navigation_defaults_then_keeps_manual_report_year_on_page(self):
        self.db.execute("INSERT INTO production(entry_date,product,quantity_kg) VALUES('2026-01-01','P',12)")
        page = self.page('annual_report', 'AnnualFarmReportPage')
        page.show()
        self.app.processEvents()
        self.assertEqual(2025, page.year_filter.currentData())
        page.year_filter.setCurrentIndex(page.year_filter.findData(2026))
        page.refresh()
        self.app.processEvents()
        self.assertEqual(2026, page.year_filter.currentData())
        page.hide()
        page.show()
        self.app.processEvents()
        self.assertEqual(2025, page.year_filter.currentData())

    def test_cached_transaction_controls_correction_relock_preserves_draft(self):
        for kind in ('income', 'expenses'):
            page = self.page('money', 'MoneyPage', kind)
            page.description.setText('Original')
            page.amount.setValue(12)
            page.save_money()
            page.load_selected(0, 0)
            identity = page.selected_money_id
            page.description.setText('Correction draft')
            self.lock()
            page.refresh_year_context_ui()
            self.assertFalse(page.save_button.isEnabled())
            self.assertFalse(page.delete_button.isEnabled())
            with patch('app.money.warn_locked_year'):
                page.save_money()
                page.delete_money()
            self.assertEqual('Original', self.db.query_one(f'SELECT description FROM {kind} WHERE id=?', (identity,))[0])
            context.begin_year_correction(self.db, 2025, 'Legitimate edit')
            page.refresh_year_context_ui()
            self.assertTrue(page.save_button.isEnabled())
            self.assertTrue(page.delete_button.isEnabled())
            self.assertEqual('Correction draft', page.description.text())
            page.save_money()
            self.assertEqual('Correction draft', self.db.query_one(f'SELECT description FROM {kind} WHERE id=?', (identity,))[0])
            page.load_selected(0, 0)
            context.finish_year_correction(self.db)
            page.refresh_year_context_ui()
            self.assertFalse(page.save_button.isEnabled())
            self.assertFalse(page.delete_button.isEnabled())
            self.db.execute('UPDATE year_locks SET is_locked=0 WHERE year=2025')

    def test_common_locked_update_delete_enforcement(self):
        row = self.db.execute("INSERT INTO production(entry_date,product,quantity_kg) VALUES('2025-01-01','P',12)")
        context.is_year_physically_locked(self.db, 2025)
        self.db.execute('INSERT INTO year_locks(year,is_locked) VALUES(2025,1)')
        for sql, params in (
            ("INSERT INTO production(entry_date,product,quantity_kg) VALUES('2025-01-02','P',1)", ()),
            ('UPDATE production SET quantity_kg=13 WHERE id=?', (row,)),
            ("UPDATE production SET entry_date='2026-01-01' WHERE id=?", (row,)),
            ('DELETE FROM production WHERE id=?', (row,)),
        ):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                self.db.execute(sql, params)
        self.assertEqual(12, self.db.query_one('SELECT quantity_kg FROM production WHERE id=?', (row,))[0])

    def test_production_correction_before_sales_page_exists(self):
        page = self.page('production', 'ProductionPage')
        self.assertIsNone(self.db.query_one("SELECT 1 FROM sqlite_master WHERE name='production_sales'"))
        product = self.db.execute("INSERT INTO products(name,unit) VALUES('First production','kg')")
        field = self.db.execute("INSERT INTO fields(name) VALUES('First field')")
        page.refresh()
        page.product.setCurrentIndex(page.product.findData(product))
        page.field.setCurrentIndex(page.field.findData(field))
        page.quantity.setValue(12)
        page.save_production()
        page.load_selected(0, 0)
        identity = page.selected_production_id
        self.lock()
        page.refresh_year_context_ui()
        self.assertFalse(page.save_button.isEnabled())
        context.begin_year_correction(self.db, 2025, 'Production before Sales')
        page.refresh_year_context_ui()
        self.assertTrue(page.save_button.isEnabled())
        page.quantity.setValue(13)
        page.save_production()
        self.assertEqual(13, self.db.query_one('SELECT quantity_kg FROM production WHERE id=?', (identity,))[0])
        page.product.setCurrentIndex(page.product.findData(product))
        page.field.setCurrentIndex(page.field.findData(field))
        page.quantity.setValue(3)
        page.save_production()
        self.assertEqual(2, self.db.query_one('SELECT COUNT(*) FROM production')[0])
        page.load_selected(0, 0)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            page.delete_production()
        self.assertEqual(1, self.db.query_one('SELECT COUNT(*) FROM production')[0])

    def test_numeric_zero_is_empty_and_first_typing_replaces_it(self):
        from app.widgets import money_input, quantity_input, area_input
        for factory in (money_input, quantity_input, area_input):
            with self.subTest(factory=factory.__name__):
                widget = factory()
                self.pages.append(widget)
                self.assertEqual('', widget.lineEdit().text())
                self.assertTrue(widget.lineEdit().placeholderText())
                widget.show()
                widget.setFocus()
                QTest.keyClicks(widget, '12')
                widget.interpretText()
                self.assertEqual(12, widget.value())

    def lock(self, year=2025):
        context.is_year_physically_locked(self.db, year)
        self.db.execute('INSERT OR REPLACE INTO year_locks(year,is_locked,reason) VALUES(?,1,?)', (year, 'Owner lock'))

    def test_cross_module_connection_guards_and_reasoned_corrections(self):
        from app.year_write_policy import DATED_TABLES
        # Test every common policy route independently of UI-button disabling,
        # including raw execute/executemany on a connection and transaction writes.
        for table, expression in DATED_TABLES.items():
            with self.subTest(table=table):
                db = Database(self.root / (table + '.db'))
                context.set_active_working_year(db, 2026, audit=False)
                context.is_year_physically_locked(db, 2025)
                date = expression.split('SUBSTR(')[1].split(',')[0] if 'SUBSTR(' in expression else expression
                if table not in ('production', 'income', 'expenses'):
                    db.execute(f'CREATE TABLE {table}(id INTEGER PRIMARY KEY,{date} TEXT,notes TEXT)')
                else:
                    required = {'production': "product,quantity_kg", 'income': 'description,amount', 'expenses': 'category,description,amount'}[table]
                    values = {'production': "'P',12", 'income': "'Entry',12", 'expenses': "'Other','Entry',12"}[table]
                raw_date = 2025 if date == 'declaration_year' else '2025-01-02'
                if table in ('production', 'income', 'expenses'):
                    insert = f'INSERT INTO {table}({date},{required}) VALUES(?,{values})'
                else:
                    insert = f'INSERT INTO {table}({date}) VALUES(?)'
                row = db.execute(insert, (raw_date,))
                db.execute('CREATE TABLE audit_events(id INTEGER PRIMARY KEY,event_time TEXT,table_name TEXT,action TEXT,record_id TEXT,details TEXT)')
                db.execute('INSERT INTO year_locks(year,is_locked) VALUES(2025,1)')
                update = f'UPDATE {table} SET {date}=? WHERE id=?'
                delete = f'DELETE FROM {table} WHERE id=?'
                for sql, params in ((insert, (raw_date,)), (update, (raw_date, row)), (delete, (row,))):
                    with self.assertRaises(sqlite3.IntegrityError), db.transaction() as tx:
                        tx.execute(sql, params)
                with db.connect() as connection:
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.executemany(update, [(raw_date, row)])
                state = context.begin_year_correction(db, 2025, 'Correction reason Ω')
                self.assertEqual(2026, state.active_year)
                self.assertTrue(context.is_year_physically_locked(db, 2025))
                new = db.execute(insert, (raw_date,))
                db.execute(update, (raw_date, row))
                db.execute(delete, (new,))
                logs = db.query("SELECT * FROM audit_events WHERE table_name=?", (table,))
                self.assertEqual(['INSERT', 'UPDATE', 'DELETE'], [r['action'] for r in logs])
                self.assertTrue(all('Correction reason Ω' in r['details'] for r in logs))
                context.finish_year_correction(db)
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(update, (raw_date, row))
                self.assertEqual('ok', db.query_one('PRAGMA integrity_check')[0])

    def test_locked_source_and_target_years_and_transaction_rollback(self):
        row = self.db.execute("INSERT INTO income(entry_date,description,amount) VALUES('2026-01-01','Open',10)")
        self.lock()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE income SET entry_date='2025-01-01' WHERE id=?", (row,))
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.transaction() as tx:
                tx.execute("UPDATE income SET amount=99 WHERE id=?", (row,))
                tx.execute("INSERT INTO expenses(entry_date,category,description,amount) VALUES('2025-01-01','Other','Blocked',12)")
        self.assertEqual(10, self.db.query_one('SELECT amount FROM income WHERE id=?', (row,))[0])
        context.begin_year_correction(self.db, 2025, 'Scoped')
        self.lock(2024)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO production(entry_date,product,quantity_kg) VALUES('2024-01-01','P',12)")
        other = Database(self.root / 'other.db')
        context.is_year_physically_locked(other, 2025)
        other.execute('INSERT INTO year_locks(year,is_locked) VALUES(2025,1)')
        with self.assertRaises(sqlite3.IntegrityError):
            other.execute("INSERT INTO income(entry_date,description,amount) VALUES('2025-01-01','Scoped',12)")
        context.initialize_year_context(self.db)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO income(entry_date,description,amount) VALUES('2025-01-01','Restart',12)")

    def test_connection_open_before_correction_observes_session_exit(self):
        self.lock()
        with self.db.connect() as connection:
            context.begin_year_correction(self.db, 2025, 'Short session')
            connection.execute("INSERT INTO income(entry_date,description,amount) VALUES('2025-01-01','Correction',12)")
            connection.commit()
            context.finish_year_correction(self.db)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE income SET amount=13")

    def test_produced_stock_carryover_and_annual_sales_metrics(self):
        sale = self.page('sales', 'SalesPage')
        product = self.db.execute("INSERT INTO products(name,unit) VALUES('Mastixa','kg')")
        self.db.execute("INSERT INTO production(entry_date,product,product_id,quantity_kg) VALUES('2024-01-01','Mastixa',?,120)", (product,))
        self.db.execute("INSERT INTO production_sales(sale_date,product,product_id,quantity_kg,price_per_kg,total_amount) VALUES('2024-02-01','Mastixa',?,101,1,101)", (product,))
        warehouse = self.page('inventory', 'InventoryPage')
        warehouse.item_name.setText('Supply')
        warehouse.initial_stock.setText('5')
        warehouse.save_item()
        for year in (2025, 2026, 2023):
            context.set_active_working_year(self.db, year, audit=False)
            warehouse.refresh_year_context_ui()
            self.assertEqual(['Mastixa', 'kg', '120', '101', '19'],
                [warehouse.produced_stock_table.item(0, c).text() for c in range(5)])
            self.assertEqual(1, self.db.query_one('SELECT COUNT(*) FROM inventory_items')[0])
            self.assertEqual(5, warehouse._current_stock(1))
            sale.refresh_year_context_ui()
            sale.product_filter.setCurrentIndex(sale.product_filter.findData(product))
            self.assertEqual('0 kg', sale.produced_metric[1].text())
            self.assertEqual('0 kg', sale.sold_metric[1].text())
            self.assertEqual('19 kg', sale.stock_metric[1].text())

    def test_numeric_decimal_replacement_delete_paste_suffix_and_limits(self):
        from app.widgets import money_input, quantity_input
        from app.numeric_inputs import NumericSpinBox, NumericLineEdit, DecimalValidator
        for factory in (money_input, quantity_input, NumericSpinBox):
            widget = factory()
            self.pages.append(widget)
            widget.setRange(-100, 100)
            widget.show()
            widget.setFocus()
            self.app.processEvents()
            for text, expected in (('12', 12), ('0', 0), ('-12', -12)):
                widget.lineEdit().selectAll()
                QTest.keyClicks(widget, text)
                widget.interpretText()
                self.assertEqual(expected, widget.value())
            if factory != NumericSpinBox:
                for text in ('12,5', '12.5'):
                    widget.lineEdit().selectAll()
                    QTest.keyClicks(widget, text)
                    widget.interpretText()
                    self.assertEqual(12.5, widget.value())
                self.app.clipboard().setText('12,25')
                widget.lineEdit().selectAll()
                QTest.keyClick(widget, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
                widget.interpretText()
                self.assertEqual(12.25, widget.value())
                self.assertEqual(widget.validate('12.5,2', 6)[0].name, 'Invalid')
                self.assertEqual(widget.validate('101', 3)[0].name, 'Invalid')
                self.assertEqual(widget.validate('12.12345', 8)[0].name, 'Invalid')
                widget.clearFocus()
                self.app.processEvents()
                self.assertTrue(widget.text().endswith(widget.suffix()))
            for key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                widget.setFocus()
                widget.lineEdit().selectAll()
                QTest.keyClick(widget, key)
                widget.interpretText()
                self.assertEqual(0, widget.value())
                self.assertEqual('', widget.lineEdit().text())
        line = NumericLineEdit()
        self.pages.append(line)
        line.setValidator(DecimalValidator(0, 100, 3, line))
        line.setText('0')
        self.assertEqual('', line.text())
        line.show()
        line.setFocus()
        QTest.keyClicks(line, '12,25')
        self.assertEqual('12,25', line.text())
        self.assertTrue(line.hasAcceptableInput())

    def test_year_selection_validation_and_cancel(self):
        bar = self.page('year_context_ui', 'YearContextBar')
        def select(year):
            bar.year_selector.setEditText(str(year))
            bar._apply_year()
        with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.Yes):
            select(2026)
            self.assertEqual(2026, context.active_working_year(self.db))
            select(2025)
            self.assertEqual(2025, context.active_working_year(self.db))
        with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.No):
            select(2024)
            self.assertEqual(2025, context.active_working_year(self.db))
            self.assertEqual('2025', bar.year_selector.currentText())
        self.assertEqual(0, self.db.query_one('SELECT COUNT(*) FROM year_locks')[0])
        for year in (context.MIN_YEAR, context.MAX_YEAR):
            context.set_active_working_year(self.db, year, audit=False)
            bar.refresh()
            self.assertEqual(str(year), bar.year_selector.currentText())
            with patch('app.year_context_ui._message') as dialog:
                select(year)
                dialog.assert_not_called()

    def test_two_correction_exit_actions_and_cancel(self):
        context.set_active_working_year(self.db, 2026, audit=False)
        self.lock()
        bar = self.page('year_context_ui', 'YearContextBar')
        for return_active, expected in ((False, 2025), (True, 2026)):
            context.set_active_working_year(self.db, 2026, audit=False)
            context.begin_year_correction(self.db, 2025, 'Correction')
            bar.refresh()
            self.assertEqual(2026, context.active_working_year(self.db))
            self.assertEqual(2025, context.effective_working_year(self.db))
            self.assertEqual('Έξοδος από προσωρινή διόρθωση', bar.return_button.text())
            self.assertIn('2026', bar.return_active_button.text())
            button = bar.return_active_button if return_active else bar.return_button
            with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.No):
                button.click()
            self.assertIsNotNone(context.correction_state(self.db))
            with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.Yes):
                button.click()
            self.assertIsNone(context.correction_state(self.db))
            self.assertEqual(expected, context.effective_working_year(self.db))
            self.assertTrue(context.is_year_write_blocked(self.db, 2025))

    def test_year_management_default_and_actual_confirmation(self):
        self.lock(2027)
        page = self.page('year_context_ui', 'EnhancedYearLockPage')
        self.assertEqual(2025, page.year.currentData())
        page.show()
        page.year.setCurrentIndex(page.year.findData(2027))
        self.assertIn('2027', page.correction_banner.text())
        self.assertIn('2025', page.correction_banner.text())
        page.correction_reason.setText('Reason')
        with patch('app.year_context_ui._message', return_value=QMessageBox.StandardButton.No) as dialog:
            page.begin_correction()
        self.assertEqual(2027, dialog.call_args.kwargs['year'])
        page.refresh()
        self.assertEqual(2027, page.year.currentData())

    def test_annual_export_weighted_per_product_averages_and_no_sales(self):
        from app.annual_report_exports import annual_html, export_annual_pdf, product_average_text
        from PySide6.QtPdf import QPdfDocument
        self.page('sales', 'SalesPage')
        products = []
        for name, unit, quantity in (('Mastixa', 'kg', 120), ('Product B', 'piece', 40), ('Unsold', 'L', 5)):
            product = self.db.execute('INSERT INTO products(name,unit) VALUES(?,?)', (name, unit))
            products.append(product)
            self.db.execute("INSERT INTO production(entry_date,product,product_id,quantity_kg) VALUES('2025-01-01',?,?,?)", (name, product, quantity))
        for product, quantity, price in ((products[0], 20, .5), (products[0], 20, 1.5), (products[1], 10, 2.5)):
            income = self.db.execute("INSERT INTO income(entry_date,description,amount) VALUES('2025-02-01','Sale',?)", (quantity * price,))
            self.db.execute("INSERT INTO production_sales(sale_date,product,product_id,quantity_kg,price_per_kg,total_amount,income_id) VALUES('2025-02-01','',?,?,?,?,?)", (product, quantity, price, quantity * price, income))
        page = self.page('annual_report', 'AnnualFarmReportPage')
        self.assertEqual(2025, page.year_filter.currentData())
        snapshot = page._annual_report_snapshot()
        self.assertEqual(65, snapshot.sales_revenue)
        self.assertEqual(65, snapshot.net_result)
        self.assertEqual('—', page.avg_price_metric[1].text())
        self.assertEqual(['1 €/kg', '2.5 €/piece', '—'], [product_average_text(row) for row in snapshot.products])
        html = annual_html(snapshot)
        self.assertIn('1 €/kg', html)
        self.assertIn('2.5 €/piece', html)
        destination = self.root / 'annual.pdf'
        export_annual_pdf(destination, snapshot)
        import os, shutil
        if os.environ.get('MASTIXA_DATA_HOME'):
            shutil.copyfile(destination, Path(os.environ['MASTIXA_DATA_HOME']).parent / 'annual-per-product.pdf')
        document = QPdfDocument()
        self.assertEqual(QPdfDocument.Error.None_, document.load(str(destination)))
        text = '\n'.join(document.getAllText(i).text() for i in range(document.pageCount()))
        self.assertIn('€/kg', text)
        self.assertIn('€/piece', text)
        self.assertIn('Unsold', text)
        document.close()
        page.product_filter.setCurrentIndex(page.product_filter.findData(products[0]))
        self.assertEqual('1 €/kg', page.avg_price_metric[1].text())


if __name__ == '__main__':
    unittest.main()
