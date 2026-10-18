"""No external services: official URL contracts and native local HTTP raster test."""
from datetime import date,timedelta
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import time
import unittest
import math
from urllib.parse import parse_qs,urlsplit

from PySide6.QtCore import QBuffer,QIODevice,QUrl
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from app.gis.map_view import ParcelMap
from app.gis.geometry import manual_coordinates
from app.gis.providers import BASEMAPS,BasemapProvider,cdse_provider,restored_basemap
from PySide6.QtNetwork import QNetworkReply,QNetworkRequest


class SatelliteContractTests(unittest.TestCase):
    def test_cdse_wms_crs_bbox_dates_and_private_instance(self):
        end=date.today();start=end-timedelta(days=7)
        instance='00000000-0000-0000-0000-000000000001'
        provider=cdse_provider(instance,'TRUE_COLOR',start.isoformat(),end.isoformat())
        url=urlsplit(provider.tile_url(12,2344,1576));query=parse_qs(url.query)
        self.assertEqual('sh.dataspace.copernicus.eu',url.hostname)
        self.assertEqual(['EPSG:3857'],query['CRS'])
        west,south,east,north=map(float,query['BBOX'][0].split(','))
        self.assertLess(west,east);self.assertLess(south,north)
        self.assertEqual(['512'],query['WIDTH'])
        self.assertNotIn(instance,repr(provider))
        self.assertFalse(provider.persistent_cache)
        self.assertFalse(provider.offline_allowed)
        with self.assertRaises(ValueError):cdse_provider('invalid','TRUE_COLOR',str(start),str(end))

    def test_only_approved_backgrounds_and_safe_legacy_selection(self):
        self.assertEqual(['neutral','osm','sentinel','pmtiles','oam','arcgis'],[p.identity for p in BASEMAPS])
        self.assertEqual(['pmtiles'],[p.identity for p in BASEMAPS if p.offline_allowed])
        for value in ('google','versatiles',2,4,99,'unknown'):
            self.assertIs(BASEMAPS[0],restored_basemap(value))
        self.assertEqual('sentinel',restored_basemap(3).identity)
        self.assertEqual('osm',restored_basemap('osm').identity)


class SatelliteRasterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_rate_limit_respects_server_wait_and_bounds_automatic_attempts(self):
        class Reply:
            NetworkError=QNetworkReply.NetworkError
            def error(self):return QNetworkReply.NetworkError.UnknownNetworkError
            def readAll(self):return b''
            def attribute(self,key):return 429
            def rawHeader(self,key):return b'7200000'
            def deleteLater(self):pass
        end=date.today();start=end-timedelta(days=7)
        provider=cdse_provider('00000000-0000-0000-0000-000000000001','TRUE_COLOR',str(start),str(end))
        with tempfile.TemporaryDirectory() as folder:
            view=ParcelMap(Path(folder));view.set_provider(provider);key=(12,2344,1576)
            try:
                view.attempts[key]=3
                before=time.monotonic()
                view.tile_finished(key,Reply(),provider,view.generation,bytearray())
                self.assertEqual(math.inf,view.failed[key])
                self.assertGreaterEqual(view.provider_wait['sentinel']-before,7200)
                view.cdse_requests=200
                view.set_provider(BASEMAPS[0]);view.set_provider(provider)
                self.assertEqual(200,view.cdse_requests)
            finally:view.shutdown();view.close();view.deleteLater()

    def test_512_webp_loads_without_persisting_sensitive_cache_or_moving_geometry(self):
        image=QImage(512,512,QImage.Format.Format_RGB32);image.fill(QColor('green'))
        buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self.assertTrue(image.save(buffer,'WEBP'),'Retained Qt WebP plugin is required')
        body=bytes(buffer.data());urls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                urls.append(self.path);self.send_response(200);self.send_header('Cache-Control','max-age=3600');self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                view=ParcelMap(Path(folder));view.resize(350,350)
                geometry=manual_coordinates('26 38\n26.001 38\n26.001 38.001\n26 38.001','EPSG:4326')
                view.set_cadastral_geometry(geometry);view.show();self.app.processEvents()
                before=view.transform().m11();overlay=view.cadastral_item
                provider=BasemapProvider('fixture','Fixture',tile_template=f'http://127.0.0.1:{server.server_port}/{{z}}/{{x}}/{{y}}',tile_size=512,max_zoom=12,persistent_cache=False)
                try:
                    view.set_provider(provider);view.load_visible_tiles()
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline and not view.tiles:self.app.processEvents();time.sleep(.01)
                    self.assertTrue(view.tiles)
                    self.assertEqual(before,view.transform().m11())
                    self.assertIs(overlay,view.cadastral_item)
                    self.assertFalse(view.boundaries)
                    for path in urls:
                        self.assertFalse(view.network.cache().metaData(QUrl(f'http://127.0.0.1:{server.server_port}{path}')).isValid())
                    self.assertLessEqual(len(view.pending),2)
                finally:view.shutdown();view.close();view.deleteLater()
        finally:server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
