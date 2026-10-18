import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QWidget,
)

from app.alpha2_step4_ui import install_alpha2_step4_ui
from app.alpha2_step5_ui import install_alpha2_step5_ui
from app.database import Database
from app.declaration import DeclarationPage
from app.fields import FieldsPage
from app.gis.dialog import ParcelMapDialog
from app.invoice_documents import InvoiceDocumentsPage
from app.upload_center import UploadCenterPage


class Alpha2Step5UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        install_alpha2_step4_ui()
        install_alpha2_step5_ui()

    def make_db(self, root: Path) -> Database:
        return Database(root / "farm.db")

    def assert_under_construction_page(self, page: QWidget) -> None:
        self.assertTrue(bool(page.property("mastixaUnderConstruction")))
        panel = page.findChild(QWidget, "alpha2UnderConstructionPanel")
        self.assertIsNotNone(panel)
        status = panel.findChild(QLabel, "underConstructionStatus")
        self.assertIsNotNone(status)
        self.assertEqual("Υπό κατασκευή", status.text())

        scroll = panel.findChild(QScrollArea, "underConstructionScroll")
        self.assertIsNotNone(scroll)
        self.assertTrue(scroll.widgetResizable())
        self.assertEqual(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
            scroll.horizontalScrollBarPolicy(),
        )

        detail = panel.findChild(QLabel, "underConstructionDetail")
        self.assertIsNotNone(detail)
        self.assertTrue(detail.wordWrap())
        self.assertEqual(
            QSizePolicy.Policy.Expanding,
            detail.sizePolicy().horizontalPolicy(),
        )
        self.assertEqual(0, detail.minimumWidth())

        surfaces = getattr(page, "_alpha2_original_surfaces", [])
        self.assertGreater(len(surfaces), 0)
        for surface in surfaces:
            self.assertTrue(surface.isHidden())
            self.assertFalse(surface.isEnabled())

    def test_declaration_and_submission_pages_are_visible_placeholders_only(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = self.make_db(Path(folder))
            pages = [DeclarationPage(db), UploadCenterPage(db)]
            try:
                for page in pages:
                    with self.subTest(page=type(page).__name__):
                        self.assert_under_construction_page(page)
                        detail = page.findChild(QLabel, "underConstructionDetail")
                        self.assertIsNotNone(detail)
                        self.assertIn("δεδομένα διατηρούνται", detail.text())
                        page.resize(360, 220)
                        page.show()
                        self.app.processEvents()
                        self.assertGreater(detail.height(), detail.fontMetrics().height())
            finally:
                for page in pages:
                    page.deleteLater()

    def test_invoice_documents_page_hides_all_unfinished_actions(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            page = InvoiceDocumentsPage(self.make_db(Path(folder)))
            try:
                self.assert_under_construction_page(page)
                detail = page.findChild(QLabel, "underConstructionDetail")
                self.assertIsNotNone(detail)
                page.resize(360, 220)
                page.show()
                self.app.processEvents()
                self.assertGreater(detail.height(), detail.fontMetrics().height())
                self.assertFalse(page.import_button.isEnabled())
                self.assertFalse(page.save_button.isEnabled())
                self.assertFalse(page.post_button.isEnabled())

                surfaces = page._alpha2_original_surfaces
                self.assertTrue(
                    any(surface.isAncestorOf(page.import_button) for surface in surfaces)
                )
                self.assertTrue(
                    any(surface.isAncestorOf(page.form_box) for surface in surfaces)
                )
            finally:
                page.deleteLater()

    def test_fields_page_keeps_normal_actions_and_adds_only_disabled_ai_import(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            page = FieldsPage(self.make_db(Path(folder)))
            try:
                button = page.findChild(QPushButton, "fieldsAiImportButton")
                self.assertIsNotNone(button)
                self.assertEqual(
                    "AI εισαγωγή από έγγραφο / φωτογραφία — Υπό κατασκευή",
                    button.text(),
                )
                self.assertFalse(button.isEnabled())
                self.assertTrue(bool(button.property("mastixaFutureOnly")))

                self.assertTrue(page.save_button.isEnabled())
                self.assertTrue(page.map_button.isEnabled())
                self.assertTrue(page.coordinates_button.isEnabled())
            finally:
                page.deleteLater()

    def test_legacy_ui_installer_preserves_verified_cadastre_queue_action(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = self.make_db(Path(folder))
            db.execute(
                """
                INSERT INTO fields
                    (name, kaek, location, area_stremma, productive_trees, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("Test field", "123456789012", "", 1.0, 0, ""),
            )
            field = db.query_one("SELECT id FROM fields ORDER BY id DESC LIMIT 1")
            self.assertIsNotNone(field)
            controller=Mock()
            db._kaek_lookup_controller=controller

            with patch(
                "app.gis.providers.UnverifiedCadastreProvider.fetch"
            ) as provider_fetch, patch(
                "app.alpha2_step5_ui.QMessageBox.information"
            ) as information:
                dialog = ParcelMapDialog(db, int(field["id"]))
                try:
                    cadastre = dialog.findChild(QPushButton, "cadastreLookupButton")
                    self.assertIsNotNone(cadastre)
                    self.assertTrue(cadastre.isEnabled())

                    enabled_texts = {
                        button.text()
                        for button in dialog.findChildren(QPushButton)
                        if button.isEnabled()
                    }
                    self.assertIn("Εισαγωγή ορίων", enabled_texts)
                    self.assertIn("Συντεταγμένες", enabled_texts)

                    cadastre.click()
                    provider_fetch.assert_not_called()
                    information.assert_not_called()
                    controller.retry.assert_called_once_with(int(field['id']))
                finally:
                    dialog.map.shutdown()
                    dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
