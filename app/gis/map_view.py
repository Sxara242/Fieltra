"""Native Qt parcel map. Geometry remains available with no network/basemap.

Only visible OSM tiles are requested after explicit selection. Qt HTTP cache
honors response caching headers; there is no prefetch or offline-pack downloader.
"""
import math
import time
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QBuffer, QByteArray, QIODevice, Signal
from PySide6.QtGui import (
    QColor,
    QPalette,
    QPainterPath,
    QPen,
    QBrush,
    QPixmap,
    QImageReader,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache, QNetworkRequest
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from .geometry import parts, transformer
from .providers import BASEMAPS
from ..localized_messages import _text

WORLD=20037508.342789244


class ParcelMap(QGraphicsView):
    tile_status = Signal(str)
    def __init__(self, cache_directory: Path, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.scene().setSceneRect(-WORLD,-WORLD,WORLD*2,WORLD*2)
        self.boundaries=[];self.markers=[];self.center_marker=None;self.bounds=None
        self.boundaries_visible=True;self.vertices_visible=True
        self.cadastral_markers=[];self.cadastral_vertices_visible=True
        self.cadastral_item=None;self.cadastral_bounds=None;self.cadastral_visible=True
        self.point_markers=[];self.track_items=[]
        self._dark_map = False
        self._apply_palette_theme()
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumSize(240,220)
        self.tiles={};self.pending={};self.failed={};self.provider=None;self.generation=0
        self.attempts={};self.provider_wait={};self.started_at=0;self.last_request=0
        self.requested_count=0;self.loaded_count=0;self.failed_count=0
        self.cdse_requests=0
        self.offline_archive=None
        self._status_template='';self._status_values={}
        self.network=QNetworkAccessManager(self)
        cache=QNetworkDiskCache(self.network)
        cache.setCacheDirectory(str(cache_directory));cache.setMaximumCacheSize(128*1024*1024)
        self.network.setCache(cache)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(180)
        self.timer.timeout.connect(self.load_visible_tiles)
        self.horizontalScrollBar().valueChanged.connect(self.schedule_tiles)
        self.verticalScrollBar().valueChanged.connect(self.schedule_tiles)

    def _is_dark_palette(self):
        colour = self.palette().color(QPalette.ColorRole.Window)
        return colour.lightness() < 128

    def _apply_palette_theme(self):
        self._dark_map = self._is_dark_palette()
        if self._dark_map:
            self.setBackgroundBrush(QColor("#151A1E"))
            boundary_colour = QColor("#72C69A")
            vertex_outline = QColor("#9FD8B8")
            vertex_fill = QColor("#F2F6F4")
        else:
            self.setBackgroundBrush(QColor("#EDF1E8"))
            boundary_colour = QColor("#23683E")
            vertex_outline = QColor("#173C29")
            vertex_fill = QColor("white")

        for item in self.boundaries:
            pen = item.pen()
            pen.setColor(boundary_colour)
            item.setPen(pen)
        for item in self.markers:
            pen = item.pen()
            pen.setColor(vertex_outline)
            item.setPen(pen)
            item.setBrush(QBrush(vertex_fill))

        self.viewport().update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in {
            event.Type.PaletteChange,
            event.Type.ApplicationPaletteChange,
        }:
            self._apply_palette_theme()

    def set_geometry(self, geometry, fit=True):
        for item in self.boundaries+self.markers+([self.center_marker] if self.center_marker else []):
            self.scene().removeItem(item)
        self.boundaries=[];self.markers=[]
        self.center_marker=None;self.bounds=None
        if geometry is None:return
        project=transformer('EPSG:4326','EPSG:3857')
        path=QPainterPath();path.setFillRule(Qt.FillRule.OddEvenFill)
        for polygon in parts(geometry.wgs84):
            for ring in polygon:
                for index,(lon,lat) in enumerate(ring):
                    x,y=project.transform(lon,lat)
                    if index==0:path.moveTo(x,-y)
                    else:path.lineTo(x,-y)
                    if index<len(ring)-1:
                        dot_pen = QColor("#9FD8B8") if self._dark_map else QColor("#173C29")
                        dot_fill = QColor("#F2F6F4") if self._dark_map else QColor("white")
                        dot=self.scene().addEllipse(-3,-3,6,6,QPen(dot_pen),QBrush(dot_fill))
                        dot.setPos(x,-y);dot.setFlag(dot.GraphicsItemFlag.ItemIgnoresTransformations);dot.setZValue(3)
                        self.markers.append(dot)
                path.closeSubpath()
        boundary_colour = QColor("#72C69A") if self._dark_map else QColor("#23683E")
        pen=QPen(boundary_colour);pen.setWidth(3);pen.setCosmetic(True)
        boundary=self.scene().addPath(path,pen,QBrush(QColor(60,140,80,55)));boundary.setZValue(2)
        self.boundaries.append(boundary);self.bounds=path.boundingRect()
        self.center_marker=self.scene().addEllipse(-4,-4,8,8,QPen(QColor('white')),QBrush(QColor('#c5571f')))
        x,y=project.transform(geometry.centroid_lon,geometry.centroid_lat)
        self.center_marker.setPos(x,-y);self.center_marker.setZValue(4)
        self.center_marker.setFlag(self.center_marker.GraphicsItemFlag.ItemIgnoresTransformations)
        self.show_boundaries(self.boundaries_visible)
        if fit:self.fit_parcel()

    def fit_parcel(self):
        # Prefer the selected field's visible cultivated boundary. A cadastral
        # reference is a distinct extent, never unioned into cultivation.
        bounds=self.bounds if self.boundaries_visible else None
        if bounds is None and self.cadastral_visible:bounds=self.cadastral_bounds
        if bounds is None:bounds=self.bounds if self.bounds is not None else self.cadastral_bounds
        if bounds is not None and not bounds.isEmpty():
            margin=max(bounds.width(),bounds.height())*.15+5
            self.fitInView(bounds.adjusted(-margin,-margin,margin,margin),Qt.AspectRatioMode.KeepAspectRatio)
            self.schedule_tiles()
            return True
        return False

    def set_cadastral_geometry(self, geometry):
        if self.cadastral_item is not None:
            self.scene().removeItem(self.cadastral_item)
        for marker in self.cadastral_markers:self.scene().removeItem(marker)
        self.cadastral_markers=[]
        self.cadastral_item=None;self.cadastral_bounds=None
        if geometry is None:return
        project=transformer('EPSG:4326','EPSG:3857')
        path=QPainterPath();path.setFillRule(Qt.FillRule.OddEvenFill)
        for polygon in parts(geometry.wgs84):
            for ring in polygon:
                for index,(lon,lat) in enumerate(ring):
                    x,y=project.transform(lon,lat)
                    if index==0:path.moveTo(x,-y)
                    else:path.lineTo(x,-y)
                    if index<len(ring)-1:
                        marker=self.scene().addEllipse(-3.5,-3.5,7,7,QPen(QColor('#352508')),QBrush(QColor('#FFBF47')))
                        marker.setPos(x,-y);marker.setFlag(marker.GraphicsItemFlag.ItemIgnoresTransformations)
                        marker.setZValue(3.2);self.cadastral_markers.append(marker)
                path.closeSubpath()
        pen=QPen(QColor('#438FE6'));pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidth(3);pen.setCosmetic(True)
        self.cadastral_item=self.scene().addPath(path,pen)
        self.cadastral_item.setZValue(2.5);self.cadastral_item.setVisible(self.cadastral_visible)
        self.cadastral_bounds=path.boundingRect()
        self.show_cadastral(self.cadastral_visible)
        self.show_cadastral_vertices(self.cadastral_vertices_visible)
        self.fit_parcel()

    def show_cadastral(self, visible):
        self.cadastral_visible=visible
        if self.cadastral_item is not None:self.cadastral_item.setVisible(visible)

    def show_cadastral_vertices(self,visible):
        self.cadastral_vertices_visible=visible
        for marker in self.cadastral_markers:marker.setVisible(visible)

    def set_points(self, points):
        for item in self.point_markers:self.scene().removeItem(item)
        self.point_markers=[];project=transformer('EPSG:4326','EPSG:3857')
        for point in points:
            x,y=project.transform(point['longitude'],max(-85,min(85,point['latitude'])))
            marker=self.scene().addEllipse(-5,-5,10,10,QPen(QColor('white')),QBrush(QColor('#803e96')))
            marker.setPos(x,-y);marker.setZValue(5);marker.setFlag(marker.GraphicsItemFlag.ItemIgnoresTransformations)
            marker.setToolTip(point['title']);self.point_markers.append(marker)

    def set_track(self, points, starts):
        for item in self.track_items:self.scene().removeItem(item)
        self.track_items=[];project=transformer('EPSG:4326','EPSG:3857');path=QPainterPath();breaks=set(starts)
        for index,point in enumerate(points):
            x,y=project.transform(point[0],max(-85,min(85,point[1])))
            if index==0 or index in breaks:path.moveTo(x,-y)
            else:path.lineTo(x,-y)
        pen=QPen(QColor('#9b46b4'));pen.setCosmetic(True);pen.setWidth(3)
        item=self.scene().addPath(path,pen);item.setZValue(4);self.track_items.append(item)

    def show_boundaries(self, visible):
        self.boundaries_visible=visible
        for item in self.boundaries:item.setVisible(visible)
        if self.center_marker is not None:self.center_marker.setVisible(visible)
        self.show_vertices(self.vertices_visible)

    def show_vertices(self, visible):
        self.vertices_visible=visible
        for item in self.markers:item.setVisible(visible and self.boundaries_visible)

    def wheelEvent(self,event):
        factor=1.3 if event.angleDelta().y()>0 else 1/1.3
        scale=self.transform().m11()*factor
        if .00001<scale<20:self.scale(factor,factor)
        self.schedule_tiles();event.accept()

    def resizeEvent(self,event):
        super().resizeEvent(event);self.schedule_tiles()

    def schedule_tiles(self,*_):
        if hasattr(self,'timer'):self.timer.start()

    def report_status(self,template,**values):
        self._status_template=template;self._status_values=values
        self.translate_status()

    def translate_status(self):
        self.tile_status.emit(_text(self._status_template,**self._status_values))

    def set_provider(self, provider):
        # Defensive fallback for an obsolete in-memory/configured provider object.
        if provider is None or provider.identity in {'google','versatiles'}:provider=BASEMAPS[0]
        archive=None
        if provider.local_path:
            from .offline_maps import LocalArchive
            archive=LocalArchive(provider.local_path)
        self.generation+=1
        if self.offline_archive is not None:
            self.offline_archive.close();self.offline_archive=None
        self.offline_archive=archive
        self.provider=provider
        replies=list(self.pending.values());self.pending.clear()
        for reply in replies:reply.abort()
        for item in self.tiles.values():self.scene().removeItem(item)
        self.tiles.clear();self.failed.clear();self.schedule_tiles()
        self.attempts.clear();self.started_at=time.monotonic();self.last_request=0
        self.requested_count=0;self.loaded_count=0;self.failed_count=0
        self.report_status('PMTiles · offline' if provider.local_path else
            'Φόρτωση υποβάθρου…' if provider.tile_template else 'Τοπική γεωμετρία · χωρίς δικτυακό υπόβαθρο')

    def load_visible_tiles(self):
        if not self.provider or not (self.provider.tile_template or self.offline_archive) or not self.isVisible():return
        scale=self.transform().m11()
        now=time.monotonic()
        if self.provider_wait.get(self.provider.identity,0)>now:
            self.timer.start(min(60_000,max(1000,int((self.provider_wait[self.provider.identity]-now)*1000))))
            return
        z=max(0,min(self.provider.max_zoom,round(math.log2(max(scale,1e-10)*WORLD*2/self.provider.tile_size))))
        size=WORLD*2/(2**z)
        rect=self.mapToScene(self.viewport().rect()).boundingRect()
        x0=max(0,int((rect.left()+WORLD)//size));x1=min(2**z-1,int((rect.right()+WORLD)//size))
        y0=max(0,int((rect.top()+WORLD)//size));y1=min(2**z-1,int((rect.bottom()+WORLD)//size))
        visible={(z,x,y) for x in range(x0,x1+1) for y in range(y0,y1+1)}
        if len(visible)>64:return
        self.failed={key:deadline for key,deadline in self.failed.items() if key in visible}
        for key in list(self.tiles):
            if key not in visible:self.scene().removeItem(self.tiles.pop(key))
        for key in visible:
            if self.offline_archive:
                if key in self.tiles or key in self.failed:continue
                try:
                    from .offline_maps import unpack
                    from .vector_tiles import render
                    data=self.offline_archive.get(*key)
                    if data is None:self.failed[key]=math.inf;continue
                    pixmap=QPixmap.fromImage(render(unpack(data,self.offline_archive.header['tile_compression']),self.provider.tile_size))
                    self._place_tile(key,pixmap,self.provider.tile_size);self.loaded_count+=1
                except (ValueError,OSError,EOFError,IndexError,UnicodeError):
                    self.failed[key]=math.inf;self.failed_count+=1
                continue
            if len(self.pending)>=2:break
            if self.provider.identity=='sentinel':
                if self.cdse_requests>=200:
                    self.report_status('Όριο αυτής της συνεδρίας: 200 αιτήματα CDSE. Κλείσε τον χάρτη για νέα συνεδρία.');break
                if time.monotonic()-self.last_request<1:
                    self.timer.start(1000);break
            if key in self.tiles or key in self.pending or self.failed.get(key,0)>time.monotonic():continue
            z,x,y=key
            request=QNetworkRequest(QUrl(self.provider.tile_url(z,x,y)))
            request.setRawHeader(b'User-Agent',b'Fieltra (+https://github.com/Sxara242/Fieltra)')
            if not self.provider.persistent_cache:
                request.setAttribute(QNetworkRequest.Attribute.CacheSaveControlAttribute,False)
                request.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute,QNetworkRequest.CacheLoadControl.AlwaysNetwork)
                request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
            request.setTransferTimeout(10000)
            reply=self.network.get(request);self.pending[key]=reply;reply.setReadBufferSize(1024*1024+1)
            self.last_request=time.monotonic();self.requested_count+=1
            if self.provider.identity=='sentinel':self.cdse_requests+=1
            self.attempts[key]=self.attempts.get(key,0)+1
            body=bytearray()
            def consume(reply=reply,body=body):
                chunk=bytes(reply.readAll())
                if len(body)+len(chunk)>1024*1024:reply.abort()
                else:body.extend(chunk)
            reply.readyRead.connect(consume)
            reply.finished.connect(lambda key=key,reply=reply,provider=self.provider,generation=self.generation,body=body:self.tile_finished(key,reply,provider,generation,body))
        deadlines=[deadline for deadline in self.failed.values() if math.isfinite(deadline)]
        if self.offline_archive:
            self.report_status('PMTiles offline · {tiles} πλακίδια · κενά/σφάλματα: {failed} · έως z{zoom}',
                tiles=len(self.tiles),failed=len(self.failed),zoom=self.provider.max_zoom)
        if deadlines:self.timer.start(max(180,int(max(0,min(deadlines)-time.monotonic())*1000)))

    def _place_tile(self,key,pixmap,tile_size):
        z,x,y=key;size=WORLD*2/(2**z)
        item=self.scene().addPixmap(pixmap);item.setScale(size/tile_size)
        item.setPos(-WORLD+x*size,-WORLD+y*size);item.setZValue(-1)
        if key in self.tiles:self.scene().removeItem(self.tiles[key])
        self.tiles[key]=item

    def tile_finished(self,key,reply,provider,generation,body):
        if self.pending.get(key) is reply:self.pending.pop(key,None)
        if generation!=self.generation or provider!=self.provider:
            reply.deleteLater();return
        data=bytes(body)+bytes(reply.readAll());loaded=False
        if reply.error()==reply.NetworkError.NoError and len(data)<=1024*1024:
            buffer=QBuffer();buffer.setData(QByteArray(data));buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            reader=QImageReader(buffer);size=reader.size()
            pixmap=QPixmap()
            if size.width()==provider.tile_size and size.height()==provider.tile_size and pixmap.loadFromData(data):
                self._place_tile(key,pixmap,provider.tile_size)
                loaded=True;self.failed.pop(key,None)
                self.loaded_count+=1
        if not loaded:
            status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            self.failed_count+=1
            if status==429:
                try:wait=float(bytes(reply.rawHeader(b'Retry-After')).decode())/(1000 if provider.identity=='sentinel' else 1)
                except (ValueError,UnicodeError):wait=60
                if not math.isfinite(wait):wait=60
                wait=max(30,wait)
                self.provider_wait[provider.identity]=max(self.provider_wait.get(provider.identity,0),time.monotonic()+wait)
                self.failed[key]=time.monotonic()+wait if self.attempts.get(key,0)<3 else math.inf
                self.timer.start(min(60_000,int(wait*1000)))
            elif status in (400,401,403,404) or self.attempts.get(key,0)>=3:
                self.failed[key]=math.inf
            else:
                self.failed[key]=time.monotonic()+30;self.timer.start(30000)
            if status in (400,401,403):
                self.report_status('Η υπηρεσία απέρριψε το αίτημα. Έλεγξε πρόσβαση και ρύθμιση υποβάθρου.')
            elif status==429:
                self.report_status('Όριο υπηρεσίας· η φόρτωση περιμένει πριν συνεχίσει.')
            else:
                self.report_status('Δεν φορτώθηκε εικόνα υποβάθρου· η τοπική γεωμετρία παραμένει διαθέσιμη.')
        else:
            self.report_status('Υπόβαθρο: {tiles} πλακίδια · {seconds:.2f} s · αποτυχίες: {failed}',
                tiles=self.loaded_count,seconds=time.monotonic()-self.started_at,failed=self.failed_count)
        reply.deleteLater()
        # Fill remaining visible slots; failures retain their bounded deadlines.
        self.timer.start(1000 if provider.identity=='sentinel' else 180)

    def shutdown(self):
        self.generation+=1
        self.timer.stop()
        replies=list(self.pending.values());self.pending.clear()
        for reply in replies:reply.abort()
        if self.offline_archive is not None:
            self.offline_archive.close();self.offline_archive=None
