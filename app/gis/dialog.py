"""Parcel map UI; import is previewed before a transactional geometry replacement."""
import json
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QCheckBox,QComboBox,QFileDialog,QInputDialog,QMessageBox,QPlainTextEdit,QApplication)
from PySide6.QtWidgets import (QTableWidget,QTableWidgetItem,QFormLayout,QLineEdit,
    QDoubleSpinBox,QDialogButtonBox,QScrollArea,QWidget,QSplitter,QTabWidget,QGroupBox,QSizePolicy)
from ..localized_messages import _message,_text
from .geometry import normalize,manual_coordinates
from .importers import import_geometry,MAX_BYTES
from .store import GeometryStore
from .providers import BASEMAPS,offline_pack,cdse_provider,restored_basemap
from .map_view import ParcelMap
from .kaek_lookup import LookupStore,valid_kaek
from .cadastral import cadastral_text,cadastral_summary,cultivated_area_text
from .toponym_widget import ToponymWidget


class ParcelMapDialog(QDialog):
    def __init__(self,db,field_id,parent=None):
        super().__init__(parent)
        self.db=db;self.field_id=field_id;self.store=GeometryStore(db);self.record=None
        self.cdse=None;self.pmtiles=None;self.map_download=None
        self.map_directory=db.path.parent/'offline-maps'
        self.setWindowTitle('Χάρτης αγροτεμαχίου');self.resize(1100,740)
        layout=QVBoxLayout(self)
        toolbar=QHBoxLayout();layout.addLayout(toolbar)
        self.fit_button=QPushButton('Επαναφορά στο αγροτεμάχιο')
        toolbar.addWidget(self.fit_button);toolbar.addStretch()
        close=QPushButton('Κλείσιμο');close.clicked.connect(self.accept);toolbar.addWidget(close)
        self.splitter=QSplitter(Qt.Orientation.Horizontal,self)
        self.splitter.setChildrenCollapsible(False);layout.addWidget(self.splitter,1)
        self.map=ParcelMap(db.path.parent/'map-http-cache',self)
        self.map.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.splitter.addWidget(self.map)
        self.fit_button.clicked.connect(self.map.fit_parcel)
        self.sidebar=QTabWidget();self.sidebar.setMinimumWidth(270)
        self.sidebar.setObjectName('parcelSidebar')
        self.sidebar.setProperty('mastixaCompactTabs',True)
        self.sidebar.tabBar().setUsesScrollButtons(False)
        self.sidebar.tabBar().setExpanding(True)
        self.sidebar.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.sidebar.setStyleSheet('QTabWidget#parcelSidebar::pane { top: 0px; } '
            'QTabWidget#parcelSidebar QTabBar::tab { min-width: 0px; padding: 6px 8px; margin-right: 0px; }')
        self.splitter.addWidget(self.sidebar)
        self.splitter.setStretchFactor(0,1);self.splitter.setStretchFactor(1,0)
        self.splitter.setSizes([740,340])
        details=self._panel('Αγροτεμάχιο')
        self.info=QLabel();self.info.setWordWrap(True);self.info.setTextFormat(self.info.textFormat().PlainText)
        # This label combines UI captions with domain names/source filenames. Translate
        # the template before interpolation so dictionary words in data remain intact.
        self.info.setProperty('mastixaI18nSkipText',True)
        self._info_template='';self._info_values={}
        self._language=getattr(QApplication.instance(),'_mastixa_language_controller',None)
        if self._language:self._language.language_changed.connect(self._translate_info)
        details.addWidget(self.info)
        self.cadastral_info=QLabel();self.cadastral_info.setWordWrap(True)
        self.cadastral_info.setTextFormat(self.info.textFormat().PlainText)
        self.cadastral_info.setProperty('mastixaI18nSkipText',True)
        details.addWidget(self.cadastral_info)
        self.toponym=ToponymWidget(db,field_id,self)
        details.addWidget(self.toponym)
        self.sources_button=QPushButton('Τεχνικά στοιχεία / Πηγές')
        self.sources_button.clicked.connect(self.show_sources);details.addWidget(self.sources_button)
        details.addStretch()
        settings=self._panel('Χάρτης')
        self.basemap=QComboBox();self.basemap.setProperty('mastixaI18nStaticItems',True)
        for provider in BASEMAPS:
            caption={'neutral':'Χωρίς υπόβαθρο','osm':'OpenStreetMap · Διαδίκτυο',
                'sentinel':'Copernicus / CDSE'}.get(provider.identity,provider.title)
            self.basemap.addItem(caption,provider.identity)
        self.basemap.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.basemap.setMinimumContentsLength(12)
        from ..ui_helpers import configure_combo_popup
        configure_combo_popup(self.basemap)
        settings.addWidget(self.basemap);self.basemap.currentIndexChanged.connect(self.select_basemap)
        configure=QPushButton('Ρύθμιση δωρεάν CDSE');configure.clicked.connect(self.configure_cdse);settings.addWidget(configure)
        self.attribution=QLabel();self.attribution.setOpenExternalLinks(True);settings.addWidget(self.attribution)
        self.imagery_info=QLabel();self.imagery_info.setProperty('mastixaI18nSkipText',True);settings.addWidget(self.imagery_info)
        self.imagery_status=QLabel();self.imagery_status.setProperty('mastixaI18nSkipText',True);settings.addWidget(self.imagery_status)
        self.map.tile_status.connect(self.imagery_status.setText)
        layers=QGroupBox('Επίπεδα γεωμετρίας');layer_layout=QVBoxLayout(layers);settings.addWidget(layers)
        self.cadastral_control=QCheckBox('Κτηματολογικό πολύγωνο')
        self.cadastral_vertices_control=QCheckBox('Κορυφές κτηματολογίου')
        for control,callback in ((self.cadastral_control,self.map.show_cadastral),
                                 (self.cadastral_vertices_control,self.map.show_cadastral_vertices)):
            control.setChecked(True);control.toggled.connect(callback);layer_layout.addWidget(control)
        legend=QLabel('Πράσινο: καλλιέργεια · μπλε: κτηματολόγιο · πορτοκαλί: κορυφές')
        layer_layout.addWidget(legend)
        actions=QGroupBox('Όρια αγροτεμαχίου');action_layout=QVBoxLayout(actions);settings.addWidget(actions)
        for title,callback in [('Εισαγωγή ορίων',self.import_file),
                               ('Συντεταγμένες',self.manual),
                               ('Ανάκτηση ΚΑΕΚ',self.cadastre)]:
            button=QPushButton(title);button.clicked.connect(callback);action_layout.addWidget(button)
            if callback==self.cadastre:button.setObjectName('cadastreLookupButton')
        self.offline_button=QPushButton('Λήψη Χίου')
        self.offline_button.clicked.connect(self.download_chios)
        settings.addWidget(self.offline_button)
        open_map=QPushButton('Άνοιγμα PMTiles');open_map.clicked.connect(self.open_pmtiles);settings.addWidget(open_map)
        offline_note=QLabel('Protomaps: χάρτης επισκόπησης z0–12. Έως 64 MiB αρχείο / 128 MiB μεταφορά, 136 MiB ελεύθερα. OSM/CDSE/ArcGIS: χωρίς offline λήψη.')
        settings.addWidget(offline_note);settings.addStretch()
        for label in (self.info,self.cadastral_info,self.attribution,self.imagery_info,self.imagery_status,offline_note,legend):
            label.setWordWrap(True);label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.finished.connect(lambda _:self.map.shutdown())
        self.lookup_controller=getattr(db,'_kaek_lookup_controller',None)
        if self.lookup_controller:
            self.lookup_controller.changed.connect(self._lookup_changed)
            self.toponym.changed.connect(lambda:self.lookup_controller.changed.emit(self.field_id))
        else:self.toponym.changed.connect(self._reload_cadastral)
        if self._language:
            self._language.language_changed.connect(self._reload_cadastral)
            self._language.language_changed.connect(self._translate_basemap)
        self.restore_basemap('neutral')
        try:
            saved=json.loads((self.map_directory/'last-map.json').read_text(encoding='utf-8'))
            self.use_pmtiles(Path(saved['path']),persist=False)
        except (OSError,ValueError,KeyError,TypeError):pass
        self.reload();QTimer.singleShot(0,self.map.fit_parcel)

    def _panel(self,title):
        scroll=QScrollArea();scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content=QWidget();content.setMinimumWidth(0)
        content.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        body=QVBoxLayout(content);scroll.setWidget(content)
        body.setContentsMargins(8,8,8,8);body.setSpacing(6)
        self.sidebar.addTab(scroll,title)
        return body

    def _lookup_changed(self,field_id=0):
        if field_id in (0,self.field_id):self.reload()

    def _reload_cadastral(self):
        view=self._view_state()
        payload=LookupStore(self.db).geometry(self.field_id)
        self.map.set_cadastral_geometry(normalize(payload['geometry'],payload['source_crs']) if payload else None)
        self.cadastral_info.setText(cadastral_summary(self.db,self.field_id))
        for control in (self.cadastral_control,self.cadastral_vertices_control):
            control.setEnabled(payload is not None)
        self.fit_button.setEnabled(self.map.bounds is not None or payload is not None)
        self.toponym.refresh()
        self._restore_view(view)

    def _view_state(self):
        if self.map.bounds is not None or self.map.cadastral_item is not None:
            return (self.map.transform(),self.map.mapToScene(self.map.viewport().rect().center()))
        return None

    def _restore_view(self,view):
        if view:
            transform,center=view
            self.map.setTransform(transform);self.map.centerOn(center)

    def _translate_info(self,*_):
        template=self._language.translate(self._info_template) if self._language else self._info_template
        values=dict(self._info_values)
        if 'cultivated' in values:
            values['cultivated']=(cultivated_area_text(values['cultivated'])
                if values['cultivated'] and float(values['cultivated'])>0 else _text('Δεν έχει οριστεί'))
        self.info.setText(template.format(**values))

    def reload(self):
        view=self._view_state()
        self._reload_cadastral()
        self.record=self.store.get(self.field_id)
        field=self.db.query_one('SELECT name,kaek,area_stremma FROM fields WHERE id=?',(self.field_id,))
        if not field:self.reject();return
        if not self.record:
            self.map.set_geometry(None,fit=False);self.map.set_points([])
            self._info_template='{name} · ΚΑΕΚ: {kaek}\nΚαλλιεργούμενη έκταση: {cultivated}'
            self._info_values={'name':field['name'],'kaek':field['kaek'],'cultivated':field['area_stremma']}
            self._translate_info()
            self._restore_view(view)
            return
        record=self.record
        geometry=normalize(json.loads(record['original_geojson']),record['source_crs'])
        self.map.set_geometry(geometry)
        self.fit_button.setEnabled(True)
        self.map.set_points(self.store.points(record['id']))
        self._info_template='{name} · ΚΑΕΚ: {kaek}\nΚαλλιεργούμενη έκταση: {cultivated}'
        self._info_values={'name':field['name'],'kaek':field['kaek'],'cultivated':field['area_stremma']}
        self._translate_info()
        self._restore_view(view)

    def show_sources(self):
        dialog=QDialog(self);dialog.setWindowTitle(_text('Τεχνικά στοιχεία / Πηγές'))
        layout=QVBoxLayout(dialog)
        text=cadastral_text(self.db,self.field_id)
        payload=LookupStore(self.db).geometry(self.field_id)
        if payload and payload.get('terms_url'):text+='\n'+payload['terms_url']
        if self.record:
            geometry=normalize(json.loads(self.record['original_geojson']),self.record['source_crs'])
            text+='\n\n'+_text('Όρια καλλιέργειας: {area:.2f} m² · Περίμετρος: {perimeter:.2f} m · {vertices} κορυφές\nCRS: {crs} · Πηγή: {source}',
                area=geometry.area_m2,perimeter=geometry.perimeter_m,vertices=geometry.vertex_count,
                crs=geometry.source_crs,source=self.record['geometry_source'])
        editor=QPlainTextEdit();editor.setReadOnly(True);editor.setPlainText(text)
        editor.setProperty('mastixaI18nSkipText',True);layout.addWidget(editor)
        # Provider/source metadata is preserved above; GeoNames has its own
        # linked Sources/Licences view next to the suggestions.
        close=QPushButton(_text('Κλείσιμο'));close.clicked.connect(dialog.accept);layout.addWidget(close)
        dialog.resize(600,460);dialog.exec()

    def select_basemap(self,index):
        provider=restored_basemap(self.basemap.itemData(index))
        if provider.identity=='sentinel' and self.cdse:provider=self.cdse
        if provider.identity=='pmtiles' and self.pmtiles:provider=self.pmtiles
        if provider.unavailable_reason:
            self.basemap.blockSignals(True)
            self.basemap.setCurrentIndex(0)
            self.basemap.blockSignals(False)
            self.map.set_provider(BASEMAPS[0]);self._translate_basemap()
            self.imagery_info.setText(provider.unavailable_reason)
            self.map.report_status('Μη διαθέσιμο / Unavailable')
            return
        try:self.map.set_provider(provider)
        except (OSError,ValueError,EOFError,IndexError,UnicodeError):
            self.map.report_status('Το τοπικό αρχείο δεν ανοίγει. Επίλεξε έγκυρο PMTiles / Cannot open local map')
            return
        self._translate_basemap()

    def use_pmtiles(self,path,persist=True):
        from .offline_maps import LocalArchive,ATTRIBUTION,DATA_LICENCE
        from .providers import BasemapProvider
        archive=LocalArchive(path)
        try:
            h=archive.header;metadata=archive.metadata
            if not all(name in {v.get('id') for v in metadata.get('vector_layers',[]) if isinstance(v,dict)}
                       for name in ('earth','water','roads')):
                raise ValueError('Expected Protomaps earth/water/roads layers')
            description=(f'{Path(path).name} · {Path(path).stat().st_size:,} bytes · z{h["min_zoom"]}–{h["max_zoom"]}\n'
                f'{DATA_LICENCE} · '+str(metadata.get('planetiler:osm:osmosisreplicationtime',''))+
                '\nΧάρτης επισκόπησης / Overview map. Η μεγέθυνση δεν προσθέτει λεπτομέρεια / Overzoom adds no detail.')
        finally:archive.close()
        self.pmtiles=BasemapProvider('pmtiles','Protomaps · Offline',ATTRIBUTION,
            offline_allowed=True,local_path=str(Path(path).resolve()),max_zoom=h['max_zoom'],tile_size=512,
            description=description)
        if persist:
            self.map_directory.mkdir(parents=True,exist_ok=True)
            (self.map_directory/'last-map.json').write_text(json.dumps({'path':self.pmtiles.local_path}),encoding='utf-8')
        self.restore_basemap('pmtiles')

    def open_pmtiles(self):
        filename,_=QFileDialog.getOpenFileName(self,_text('Άνοιγμα τοπικού PMTiles'),str(self.map_directory),'PMTiles (*.pmtiles)')
        if not filename:return
        try:self.use_pmtiles(Path(filename))
        except (OSError,ValueError,EOFError,IndexError,UnicodeError) as error:
            _message(self,'warning','PMTiles',str(error))

    def download_chios(self):
        if self.map_download and self.map_download.isRunning():
            self.map_download.requestInterruption();self.offline_button.setEnabled(False);return
        path=self.map_directory/'Chios-z12.pmtiles'
        if path.exists():
            try:self.use_pmtiles(path)
            except (OSError,ValueError,EOFError,IndexError,UnicodeError) as error:_message(self,'warning','PMTiles',str(error))
            return
        if QMessageBox.question(self,'Protomaps',
            'Λήψη Χίου 25.75,38.00–26.65,38.65 · z0–12;\n'
            'Το τελικό μέγεθος θα εμφανιστεί μετά τη λήψη. Όρια: 64 MiB αρχείο, 128 MiB μεταφορά.\n'
            'Απαιτούνται 136 MiB ελεύθερα. © OpenStreetMap contributors · ODbL Produced Work.\n'
            'Download this Chios overview? Final size is not known in advance.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        from .map_download import MapDownload
        worker=MapDownload(path,QApplication.instance());self.map_download=worker
        self.offline_button.setText('Ακύρωση λήψης / Cancel download')
        worker.progress.connect(self._map_progress)
        worker.completed.connect(self._map_downloaded)
        worker.failed.connect(self.imagery_status.setText)
        worker.finished.connect(self._download_finished)
        self.finished.connect(worker.requestInterruption)
        def stop():
            worker.requestInterruption();worker.wait(25000)
        QApplication.instance().aboutToQuit.connect(stop)
        worker.start()

    def _map_progress(self,n,total,size):
        if self.isVisible():self.imagery_status.setText(f'PMTiles: {n}/{total} · {size:,} bytes')

    def _map_downloaded(self,result):
        if not self.isVisible():return
        path=self.map_download.destination
        try:
            self.use_pmtiles(path)
            self.imagery_status.setText(f'PMTiles: {result["bytes"]:,} bytes · {result["tiles"]} tiles · offline')
        except (OSError,ValueError,EOFError,IndexError,UnicodeError) as error:self.imagery_status.setText(str(error))

    def _download_finished(self):
        self.offline_button.setEnabled(True);self.offline_button.setText('Λήψη Χίου')

    def restore_basemap(self,value):
        index=self.basemap.findData(restored_basemap(value).identity)
        if self.basemap.currentIndex()==index:self.select_basemap(index)
        else:self.basemap.setCurrentIndex(index)

    def _translate_basemap(self,*_):
        provider=self.map.provider
        if not provider:return
        self.basemap.setToolTip(self.basemap.currentText())
        attribution=provider.attribution
        if provider.identity=='osm':
            attribution='<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>'
        elif provider.identity=='pmtiles':
            attribution=('<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a> · '
                '<a href="https://protomaps.com">Protomaps</a> · '
                '<a href="https://www.naturalearthdata.com/about/terms-of-use/">Natural Earth</a> · '
                '<a href="https://opendatacommons.org/licenses/odbl/1-0/">ODbL</a>')
        self.attribution.setText(attribution or _text('Χωρίς υπόβαθρο · τοπική γεωμετρία'))
        description=(_text('Sentinel-2: φυσική ανάλυση RGB 10 m · διάστημα {period}. Μωσαϊκό· δεν επιστρέφεται ακριβής ημερομηνία λήψης. Η μεγέθυνση δεν προσθέτει λεπτομέρεια.',period=provider.time_range)
            if provider.identity=='sentinel' else _text(provider.description))
        self.imagery_info.setText(description if description else
            _text('Η ορατή περιοχή ζητείται από τον πάροχο μέσω διαδικτύου') if provider.tile_template else '')
        self.map.translate_status()

    def configure_cdse(self):
        from datetime import date,timedelta
        dialog=QDialog(self);dialog.setWindowTitle(_text('Ρύθμιση δωρεάν CDSE'))
        form=QFormLayout(dialog)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        dialog.resize(480,430)
        explanation=QLabel(_text('Δωρεάν λογαριασμός CDSE και Sentinel-2 L2A True Color στο Configuration Utility. Μόνο η τρέχουσα συνεδρία· δεν αποθηκεύονται διαπιστευτήρια.'))
        explanation.setWordWrap(True);form.addRow(explanation)
        links=QLabel('<a href="https://documentation.dataspace.copernicus.eu/Registration.html">CDSE registration</a> · <a href="https://shapps.dataspace.copernicus.eu/dashboard/">Configuration Utility</a>')
        links.setOpenExternalLinks(True);links.setWordWrap(True);form.addRow(links)
        instance=QLineEdit();instance.setEchoMode(QLineEdit.EchoMode.Password)
        layer=QLineEdit('TRUE_COLOR');start=QLineEdit((date.today()-timedelta(days=30)).isoformat());end=QLineEdit(date.today().isoformat())
        for label,widget in [('Instance ID',instance),('Layer ID · Sentinel-2 L2A True Color',layer),('Από ημερομηνία (YYYY-MM-DD)',start),('Έως ημερομηνία (YYYY-MM-DD)',end)]:
            form.addRow(_text(label),widget)
        error=QLabel();error.setWordWrap(True);form.addRow(error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);form.addRow(buttons)
        buttons.rejected.connect(dialog.reject)
        def accept():
            try:self.cdse=cdse_provider(instance.text(),layer.text(),start.text(),end.text())
            except ValueError:
                error.setText(_text('Έλεγξε Instance ID, Layer ID και ημερομηνίες.'));return
            dialog.accept()
        buttons.accepted.connect(accept)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.restore_basemap('sentinel')

    def source_crs(self,default=''):
        text,ok=QInputDialog.getText(self,'Σύστημα συντεταγμένων πηγής',
            'Πραγματικό EPSG πηγής (κενό για CRS αρχείου / WGS84 GeoJSON-KML)',text=default)
        return text.strip() if ok else None

    def import_file(self):
        filename,_=QFileDialog.getOpenFileName(self,_text('Εισαγωγή ορίων'),'',
            _text("Γεωμετρία") + " (*.geojson *.json *.kml *.gml *.xml *.zip *.dxf)")
        if not filename:return
        crs=self.source_crs()
        if crs is None:return
        try:
            with open(filename,'rb') as stream:data=stream.read(MAX_BYTES+1)
            geometry=import_geometry(data,filename,crs)
            self.confirm_geometry(geometry,Path(filename).name)
        except Exception:QMessageBox.warning(self,'Εισαγωγή','Η εισαγωγή απέτυχε. Έλεγξε τη μορφή αρχείου, τα όρια και το EPSG πηγής.')

    def manual(self):
        crs=self.source_crs('EPSG:4326')
        if crs is None:return
        dialog=QDialog(self);dialog.setWindowTitle('X Y / γεωγραφικό μήκος και πλάτος');layout=QVBoxLayout(dialog)
        layout.addWidget(QLabel('Μία κορυφή ανά γραμμή, X Y (γεωγραφικό μήκος, πλάτος). Τελεία δεκαδικών.'))
        editor=QPlainTextEdit();editor.setPlaceholderText('26.00000000 38.00000000');layout.addWidget(editor)
        button=QPushButton('Προεπισκόπηση');button.clicked.connect(dialog.accept);layout.addWidget(button)
        dialog.resize(600,400)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:self.confirm_geometry(manual_coordinates(editor.toPlainText(),crs),'manual')
        except Exception:QMessageBox.warning(self,'Συντεταγμένες','Δεν ήταν δυνατή η αποθήκευση. Έλεγξε τις συντεταγμένες και το EPSG πηγής ή άνοιξε ξανά τον χάρτη αν τα όρια άλλαξαν.')

    def confirm_geometry(self,geometry,source):
        # The original data is untouched until confirmation, then revision checked.
        preview=f'{geometry.source_crs} · {geometry.vertex_count} κορυφές\n{geometry.area_m2:.2f} m² · {geometry.perimeter_m:.2f} m\n'
        from .geometry import vertices
        preview+='\n'.join(f'{p}/{r}/{v}: {x:.8f}, {y:.8f}' for p,r,v,x,y in list(vertices(geometry.original))[:5])
        if self.record:preview+='\nΘα αντικατασταθούν τα αποθηκευμένα όρια.'
        answer=QMessageBox.question(self,'Αποθήκευση ορίων;',preview)
        if answer!=QMessageBox.StandardButton.Yes:return
        self.store.save(self.field_id,geometry,source,expected_revision=self.record['revision'] if self.record else None)
        self.reload()

    def cadastre(self):
        field=self.db.query_one('SELECT kaek FROM fields WHERE id=?',(self.field_id,))
        if not field or not valid_kaek(field['kaek']):
            _message(self,'information','Κτηματολόγιο','Συμπλήρωσε έγκυρο 12ψήφιο ΚΑΕΚ.');return
        if self.lookup_controller is None:
            from .kaek_worker import controller_for
            owner=self.parentWidget().window() if self.parentWidget() else QApplication.instance()
            self.lookup_controller=controller_for(self.db,owner)
            self.lookup_controller.changed.connect(self._lookup_changed)
        # Reuse the working queue/provider. No browser API or separate lookup path.
        self.lookup_controller.retry(self.field_id)

    def offline(self):
        if self.record:
            extent=json.loads(self.record['bbox'])
        else:
            payload=LookupStore(self.db).geometry(self.field_id)
            if not payload:
                _message(self,'information','Χάρτης εκτός σύνδεσης','Χρειάζονται όρια καλλιέργειας ή ανακτημένο κτηματολογικό πολύγωνο.');return
            extent=normalize(payload['geometry'],payload['source_crs']).bbox
        state=offline_pack(str(self.field_id),extent)
        _message(self,'information','Χάρτης εκτός σύνδεσης',
            'Δεν έχει ενεργοποιηθεί μαζική λήψη με επαληθευμένους όρους άδειας. Η προσωρινή cache ορατών πλακιδίων δεν είναι εγγυημένος offline χάρτης.\nΠλαίσιο με περιθώριο: {bbox}\nΔεν έγινε λήψη.',bbox=state.bbox)

    def points(self):
        if not self.record:
            QMessageBox.information(self,'Σημεία','Εισήγαγε πρώτα όρια');return
        dialog=QDialog(self);dialog.setWindowTitle('Σημεία');dialog.resize(750,430);layout=QVBoxLayout(dialog)
        table=QTableWidget(0,5);table.setHorizontalHeaderLabels(['Τίτλος','Τύπος','Γεωγραφικό πλάτος','Γεωγραφικό μήκος','Ακρίβεια (m)'])
        table.setSelectionBehavior(table.SelectionBehavior.SelectRows);table.setEditTriggers(table.EditTrigger.NoEditTriggers);layout.addWidget(table)
        rows=[]
        from .store import POINT_TYPES
        point_labels=dict(zip(POINT_TYPES,['Δέντρο','Βάνα','Άρδευση','Δεξαμενή','Γεώτρηση','Πρόβλημα','Σημείωση','Άλλο']))
        def refresh(*_):
            rows[:]=self.store.points(self.record['id']);table.setRowCount(len(rows))
            for index,row in enumerate(rows):
                for col,value in enumerate([row['title'],self._language.translate(point_labels.get(row['point_type'],row['point_type'])) if self._language else point_labels.get(row['point_type'],row['point_type']),f"{row['latitude']:.8f}",f"{row['longitude']:.8f}",row['accuracy']]):table.setItem(index,col,QTableWidgetItem(str(value)))
            self.map.set_points(rows)
        def edit(existing=None):
            form=QDialog(dialog);form.setWindowTitle('Σημείο');fields=QFormLayout(form)
            title=QLineEdit(existing['title'] if existing else '');notes=QPlainTextEdit(existing['notes'] if existing else '')
            from .store import POINT_TYPES
            kind=QComboBox();kind.addItems(['Δέντρο','Βάνα','Άρδευση','Δεξαμενή','Γεώτρηση','Πρόβλημα','Σημείωση','Άλλο'])
            kind.setCurrentIndex(POINT_TYPES.index(existing['point_type']) if existing else 0)
            fields.addRow('Τίτλος',title);fields.addRow('Τύπος',kind);fields.addRow('Σημειώσεις',notes)
            coordinates=[]
            for key,low,high in [('longitude',-180,180),('latitude',-90,90),('accuracy',0,1000000)]:
                spin=QDoubleSpinBox();spin.setRange(low,high);spin.setDecimals(8 if key!='accuracy' else 2)
                default=self.record['centroid_lon' if key=='longitude' else 'centroid_lat'] if key!='accuracy' else 0
                spin.setValue(existing[key] if existing else default);fields.addRow({'longitude':'Γεωγραφικό μήκος · WGS84','latitude':'Γεωγραφικό πλάτος · WGS84','accuracy':'Δηλωμένη ακρίβεια (m)'}[key],spin);coordinates.append(spin)
            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);fields.addRow(buttons);buttons.rejected.connect(form.reject)
            buttons.button(QDialogButtonBox.StandardButton.Save).setText('Αποθήκευση');buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Ακύρωση')
            def save():
                try:
                    self.store.save_point(self.record['id'],POINT_TYPES[kind.currentIndex()],title.text(),notes.toPlainText(),*[s.value() for s in coordinates],identity=existing['id'] if existing else None,expected_revision=existing['revision'] if existing else None)
                    form.accept();refresh()
                except ValueError:QMessageBox.warning(form,'Σημείο','Δεν ήταν δυνατή η αποθήκευση. Έλεγξε τις τιμές ή άνοιξε ξανά τη φόρμα αν το σημείο άλλαξε.')
            buttons.accepted.connect(save);form.exec()
        def selected():
            index=table.currentRow();return rows[index] if 0<=index<len(rows) else None
        def delete():
            row=selected()
            if row and QMessageBox.question(dialog,'Διαγραφή','Διαγραφή επιλεγμένου σημείου;')==QMessageBox.StandardButton.Yes:
                try:self.store.delete_object('geo_points',row['id'],row['revision']);refresh()
                except ValueError:QMessageBox.warning(dialog,'Σημείο','Δεν ήταν δυνατή η διαγραφή. Άνοιξε ξανά τη λίστα αν το σημείο άλλαξε.')
        actions=QHBoxLayout();layout.addLayout(actions)
        for text,callback in [('Νέο',lambda:edit()),('Επεξεργασία',lambda:edit(selected()) if selected() else None),('Διαγραφή',delete),('Κλείσιμο',dialog.accept)]:
            button=QPushButton(text);button.clicked.connect(callback);actions.addWidget(button)
        refresh()
        if self._language:self._language.language_changed.connect(refresh)
        try:dialog.exec()
        finally:
            if self._language:self._language.language_changed.disconnect(refresh)

    def tracks(self):
        rows=self.store.tracks(self.record['id']) if self.record else []
        if not rows:QMessageBox.information(self,'Διαδρομές','Δεν υπάρχουν αποθηκευμένες διαδρομές');return
        labels=[f"{index+1}. {row['title']} · {row['distance_m']:.1f} m · {row['duration_ms']/1000:.0f} s" for index,row in enumerate(rows)]
        choice,ok=QInputDialog.getItem(self,'Διαδρομές','Προβολή',labels,editable=False)
        if ok:
            row=rows[labels.index(choice)];self.map.set_track(json.loads(row['positions_json']),json.loads(row['segment_starts_json']))
