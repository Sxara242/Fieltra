"""Scoped composed presentation: complete templates and opaque raw values."""
import copy
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QGroupBox, QLabel, QMainWindow, QMessageBox, QTableWidget, QTableWidgetItem, QWidget
from app.database import Database
from app import version_integration
from app.version import APP_NAME, APP_VERSION
from tests.language_fixture import scoped_language

RAW = "User — Παραγωγή Αποθήκευση Ναι Έξοδα Save Production <b>tag</b> {year} {2027}"
ERROR = "Παραγωγή Save {year} <b>tag</b>"


class ComposedUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.controller = self.enterContext(scoped_language(self.app, "el"))
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.db = Database(Path(self.temp) / "test.db")
        self.pages = []
        self.addCleanup(self.close_pages)

    def close_pages(self):
        for page in self.pages:
            page.close()
            page.deleteLater()
        self.app.processEvents()

    def keep(self, page):
        self.pages.append(page)
        return page

    def snapshot(self):
        with self.db.connect() as connection:
            return tuple(connection.iterdump())

    def cycle(self, owner, read, expected):
        before = self.snapshot()
        for code in ("el", "en", "el"):
            with self.subTest(language=code):
                with patch.object(self.db, "execute", side_effect=AssertionError("language switch wrote to DB")):
                    self.controller.set_language(code, persist=False)
                    self.controller.apply_to(owner)
                    self.controller.apply_to(owner)
                self.assertEqual(read(), expected[code])
                self.assertEqual(self.snapshot(), before)

    def dialog(self, action, raw, english, answer=QMessageBox.StandardButton.Ok, check=None):
        seen = []
        def inspect(box):
            seen.append(box)
            for code in ("el", "en", "el"):
                with self.subTest(dialog_language=code):
                    self.controller.set_language(code, persist=False)
                    self.controller.apply_to(box)
                    self.assertIn(raw, box.text())
                    if code == "en":
                        self.assertIn(english, box.text())
                    if check:
                        check(box, code)
            return answer
        def legacy(parent, title, text, *args):
            box = self.keep(QMessageBox(parent))
            box.setWindowTitle(title)
            box.setText(text)
            return inspect(box)
        with ExitStack() as stack:
            for kind in ("warning", "critical", "information", "question"):
                stack.enter_context(patch.object(QMessageBox, kind, side_effect=legacy))
            stack.enter_context(patch.object(QMessageBox, "exec", inspect))
            action()
        self.assertTrue(seen, "production action did not display a dialog")

    def test_unmarked_titles_still_translate(self):
        window = self.keep(QWidget())
        window.setWindowTitle("Παραγωγή")
        group = QGroupBox("Παραγωγή", window)
        self.cycle(window, lambda: (window.windowTitle(), group.title()),
                   {"el": ("Παραγωγή", "Παραγωγή"), "en": ("Production", "Production")})

    def test_opt_in_title_guards(self):
        window = self.keep(QWidget())
        group = QGroupBox(RAW, window)
        window.setWindowTitle(RAW)
        window.setProperty("mastixaI18nSkipWindowTitle", True)
        group.setProperty("mastixaI18nSkipTitle", True)
        self.cycle(window, lambda: (window.windowTitle(), group.title()),
                   {code: (RAW, RAW) for code in ("el", "en")})

    def test_version_title(self):
        class WindowShell(QMainWindow):
            def __init__(self, name=RAW):
                super().__init__()
                self.profile_manager = SimpleNamespace(active_profile=SimpleNamespace(name=name))
        with patch.object(version_integration, "MainWindow", WindowShell), patch.object(version_integration, "_INSTALLED", False):
            version_integration.install_version_ui()
            page = self.keep(WindowShell())
            exact_key_page = self.keep(WindowShell("Παραγωγή"))
        expected = f"{APP_NAME} v{APP_VERSION} — {RAW}"
        self.cycle(page, page.windowTitle, {"el": expected, "en": expected})
        expected = f"{APP_NAME} v{APP_VERSION} — Παραγωγή"
        self.cycle(exact_key_page, exact_key_page.windowTitle, {"el": expected, "en": expected})

    def test_crop_program_heading(self):
        from app.crop_programs import CropProgramsPage
        page = self.keep(CropProgramsPage(self.db))
        page.selected_program_id = "test-program"
        page.name_edit.setText(RAW)
        page._update_rules_heading()
        self.cycle(page, page.rules_box.title,
                   {"el": "Κανόνες του προγράμματος: " + RAW, "en": "Program rules: " + RAW})
        page.name_edit.setText("Παραγωγή")
        for _ in range(3): page._update_rules_heading()
        self.cycle(page, page.rules_box.title, {"el": "Κανόνες του προγράμματος: Παραγωγή", "en": "Program rules: Παραγωγή"})
        with patch.object(page, "_update_rules_heading", wraps=page._update_rules_heading) as render:
            self.controller.set_language("en", persist=False)
            render.assert_called_once_with()

    def test_dashboard_farm_name(self):
        from app.dashboard import DashboardPage
        self.db.set_app_setting("farm_name", RAW)
        page = self.keep(DashboardPage(self.db))
        page.refresh()
        self.cycle(page, page.subtitle.text,
                   {"el": "Συνολική εικόνα εκμετάλλευσης — " + RAW, "en": "Overall farm overview — " + RAW})

    def test_field_identity(self):
        from app.field_profile import FieldProfilePage
        field_id = self.db.execute("INSERT INTO fields(name,location,kaek) VALUES(?,?,?)", (RAW, RAW, RAW))
        page = self.keep(FieldProfilePage(self.db))
        page.field.setCurrentIndex(page.field.findData(field_id))
        page.refresh()
        self.cycle(page, lambda: (page.name_value.text(), page.location_value.text(), page.kaek_value.text()),
                   {code: (RAW, RAW, RAW) for code in ("el", "en")})
        page._clear()
        page.refresh()
        self.cycle(page, page.trees_value.text, {"el": "0", "en": "0"})

    def csv(self, module, cls, failure=False):
        import importlib
        owner = self.keep(QWidget())
        owner.table = QTableWidget(1, 1, owner)
        owner.table.setHorizontalHeaderLabels(["raw"])
        owner.table.setItem(0, 0, QTableWidgetItem(RAW))
        owner.year = QComboBox(owner)
        owner.year.addItem("2027", 2027)
        path = Path(self.temp) / "Παραγωγή Αποθήκευση Save Ναι {2027}.csv"
        action = lambda: getattr(importlib.import_module("app." + module), cls).export_csv(owner)
        with patch(f"app.{module}.QFileDialog.getSaveFileName", return_value=(str(path), "")):
            if failure:
                with patch.object(Path, "open", side_effect=OSError(ERROR)):
                    self.dialog(action, ERROR, "Export failed.")
            else:
                self.dialog(action, str(path), "CSV created")
                self.assertEqual(path.read_text(encoding="utf-8-sig"), "raw\n" + RAW + "\n")

    def test_audit_export(self): self.csv("audit", "AuditPage")
    def test_audit_error(self): self.csv("audit", "AuditPage", True)
    def test_field_finance_export(self): self.csv("field_finance", "FieldFinancePage")
    def test_field_finance_error(self): self.csv("field_finance", "FieldFinancePage", True)

    def test_upload_export(self):
        from app.upload_center import UploadCenterPage
        owner = self.keep(QWidget())
        owner.current_validation_errors = []
        owner.current_payload = {"year": 2027, "raw": RAW}
        before = copy.deepcopy(owner.current_payload)
        path = Path(self.temp) / "Παραγωγή Ναι {2027}.json"
        with patch("app.upload_center.QFileDialog.getSaveFileName", return_value=(str(path), "")):
            self.dialog(lambda: UploadCenterPage.export_json(owner), str(path), "JSON created")
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), before)
        self.assertEqual(owner.current_payload, before)

    def test_settings_profile_export(self):
        from app.settings import SettingsPage
        owner = self.keep(QWidget())
        owner._selected_profile_id = lambda: "raw-id"
        owner._request_profile_pin = lambda *args: True
        owner.profiles = SimpleNamespace(get=lambda _: SimpleNamespace(name=RAW), export_profile=Mock(return_value=RAW))
        with patch("app.settings.QFileDialog.getSaveFileName", return_value=("C:/qa/profile.fieltraprofile", "")):
            self.dialog(lambda: SettingsPage.export_profile(owner), RAW, "profile")
        owner.profiles.export_profile.assert_called_once_with("raw-id", Path("C:/qa/profile.fieltraprofile"))

    def test_dashboard_backup_success(self):
        from app.dashboard import DashboardPage
        owner = self.keep(QWidget())
        owner.backup_manager = SimpleNamespace(create_backup=Mock(return_value=RAW))
        owner._refresh_backup_status = Mock()
        self.dialog(lambda: DashboardPage.create_backup(owner), RAW, "backup")
        owner.backup_manager.create_backup.assert_called_once_with()

    def test_invoice_export_error(self):
        from app.invoice_documents import InvoiceDocumentsPage
        owner = self.keep(QWidget())
        owner._selected_ids = lambda: [64]
        owner.build_export_zip = Mock(side_effect=OSError(ERROR))
        with patch("app.invoice_documents.QFileDialog.getSaveFileName", return_value=("qa.zip", "")):
            self.dialog(lambda: InvoiceDocumentsPage.export_selected(owner), ERROR, ERROR)

    def test_all_locked_headings_and_edit_state(self):
        import importlib
        from tests.test_phase16j_generated_tables_localization import record
        cases = [
            ("activities", "ActivitiesPage", "load_selected", "table", "form_box", "farm_activities", "καταγραφής", "activity", ()),
            ("inventory", "InventoryPage", "load_movement", "movement_table", "movement_box", "inventory_movements", "κίνησης", "movement", ()),
            ("labor", "LaborPage", "load_entry", "entry_table", "entry_box", "labor_entries", "εργατικών", "labor", ()),
            ("money", "MoneyPage", "load_selected", "table", "form_box", "income", "εσόδου", "income", ("income",)),
            ("money", "MoneyPage", "load_selected", "table", "form_box", "expenses", "εξόδου", "expense", ("expenses",)),
            ("plantings", "PlantingsPage", "load_record", "table", "form_box", "planting_batches", "φύτευσης", "planting", ()),
            ("production", "ProductionPage", "load_selected", "table", "form_box", "production", "παραγωγής", "production", ()),
            ("sales", "SalesPage", "load_sale", "table", "form_box", "production_sales", "πώλησης", "sale", ()),
        ]
        for module, cls, method, table_name, box_name, db_table, greek, english, args in cases:
            with self.subTest(owner=module, table=db_table):
                page = self.keep(getattr(importlib.import_module("app." + module), cls)(self.db, *args))
                source = record(id=64, field_id=None, product_id=None, partner_id=None, worker_id=None, buyer_id=None,
                                source_type="", status="Ολοκληρώθηκε", category="Πότισμα", product=RAW,
                                planting_date="2027-01-02", sale_date="2027-01-02", supplier_name=RAW,
                                movement_type="Παραλαβή", quantity_kg=2, material_type="", trees_planted=3, trees_alive=2,
                                source=RAW, variety=RAW, spacing=RAW, partner=RAW, work_type=RAW)
                table = getattr(page, table_name)
                table.setRowCount(1)
                item = QTableWidgetItem("raw row")
                item.setData(Qt.ItemDataRole.UserRole, 64)
                table.setItem(0, 0, item)
                original_query = self.db.query_one
                def query(sql, params=()):
                    if "select *" in sql.lower() and ("from " + db_table) in " ".join(sql.lower().split()):
                        return source
                    return original_query(sql, params)
                with patch.object(self.db, "query_one", side_effect=query), patch("app." + module + ".is_year_locked", return_value=True):
                    getattr(page, method)(0, 0)
                before = copy.deepcopy(source)
                buttons = [b for b in page.findChildren(__import__('PySide6.QtWidgets', fromlist=['QPushButton']).QPushButton)]
                enabled = [b.isEnabled() for b in buttons]
                box = getattr(page, box_name)
                self.cycle(page, box.title, {"el": f"Προβολή {greek} — ΚΛΕΙΔΩΜΕΝΟ 2027", "en": f"View {english} — LOCKED 2027"})
                self.assertEqual(source, before)
                self.assertEqual([b.isEnabled() for b in buttons], enabled)
                with patch.object(self.db, "query_one", side_effect=query), patch("app." + module + ".is_year_locked", return_value=False):
                    getattr(page, method)(0, 0)
                self.assertNotIn("ΚΛΕΙΔΩΜΕΝΟ", box.title())
                self.assertNotIn("LOCKED", box.title())

    def test_declaration_locked_status(self):
        from app.declaration import DeclarationPage
        page = self.keep(DeclarationPage(self.db))
        page.year.addItem("2027", 2027)
        page.year.setCurrentIndex(page.year.findData(2027))
        page._composed_text(page.status, "Πρόχειρη — αποθηκευμένη ({updated_at})", updated_at=RAW)
        with patch("app.declaration.is_year_locked", return_value=True):
            page._apply_edit_mode()
        self.cycle(page, page.status.text, {"el": f"Πρόχειρη — αποθηκευμένη ({RAW}) — ΚΛΕΙΔΩΜΕΝΟ 2027", "en": f"Draft — saved ({RAW}) — LOCKED 2027"})
        self.assertFalse(page._editing)
        self.assertFalse(page.save_button.isEnabled())

    def test_invoice_ocr_suggestions_and_rejected_filename(self):
        from app.invoice_documents import InvoiceDocumentsPage
        from tests.test_phase16j_generated_tables_localization import record
        page = self.keep(InvoiceDocumentsPage(self.db))
        source = record(original_filename=RAW, ocr_status="metadata_found", ocr_suggested_date="2027-01-02",
                        ocr_suggested_supplier=RAW, ocr_suggested_amount="12.50", financial_entry_type="", financial_entry_id=None)
        with patch.object(self.db, "query_one", return_value=source), patch.object(page.supplier, "setText"), patch.object(page, "_stored_path", return_value=Path(self.temp)/"absent.pdf"), patch("app.invoice_documents.is_year_locked", return_value=False):
            page._load_by_id(64)
        before = copy.deepcopy(source)
        self.cycle(page, page.ocr_status.text, {
            "el": f"OCR: προτάθηκαν ασφαλή μεταδεδομένα — ημερομηνία 2027-01-02; προμηθευτής «{RAW}»; σύνολο 12.50. Έλεγξε/διόρθωσε πριν αποθήκευση.",
            "en": f"OCR: reliable metadata suggested — date 2027-01-02; supplier “{RAW}”; total 12.50. Review/correct before saving."})
        self.assertEqual(source, before)
        owner = self.keep(QWidget())
        owner.refresh = Mock()
        missing = Path(self.temp)/"Παραγωγή Αποθήκευση Ναι {year}.invalid"
        self.dialog(lambda: InvoiceDocumentsPage.import_files(owner, [missing]), missing.name, "Not imported:")

    def test_update_status_errors_and_release_notes(self):
        from app.settings import SettingsPage
        from app.update_integration import _add_updates_tab
        from app.update_manager import UpdateInfo
        from PySide6.QtWidgets import QTabWidget
        class UpdateOwner(QWidget):
            _composed_text = SettingsPage._composed_text
            _refresh_composed_text = SettingsPage._refresh_composed_text
        page = self.keep(UpdateOwner())
        page.tabs = QTabWidget(page)
        _add_updates_tab(page)
        info = UpdateInfo("99.0.0", "alpha", "https://example.invalid/Παραγωγή", RAW, None, None)
        page._mastixa_update_signals.checked.emit(info)
        self.cycle(page, page._mastixa_update_status.text,
                   {"el": "Νέα έκδοση διαθέσιμη: 99.0.0\n" + RAW, "en": "New version available: 99.0.0\n" + RAW})
        self.assertIs(page._mastixa_update_info, info)
        page._mastixa_update_signals.failed.emit(ERROR)
        self.cycle(page, page._mastixa_update_status.text,
                   {"el": "Αποτυχία ενημέρωσης: " + ERROR, "en": "Update failed: " + ERROR})
        page._mastixa_update_signals.failed.emit(("Αποτυχία ελέγχου ενημερώσεων: {error}", ERROR))
        self.cycle(page, page._mastixa_update_status.text,
                   {"el": "Αποτυχία ελέγχου ενημερώσεων: " + ERROR, "en": "Update check failed: " + ERROR})
        def check(box, code):
            self.assertEqual(box.standardButtons(), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            self.assertIs(box.defaultButton(), box.button(QMessageBox.StandardButton.Yes))
        with patch("app.update_integration.launch_windows_installer") as launch:
            self.dialog(lambda: page._mastixa_update_signals.downloaded.emit(info, Path("qa.exe")), "99.0.0", "SHA-256", QMessageBox.StandardButton.No, check)
            launch.assert_not_called()
        self.cycle(page, page._mastixa_update_status.text,
                   {"el": "Η έκδοση 99.0.0 είναι έτοιμη για εγκατάσταση.", "en": "Version 99.0.0 is ready to install."})

    def test_upload_comparison_and_integrity(self):
        from app.upload_center import UploadCenterPage
        class UploadOwner(QWidget):
            _diff_values = UploadCenterPage._diff_values
            _diff_payloads = UploadCenterPage._diff_payloads
            _composed_text = UploadCenterPage._composed_text
            _refresh_composed_text = UploadCenterPage._refresh_composed_text
        page = self.keep(UploadOwner())
        page.selected_snapshot_id = 64
        page.db = self.db
        page.current_payload = {RAW: [RAW, RAW]}
        snapshot = {"id": 64, "payload_json": json.dumps({RAW: RAW}), "payload_hash": RAW}
        before = copy.deepcopy(page.current_payload)
        with patch.object(self.db, "query_one", return_value=snapshot):
            self.dialog(lambda: UploadCenterPage.compare_selected_snapshot(page), RAW, "type/value changed")
        self.assertEqual(page.current_payload, before)
        from PySide6.QtWidgets import QPlainTextEdit
        page.history_table = QTableWidget(1, 1, page)
        page.history_table.setItem(0, 0, QTableWidgetItem("64"))
        page.history_table.selectRow(0)
        page.snapshot_status = QLabel(page)
        page.snapshot_preview = QPlainTextEdit(page)
        page._snapshot_integrity_ok = Mock(return_value=True)
        page._set_snapshot_action_state = Mock()
        with patch.object(self.db, "query_one", return_value=snapshot):
            UploadCenterPage._snapshot_selection_changed(page)
        self.cycle(page, page.snapshot_status.text, {"el": f"Snapshot #64 — ακέραιο — SHA-256: {RAW}", "en": f"Snapshot #64 — intact — SHA-256: {RAW}"})
        self.assertEqual(page.snapshot_preview.toPlainText(), snapshot["payload_json"])
        page._snapshot_integrity_ok.return_value = False
        with patch.object(self.db, "query_one", return_value=snapshot):
            UploadCenterPage._snapshot_selection_changed(page)
        self.cycle(page, page.snapshot_status.text, {"el": "Snapshot #64 — ΠΡΟΕΙΔΟΠΟΙΗΣΗ: το περιεχόμενο δεν συμφωνεί με το αποθηκευμένο SHA-256.", "en": "Snapshot #64 — WARNING: the content does not match the stored SHA-256."})
        self.assertEqual(page.snapshot_preview.toPlainText(), snapshot["payload_json"])

    def test_catalog_contract(self):
        from string import Formatter
        path = Path(__file__).parents[1]/"app/locales/en_phase16j_composed_ui.json"
        pairs = json.loads(path.read_text(encoding="utf-8"))["translations"]
        def slots(text):
            return sorted((field, spec, conv or "") for _, field, spec, conv in Formatter().parse(text) if field is not None)
        for source, target in pairs.items():
            self.assertTrue(target)
            self.assertEqual(slots(source), slots(target))
            self.assertFalse(any("\u0370" <= c <= "\u03ff" for c in target))
        for other in path.parent.glob("*.json"):
            if other != path:
                keys = json.loads(other.read_text(encoding="utf-8"))["translations"]
                self.assertFalse(set(pairs) & set(keys), other.name)

    def test_settings_profile_state_and_single_callback(self):
        from app.settings import SettingsPage
        from PySide6.QtWidgets import QPushButton
        class Owner(QWidget):
            _composed_text = SettingsPage._composed_text
            _refresh_composed_text = SettingsPage._refresh_composed_text
        page = self.keep(Owner())
        for name in ("activate_profile_button", "rename_profile_button", "archive_profile_button", "profile_color_button", "remove_avatar_button", "profile_pin_button", "remove_pin_button"):
            setattr(page, name, QPushButton(page))
        page.profile_status = QLabel(page)
        page.profile_avatar = QLabel(page)
        page._selected_profile_id = lambda: "qa-id"
        profile = SimpleNamespace(id="qa-id", is_active=True, has_pin=True, color="#123456", avatar_path=None, name=RAW, database_path=RAW)
        page.profiles = SimpleNamespace(DEFAULT_ID="default", get=lambda _: profile)
        for _ in range(3):
            SettingsPage._update_profile_actions(page)
        self.cycle(page, page.profile_status.text, {"el": "Ενεργό προφίλ · PIN ενεργό\nΒάση: " + RAW, "en": "Active profile · PIN enabled\nDatabase: " + RAW})
        with patch("app.settings._text", wraps=__import__('app.settings', fromlist=['_text'])._text) as render:
            self.controller.set_language("en", persist=False)
            self.assertEqual(render.call_count, 3)  # two owned labels + complete template, once
        profile.is_active = False
        profile.has_pin = False
        SettingsPage._update_profile_actions(page)
        self.cycle(page, page.profile_status.text, {"el": "Ανενεργό προφίλ · χωρίς PIN\nΒάση: " + RAW, "en": "Inactive profile · no PIN\nDatabase: " + RAW})
        page._selected_profile_id = lambda: None
        SettingsPage._update_profile_actions(page)
        self.cycle(page, page.profile_status.text, {"el": "", "en": ""})

    def test_settings_profile_create_import_and_errors(self):
        from app.settings import SettingsPage
        from app.profile_manager import ProfileError
        page = self.keep(QWidget())
        page._refresh_profiles = Mock()
        profile = SimpleNamespace(name=RAW, id="qa-id")
        page.profiles = SimpleNamespace(create=Mock(return_value=profile), import_profile=Mock(return_value=profile))
        with patch("app.settings.QInputDialog.getText", return_value=(RAW, True)):
            self.dialog(lambda: SettingsPage.create_profile(page), RAW, "independent database")
            page.profiles.create.assert_called_once_with(RAW)
            page.profiles.create.side_effect = ProfileError(ERROR)
            self.dialog(lambda: SettingsPage.create_profile(page), ERROR, ERROR)
        with patch("app.settings.QFileDialog.getOpenFileName", return_value=("C:/Παραγωγή Save/Ναι {2027}.fieltraprofile", "")):
            self.dialog(lambda: SettingsPage.import_profile(page), RAW, "own database")
        page.profiles.import_profile.assert_called_once_with(Path("C:/Παραγωγή Save/Ναι {2027}.fieltraprofile"))

    def test_settings_archive_activate_cancel_preserve_state(self):
        from app.settings import SettingsPage
        page = self.keep(QWidget())
        page._selected_profile_id = lambda: "qa-id"
        page._request_profile_pin = lambda *args: True
        page.profiles = SimpleNamespace(get=lambda _: SimpleNamespace(name=RAW, is_active=False), archive=Mock())
        page.profile_switch_requested = Mock()
        def check(box, code):
            self.assertEqual(box.standardButtons(), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            self.assertIs(box.defaultButton(), box.button(QMessageBox.StandardButton.No))
        for method, english in ((SettingsPage.archive_profile, "Remove profile"), (SettingsPage.activate_profile, "Activate profile")):
            self.dialog(lambda: method(page), RAW, english, QMessageBox.StandardButton.No, check)
        page.profiles.archive.assert_not_called()
        page.profile_switch_requested.emit.assert_not_called()

    def test_settings_backup_folder_errors(self):
        from app.settings import SettingsPage
        from PySide6.QtWidgets import QLineEdit
        page = self.keep(QWidget())
        page.backup_dir = QLineEdit("C:/Παραγωγή Save/Ναι {2027}", page)
        with patch.object(Path, "mkdir", side_effect=OSError(ERROR)):
            self.dialog(lambda: SettingsPage.open_backup_folder(page), ERROR, "folder could not be created")
            self.dialog(lambda: SettingsPage.save(page), ERROR, "folder could not be used")

    def test_sales_insufficient_stock_product_and_no_write(self):
        from app.sales import SalesPage
        from PySide6.QtCore import QDate
        from PySide6.QtWidgets import QDateEdit, QDoubleSpinBox
        page = self.keep(QWidget())
        page.db = self.db
        page.sale_date = QDateEdit(QDate(2027, 1, 2), page)
        page.selected_sale_id = None
        page.buyer = QComboBox(page); page.buyer.addItem(RAW, 1)
        page.product = QComboBox(page); page.product.addItem(RAW, 64)
        page.quantity = QDoubleSpinBox(page); page.quantity.setValue(2)
        page._available_for_sale = Mock(return_value=1)
        before = self.snapshot()
        with patch("app.sales.is_year_locked", return_value=False), patch("app.sales.product_row", return_value={"id": 64, "name": RAW, "unit": "kg"}):
            self.dialog(lambda: SalesPage.save_sale(page), RAW, "Available:")
        self.assertEqual(self.snapshot(), before)
        page._available_for_sale.assert_called_once_with(None, 64)

    def test_fields_delete_error(self):
        from app.fields import FieldsPage
        from PySide6.QtWidgets import QLineEdit
        page = self.keep(QWidget())
        page.selected_field_id = 64
        page.name = QLineEdit(RAW, page)
        page.confirm_delete = Mock(return_value=True)
        page.db = self.db
        # The callable now checks the year context before attempting DELETE.
        # Initialize the normal startup context before injecting SQL failure.
        from app.year_context import active_working_year, is_year_physically_locked
        is_year_physically_locked(self.db, active_working_year(self.db))
        before = self.snapshot()
        real_execute = self.db.execute
        delete_sql = "DELETE FROM fields WHERE id=?"
        def fail_delete(sql, *args, **kwargs):
            # Existing lock guards ensure their table with idempotent DDL.
            # Inject failure in the DELETE being tested, not in that setup.
            if sql == delete_sql:
                raise RuntimeError(ERROR)
            return real_execute(sql, *args, **kwargs)
        with patch.object(self.db, "execute", side_effect=fail_delete) as execute:
            self.dialog(lambda: FieldsPage.delete_field(page), ERROR, "Details:")
            deletes = [call for call in execute.call_args_list if call.args[0] == delete_sql]
            self.assertEqual(1, len(deletes))
            self.assertEqual((delete_sql, (64,)), deletes[0].args)
        self.assertEqual(self.snapshot(), before)

    def test_main_window_profile_errors_and_rollback(self):
        from app.main_window import ApplicationController
        from app.profile_manager import ProfileError
        window = self.keep(QWidget())
        owner = SimpleNamespace(window=window, profiles=SimpleNamespace(get=Mock(side_effect=ProfileError(ERROR))))
        self.dialog(lambda: ApplicationController.switch_profile(owner, "new-id"), ERROR, ERROR)
        window.db = self.db
        owner.profiles = SimpleNamespace(get=Mock(return_value=SimpleNamespace(is_active=False)), active_profile=SimpleNamespace(id="old-id"), set_active=Mock())
        owner.language = SimpleNamespace(sync_active_profile=Mock())
        owner._build_window = Mock(side_effect=RuntimeError(ERROR))
        with patch.object(self.db, "get_app_setting_bool", return_value=False):
            self.dialog(lambda: ApplicationController.switch_profile(owner, "new-id"), ERROR, "could not be activated")
        self.assertEqual([call.args for call in owner.profiles.set_active.call_args_list], [("new-id",), ("old-id",)])
        self.assertIs(owner.window, window)

    def test_year_lock_next_year_yes_no_and_already_locked(self):
        from app.year_context import set_active_working_year, active_working_year, is_year_physically_locked
        from app.year_context_ui import EnhancedYearLockPage
        set_active_working_year(self.db, 2027, audit=False)
        page = self.keep(EnhancedYearLockPage(self.db))
        def select():
            page.year.setCurrentIndex(page.year.findData(2027))
            page.reason.setText(RAW)
        select()
        before = self.snapshot()
        # The existing first confirmation still cancels the lock itself.
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.No):
            page.lock_year()
        self.assertEqual(self.snapshot(), before)
        for answer, next_locked in ((QMessageBox.StandardButton.No, False), (QMessageBox.StandardButton.Yes, True), (QMessageBox.StandardButton.Yes, False)):
            self.db.execute("DELETE FROM year_locks")
            set_active_working_year(self.db, 2027, audit=False)
            if next_locked:
                self.db.execute("INSERT INTO year_locks(year,is_locked,reason) VALUES(2028,1,?)", (RAW,))
            page.refresh(); select()
            observed = []
            def inspect(box):
                is_question = box.icon() == QMessageBox.Icon.Question
                observed.append(is_question)
                locked_snapshot = self.snapshot()
                for code in ("el", "en", "el"):
                    self.controller.set_language(code, persist=False)
                    self.controller.apply_to(box)
                    expected = ("Το 2027 κλειδώθηκε. Να μεταβείς στο ενεργό έτος 2028;" if code == "el" else "2027 was locked. Switch the active year to 2028?") if is_question else ("Το ενεργό έτος άλλαξε επιτυχώς σε 2028." if code == "el" else "The active year was successfully changed to 2028.")
                    self.assertEqual(box.text(), expected)
                    self.assertEqual(self.snapshot(), locked_snapshot)
                if is_question:
                    self.assertIs(box.defaultButton(), box.button(QMessageBox.StandardButton.Yes))
                    self.assertEqual(box.standardButtons(), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                return answer if is_question else QMessageBox.StandardButton.Ok
            with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes), patch.object(QMessageBox, "information"), patch.object(QMessageBox, "exec", inspect):
                page.lock_year()
            self.assertTrue(is_year_physically_locked(self.db, 2027))
            self.assertEqual(self.db.query_one("SELECT reason FROM year_locks WHERE year=2027")["reason"], RAW)
            self.assertEqual(active_working_year(self.db), 2028 if answer == QMessageBox.StandardButton.Yes else 2027)
            self.assertEqual(observed, [True, False] if answer == QMessageBox.StandardButton.Yes else [True])

    def test_dashboard_backup_filename_and_restore_paths(self):
        from app.dashboard import DashboardPage
        class Owner(QWidget):
            _composed_text = DashboardPage._composed_text
            _refresh_composed_text = DashboardPage._refresh_composed_text
        page = self.keep(Owner())
        page.db = self.db
        page.auto_backup_status = QLabel(page)
        page.backup_status = QLabel(page)
        backup = Path(self.temp)/"Παραγωγή Αποθήκευση Ναι {2027}.db"
        backup.write_bytes(b"qa only")
        page.backup_manager = SimpleNamespace(auto_keep=7, list_backups=lambda: [backup], list_auto_backups=lambda: [backup], backup_dir=Path(self.temp), restore_backup=Mock(return_value=(str(backup), RAW)))
        DashboardPage._refresh_backup_status(page)
        for code in ("el", "en", "el"):
            self.controller.set_language(code, persist=False)
            self.controller.apply_to(page)
            self.assertIn(backup.name, page.backup_status.text())
            self.assertEqual(backup.read_bytes(), b"qa only")
        page.refresh = Mock()
        def inspect(box):
            for code in ("el", "en", "el"):
                self.controller.set_language(code, persist=False)
                self.controller.apply_to(box)
                self.assertIn(str(backup), box.text())
                self.assertIn(RAW, box.text())
            return QMessageBox.StandardButton.Ok
        with patch("app.dashboard.QFileDialog.getOpenFileName", return_value=(str(backup), "")), patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes), patch.object(self.db, "initialize"), patch.object(QMessageBox, "exec", inspect):
            DashboardPage.restore_backup(page)
        page.backup_manager.restore_backup.assert_called_once_with(backup)

    def test_snapshot_export_bytes_and_invalid_integrity(self):
        from app.upload_center import UploadCenterPage
        page = self.keep(QWidget())
        page.selected_snapshot_id = 64
        page.db = self.db
        page._snapshot_integrity_ok = lambda _: True
        payload = json.dumps({RAW: RAW}, ensure_ascii=False)
        snapshot = {"id": 64, "declaration_year": 2027, "payload_json": payload}
        path = Path(self.temp)/"Παραγωγή Ναι {2027}.json"
        with patch.object(self.db, "query_one", return_value=snapshot), patch("app.upload_center.QFileDialog.getSaveFileName", return_value=(str(path), "")):
            self.dialog(lambda: UploadCenterPage.export_selected_snapshot(page), str(path), "Snapshot exported")
            self.assertEqual(path.read_bytes(), payload.encode("utf-8"))
            with patch.object(Path, "write_text", side_effect=OSError(ERROR)):
                self.dialog(lambda: UploadCenterPage.export_selected_snapshot(page), ERROR, "Export failed")
            self.assertEqual(path.read_bytes(), payload.encode("utf-8"))

    def test_real_modal_path_live_switch(self):
        from app.settings import SettingsPage
        from PySide6.QtCore import QTimer
        page = self.keep(QWidget())
        page._selected_profile_id = lambda: "qa-id"
        page._request_profile_pin = lambda *args: True
        page.profiles = SimpleNamespace(get=lambda _: SimpleNamespace(name=RAW), export_profile=Mock(return_value=RAW))
        errors = []
        def visit():
            box = self.app.activeModalWidget()
            try:
                self.assertIsInstance(box, QMessageBox)
                for code in ("el", "en", "el"):
                    self.controller.set_language(code, persist=False)
                    self.controller.apply_to(box)
                    self.assertEqual(box.text(), ("The complete profile was saved here:\n" if code == "en" else "Το πλήρες προφίλ αποθηκεύτηκε εδώ:\n") + RAW)
                    self.assertEqual(box.textFormat(), Qt.TextFormat.PlainText)
            except BaseException as exc:
                errors.append(exc)
            finally:
                if isinstance(box, QMessageBox): box.accept()
        QTimer.singleShot(0, visit)
        with patch("app.settings.QFileDialog.getSaveFileName", return_value=(str(Path(self.temp)/"qa.fieltraprofile"), "")):
            SettingsPage.export_profile(page)
        if errors: raise errors[0]

    def test_invoice_export_success(self):
        from app.invoice_documents import InvoiceDocumentsPage
        page = self.keep(QWidget())
        page._selected_ids = lambda: [64]
        path = Path(self.temp)/"Παραγωγή Αποθήκευση Ναι {2027}.zip"
        page.build_export_zip = Mock(side_effect=lambda target, ids: target.write_bytes(b"unchanged export bytes"))
        with patch("app.invoice_documents.QFileDialog.getSaveFileName", return_value=(str(path), "")):
            self.dialog(lambda: InvoiceDocumentsPage.export_selected(page), str(path), "Package created")
        page.build_export_zip.assert_called_once_with(path, [64])
        self.assertEqual(path.read_bytes(), b"unchanged export bytes")

    def test_profile_archive_recovery_path(self):
        from app.settings import SettingsPage
        page = self.keep(QWidget())
        page._selected_profile_id = lambda: "qa-id"
        page._request_profile_pin = lambda *args: True
        page._refresh_profiles = Mock()
        path = r"C:\Παραγωγή Αποθήκευση Save\Ναι {2027}\file.db"
        page.profiles = SimpleNamespace(get=lambda _: SimpleNamespace(name=RAW), archive=Mock(return_value=path))
        def inspect(box):
            question = box.icon() == QMessageBox.Icon.Warning
            for code in ("el", "en", "el"):
                self.controller.set_language(code, persist=False)
                self.controller.apply_to(box)
                self.assertIn(RAW if question else path, box.text())
                if code == "en": self.assertIn("Remove profile" if question else "recoverable here:", box.text())
            return QMessageBox.StandardButton.Yes if question else QMessageBox.StandardButton.Ok
        with patch.object(QMessageBox, "exec", inspect): SettingsPage.archive_profile(page)
        page.profiles.archive.assert_called_once_with("qa-id")
        page._refresh_profiles.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
