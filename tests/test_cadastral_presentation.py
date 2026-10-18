"""Focused Sandbox checks: grid measurements, provenance and existing parcel UI."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app.database import Database
from app.fields import FieldsPage
from app.field_profile import FieldProfilePage
from app.gis.cadastral import grid_measurements, cadastral_text, cadastral_summary
from app.gis.dialog import ParcelMapDialog
from app.gis.kaek_lookup import LookupStore, ANDROID_KAEK_SYNC_ENABLED
from app.gis.kaek_provider import NorthAegeanProvider
from app.gis.store import GeometryStore
from tests.language_fixture import scoped_language
from tests.test_kaek_lookup import KAEK, NOW, Response, dataset


class CadastralPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('app.database.DATA_DIR',self.root/'data'))
        self.enterContext(scoped_language(self.app,'el'))
        self.db=Database(self.root/'farm.db')
        self.field=self.db.execute('INSERT INTO fields(name,kaek,area_stremma) VALUES(?,?,?)',('My field',KAEK,0))
        self.lookup=LookupStore(self.db,lambda:NOW)
        self.provider=NorthAegeanProvider(self.root/'cache',Mock(side_effect=lambda *a,**k:Response(dataset())),lambda:NOW/1000)
        self.lookup.enqueue(self.field,self.provider)
        self.result=self.provider.fetch(self.lookup.claim(self.provider))

    def snapshot(self):
        with self.db.connect() as con:return list(con.iterdump())

    def test_epsg2100_holes_and_multipart_area_perimeter(self):
        outer=[[500000,4200000],[500100,4200000],[500100,4200100],[500000,4200100],[500000,4200000]]
        hole=[[500010,4200010],[500010,4200030],[500030,4200030],[500030,4200010],[500010,4200010]]
        other=[[500200,4200000],[500210,4200000],[500210,4200010],[500200,4200010],[500200,4200000]]
        payload=dict(self.result,geometry={'type':'MultiPolygon','coordinates':[[outer,hole],[other]]})
        values=grid_measurements(payload)
        self.assertEqual(9700,values['area_m2'])
        self.assertEqual(9.7,values['area_stremma'])
        self.assertEqual(520,values['perimeter_m'])
        self.assertEqual('EPSG:2100',values['measurement_crs'])

    def test_snapshot_metadata_bound_to_exact_result_and_legacy_is_unknown(self):
        self.lookup.complete(self.result,self.provider,snapshot={'downloaded_at':NOW/1000-100,'checked_at':NOW/1000,'refresh_error':'offline_or_timeout'})
        text=cadastral_text(self.db,self.field)
        self.assertIn('10000.00 m²',text)
        self.assertIn('10.000 στρ.',text)
        self.assertIn('400.00 m',text)
        self.assertIn('2026-10-06',text)
        self.assertIn('παλαιότερο',text)
        with scoped_language(self.app,'en'):
            text=cadastral_text(self.db,self.field)
            self.assertIn('Computed cadastral area:',text)
            self.assertIn('not an officially registered legal area',text)
        self.db.execute("UPDATE cadastral_details SET result_hash='different'")
        self.assertEqual({},self.lookup.details(self.field))
        self.assertIn('Λήψη συνόλου δεδομένων: Μη διαθέσιμο',cadastral_text(self.db,self.field))

    def test_invalid_dbf_update_date_keeps_geometry_but_never_invents_date(self):
        provider=NorthAegeanProvider(self.root/'unknown-date',
            Mock(side_effect=lambda *a,**kw:Response(dataset(parcel_date='unknown'))),lambda:NOW/1000)
        payload=provider.fetch(self.lookup.request(self.lookup.job(self.field)))
        self.assertEqual('',payload['source_date'])
        self.lookup.complete(payload,provider)
        self.assertIn('Τελευταία ενημέρωση γεωτεμαχίου: Μη διαθέσιμο',cadastral_text(self.db,self.field))
        self.assertEqual(10000,grid_measurements(payload)['area_m2'])

    def test_compact_summary_uses_known_parcel_date_and_omits_technical_metadata(self):
        self.lookup.complete(self.result,self.provider)
        before=self.snapshot()
        for code in ('el','en'):
            with scoped_language(self.app,code):
                summary=cadastral_summary(self.db,self.field)
                self.assertIn('10.000',summary)
                self.assertIn('400.00 m',summary)
                self.assertIn('2026-10-06',summary)
                self.assertIn('not an officially registered legal area' if code=='en' else 'όχι επίσημο',summary)
                for technical in ('EPSG','https://','.zip','2026-10-17T'):
                    self.assertNotIn(technical,summary)
        self.assertEqual(before,self.snapshot())

    def test_cadastral_only_map_and_offline_extent_never_create_cultivation(self):
        self.lookup.complete(self.result,self.provider)
        before=self.snapshot()
        dialog=ParcelMapDialog(self.db,self.field)
        try:
            self.assertIsNotNone(dialog.map.cadastral_item)
            self.assertEqual(Qt.TextFormat.PlainText,dialog.cadastral_info.textFormat())
            self.assertIn('10.000',dialog.cadastral_info.text())
            self.assertNotIn('EPSG:',dialog.cadastral_info.text())
            with patch('app.gis.dialog._message') as message:
                dialog.offline()
            self.assertIn('Πλαίσιο με περιθώριο',message.call_args.args[3])
            self.assertNotIn('Χρειάζονται όρια',message.call_args.args[3])
            self.assertEqual(4,len(message.call_args.kwargs['bbox']))
            self.assertEqual([],dialog.map.boundaries)
            self.assertIsNone(GeometryStore(self.db).get(self.field))
            self.assertEqual(before,self.snapshot())
        finally:dialog.map.shutdown();dialog.close();dialog.deleteLater()

    def test_metadata_refresh_preserves_user_view(self):
        self.lookup.complete(self.result,self.provider)
        dialog=ParcelMapDialog(self.db,self.field)
        try:
            dialog.show();self.app.processEvents()
            dialog.map.scale(.7,.7)
            dialog.map.centerOn(dialog.map.cadastral_bounds.center().x()+50,dialog.map.cadastral_bounds.center().y()+50)
            before=dialog.map.transform()
            center=dialog.map.mapToScene(dialog.map.viewport().rect().center())
            dialog._reload_cadastral()
            self.assertEqual(before,dialog.map.transform())
            after=dialog.map.mapToScene(dialog.map.viewport().rect().center())
            # centerOn quantizes each scrollbar to integer viewport pixels.
            # Keep the existing two-pixel L1 bound; allow only floating-point
            # subtraction noise from the large projected scene coordinates.
            shift_pixels=(after-center).manhattanLength()*before.m11()
            self.assertLessEqual(shift_pixels,2.0+1e-8)
        finally:dialog.map.shutdown();dialog.close();dialog.deleteLater()

    def test_map_lookup_button_reuses_existing_queue_without_legacy_arcgis_call(self):
        self.lookup.complete(self.result,self.provider)
        dialog=ParcelMapDialog(self.db,self.field)
        try:
            controller=Mock()
            dialog.lookup_controller=controller
            before=self.snapshot()
            dialog.cadastre()
            controller.retry.assert_called_once_with(self.field)
            self.assertEqual(before,self.snapshot())
        finally:dialog.map.shutdown();dialog.close();dialog.deleteLater()

    def test_fields_and_card_do_not_present_missing_cultivated_area_as_zero(self):
        self.lookup.complete(self.result,self.provider)
        page=FieldsPage(self.db)
        card=FieldProfilePage(self.db)
        try:
            page.lookup.stop()
            page.refresh()
            self.assertEqual('Δεν έχει δηλωθεί',page.table.item(0,3).text())
            self.assertEqual(0,self.db.query_one('SELECT area_stremma FROM fields WHERE id=?',(self.field,))[0])
            self.assertFalse(ANDROID_KAEK_SYNC_ENABLED)
        finally:page.lookup.stop();page.close();card.close();page.deleteLater();card.deleteLater()


if __name__=='__main__':unittest.main()
