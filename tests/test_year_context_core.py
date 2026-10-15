"""Owner QA batch 1: effective dates and real correction-mode writes."""
from contextlib import closing
from pathlib import Path
import importlib
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QMessageBox

from app.database import Database
from app import year_context as context
from app.year_context_ui import EnhancedYearLockPage, YearContextBar, apply_effective_year_to_new_forms
from tests.language_fixture import scoped_language


class FixedDate(QDate):
    @staticmethod
    def currentDate():
        return QDate(2026, 10, 3)


class YearContextCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.enterContext(scoped_language(self.qt, "el"))
        properties = ("mastixaActiveWorkingYear", "mastixaEffectiveWorkingYear", "mastixaCorrectionYear", "mastixaCorrectionReason")
        previous = {key: self.qt.property(key) for key in properties}
        self.addCleanup(lambda: [self.qt.setProperty(key, value) for key, value in previous.items()])
        root = self.enterContext(tempfile.TemporaryDirectory())
        self.db = Database(Path(root) / "year.db")
        self.addCleanup(context.initialize_year_context, self.db)
        self.enterContext(patch("app.year_context.QDate", FixedDate))
        context.set_active_working_year(self.db, 2027, audit=False)
        self.field = self.db.execute("INSERT INTO fields(name) VALUES('Field')")
        self.messages = self.enterContext(patch("app.year_context_ui._message", return_value=QMessageBox.StandardButton.Yes))
        self.enterContext(patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.No))
        self.enterContext(patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.No))

    def page(self, module, name, *args):
        page = getattr(importlib.import_module("app." + module), name)(self.db, *args)
        self.addCleanup(page.deleteLater)
        self.addCleanup(page.close)
        return page

    def lock(self, year):
        context.is_year_physically_locked(self.db, year)
        self.db.execute("INSERT OR REPLACE INTO year_locks(year,is_locked,reason) VALUES(?,1,'physical')", (year,))

    def test_lock_lookup_is_read_only_including_legacy_missing_table(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                if legacy:
                    self.db.execute("DROP TABLE year_locks")
                with self.db.connect() as con:
                    before = tuple(con.iterdump())
                with patch.object(self.db, "execute", wraps=self.db.execute) as write:
                    self.assertFalse(context.is_year_physically_locked(self.db, 2026))
                    write.assert_not_called()
                with self.db.connect() as con:
                    self.assertEqual(before, tuple(con.iterdump()))

    def test_effective_date_leap_day_and_profile_isolation(self):
        self.assertEqual(QDate(2027, 10, 3), context.working_context_date(self.db))
        self.assertEqual(QDate(2027, 2, 28), context.qdate_in_year(2027, QDate(2024, 2, 29)))
        self.lock(2026)
        context.begin_year_correction(self.db, 2026, "reason")
        self.assertEqual(QDate(2026, 10, 3), context.working_context_date(self.db))
        other = Database(self.db.path.parent / "other.db")
        context.set_active_working_year(other, 2030, audit=False)
        self.assertEqual(2026, context.working_context_date(self.db).year())
        self.assertEqual(2030, context.working_context_date(other).year())

    def test_only_correction_year_writable_and_restart_relocks(self):
        self.lock(2026)
        self.lock(2025)
        self.assertTrue(context.is_year_write_blocked(self.db, 2026))
        context.begin_year_correction(self.db, 2026, "reason")
        self.assertFalse(context.is_year_write_blocked(self.db, 2026))
        self.assertTrue(context.is_year_write_blocked(self.db, 2025))
        context.initialize_year_context(Database(self.db.path))
        self.assertTrue(context.is_year_physically_locked(self.db, 2026))
        self.assertTrue(context.is_year_write_blocked(self.db, 2026))
        self.assertEqual(2027, context.effective_working_year(self.db))

    def test_annual_forms_initial_reset_switch_and_existing_date(self):
        specs = (
            ("money", "MoneyPage", ("income",), "date", "clear_form", "selected_money_id"),
            ("production", "ProductionPage", (), "date", "clear_form", "selected_production_id"),
            ("sales", "SalesPage", (), "sale_date", "clear_form", "selected_sale_id"),
            ("activities", "ActivitiesPage", (), "date", "clear_form", "selected_activity_id"),
            ("inventory", "InventoryPage", (), "movement_date", "clear_movement_form", "selected_movement_id"),
            ("equipment", "EquipmentPage", (), "service_date", "clear_service", "selected_service_id"),
            ("plant_protection", "PlantProtectionPage", (), "date", "clear_form", "selected_id"),
            ("labor", "LaborPage", (), "work_date", "clear_entry_form", "selected_entry_id"),
            ("plantings", "PlantingsPage", (), "planting_date", "clear_form", "selected_id"),
        )
        self.lock(2026)
        for module, name, args, attr, clear, selected in specs:
            with self.subTest(page=module):
                page = self.page(module, name, *args)
                edit = getattr(page, attr)
                self.assertEqual(2027, edit.date().year())
                context.begin_year_correction(self.db, 2026, "reason")
                apply_effective_year_to_new_forms(page, self.db)
                self.assertEqual(2026, edit.date().year())
                getattr(page, clear)()
                self.assertEqual(2026, edit.date().year())
                setattr(page, selected, 77)
                edit.setDate(QDate(2024, 2, 29))
                context.finish_year_correction(self.db)
                apply_effective_year_to_new_forms(page, self.db)
                self.assertEqual(QDate(2024, 2, 29), edit.date())
                setattr(page, selected, None)
                getattr(page, clear)()
                self.assertEqual(2027, edit.date().year())

    def test_inventory_initial_stock_and_movement_defaults(self):
        page = self.page("inventory", "InventoryPage")
        self.lock(2026)
        for name, year in (("Active", 2027), ("Correction", 2026)):
            if year == 2026:
                context.begin_year_correction(self.db, 2026, "reason")
            page.item_name.setText(name)
            page.item_unit.setCurrentText("kg")
            page.initial_stock.setText("5")
            page.save_item()
            row = self.db.query_one("SELECT m.* FROM inventory_movements m JOIN inventory_items i ON i.id=m.item_id WHERE i.name=?", (name,))
            self.assertIsNotNone(row)
            self.assertEqual(f"{year}-10-03", row["movement_date"])
            self.assertEqual(5, row["quantity"])
            page.clear_movement_form()
            self.assertEqual(year, page.movement_date.date().year())

    def test_money_correction_insert_update_and_physical_lock(self):
        self.lock(2026)
        for kind in ("income", "expenses"):
            with self.subTest(kind=kind):
                page = self.page("money", "MoneyPage", kind)
                page.date.setDate(QDate(2026, 3, 4))
                page.description.setText("Blocked")
                page.amount.setValue(12)
                page.save_money()
                self.assertEqual(0, self.db.query_one(f"SELECT COUNT(*) FROM {kind}")[0])
                # A rejected create now intentionally clears the draft. Enter
                # a new correction draft rather than relying on rejected data.
                self.assertEqual("", page.description.text())
                context.begin_year_correction(self.db, 2026, "reason")
                page.date.setDate(QDate(2026, 3, 4))
                page.description.setText("Correction")
                page.amount.setValue(12)
                page.save_money()
                page.load_selected(0, 0)
                self.assertTrue(page.save_button.isEnabled())
                page.amount.setValue(19)
                page.save_money()
                with closing(sqlite3.connect(self.db.path)) as con:
                    self.assertEqual([("2026-03-04", 19)], con.execute(f"SELECT entry_date,amount FROM {kind}").fetchall())
                context.finish_year_correction(self.db)
                self.assertTrue(context.is_year_physically_locked(self.db, 2026))

    def test_permanent_unlock_reason_and_audit(self):
        self.db.execute("CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY,event_time TEXT,table_name TEXT,action TEXT,record_id TEXT,details TEXT)")
        self.lock(2026)
        page = self.page("year_context_ui", "EnhancedYearLockPage")
        page.year.setCurrentIndex(page.year.findData(2026))
        page.unlock_year()
        self.assertTrue(context.is_year_physically_locked(self.db, 2026))
        with self.assertRaises(ValueError):
            context.permanently_unlock_year(self.db, 2026, "  ")
        reason = "Raw {year} Αιτία <b> & path"
        page.correction_reason.setText(reason)
        page.unlock_year()
        self.assertFalse(context.is_year_physically_locked(self.db, 2026))
        audit = self.db.query_one("SELECT * FROM audit_events WHERE table_name='year_context' ORDER BY id DESC LIMIT 1")
        self.assertEqual("2026", audit["record_id"])
        self.assertIn("Μόνιμο ξεκλείδωμα", audit["details"])
        self.assertIn(reason, audit["details"])
        self.assertTrue(audit["event_time"])

    def test_locked_navigation_and_success_only_for_real_change(self):
        self.lock(2026)
        bar = self.page("year_context_ui", "YearContextBar")
        bar.year_selector.setEditText('2026')
        bar._apply_year()
        self.assertEqual(2026, context.active_working_year(self.db))
        self.assertIsNone(context.correction_state(self.db))
        self.assertTrue(context.is_year_write_blocked(self.db, 2026))
        self.assertIn("Μόνο προβολή", bar.warning_label.text())
        self.assertEqual("active", bar.property("yearContextState"))
        # Owner acceptance intentionally adds confirmation before the existing
        # success message; unchanged year and failed writes must not report success.
        self.assertEqual(2, self.messages.call_count)
        self.assertEqual("question", self.messages.call_args_list[0].args[1])
        self.assertEqual("information", self.messages.call_args.args[1])
        self.messages.reset_mock()
        bar._apply_year()
        self.messages.assert_not_called()
        bar.year_selector.setEditText('2028')
        with patch("app.year_context_ui.set_active_working_year", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                bar._apply_year()
        self.messages.assert_called_once()
        self.assertEqual("question", self.messages.call_args.args[1])
        self.messages.reset_mock()
        context.begin_year_correction(self.db, 2026, "reason")
        bar._apply_year()
        bar.refresh()
        self.assertEqual("correction", bar.property("yearContextState"))
        context.finish_year_correction(self.db)
        bar.refresh()
        self.messages.assert_not_called()

    def test_crop_and_declaration_year_defaults(self):
        crop = self.page("crop_programs", "CropProgramsPage")
        declaration = self.page("declaration", "DeclarationPage")
        self.assertEqual(2027, crop.season_year.value())
        self.assertEqual(2027, declaration.year.currentData())
        self.lock(2026)
        context.begin_year_correction(self.db, 2026, "reason")
        crop.refresh_year_context_ui()
        declaration.refresh_year_context_ui()
        self.assertEqual(2026, crop.season_year.value())
        self.assertEqual(2026, declaration.year.currentData())

    def test_crop_task_and_event_mutations_respect_correction(self):
        from app.crop_program import CropProgramRule
        from app.crop_program_store import CropProgramStore
        from app.plant_tracking import PlantRecord, PlantEvent
        from app.plant_tracking_store import PlantTrackingStore
        crop = CropProgramStore(self.db)
        rule = CropProgramRule.from_mapping({"id": "rule", "category": "irrigation", "title": "Task", "schedule_kind": "fixed_date", "month": 3, "day": 4})
        crop.save_program("program", "Program", [rule])
        plants = PlantTrackingStore(self.db)
        plants.save_plant(PlantRecord(id="plant", field_id=str(self.field), label="Plant"))
        event = PlantEvent(id="event", plant_id="plant", event_date="2026-03-04", kind="note", notes="Test")
        self.lock(2026)
        with self.assertRaises(ValueError):
            crop.generate_for_field("program", self.field, 2026)
        with self.assertRaises(ValueError):
            plants.append_event(event)
        context.begin_year_correction(self.db, 2026, "reason")
        tasks = crop.generate_for_field("program", self.field, 2026)
        self.assertEqual(1, len(tasks))
        plants.append_event(event)
        context.finish_year_correction(self.db)
        with self.assertRaises(ValueError):
            crop.set_task_status(tasks[0]["generation_key"], "completed")
        with self.assertRaises(ValueError):
            crop.archive_program("program")
        context.begin_year_correction(self.db, 2026, "reason")
        crop.set_task_status(tasks[0]["generation_key"], "completed")
        self.assertEqual("completed", crop.tasks()[0]["status"])

    def test_permanent_unlock_cancel_and_existing_edit_preserved(self):
        self.lock(2026)
        page = self.page("year_context_ui", "EnhancedYearLockPage")
        page.year.setCurrentIndex(page.year.findData(2026))
        page.correction_reason.setText("reason")
        self.messages.return_value = QMessageBox.StandardButton.No
        page.unlock_year()
        self.assertTrue(context.is_year_physically_locked(self.db, 2026))
        money = self.page("money", "MoneyPage", "income")
        record = self.db.execute("INSERT INTO income(entry_date,description,amount) VALUES('2024-02-29','Stored',10)")
        money.refresh()
        money.year_filter.setCurrentIndex(money.year_filter.findData('2024'))
        money.load_selected(0, 0)
        context.set_active_working_year(self.db, 2031, audit=False)
        apply_effective_year_to_new_forms(money, self.db)
        self.assertEqual(QDate(2024, 2, 29), money.date.date())
        self.assertEqual("2024-02-29", self.db.query_one("SELECT entry_date FROM income WHERE id=?", (record,))[0])
