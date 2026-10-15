"""Native Qt parcel map. Geometry remains available with no network/basemap.

Only visible OSM tiles are requested after explicit selection. Qt HTTP cache
honors response caching headers; there is no prefetch or offline-pack downloader.
"""
import math
import time
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QBuffer, QByteArray, QIODevice
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

WORLD=20037508.342789244


class ParcelMap(QGraphicsView):
    def __init__(self, cache_directory: Path, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.scene().setSceneRect(-WORLD,-WORLD,WORLD*2,WORLD*2)
        self.boundaries=[];self.markers=[];self.center_marker=None;self.bounds=None
        self.point_markers=[];self.track_items=[]
        self._dark_map = False
        self._apply_palette_theme()
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumHeight(330)
        self.tiles={};self.pending={};self.failed={};self.provider=None;self.generation=0
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
        if fit:self.fit_parcel()

    def fit_parcel(self):
        if self.bounds:
            margin=max(self.bounds.width(),self.bounds.height())*.15+5
            self.fitInView(self.bounds.adjusted(-margin,-margin,margin,margin),Qt.AspectRatioMode.KeepAspectRatio)
            self.schedule_tiles()

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
        for item in self.boundaries:item.setVisible(visible)

    def show_vertices(self, visible):
        for item in self.markers:item.setVisible(visible)

    def wheelEvent(self,event):
        factor=1.3 if event.angleDelta().y()>0 else 1/1.3
        scale=self.transform().m11()*factor
        if .00001<scale<20:self.scale(factor,factor)
        self.schedule_tiles();event.accept()

    def resizeEvent(self,event):
        super().resizeEvent(event);self.schedule_tiles()

    def schedule_tiles(self,*_):
        if hasattr(self,'timer'):self.timer.start()

    def set_provider(self, provider):
        self.generation+=1
        self.provider=provider
        replies=list(self.pending.values());self.pending.clear()
        for reply in replies:reply.abort()
        for item in self.tiles.values():self.scene().removeItem(item)
        self.tiles.clear();self.failed.clear();self.schedule_tiles()

    def load_visible_tiles(self):
        if not self.provider or not self.provider.tile_template or not self.isVisible():return
        scale=self.transform().m11()
        z=max(0,min(19,round(math.log2(max(scale,1e-10)*WORLD*2/256))))
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
            if key in self.tiles or key in self.pending or self.failed.get(key,0)>time.monotonic():continue
            z,x,y=key
            request=QNetworkRequest(QUrl(self.provider.tile_template.format(z=z,x=x,y=y)))
            request.setRawHeader(b'User-Agent',b'Fieltra/1.0.0 (+https://github.com/Sxara242/Mastixa-Manager-Source)')
            request.setTransferTimeout(10000)
            reply=self.network.get(request);self.pending[key]=reply;reply.setReadBufferSize(1024*1024+1)
            body=bytearray()
            def consume(reply=reply,body=body):
                chunk=bytes(reply.readAll())
                if len(body)+len(chunk)>1024*1024:reply.abort()
                else:body.extend(chunk)
            reply.readyRead.connect(consume)
            reply.finished.connect(lambda key=key,reply=reply,provider=self.provider,generation=self.generation,body=body:self.tile_finished(key,reply,provider,generation,body))
        if self.failed:self.timer.start(max(180,int(max(0,min(self.failed.values())-time.monotonic())*1000)))

    def tile_finished(self,key,reply,provider,generation,body):
        if self.pending.get(key) is reply:self.pending.pop(key,None)
        if generation!=self.generation or provider!=self.provider:
            reply.deleteLater();return
        data=bytes(body)+bytes(reply.readAll());loaded=False
        if reply.error()==reply.NetworkError.NoError and len(data)<=1024*1024:
            buffer=QBuffer();buffer.setData(QByteArray(data));buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            reader=QImageReader(buffer);size=reader.size()
            pixmap=QPixmap()
            if size.width()==256 and size.height()==256 and pixmap.loadFromData(data):
                z,x,y=key;size=WORLD*2/(2**z)
                item=self.scene().addPixmap(pixmap);item.setScale(size/256)
                item.setPos(-WORLD+x*size,-WORLD+y*size);item.setZValue(-1)
                if key in self.tiles:self.scene().removeItem(self.tiles[key])
                self.tiles[key]=item;loaded=True;self.failed.pop(key,None)
        if not loaded:
            self.failed[key]=time.monotonic()+30;self.timer.start(30000)
        reply.deleteLater()

    def shutdown(self):
        self.generation+=1
        self.timer.stop()
        replies=list(self.pending.values());self.pending.clear()
        for reply in replies:reply.abort()
