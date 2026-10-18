"""Native Qt checks: execute in the retained owner-operated Sandbox only."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.database import Database
from app.gis.dialog import ParcelMapDialog
from app.gis.geometry import manual_coordinates
from app.gis.store import GeometryStore
from tests.language_fixture import scoped_language
from tests.test_map_acceptance_ui import scaled_font


class MapProviderUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name!='nt' or os.environ.get('USERNAME','').lower()!='wdagutilityaccount':
            raise RuntimeError('Execute this native acceptance module only inside Windows Sandbox')
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('app.database.DATA_DIR',self.root))
        self.language=self.enterContext(scoped_language(self.app,'el'))
        self.db=Database(self.root/'farm.db')
        self.field=self.db.execute('INSERT INTO fields(name,kaek,area_stremma) VALUES(?,?,?)',('Provider fixture','510201507004',1))
        self.geometry=manual_coordinates('26.055 38.223\n26.056 38.223\n26.056 38.224\n26.055 38.224','EPSG:4326')
        GeometryStore(self.db).save(self.field,self.geometry,'manual')

    def dialog(self):
        dialog=ParcelMapDialog(self.db,self.field)
        self.addCleanup(dialog.deleteLater);self.addCleanup(dialog.close);self.addCleanup(dialog.map.shutdown)
        # Every Qt HTTP request is a test failure, including requests after switching.
        self.enterContext(patch.object(dialog.map.network,'get',side_effect=AssertionError('Networking disabled for provider test')))
        dialog.show();self.app.processEvents();return dialog

    def snapshot(self):
        with self.db.connect() as connection:return list(connection.iterdump())


    def test_no_basemap_pan_zoom_overlay_fit_and_reopen_preserve_data(self):
        before=self.snapshot();dialog=self.dialog();view=dialog.map
        view.set_cadastral_geometry(self.geometry)
        cultivated=view.boundaries[0];cadastral=view.cadastral_item;vertices=list(view.cadastral_markers)
        transform=view.transform();center=view.mapToScene(view.viewport().rect().center())
        view.load_visible_tiles()
        self.assertFalse(view.tiles);self.assertEqual(transform,view.transform())
        self.assertLessEqual((view.mapToScene(view.viewport().rect().center())-center).manhattanLength()*transform.m11(),2.1)
        for provider in ('neutral','pmtiles','oam'):
            dialog.restore_basemap(provider);view.load_visible_tiles()
            self.assertEqual('neutral',view.provider.identity)
            self.assertIs(cultivated,view.boundaries[0]);self.assertIs(cadastral,view.cadastral_item)
            self.assertEqual(vertices,view.cadastral_markers)
        view.scale(.7,.7);view.centerOn(view.cadastral_bounds.center());view.load_visible_tiles()
        view.show_cadastral(False);view.show_cadastral_vertices(True)
        self.assertFalse(cadastral.isVisible());self.assertTrue(all(v.isVisible() for v in vertices))
        self.assertTrue(view.fit_parcel());dialog.close()
        reopened=self.dialog();self.assertEqual('neutral',reopened.map.provider.identity)
        reopened.map.load_visible_tiles();self.assertFalse(reopened.map.tiles)
        self.assertEqual(before,self.snapshot())

    def test_unavailable_services_never_issue_tiles_and_keep_geometry(self):
        before=self.snapshot();dialog=self.dialog();boundary=dialog.map.boundaries[0]
        for identity,expected in (('arcgis','ArcGIS'),):
            dialog.restore_basemap(identity);self.app.processEvents()
            self.assertEqual('neutral',dialog.map.provider.identity)
            self.assertIn(expected,dialog.imagery_info.text());self.assertIs(boundary,dialog.map.boundaries[0])
        self.assertEqual(before,self.snapshot())

    def test_tabs_have_no_literal_ampersand_and_keep_keyboard_navigation(self):
        dialog=self.dialog()
        for code in ('en','el'):
            self.language.set_language(code,persist=False);self.app.processEvents()
            self.assertEqual(['Field','Map'] if code=='en' else ['Αγροτεμάχιο','Χάρτης'],
                [dialog.sidebar.tabText(i) for i in range(2)])
        bar=dialog.sidebar.tabBar();dialog.sidebar.setCurrentIndex(0);bar.setFocus()
        QTest.keyClick(bar,Qt.Key.Key_Right);self.assertEqual(1,dialog.sidebar.currentIndex())
        QTest.keyClick(bar,Qt.Key.Key_Left);self.assertEqual(0,dialog.sidebar.currentIndex())

    def test_popup_selection_remains_keyboard_accessible(self):
        dialog=self.dialog();combo=dialog.basemap;combo.setFocus();combo.showPopup();self.app.processEvents()
        view=combo.view();view.setCurrentIndex(combo.model().index(1,0))
        QTest.keyClick(view,Qt.Key.Key_Return)
        self.assertEqual('osm',combo.currentData());self.assertFalse(view.isVisible())
        # No tile event loop turn is allowed for the intentionally selected OSM.
        dialog.restore_basemap('neutral')
        from app.ui_helpers import _ComboPopupDelegate
        self.assertIsInstance(view.itemDelegate(),_ComboPopupDelegate)

    def test_pixel_font_scaling_does_not_assign_negative_point_size(self):
        original=QFont();original.setPixelSize(14)
        self.assertEqual(-1,original.pointSizeF())
        for factor,expected in ((1,14),(1.25,18),(1.5,21)):
            font=scaled_font(original,factor);self.assertEqual(expected,font.pixelSize())


if __name__=='__main__':unittest.main()
