"""Pure Python provider/format tests: safe to run without importing Qt."""
import gzip
import io
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from app.gis.offline_maps import (Archive,LocalArchive,RangeSource,CHIOS,SOURCE,
    extract_chios,region_tiles,unpack,MAX_BLOCK)
from app.gis.providers import BASEMAPS,restored_basemap
from app.gis.vector_tiles import decode,geometry,varint
from app.vendor.pmtiles.tile import Compression,TileType,zxy_to_tileid,write_varint
from app.vendor.pmtiles.writer import Writer


def vi(value):
    stream=io.BytesIO();write_varint(stream,value);return stream.getvalue()


def field(number,value):
    return vi(number*8+2)+vi(len(value))+value


def sample_tile():
    # Independent MVT wire fixture: one triangular polygon, one UTF-8 name.
    feature=vi(3*8)+vi(3)+field(2,vi(0)+vi(0))+field(4,b''.join(map(vi,[9,20,20,18,200,0,0,200,15])))
    layer=field(1,b'earth')+field(2,feature)+field(3,b'name')+field(4,field(1,'Χίος'.encode()))+vi(5*8)+vi(4096)+vi(15*8)+vi(2)
    return field(3,layer)


def archive_bytes(keys=((0,0,0),),tile=None):
    stream=io.BytesIO();writer=Writer(stream)
    for key in sorted(keys,key=lambda xyz:zxy_to_tileid(*xyz)):
        writer.write_tile(zxy_to_tileid(*key),gzip.compress(tile or sample_tile()))
    writer.finalize({'tile_type':TileType.MVT,'tile_compression':Compression.GZIP},
        {'vector_layers':[{'id':name} for name in ('earth','water','roads')]})
    return stream.getvalue()


class OfflineMapTests(unittest.TestCase):
    def test_native_provider_gates_and_legacy_ids(self):
        self.assertEqual({'pmtiles'}, {p.identity for p in BASEMAPS if p.offline_allowed})
        for identity in ('oam','arcgis'):
            provider=restored_basemap(identity)
            self.assertTrue(provider.unavailable_reason);self.assertFalse(provider.tile_template)
            self.assertFalse(provider.persistent_cache);self.assertFalse(provider.offline_allowed)
        for old in ('google','versatiles',2,4,99):self.assertEqual('neutral',restored_basemap(old).identity)
        self.assertEqual('sentinel',restored_basemap(3).identity)

    def test_real_chios_coordinate_is_inside_download_and_plan_is_bounded(self):
        self.assertTrue(CHIOS[0]<26.0550712259<CHIOS[2]);self.assertTrue(CHIOS[1]<38.2238264672<CHIOS[3])
        self.assertEqual(172,len(list(region_tiles())))
        with self.assertRaises(ValueError):list(region_tiles(max_zoom=16))

    def test_roundtrip_archive_reopen_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'map.pmtiles';path.write_bytes(archive_bytes())
            for _ in range(2):
                archive=LocalArchive(path)
                with patch('urllib.request.urlopen',side_effect=AssertionError('Network forbidden')):
                    features=decode(unpack(archive.get(0,0,0),archive.header['tile_compression']))
                self.assertEqual('Χίος',features[0][3]['name']);archive.close()

    def test_known_wire_polygon_closure_and_extent(self):
        feature=decode(sample_tile())[0]
        self.assertEqual(('earth',4096,3),feature[:3])
        self.assertEqual([(10,10),(110,10),(110,110),(10,10)],feature[4][0])

    def test_missing_tile_and_invalid_section_do_not_return_other_tile(self):
        data=archive_bytes();archive=Archive(lambda o,n:data[o:o+n],len(data))
        self.assertIsNone(archive.get(1,1,1))
        with self.assertRaises(ValueError):Archive(lambda o,n:data[o:o+n],150)

    def test_invalid_header_is_a_user_facing_value_error(self):
        for data in (b'not a map',b'notPMTiles'+bytes(127)):
            with self.assertRaises(ValueError):Archive(lambda o,n:data[o:o+n],len(data))

    def test_truncated_and_malicious_mvt_are_rejected(self):
        for data in (b'\x1a\x20x',b'\x00',b'\xff'*11):
            with self.assertRaises(ValueError):decode(data)
        with self.assertRaises(ValueError):geometry([18,2,2])
        with self.assertRaises(ValueError):geometry([9,2])
        with self.assertRaises(ValueError):varint(b'\xff'*11,0)

    def test_expanded_size_limit_and_compression_gate(self):
        with self.assertRaises(ValueError):unpack(gzip.compress(b'x'*(8*1024*1024+1)),Compression.GZIP)
        with self.assertRaises(ValueError):unpack(b'x',Compression.BROTLI)

    def test_range_source_refuses_full_response_and_oversized_ranges(self):
        class Response:
            status=200;headers={}
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self,*_):raise AssertionError('Must not read full planet response')
        with patch('app.gis.offline_maps.urlopen',return_value=Response()):
            with self.assertRaises(ValueError):RangeSource()(0,127)
        with self.assertRaises(ValueError):RangeSource()(0,MAX_BLOCK+1)
        with self.assertRaises(ValueError):RangeSource('https://tile.openstreetmap.org/0/0/0.png')

    def test_range_snapshot_etag_and_byte_accounting(self):
        class Response:
            status=206
            def __init__(self,etag):self.headers={'Content-Range':'bytes 0-126/1000','ETag':etag}
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self,n):return b'x'*127
        source=RangeSource()
        with patch('app.gis.offline_maps.urlopen',return_value=Response('"version-a"')) as request:
            self.assertEqual(b'x'*127,source(0,127));self.assertEqual(127,source.transferred)
        source.cache.clear()
        with patch('app.gis.offline_maps.urlopen',return_value=Response('"version-b"')) as request:
            with self.assertRaises(ValueError):source(0,127)
            self.assertEqual('"version-a"',request.call_args.args[0].get_header('If-match'))

    def test_region_extraction_persists_bytes_and_refuses_overwrite(self):
        keys=list(region_tiles(max_zoom=1));data=archive_bytes(keys)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'chios.pmtiles'
            with patch('app.gis.offline_maps.shutil.disk_usage',return_value=type('Space',(),{'free':1024**3})()):
                result=extract_chios(path,source=lambda o,n:data[o:o+n],max_zoom=1)
            self.assertEqual(len(keys),result['tiles']);self.assertEqual(path.stat().st_size,result['bytes'])
            archive=LocalArchive(path)
            self.assertEqual(list(CHIOS),archive.metadata['fieltra_bbox'])
            self.assertEqual(SOURCE,archive.metadata['fieltra_source']);archive.close()
            with self.assertRaises(FileExistsError):extract_chios(path)

    def test_cancel_leaves_no_completed_or_partial_map(self):
        data=archive_bytes(list(region_tiles(max_zoom=1)))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'chios.pmtiles'
            with patch('app.gis.offline_maps.shutil.disk_usage',return_value=type('Space',(),{'free':1024**3})()):
                with self.assertRaises(InterruptedError):extract_chios(path,cancel=lambda:True,source=lambda o,n:data[o:o+n],max_zoom=1)
            self.assertEqual([],list(Path(folder).iterdir()))

    def test_low_disk_space_blocks_before_any_network_or_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'chios.pmtiles'
            with patch('app.gis.offline_maps.shutil.disk_usage',return_value=type('Space',(),{'free':0})()), \
                 patch('app.gis.offline_maps.urlopen',side_effect=AssertionError('No network on low disk')):
                with self.assertRaisesRegex(OSError,'136 MiB'):extract_chios(path)
            self.assertEqual([],list(Path(folder).iterdir()))


if __name__=='__main__':unittest.main()
