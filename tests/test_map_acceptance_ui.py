"""Focused native Sandbox checks for the owner-approved map redesign. No public HTTP."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent,QPoint,QRect,Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication,QPushButton,QScrollArea,QCheckBox,QToolButton,QWidgetItem

from app.database import Database
from app.gis.dialog import ParcelMapDialog
from app.gis.geometry import manual_coordinates
from app.gis.kaek_lookup import LookupStore
from app.gis.map_view import ParcelMap
from app.gis.providers import BASEMAPS,BasemapProvider,cdse_provider
from app.gis.store import GeometryStore
from app.gis.toponyms import ToponymStore
from tests.language_fixture import scoped_language


def scaled_font(original,factor):
    font=QFont(original)
    if original.pixelSize()>0:font.setPixelSize(max(1,round(original.pixelSize()*factor)))
    else:font.setPointSizeF(max(1.0,original.pointSizeF()*factor))
    return font


class MapAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('app.database.DATA_DIR',self.root/'data'))
        self.language=self.enterContext(scoped_language(self.app,'el'))
        # Bind the timer to a no-op before constructing views; these tests must
        # exercise real widgets/geometry without contacting public tile servers.
        self.enterContext(patch.object(ParcelMap,'load_visible_tiles',lambda *_:None))
        self.db=Database(self.root/'farm.db')
        self.field=self.db.execute('INSERT INTO fields(name,kaek,area_stremma) VALUES(?,?,?)',
                                  ('Παραγωγή / Owner field','510201507004',1))
        self.cultivated=manual_coordinates('26.075 38.24\n26.076 38.24\n26.076 38.241\n26.075 38.241','EPSG:4326')
        self.reference=manual_coordinates('26.055 38.223\n26.056 38.223\n26.056 38.224\n26.055 38.224','EPSG:4326')
        self.lookup=LookupStore(self.db,lambda:1_800_000_000_000)
        provider=SimpleNamespace(identity='fixture',supports=lambda _:True,
            source_url='https://example.invalid/parcel',terms_url='https://example.invalid/terms',attribution='Synthetic reference')
        self.lookup.enqueue(self.field,provider)
        request=self.lookup.claim(provider)
        self.lookup.complete(dict(request,kind='kaek-result',geometry=self.reference.wgs84,
            source_crs='EPSG:4326',provider=provider.identity,source_url=provider.source_url,
            terms_url=provider.terms_url,attribution=provider.attribution,source_date='',
            retrieved_at=request['requested_at']),provider)

    def dialog(self,field=None):
        dialog=ParcelMapDialog(self.db,self.field if field is None else field)
        self.addCleanup(dialog.deleteLater);self.addCleanup(dialog.close);self.addCleanup(dialog.map.shutdown)
        dialog.show();self.app.processEvents()
        return dialog

    def snapshot(self):
        with self.db.connect() as con:return list(con.iterdump())

    def assert_visible(self,view,bounds):
        pixels=view.mapFromScene(bounds).boundingRect()
        self.assertTrue(view.viewport().rect().contains(pixels),
                        f'Parcel {pixels} clipped by viewport {view.viewport().rect()}')

    def test_cadastral_only_fit_after_pan_zoom_preserves_basemap_and_data(self):
        before=self.snapshot();dialog=self.dialog();view=dialog.map
        dialog.restore_basemap('osm');provider=view.provider
        view.scale(.3,.3);view.centerOn(0,0)
        dialog.fit_button.click();self.app.processEvents()
        self.assert_visible(view,view.cadastral_bounds)
        self.assertIs(provider,view.provider);self.assertTrue(view.cadastral_item.isVisible())
        self.assertFalse(view.boundaries);self.assertEqual(before,self.snapshot())
        transform=view.transform();dialog.fit_button.click()
        self.assertAlmostEqual(transform.m11(),view.transform().m11(),places=10)
        self.assert_visible(view,view.cadastral_bounds)

    def test_cultivated_extent_is_preferred_to_a_different_reference(self):
        GeometryStore(self.db).save(self.field,self.cultivated,'manual')
        before=self.snapshot();dialog=self.dialog();view=dialog.map
        dialog.cadastral_vertices_control.setChecked(False)
        dialog.restore_basemap('osm');view.scale(3,3);view.centerOn(0,0)
        dialog.fit_button.click();self.app.processEvents()
        self.assert_visible(view,view.bounds)
        visible=view.mapToScene(view.viewport().rect()).boundingRect()
        self.assertFalse(visible.contains(view.cadastral_bounds),'Fit incorrectly unions cultivation with another extent')
        self.assertEqual('osm',view.provider.identity)
        self.assertTrue(all(not point.isVisible() for point in view.cadastral_markers))
        self.assertEqual(before,self.snapshot())

    def test_hidden_cultivation_fits_visible_reference_without_toggling_layers(self):
        GeometryStore(self.db).save(self.field,self.cultivated,'manual')
        dialog=self.dialog();dialog.map.show_boundaries(False)
        dialog.fit_button.click();self.app.processEvents()
        self.assert_visible(dialog.map,dialog.map.cadastral_bounds)
        self.assertFalse(dialog.map.boundaries_visible)
        self.assertTrue(dialog.cadastral_control.isChecked())

    def test_no_geometry_fit_is_safe_and_keeps_provider_and_transform(self):
        field=self.db.execute('INSERT INTO fields(name) VALUES(?)',('Empty',))
        dialog=self.dialog(field);dialog.restore_basemap('osm')
        before=dialog.map.transform()
        self.assertFalse(dialog.map.fit_parcel())
        dialog.fit_button.click();self.assertEqual(before,dialog.map.transform())
        self.assertEqual('osm',dialog.map.provider.identity)

    def test_vertex_layers_are_independent_and_survive_metadata_refresh(self):
        GeometryStore(self.db).save(self.field,self.cultivated,'manual')
        before=self.snapshot();dialog=self.dialog();view=dialog.map
        self.assertEqual(4,len(view.markers));self.assertEqual(4,len(view.cadastral_markers))
        dialog.cadastral_vertices_control.setChecked(False)
        self.assertTrue(all(point.isVisible() for point in view.markers))
        self.assertTrue(all(not point.isVisible() for point in view.cadastral_markers))
        dialog._reload_cadastral()
        self.assertTrue(all(not point.isVisible() for point in view.cadastral_markers))
        dialog.cadastral_vertices_control.setChecked(True)
        view.show_vertices(False)
        self.assertTrue(all(point.isVisible() for point in view.cadastral_markers))
        self.assertTrue(all(not point.isVisible() for point in view.markers))
        dialog.cadastral_control.setChecked(False)
        self.assertTrue(all(point.isVisible() for point in view.cadastral_markers))
        dialog.cadastral_control.setChecked(True)
        self.assertTrue(all(point.isVisible() for point in view.cadastral_markers))
        self.assertEqual(before,self.snapshot())

    def check_cadastral_layers(self,polygon,vertices):
        before=self.snapshot();dialog=self.dialog();view=dialog.map
        geometry=self.lookup.geometry(self.field)
        dialog.cadastral_control.setChecked(polygon)
        dialog.cadastral_vertices_control.setChecked(vertices)
        for operation in (lambda:None,dialog._reload_cadastral,
                          lambda:dialog.restore_basemap('osm'),
                          lambda:dialog.restore_basemap('neutral'),
                          lambda:(view.scale(.5,.5),view.centerOn(0,0),dialog.fit_button.click())):
            operation();self.app.processEvents()
            self.assertEqual(polygon,view.cadastral_item.isVisible())
            self.assertEqual(4,len(view.cadastral_markers),'No duplicate closing vertex')
            self.assertTrue(all(point.isVisible()==vertices for point in view.cadastral_markers))
            for point in view.cadastral_markers:
                self.assertEqual('#ffbf47',point.brush().color().name())
                self.assertEqual('#352508',point.pen().color().name())
                self.assertEqual(7,point.rect().width())
        self.assert_visible(view,view.cadastral_bounds)
        self.assertEqual(geometry,self.lookup.geometry(self.field));self.assertEqual(before,self.snapshot())

    def test_polygon_off_vertices_off(self):self.check_cadastral_layers(False,False)
    def test_polygon_on_vertices_off(self):self.check_cadastral_layers(True,False)
    def test_polygon_on_vertices_on(self):self.check_cadastral_layers(True,True)
    def test_polygon_off_vertices_on(self):self.check_cadastral_layers(False,True)

    def test_cadastral_only_vertices_toggle_does_not_create_cultivation(self):
        before=self.snapshot();dialog=self.dialog()
        self.assertFalse(dialog.map.markers)
        self.assertTrue(all(point.isVisible() for point in dialog.map.cadastral_markers))
        dialog.cadastral_vertices_control.setChecked(False)
        self.assertTrue(all(not point.isVisible() for point in dialog.map.cadastral_markers))
        self.assertIsNone(GeometryStore(self.db).get(self.field))
        self.assertEqual(before,self.snapshot())

    def test_provider_switch_preserves_free_view_without_comparison_mode(self):
        from datetime import date,timedelta
        dialog=self.dialog();view=dialog.map;end=date.today()
        dialog.cdse=cdse_provider('00000000-0000-0000-0000-000000000001','TRUE_COLOR',
                                  str(end-timedelta(days=7)),str(end))
        view.scale(.6,.6);view.centerOn(view.cadastral_bounds.center().x()+50,view.cadastral_bounds.center().y()+50)
        transform=view.transform();center=view.mapToScene(view.viewport().rect().center());item=view.cadastral_item
        for provider in ('osm','sentinel','neutral'):
            dialog.restore_basemap(provider);self.app.processEvents()
            self.assertEqual(transform,view.transform())
            shift=(view.mapToScene(view.viewport().rect().center())-center).manhattanLength()*transform.m11()
            self.assertLessEqual(shift,2.0+1e-8)
            self.assertIs(item,view.cadastral_item)
        self.assertFalse(hasattr(dialog,'comparison_view'))

    def test_removed_provider_references_fall_back_without_touching_geometry(self):
        before=self.snapshot();dialog=self.dialog();view=dialog.map;item=view.cadastral_item
        self.assertEqual([p.identity for p in BASEMAPS],[dialog.basemap.itemData(i) for i in range(dialog.basemap.count())])
        for value in ('google','versatiles',2,4,99):
            dialog.restore_basemap(value)
            self.assertEqual('neutral',view.provider.identity)
            self.assertFalse(view.provider.tile_template);self.assertIs(item,view.cadastral_item)
        view.set_provider(BasemapProvider('versatiles','Removed',tile_template='https://example.invalid/{z}'))
        self.assertIs(BASEMAPS[0],view.provider);self.assertEqual(before,self.snapshot())

    def test_ui_has_one_fit_no_points_tracks_and_explicit_protomaps_download(self):
        dialog=self.dialog()
        captions=[button.text() for button in dialog.findChildren(QPushButton)]
        self.assertEqual(1,captions.count('Επαναφορά στο αγροτεμάχιο'))
        for text in ('Σημεία','Διαδρομές','Στο αγροτεμάχιο','Σταθερή προβολή σύγκρισης'):
            self.assertNotIn(text,captions)
        self.assertTrue(dialog.offline_button.isEnabled())
        self.assertIn('Χίου',dialog.offline_button.text())
        self.assertTrue(callable(dialog.points));self.assertTrue(callable(dialog.tracks));self.assertTrue(callable(dialog.offline))
        with patch('app.gis.dialog._message') as message:
            dialog.offline()
        self.assertEqual(4,len(message.call_args.kwargs['bbox']))
        self.assertIn('άδειας',message.call_args.args[3])

    def test_only_reference_checkboxes_cultivation_remains_visible_by_default(self):
        GeometryStore(self.db).save(self.field,self.cultivated,'manual')
        before=self.snapshot();dialog=self.dialog()
        self.assertEqual({'Κτηματολογικό πολύγωνο','Κορυφές κτηματολογίου'},
                         {box.text() for box in dialog.findChildren(QCheckBox)})
        self.assertTrue(all(item.isVisible() for item in dialog.map.boundaries))
        self.assertTrue(all(item.isVisible() for item in dialog.map.markers))
        dialog._reload_cadastral();dialog.restore_basemap('osm')
        self.assertTrue(all(item.isVisible() for item in dialog.map.boundaries))
        self.assertEqual(before,self.snapshot())

    def test_missing_geometry_disables_reference_controls_without_writing_old_profile(self):
        field=self.db.execute('INSERT INTO fields(name,area_stremma) VALUES(?,?)',('Legacy',0))
        before=self.snapshot();dialog=self.dialog(field)
        self.assertFalse(dialog.cadastral_control.isEnabled())
        self.assertFalse(dialog.cadastral_vertices_control.isEnabled())
        self.assertFalse(dialog.toponym.confirm.isEnabled())
        self.assertIn('Δεν έχει οριστεί',dialog.info.text())
        self.assertNotIn('0.000',dialog.info.text())
        self.assertEqual(before,self.snapshot())

    def test_real_basemap_arrow_reopens_after_same_selection_and_escape(self):
        from app.appearance_theme import ThemeController
        from app.main_window import STYLESHEET,build_app_palette
        from tests.test_combo_popup import click_arrow,select_popup_item,escape_popup,popup_events
        self.enterContext(patch('app.appearance_theme._SETTINGS_FILE',self.root/'appearance.ini'))
        previous_style,previous_palette=self.app.styleSheet(),self.app.palette()
        self.addCleanup(self.app.setStyleSheet,previous_style);self.addCleanup(self.app.setPalette,previous_palette)
        self.app.setStyleSheet(STYLESHEET);self.app.setPalette(build_app_palette())
        theme=ThemeController(self.app,STYLESHEET,build_app_palette())
        self.addCleanup(theme.deleteLater);self.addCleanup(self.app.removeEventFilter,theme)
        theme.apply_saved_theme()
        dialog=self.dialog();dialog.sidebar.setCurrentIndex(1);self.app.processEvents()
        self.addCleanup(dialog.basemap.hidePopup)
        for mode in ('light','dark','light'):
            theme.set_theme(mode,persist=False)
            for index in (1,0,0):
                click_arrow(dialog.basemap);self.assertTrue(dialog.basemap.view().isVisible())
                select_popup_item(dialog.basemap,index)
                evidence=popup_events(dialog.basemap).describe()
                self.assertFalse(dialog.basemap.view().window().isVisible(),evidence)
                self.assertEqual(index,dialog.basemap.currentIndex(),evidence)
                self.assertEqual('osm' if index else 'neutral',dialog.map.provider.identity)
            click_arrow(dialog.basemap);self.assertTrue(dialog.basemap.view().isVisible())
            selected=dialog.basemap.currentIndex();escape_popup(dialog.basemap)
            self.assertFalse(dialog.basemap.view().window().isVisible(),popup_events(dialog.basemap).describe())
            self.assertEqual(selected,dialog.basemap.currentIndex())
            click_arrow(dialog.basemap);self.assertTrue(dialog.basemap.view().isVisible())
            escape_popup(dialog.basemap)

    def test_compact_summary_unknown_date_and_optional_sources_keep_provenance(self):
        from PySide6.QtWidgets import QDialog,QPlainTextEdit
        dialog=self.dialog();before=self.snapshot()
        self.assertNotIn('Ημερομηνία',dialog.cadastral_info.text())
        self.assertIn('Δοκιμαστικά δεδομένα',dialog.cadastral_info.text())
        self.assertIn('όχι επίσημο',dialog.cadastral_info.text())
        for value in ('EPSG','https://','Synthetic reference','fixture'):
            self.assertNotIn(value,dialog.info.text()+dialog.cadastral_info.text())
        def inspect(modal):
            source=modal.findChild(QPlainTextEdit).toPlainText()
            self.assertIn('EPSG:4326',source)
            self.assertIn('https://example.invalid/parcel',source)
            self.assertIn('https://example.invalid/terms',source)
            self.assertIn('Synthetic reference',source)
            return QDialog.DialogCode.Rejected
        with patch.object(QDialog,'exec',new=inspect):dialog.show_sources()
        self.assertEqual(before,self.snapshot())

    def test_sidebar_resize_font_stress_and_language_cycles_do_not_change_data(self):
        from app.main_window import STYLESHEET
        from app.icon_theme import apply_icon_theme
        previous=self.app.styleSheet();self.addCleanup(self.app.setStyleSheet,previous)
        self.app.setStyleSheet(STYLESHEET)
        before=self.snapshot();dialog=self.dialog();original=QFont(dialog.font())
        for factor,width,height in ((1,1100,740),(1.25,1000,700),(1.5,900,640)):
            font=scaled_font(original,factor)
            dialog.setFont(font);dialog.resize(width,height);dialog.splitter.setSizes([width-330,300])
            for code in ('en','el'):
                self.language.set_language(code,persist=False);self.app.processEvents()
                apply_icon_theme(dialog);self.app.processEvents()
                self.assertGreater(dialog.map.width(),dialog.width()/2,f'font scale {factor}, language {code}')
                self.assertEqual('Fit to parcel' if code=='en' else 'Επαναφορά στο αγροτεμάχιο',dialog.fit_button.text())
                self.assertEqual(2,dialog.sidebar.count())
                self.assertEqual(['Parcel','Map'] if code=='en' else ['Αγροτεμάχιο','Χάρτης'],
                                 [dialog.sidebar.tabText(i).replace('&','') for i in range(2)])
                bar=dialog.sidebar.tabBar()
                self.assertFalse(bar.usesScrollButtons())
                self.assertTrue(all(not button.isVisible() for button in bar.findChildren(QToolButton)))
                self.assertTrue(all(bar.rect().contains(bar.tabRect(i)) for i in range(2)))
                # Edit is intentionally hidden until a saved confirmation exists.
                # QWidgetItem::isEmpty excludes it; its stale/default geometry
                # cannot describe clipping of an action the user can see.
                self.assertTrue(dialog.toponym.edit.isHidden())
                self.assertFalse(dialog.toponym.edit.sizePolicy().retainSizeWhenHidden())
                self.assertTrue(QWidgetItem(dialog.toponym.edit).isEmpty())
                self.assert_sidebar_actions_fit(dialog,f'{factor}/{code}/unconfirmed')
                self.assertIn('Παραγωγή / Owner field',dialog.info.text())
                self.assertIn('510201507004',dialog.info.text())
        self.assertEqual(before,self.snapshot())

    def assert_sidebar_actions_fit(self,dialog,context):
        for index in range(dialog.sidebar.count()):
            dialog.sidebar.setCurrentIndex(index)
            # Translation posts zero-timer work, followed by LayoutRequest.
            # Drain both event turns before inspecting Qt-managed rectangles.
            for _ in range(2):
                self.app.processEvents()
                QApplication.sendPostedEvents(None,QEvent.Type.LayoutRequest.value)
            scroll=dialog.sidebar.widget(index)
            self.assertIsInstance(scroll,QScrollArea)
            self.assertEqual(0,scroll.horizontalScrollBar().maximum())
            content=scroll.widget()
            self.assertFalse(content.findChildren(QScrollArea),'Nested sidebar scroll areas')
            self.assertLessEqual(content.width(),scroll.viewport().width(),'Sidebar content exceeds viewport width')
            actions=[button for button in content.findChildren(QPushButton) if button.isVisibleTo(content)]
            self.assertTrue(actions,f'No visible actions: {context}/{index}')
            for button in actions:
                detail=(f'{context}/{index}: {button.text()}, hidden={button.isHidden()}, '
                    f'geometry={button.geometry()}, parent={button.parentWidget().rect()}, '
                    f'content={content.rect()}, viewport={scroll.viewport().rect()}')
                self.assertFalse(QWidgetItem(button).isEmpty(),detail)
                rect=QRect(button.mapTo(content,QPoint(0,0)),button.size())
                self.assertTrue(content.rect().contains(rect),'Sidebar action clipped: '+detail)
                self.assertTrue(button.parentWidget().rect().contains(button.geometry()),detail)
                scroll.ensureWidgetVisible(button,0,0);self.app.processEvents()
                visible=QRect(button.mapTo(scroll.viewport(),QPoint(0,0)),button.size())
                self.assertTrue(scroll.viewport().rect().contains(visible),'Action cannot be scrolled fully into view: '+detail)
        dialog.sidebar.setCurrentIndex(0);self.app.processEvents()
        self.assertTrue(dialog.toponym.clear.isVisible())
        if dialog.toponym.edit.isHidden():self.assertTrue(dialog.toponym.confirm.isVisible())
        else:self.assertTrue(dialog.toponym.edit.isVisible())

    def test_saved_locality_edit_confirm_clear_actions_fit_after_language_and_font_changes(self):
        from app.main_window import STYLESHEET
        previous=self.app.styleSheet();self.addCleanup(self.app.setStyleSheet,previous)
        self.app.setStyleSheet(STYLESHEET)
        original=self.dialog();original.toponym.name.setText('Πάνω Πλακοτές');original.toponym.confirm.click()
        before=self.snapshot();original.close();base_font=QFont(original.font())
        for factor,width,height in ((1,1100,740),(1.25,1000,700),(1.5,900,640)):
            for code in ('en','el'):
                self.language.set_language(code,persist=False)
                dialog=self.dialog();font=scaled_font(base_font,factor)
                dialog.setFont(font);dialog.resize(width,height);dialog.splitter.setSizes([width-330,300])
                self.assertTrue(dialog.toponym.name.isHidden())
                self.assertTrue(dialog.toponym.confirm.isHidden())
                self.assertFalse(dialog.toponym.edit.isHidden())
                self.assert_sidebar_actions_fit(dialog,f'{factor}/{code}/confirmed')
                dialog.toponym.edit.click()
                self.assertTrue(dialog.toponym.edit.isHidden())
                self.assertFalse(dialog.toponym.name.isHidden())
                self.assertFalse(dialog.toponym.confirm.isHidden())
                self.assert_sidebar_actions_fit(dialog,f'{factor}/{code}/editing')
                self.assertEqual('Πάνω Πλακοτές',dialog.toponym.name.text());dialog.close()
        self.assertEqual(before,self.snapshot())

    def test_locality_confirmation_remains_separate_and_persists(self):
        dialog=self.dialog();field=dict(self.db.query_one('SELECT * FROM fields WHERE id=?',(self.field,)))
        geometry=self.lookup.geometry(self.field)
        dialog.sidebar.setCurrentIndex(0);self.app.processEvents()
        widget=dialog.toponym
        candidate=next(i for i,value in enumerate(widget.candidates) if value['name']=='Πλακοτές')
        widget.suggestions.setCurrentIndex(candidate);widget.name.setText('Πάνω Πλακοτές');widget.confirm.click()
        self.assertEqual('Πάνω Πλακοτές',ToponymStore(self.db).load(self.field)['confirmed_name'])
        self.assertEqual(field,dict(self.db.query_one('SELECT * FROM fields WHERE id=?',(self.field,))))
        self.assertEqual(geometry,self.lookup.geometry(self.field))
        reopened=self.dialog()
        self.assertEqual('Πάνω Πλακοτές',reopened.toponym.name.text())
        before=self.snapshot()
        for code in ('en','el','en','el'):
            self.language.set_language(code,persist=False);self.app.processEvents()
            self.assertEqual('Πάνω Πλακοτές',reopened.toponym.name.text())
            self.assertIn('Πάνω Πλακοτές',reopened.toponym.status.text())
            self.assertEqual('Πλακοτές',reopened.toponym._candidate['name'])
        self.assertEqual(before,self.snapshot())

    def test_locality_draft_and_selection_survive_language_then_edit_and_clear(self):
        dialog=self.dialog();widget=dialog.toponym
        original_geometry=self.lookup.geometry(self.field)
        index=next(i for i,item in enumerate(widget.candidates) if item['name']=='Πλακοτές')
        widget.suggestions.setCurrentIndex(index);widget.name.setText('Πάνω Πλακοτές');widget._edited()
        before=self.snapshot()
        for code in ('en','el'):
            self.language.set_language(code,persist=False);self.app.processEvents()
            self.assertEqual(index,widget.suggestions.currentIndex())
            self.assertEqual('Πάνω Πλακοτές',widget.name.text())
        self.assertEqual(before,self.snapshot());widget.confirm.click()
        self.assertFalse(widget.name.isVisible());self.assertTrue(widget.edit.isVisible())
        widget.edit.click();self.assertTrue(widget.name.isVisible())
        widget.name.setText('Άνω Πλακοτές');widget.confirm.click()
        self.assertEqual('Άνω Πλακοτές',ToponymStore(self.db).load(self.field)['confirmed_name'])
        widget.clear.click()
        self.assertEqual('unspecified',ToponymStore(self.db).load(self.field)['decision'])
        widget.clear.click()
        self.assertEqual('rejected',ToponymStore(self.db).load(self.field)['decision'])
        self.assertEqual(original_geometry,self.lookup.geometry(self.field))

    def test_two_tabs_are_keyboard_accessible(self):
        from PySide6.QtTest import QTest
        dialog=self.dialog();bar=dialog.sidebar.tabBar()
        dialog.sidebar.setCurrentIndex(0);bar.setFocus()
        QTest.keyClick(bar,Qt.Key.Key_Right);self.app.processEvents()
        self.assertEqual(1,dialog.sidebar.currentIndex())
        QTest.keyClick(bar,Qt.Key.Key_Left);self.app.processEvents()
        self.assertEqual(0,dialog.sidebar.currentIndex())


if __name__=='__main__':unittest.main()
