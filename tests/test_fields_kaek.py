"""Phase 1 KAEK: local field CRUD, preserved legacy data and explicit browser link."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.database import Database
from app.fields import FieldsPage
from app.gis.geometry import manual_coordinates
from app.gis.store import GeometryStore
from tests.language_fixture import scoped_language


class FieldsKaekTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch("app.database.DATA_DIR", self.root / "data"))
        self.enterContext(scoped_language(self.app, "el"))
        self.db = Database(self.root / "farm.db")
        self.page = FieldsPage(self.db)
        self.addCleanup(self.page.deleteLater)
        self.page.name.setText("Synthetic field")

    def test_optional_empty_kaek(self):
        self.page.kaek.setText("   ")
        self.page.save_field()
        row = self.db.query_one("SELECT name,kaek,typeof(kaek) AS storage FROM fields")
        self.assertEqual(("Synthetic field", "", "text"), tuple(row))

    def test_leading_zeros_survive_create_edit_and_reopen(self):
        self.page.kaek.setText(" 001234567890 ")
        self.page.save_field()
        self.assertEqual("001234567890", self.page.table.item(0, 1).text())
        self.page.load_selected(0, 0)
        self.assertEqual("001234567890", self.page.kaek.text())
        self.page.kaek.setText("000000000001")
        self.page.save_field()
        reopened = Database(self.db.path)
        row = reopened.query_one("SELECT kaek,typeof(kaek) AS storage FROM fields")
        self.assertEqual(("000000000001", "text"), tuple(row))

    def test_nonstandard_populated_values_are_rejected_without_writing(self):
        invalid = ("12345678901", "1234567890123", "12345678901A",
                   "12345 678901", "+12345678901", "001234567890/0/0",
                   "１２３４５６７８９０１２", "٠١٢٣٤٥٦٧٨٩٠١")
        for value in invalid:
            with self.subTest(value=value), patch("app.fields._message") as warning:
                self.page.kaek.setText(value)
                self.page.save_field()
                warning.assert_called_once()
                self.assertEqual(value, self.page.kaek.text())
                self.assertEqual(0, self.db.query_one("SELECT count(*) FROM fields")[0])

    def test_legacy_data_and_manual_geometry_remain_intact(self):
        identity = self.db.execute(
            "INSERT INTO fields(name,kaek,location,area_stremma,productive_trees,notes) "
            "VALUES(?,?,?,?,?,?)",
            ("Legacy field", "001234567890/0/0", "Synthetic location", 2.5, 8, "Keep notes"),
        )
        store = GeometryStore(self.db)
        geometry = manual_coordinates(
            "26 38\n26.001 38\n26.001 38.001\n26 38.001", "EPSG:4326"
        )
        store.save(identity, geometry, source="manual")
        before_geometry = store.get(identity)
        before = tuple(self.db.query_one("SELECT * FROM fields WHERE id=?", (identity,)))
        Database(self.db.path)  # Existing schema/legacy values remain compatible.
        self.page.refresh()
        self.page.load_selected(0, 0)
        self.assertEqual("001234567890/0/0", self.page.kaek.text())
        self.page.name.setText("Edited name")
        with patch("app.fields._message") as warning:
            self.page.save_field()
        warning.assert_called_once()
        self.assertEqual(before, tuple(self.db.query_one("SELECT * FROM fields WHERE id=?", (identity,))))
        self.page.kaek.setText("001234567890")
        self.page.save_field()
        row = self.db.query_one("SELECT * FROM fields WHERE id=?", (identity,))
        self.assertEqual(("Edited name", "001234567890", "Synthetic location", 2.5, 8, "Keep notes"), tuple(row)[1:])
        after_geometry = store.get(identity)
        for key in before_geometry:
            if key not in ("current_name", "current_kaek"):
                self.assertEqual(before_geometry[key], after_geometry[key], key)
        self.assertEqual("manual", after_geometry["geometry_source"])

    def test_map_opens_only_on_click_with_no_user_data(self):
        with patch("app.fields.QDesktopServices.openUrl", return_value=True) as browser:
            page = FieldsPage(self.db)
            try:
                page.name.setText("Private field name")
                page.kaek.setText("001234567890")
                page.save_field()
                browser.assert_not_called()
                page.cadastre_button.click()
                browser.assert_called_once()
                url = browser.call_args.args[0]
                self.assertEqual("https://maps.ktimatologio.gr/", url.toString())
                self.assertFalse(url.hasQuery())
                self.assertFalse(url.hasFragment())
            finally:
                page.deleteLater()

    def test_browser_failure_does_not_block_local_crud(self):
        with patch("app.fields.QDesktopServices.openUrl", return_value=False), patch("app.fields._message") as warning:
            self.page.cadastre_button.click()
            warning.assert_called_once()
        self.page.kaek.setText("001234567890")
        self.page.save_field()
        self.page.load_selected(0, 0)
        self.page.kaek.clear()
        self.page.save_field()
        self.assertEqual("", self.db.query_one("SELECT kaek FROM fields")[0])

    def test_english_labels_keep_kaek_as_user_data(self):
        with scoped_language(self.app, "en") as language:
            language.apply_to(self.page)
            self.assertEqual("Optional · 12 digits", self.page.kaek.placeholderText())
            self.assertEqual("Official Greek Cadastre map (online)", self.page.cadastre_button.text())
            self.assertIn("may differ", self.page.boundary_notice.text())
            self.assertIn("No KAEK or coordinates", self.page.cadastre_button.toolTip())
            self.page.kaek.setText("001234567890")
            language.apply_to(self.page)
            self.assertEqual("001234567890", self.page.kaek.text())
            self.assertIn("exactly 12 digits", language.translate_exact(
                "Ο ΚΑΕΚ γεωτεμαχίου πρέπει να περιέχει ακριβώς 12 ψηφία (0–9) ή να μείνει κενός."
            ))


if __name__ == "__main__":
    unittest.main()
