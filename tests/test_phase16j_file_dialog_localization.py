"""Native dialog arguments are owned text; filenames and patterns are not."""
from contextlib import ExitStack
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
from string import Formatter
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, mock_open, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from app import language


RAW_NAME = "Αποθήκευση Παραγωγή Ναι {year} & Ω"
RAW_DIR = r"C:\Δοκιμή Αποθήκευση Save\Παραγωγή {2027} & Ω"
STAMP = datetime(2027, 4, 5, 6, 7, 8)
# Independent expected arguments, not obtained from the translation catalog.
# module, class, method, dialog method, EL caption, EN caption, default, EL/EN filter
CASES = [
    ("annual_report", "AnnualFarmReportPage", "export_csv", "getSaveFileName", "Αποθήκευση Ετήσιας Αναφοράς", "Save Annual Report", "annual_report_2027.csv", "CSV (*.csv)", "CSV (*.csv)"),
    ("audit", "AuditPage", "export_csv", "getSaveFileName", "Εξαγωγή ιστορικού CSV", "Export history CSV", "mastixa_audit_history.csv", "CSV (*.csv)", "CSV (*.csv)"),
    ("dashboard", "DashboardPage", "restore_backup", "getOpenFileName", "Επίλεξε backup για επαναφορά", "Select a backup to restore", RAW_DIR, "SQLite Database (*.db);;Όλα τα αρχεία (*)", "SQLite Database (*.db);;All files (*)"),
    ("data_export", "DataExportPage", "export_zip", "getSaveFileName", "Δημιουργία φορητού ZIP", "Create portable ZIP", "mastixa_data_export_20270405_060708.zip", "ZIP (*.zip)", "ZIP (*.zip)"),
    ("data_quality", "DataQualityPage", "export_csv", "getSaveFileName", "Εξαγωγή ελέγχου δεδομένων", "Export data check", "mastixa_data_quality.csv", "CSV (*.csv)", "CSV (*.csv)"),
    ("field_finance", "FieldFinancePage", "export_csv", "getSaveFileName", "Εξαγωγή κόστους ανά αγροτεμάχιο", "Export cost by field", "mastixa_field_costs_2027.csv", "CSV (*.csv)", "CSV (*.csv)"),
    ("gis.dialog", "ParcelMapDialog", "import_file", "getOpenFileName", "Εισαγωγή ορίων", "Import boundary", "", "Γεωμετρία (*.geojson *.json *.kml *.gml *.xml *.zip *.dxf)", "Geometry (*.geojson *.json *.kml *.gml *.xml *.zip *.dxf)"),
    ("gis.export_dialog", "CoordinateExportDialog", "export", "getSaveFileName", "Εξαγωγή", "Export", RAW_NAME + "_KAEK_123_coordinates_source.csv", "CSV (*.csv)", "CSV (*.csv)"),
    ("inventory_report", "InventoryReportPage", "export_csv", "getSaveFileName", "Αποθήκευση Αναφοράς Αποθήκης", "Save Inventory Report", "inventory_stock_report.csv", "CSV (*.csv)", "CSV (*.csv)"),
    ("invoice_documents", "InvoiceDocumentsPage", "choose_files", "getOpenFileNames", "Εισαγωγή τιμολογίων", "Import invoices", "", "Τιμολόγια (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp *.pdf);;Όλα (*.*)", "Invoices (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp *.pdf);;All (*.*)"),
    ("invoice_documents", "InvoiceDocumentsPage", "export_selected", "getSaveFileName", "Εξαγωγή επιλεγμένων τιμολογίων", "Export selected invoices", "mastixa_invoices_20270405_060708.zip", "ZIP (*.zip)", "ZIP (*.zip)"),
    ("reports", "ReportsPage", "export_pdf", "getSaveFileName", "Εξαγωγή αναφοράς σε PDF", "Export report to PDF", "mastixa_report_2027.pdf", "PDF (*.pdf)", "PDF (*.pdf)"),
    ("reports", "ReportsPage", "export_excel", "getSaveFileName", "Εξαγωγή αναφοράς σε Excel", "Export report to Excel", "mastixa_report_2027.xlsx", "Excel (*.xlsx)", "Excel (*.xlsx)"),
    ("sales_report", "SalesReportPage", "export_csv", "getSaveFileName", "Αποθήκευση Αναφοράς Πωλήσεων", "Save Sales Report", "sales_report.csv", "CSV (*.csv)", "CSV (*.csv)"),
    ("settings", "SettingsPage", "choose_profile_avatar", "getOpenFileName", "Εικόνα προφίλ", "Profile image", "", "Εικόνες (*.png *.jpg *.jpeg *.webp *.bmp)", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"),
    ("settings", "SettingsPage", "export_profile", "getSaveFileName", "Εξαγωγή προφίλ", "Export profile", RAW_NAME + ".fieltraprofile", "Προφίλ Mastixa (*.fieltraprofile)", "Mastixa profile (*.fieltraprofile)"),
    ("settings", "SettingsPage", "import_profile", "getOpenFileName", "Εισαγωγή προφίλ", "Import profile", "", "Προφίλ Mastixa (*.fieltraprofile)", "Mastixa profile (*.fieltraprofile)"),
    ("settings", "SettingsPage", "choose_backup_folder", "getExistingDirectory", "Επιλογή φακέλου backups", "Choose backup folder", RAW_DIR, None, None),
    ("upload_center", "UploadCenterPage", "export_selected_snapshot", "getSaveFileName", "Εξαγωγή επιλεγμένου snapshot", "Export selected snapshot", "mastixa_snapshot_2027_64.json", "JSON (*.json)", "JSON (*.json)"),
    ("upload_center", "UploadCenterPage", "export_json", "getSaveFileName", "Εξαγωγή πακέτου JSON", "Export JSON package", "mastixa_declaration_2027.json", "JSON (*.json)", "JSON (*.json)"),
]


class FileDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.modules = {c[0]: importlib.import_module("app." + c[0]) for c in CASES}

    def setUp(self):
        self.previous = getattr(self.app, "_mastixa_language_controller", None)
        self.previous_enabled = getattr(self.previous, "_enabled", False)
        self.profiles = Mock()
        self.profiles.active_profile.language = "el"
        self.controller = language.LanguageController(self.app, self.profiles)
        # Minimal owner exercises the real method, without unrelated page startup.
        self.owner = Mock()
        o = self.owner
        o.year.currentData.return_value = 2027
        # Annual export now consumes its immutable report snapshot.
        o._annual_report_snapshot.return_value = SimpleNamespace(year=2027)
        o.year_filter = o.year
        o.product_filter.currentData.return_value = None
        o.table.rowCount.return_value = 1
        o._rows_cache = [{"raw": RAW_NAME}]
        o._filtered_issues.return_value = [{"raw": RAW_NAME}]
        o._sales_rows.return_value = [{"raw": RAW_NAME}]
        o._selected_sections.return_value = [("producer", "Παραγωγός", ["producer"])]
        o._selected_product.return_value = None
        o._selected_ids.return_value = [64]
        o._selected_profile_id.return_value = "qa-profile"
        o._request_profile_pin.return_value = True
        o.profiles.get.return_value = SimpleNamespace(name=RAW_NAME)
        o.backup_dir.text.return_value = RAW_DIR
        o.backup_manager.backup_dir = Mock(spec=Path)
        o.backup_manager.backup_dir.__str__ = Mock(return_value=RAW_DIR)
        o.parcels = [SimpleNamespace(name=RAW_NAME, kaek="123")]
        o.format.currentText.return_value = "CSV"
        o.effective_mode.return_value = "source"
        o.current_validation_errors = []
        o.current_payload = {"year": 2027, "raw": RAW_NAME}
        o.selected_snapshot_id = 64
        o.db.query_one.return_value = {"id": 64, "declaration_year": 2027, "payload_json": RAW_NAME}
        o._snapshot_integrity_ok.return_value = True

    def tearDown(self):
        self.app.removeEventFilter(self.controller)
        self.controller._enabled = False
        self.app._mastixa_language_controller = self.previous
        if self.previous is not None:
            self.previous._enabled = self.previous_enabled
            if self.previous_enabled:
                self.app.installEventFilter(self.previous)
        self.controller.deleteLater()

    def invoke(self, case, returned=None):
        module, cls, method, api = case[:4]
        if returned is None:
            returned = [] if api == "getOpenFileNames" else ""
        result = returned if api == "getExistingDirectory" else (returned, "")
        with patch.object(QFileDialog, api, return_value=result) as dialog:
            getattr(getattr(self.modules[module], cls), method)(self.owner)
        dialog.assert_called_once()
        return dialog.call_args.args

    def check_arguments(self, case):
        for code in ("el", "en", "el"):
            with self.subTest(language=code):
                self.controller.set_language(code, persist=False)
                with ExitStack() as stack:
                    for name in ("data_export", "invoice_documents"):
                        clock = stack.enter_context(patch.object(self.modules[name], "datetime"))
                        clock.now.return_value = STAMP
                    args = self.invoke(case)
                self.assertIs(args[0], self.owner)
                self.assertEqual(args[1], case[4 if code == "el" else 5])
                if code == "en":
                    self.assertNotRegex(args[1], r"[\u0370-\u03ff\u1f00-\u1fff]")
                self.assertEqual(args[2], case[6])
                if case[7] is not None:
                    self.assertEqual(args[3], case[7 if code == "el" else 8])
        self.profiles.set_language.assert_not_called()

    def test_cancellation_has_no_downstream_writes_all_twenty(self):
        for code in ("el", "en"):
            self.controller.set_language(code, persist=False)
            for case in CASES:
                with self.subTest(language=code, surface=case[:3]), ExitStack() as stack:
                    self.owner.reset_mock()
                    operations = [stack.enter_context(patch(target)) for target in (
                        "builtins.open", "pathlib.Path.open", "pathlib.Path.write_text",
                        "pathlib.Path.mkdir", "os.replace", "tempfile.mkstemp", "shutil.copy2",
                        "zipfile.ZipFile")]
                    for target in ("app.reports.export_report_pdf", "app.reports.export_report_xlsx", "app.gis.dialog.import_geometry", "app.gis.export_dialog.exports.write"):
                        operations.append(stack.enter_context(patch(target)))
                    self.invoke(case)
                    for operation in operations:
                        operation.assert_not_called()
                    self.owner.db.execute.assert_not_called()
                    self.owner.db.connect.assert_not_called()
                    self.owner.import_files.assert_not_called()
                    self.owner.build_export_zip.assert_not_called()
                    self.owner.profiles.set_avatar.assert_not_called()
                    self.owner.profiles.export_profile.assert_not_called()
                    self.owner.profiles.import_profile.assert_not_called()
                    self.owner.backup_dir.setText.assert_not_called()
                    self.owner.backup_manager.restore_backup.assert_not_called()
                    self.owner.source_crs.assert_not_called()
                    # Existing dashboard pre-dialog directory preparation is retained.
                    if case[0] == "dashboard":
                        self.owner.backup_manager.backup_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
                    else:
                        self.owner.backup_manager.backup_dir.mkdir.assert_not_called()

    def test_selected_report_paths_exact(self):
        for code in ("el", "en"):
            self.controller.set_language(code, persist=False)
            for index, exporter, ext in ((11, "export_report_pdf", ".pdf"), (12, "export_report_xlsx", ".xlsx")):
                path = RAW_DIR + r"\file" + ext
                with patch.object(self.modules["reports"], exporter) as write, patch.object(self.modules["reports"], "_message"):
                    self.invoke(CASES[index], path)
                    self.assertEqual(write.call_args.args[0], path)

    def test_selected_csv_path_exact(self):
        path = RAW_DIR + r"\file.csv"
        for code in ("el", "en"):
            self.controller.set_language(code, persist=False)
            self.owner._issue_values.return_value = [RAW_NAME]
            with patch.object(Path, "open", autospec=True, return_value=mock_open()()) as write, patch.object(self.modules["data_quality"], "_message"):
                self.invoke(CASES[4], path)
                self.assertEqual(str(write.call_args.args[0]), path)

    def test_selected_invoice_files_and_export_exact(self):
        paths = [r"C:\Invoices\Αποθήκευση Παραγωγή Ναι {year}.pdf", RAW_DIR + r"\Ναι.png"]
        for code in ("el", "en"):
            self.controller.set_language(code, persist=False)
            self.owner.import_files.reset_mock()
            self.invoke(CASES[9], paths)
            self.owner.import_files.assert_called_once_with([Path(p) for p in paths])
            path = RAW_DIR + r"\file.zip"
            with patch.object(self.modules["invoice_documents"], "_message"):
                self.invoke(CASES[10], path)
            self.owner.build_export_zip.assert_called_with(Path(path), [64])

    def test_selected_profile_avatar_and_directory_paths_exact(self):
        for code in ("el", "en"):
            self.controller.set_language(code, persist=False)
            for index, operation, ext in ((14, "set_avatar", ".png"), (15, "export_profile", ".fieltraprofile"), (16, "import_profile", ".fieltraprofile")):
                path = RAW_DIR + "\\" + RAW_NAME + ext
                with patch.object(self.modules["settings"], "_message"):
                    self.invoke(CASES[index], path)
                args = getattr(self.owner.profiles, operation).call_args.args
                self.assertEqual(str(args[-1]), path)
            self.invoke(CASES[17], RAW_DIR)
            self.owner.backup_dir.setText.assert_called_with(RAW_DIR)

    def test_gis_import_path_and_crs_exact(self):
        path = RAW_DIR + r"\file.geojson"
        self.owner.source_crs.return_value = "EPSG:2100"
        for code in ("el", "en"):
            self.controller.set_language(code, persist=False)
            with patch("builtins.open", mock_open(read_data=b"geometry")) as read, patch.object(self.modules["gis.dialog"], "import_geometry") as importer:
                self.invoke(CASES[6], path)
            read.assert_called_once_with(path, "rb")
            importer.assert_called_once_with(b"geometry", path, "EPSG:2100")
            self.owner.confirm_geometry.assert_called_with(importer.return_value, "file.geojson")

    def test_gis_export_patterns_and_filenames_all_formats(self):
        for code in ("el", "en"):
            self.controller.set_language(code, persist=False)
            for ext in ("csv", "xlsx", "pdf", "geojson", "kml"):
                self.owner.format.currentText.return_value = ext.upper()
                args = self.invoke(CASES[7])
                self.assertEqual(args[2], RAW_NAME + "_KAEK_123_coordinates_source." + ext)
                self.assertEqual(args[3], f"{ext.upper()} (*.{ext})")

    def test_selected_snapshot_and_json_paths_and_values_exact(self):
        path = RAW_DIR + r"\file.json"
        for code in ("el", "en"):
            self.controller.set_language(code, persist=False)
            for index in (18, 19):
                with patch.object(Path, "write_text", autospec=True) as write, patch.object(self.modules["upload_center"], "_message"):
                    self.invoke(CASES[index], path)
                self.assertEqual(str(write.call_args.args[0]), path)
                payload = write.call_args.args[1]
                self.assertEqual(payload if index == 18 else json.loads(payload)["raw"], RAW_NAME)
                self.owner.db.execute.assert_not_called()

    def test_selected_gis_export_destination_exact(self):
        path = RAW_DIR + r"\file.csv"
        module = self.modules["gis.export_dialog"]
        for code in ("el", "en"):
            self.controller.set_language(code, persist=False)
            with patch.object(module.tempfile, "mkstemp", return_value=(64, "synthetic-stage.csv")) as stage, patch.object(module.os, "close"), patch.object(module.exports, "write") as write, patch.object(module.os, "replace") as replace, patch.object(QMessageBox, "information"):
                self.invoke(CASES[7], path)
            self.assertEqual(stage.call_args.kwargs["dir"], Path(RAW_DIR))
            write.assert_called_once_with("synthetic-stage.csv", self.owner.parcels, "source", "csv")
            replace.assert_called_once_with("synthetic-stage.csv", Path(path))

    def test_new_catalog_has_five_unique_owned_keys(self):
        catalogs = Path(language.__file__).parent / "locales"
        target = catalogs / "en_phase16j_file_dialogs.json"
        entries = json.loads(target.read_text(encoding="utf-8"))["translations"]
        self.assertEqual(set(entries), {"Εισαγωγή τιμολογίων", "Όλα τα αρχεία", "Γεωμετρία", "Εικόνες", "Προφίλ Mastixa"})
        for source, translated in entries.items():
            self.assertNotRegex(translated, r"[\u0370-\u03ff\u1f00-\u1fff]")
            self.assertNotIn("*", translated)
            fields = lambda text: [field for _, field, _, _ in Formatter().parse(text) if field is not None]
            self.assertEqual(fields(source), fields(translated))
        for catalog in catalogs.glob("*.json"):
            if catalog != target:
                self.assertFalse(entries.keys() & json.loads(catalog.read_text(encoding="utf-8"))["translations"].keys(), catalog.name)


def _argument_test(case):
    def test(self):
        self.check_arguments(case)
    return test


for _case in CASES:
    setattr(FileDialogTests, "test_arguments_" + _case[0].replace(".", "_") + "_" + _case[2], _argument_test(_case))


if __name__ == "__main__":
    unittest.main()
