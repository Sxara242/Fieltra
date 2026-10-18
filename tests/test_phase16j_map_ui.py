"""Map summary localization must not translate parcel names or source filenames."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (QApplication, QAbstractButton, QDialog, QLabel,
    QTableWidget, QComboBox, QLineEdit, QPlainTextEdit, QMessageBox)
from app.database import Database
from app.gis.dialog import ParcelMapDialog
from app.gis.geometry import manual_coordinates
from app.gis.store import GeometryStore
from app.language import LanguageController, _has_greek


class MapLocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.folder.name) / 'map-ui.db')
        self.field = self.db.execute('INSERT INTO fields(name,kaek) VALUES(?,?)',
                                     ('Παραγωγή / Αποθήκη', '000123'))
        self.language = LanguageController(
            self.app, SimpleNamespace(active_profile=SimpleNamespace(language='el')))
        self.dialog = None

    def tearDown(self):
        if self.dialog:
            self.dialog.close()
            self.dialog.deleteLater()
        self.app.removeEventFilter(self.language)
        self.language._enabled = False
        self.app.processEvents()
        self.folder.cleanup()

    def verify_cycles(self, has_geometry):
        with self.db.connect() as conn:
            before = list(conn.iterdump())
        self.dialog = ParcelMapDialog(self.db, self.field)
        self.dialog.show()
        self.app.processEvents()
        for code in ('el', 'en', 'el', 'en', 'el', 'en'):
            with self.subTest(language=code):
                self.language.set_language(code, persist=False)
                self.app.processEvents()
                text = self.dialog.info.text()
                self.assertTrue(text.startswith('Παραγωγή / Αποθήκη · '), text)
                self.assertIn('000123', text)
                if has_geometry:
                    self.assertNotIn('Παραγωγή.geojson', text)
                    def inspect_sources(modal):
                        technical=modal.findChild(QPlainTextEdit).toPlainText()
                        self.assertIn('Παραγωγή.geojson',technical)
                        self.assertIn('Perimeter:' if code=='en' else 'Περίμετρος:',technical)
                        return QDialog.DialogCode.Rejected
                    with patch.object(QDialog,'exec',new=inspect_sources):self.dialog.show_sources()
                self.assertIn('Not specified' if code=='en' else 'Δεν έχει οριστεί',text)
                self.assertNotIn('CRS:',text)
                self.assertEqual('Parcel map' if code == 'en' else 'Χάρτης αγροτεμαχίου', self.dialog.windowTitle())
                if code == 'en':
                    captions = [w.text() for w in self.dialog.findChildren(QAbstractButton)]
                    captions += [self.dialog.basemap.itemText(i) for i in range(self.dialog.basemap.count())]
                    captions += [self.dialog.attribution.text()]
                    self.assertFalse(any(_has_greek(value) for value in captions), captions)
        with self.db.connect() as conn:
            self.assertEqual(before, list(conn.iterdump()))

    def test_saved_boundary_keeps_name_and_source_through_language_cycles(self):
        GeometryStore(self.db).save(self.field, manual_coordinates(
            '26 38\n26.001 38\n26.001 38.001\n26 38.001', 'EPSG:4326'), 'Παραγωγή.geojson')
        self.verify_cycles(True)

    def test_native_map_background_follows_application_palette(self):
        from app.gis.map_view import ParcelMap

        map_view = ParcelMap(Path(self.folder.name) / "theme-map-cache")
        try:
            light = QPalette()
            light.setColor(QPalette.ColorRole.Window, QColor("#F5F6F3"))
            map_view.setPalette(light)
            map_view._apply_palette_theme()
            self.assertFalse(map_view._dark_map)
            self.assertEqual(
                "#edf1e8",
                map_view.backgroundBrush().color().name(),
            )

            dark = QPalette()
            dark.setColor(QPalette.ColorRole.Window, QColor("#171D21"))
            map_view.setPalette(dark)
            map_view._apply_palette_theme()
            self.assertTrue(map_view._dark_map)
            self.assertEqual(
                "#151a1e",
                map_view.backgroundBrush().color().name(),
            )
        finally:
            map_view.shutdown()
            map_view.deleteLater()

    def test_empty_map_preserves_name_and_switches_empty_state(self):
        self.verify_cycles(False)

    def open_mapped_dialog(self):
        GeometryStore(self.db).save(self.field, manual_coordinates(
            '26 38\n26.001 38\n26.001 38.001\n26 38.001', 'EPSG:4326'), 'manual')
        self.dialog = ParcelMapDialog(self.db, self.field)
        self.dialog.show()
        self.app.processEvents()

    def test_point_list_and_editor_cycle_without_changing_protocol_or_user_data(self):
        self.open_mapped_dialog()
        self.dialog.store.save_point(self.dialog.record['id'], 'tree', 'Παραγωγή',
                                     'Αποθήκη', 26.0005, 38.0005, 2)
        with self.db.connect() as conn:
            before = list(conn.iterdump())
        inspected = []

        def inspect(modal):
            table = modal.findChild(QTableWidget)
            modal.show()
            for code in ('en', 'el', 'en'):
                self.language.set_language(code, persist=False)
                self.app.processEvents()
                if table is not None:
                    self.assertEqual('Παραγωγή', table.item(0, 0).text())
                    self.assertEqual('Tree' if code == 'en' else 'Δέντρο', table.item(0, 1).text())
                else:
                    self.assertEqual('Παραγωγή', modal.findChild(QLineEdit).text())
                    self.assertEqual('Αποθήκη', modal.findChild(QPlainTextEdit).toPlainText())
                    self.assertEqual(0, modal.findChild(QComboBox).currentIndex())
                if code == 'en':
                    captions = [w.text() for w in modal.findChildren(QLabel)]
                    captions += [w.text() for w in modal.findChildren(QAbstractButton)]
                    self.assertFalse(any(_has_greek(c) for c in captions), captions)
            inspected.append('list' if table is not None else 'editor')
            if table is not None:
                table.selectRow(0)
                next(w for w in modal.findChildren(QAbstractButton) if w.text() == 'Edit').click()
            modal.hide()
            return QDialog.DialogCode.Rejected

        with patch.object(QDialog, 'exec', new=inspect):
            self.dialog.points()
        self.assertEqual(['list', 'editor'], inspected)
        # Closed modal must not retain its table refresh connection.
        self.language.set_language('el', persist=False)
        with self.db.connect() as conn:
            self.assertEqual(before, list(conn.iterdump()))

    def test_provider_offline_empty_and_import_failure_messages_are_localized(self):
        self.open_mapped_dialog()
        with self.db.connect() as conn:
            before = list(conn.iterdump())
        inspected = []

        def inspect_box(box):
            text = box.text()
            for code in ('el', 'en', 'el', 'en'):
                self.language.set_language(code, persist=False)
                self.language.apply_to(box)
                if code == 'en':
                    self.assertFalse(_has_greek(box.text()), box.text())
                    self.assertFalse(_has_greek(box.windowTitle()), box.windowTitle())
                else:
                    self.assertTrue(_has_greek(box.text()), box.text())
            inspected.append(text)
            return QMessageBox.StandardButton.Ok

        def inspect(parent, title, text, *args):
            box = QMessageBox(parent)
            box.setWindowTitle(title)
            box.setText(text)
            try:return inspect_box(box)
            finally:box.deleteLater()

        with patch.object(QMessageBox, 'information', side_effect=inspect), patch.object(QMessageBox, 'warning', side_effect=inspect), patch.object(QMessageBox, 'exec', new=inspect_box):
            for index in (2,):
                self.dialog.select_basemap(index)
                self.assertEqual(0,self.dialog.basemap.currentIndex())
                self.assertFalse(self.dialog.map.provider.tile_template)
                for code in ('el','en'):
                    self.language.set_language(code,persist=False)
                    self.dialog._translate_basemap()
                    status=self.dialog.imagery_status.text()
                    self.assertEqual('Unavailable' if code=='en' else 'Μη διαθέσιμο / Unavailable',status)
            self.dialog.offline()
            self.assertIn('Bulk downloading has not been enabled under verified licensing terms.',inspected[-1])
            self.assertIn('Nothing was downloaded.',inspected[-1])
            self.dialog.cadastre()
            self.dialog.tracks()
            invalid = Path(self.folder.name) / 'invalid.geojson'
            invalid.write_text('not geometry', encoding='utf-8')
            with patch('app.gis.dialog.QFileDialog.getOpenFileName', return_value=(str(invalid), '')), patch.object(self.dialog, 'source_crs', return_value='EPSG:4326'):
                self.dialog.import_file()
        self.assertEqual(4, len(inspected))
        with self.db.connect() as conn:
            self.assertEqual(before, list(conn.iterdump()))

    def test_empty_offline_warning_cycles_from_english_and_never_downloads(self):
        self.dialog=ParcelMapDialog(self.db,self.field)
        self.language.set_language('en',persist=False)
        def inspect(box):
            self.assertEqual('Offline map',box.windowTitle())
            for code in ('el','en','el','en'):
                self.language.set_language(code,persist=False)
                self.assertEqual(code=='el',_has_greek(box.text()))
                self.assertEqual(code=='el',_has_greek(box.windowTitle()))
            return QMessageBox.StandardButton.Ok
        with patch.object(QMessageBox,'exec',new=inspect), patch('app.gis.dialog.offline_pack') as pack:
            self.dialog.offline()
        pack.assert_not_called()

    def test_manual_coordinate_dialog_localizes_instructions_and_keeps_input(self):
        self.open_mapped_dialog()
        def inspect(modal):
            editor = modal.findChild(QPlainTextEdit)
            editor.setPlainText('26 38\n26.001 38.001')
            for code in ('el', 'en', 'el', 'en'):
                self.language.set_language(code, persist=False)
                self.language.apply_to(modal)
                self.assertEqual('26 38\n26.001 38.001', editor.toPlainText())
                self.assertEqual(code == 'el', _has_greek(modal.windowTitle()))
                for label in modal.findChildren(QLabel):
                    self.assertEqual(code == 'el', _has_greek(label.text()))
            return QDialog.DialogCode.Rejected
        with patch.object(self.dialog, 'source_crs', return_value='EPSG:4326'), patch.object(QDialog, 'exec', new=inspect):
            self.dialog.manual()
