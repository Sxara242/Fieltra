"""Synthetic local regional/WMS/Atom/offline security tests; no live services.
SPDX-License-Identifier: AGPL-3.0-only
"""
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import closing
from dataclasses import replace
import io
import hashlib
import binascii
from pathlib import Path
import struct
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch
import zipfile
from defusedxml.common import DefusedXmlException

from app.country_extensions import IdentifierScope
from app.gis.cadastral_protocol import ScopedParcelIdentity
from app.gis.greek_cadastre import GreekCadastreDataset
from app.gis.kaek_provider import NorthAegeanProvider
from app.gis.cadastre_wms import WmsDescriptor, capabilities_request, parse_capabilities, map_request, WmsClient
from app.gis.provider_io import Response, safe_xml
from app.gis.inspire_offline import (FeedDescriptor, parse_feed, OfflineDatasetStore, inspect_zip, resume_is_valid)

CAPABILITIES = b'''<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
<Service><Fees>fixture only</Fees><AccessConstraints>synthetic terms</AccessConstraints></Service>
<Capability><Request><GetMap><Format>image/png</Format></GetMap></Request>
<Layer><CRS>EPSG:4326</CRS><CRS>EPSG:2100</CRS><Style><Name>synthetic-style</Name></Style>
<Layer><Name>synthetic-layer</Name><Title>Synthetic orthophoto</Title></Layer></Layer></Capability></WMS_Capabilities>'''
FEED = b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:dct="http://purl.org/dc/terms/" xmlns:georss="http://www.georss.org/georss">
<id>urn:synthetic:feed</id><rights>Test rights, no official license claim</rights>
<entry><id>urn:synthetic:region</id><title>Synthetic vector archive</title><updated>2026-10-20T00:00:00Z</updated>
<dct:hasVersion>fixture-v1</dct:hasVersion><georss:box>34 19 42 30</georss:box>
<link rel="enclosure" type="application/zip" href="region.zip"/></entry></feed>'''


def archive_bytes(name='synthetic.txt', payload=b'synthetic vector candidate'):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        archive.writestr(name,payload)
    return stream.getvalue()


def raw_archive_bytes(*names, local_names=None):
    """Tiny stored UTF-8 ZIPs with literal header names, bypassing ZipInfo.

    writestr sanitizes backslashes on Windows and truncates NUL names. Pack
    local/central headers directly so every hostile spelling survives on disk.
    Optional distinct local names exercise ZipFile.open's consistency check.
    """
    local_names = names if local_names is None else local_names
    if len(names) != len(local_names):
        raise ValueError('One local name per central-directory name required')
    body, central = bytearray(), bytearray()
    for name, local_name in zip(names, local_names):
        encoded, local = name.encode('utf-8'), local_name.encode('utf-8')
        payload = b'' if name.endswith('/') else b'synthetic vector candidate'
        crc = binascii.crc32(payload)
        offset = len(body)
        body.extend(struct.pack('<4s5H3I2H', b'PK\x03\x04', 20, 0x800, 0, 0, 33,
                                crc, len(payload), len(payload), len(local), 0))
        body.extend(local)
        body.extend(payload)
        central.extend(struct.pack('<4s6H3I5H2I', b'PK\x01\x02', 20, 20, 0x800, 0, 0, 33,
                                   crc, len(payload), len(payload), len(encoded), 0, 0, 0, 0, 0, offset))
        central.extend(encoded)
    end = struct.pack('<4s4H2IH', b'PK\x05\x06', 0, 0, len(names), len(names), len(central), len(body), 0)
    return bytes(body + central + end)


class WmsTests(unittest.TestCase):
    def test_coalescing_removal_cancellation_and_reserved_parameters(self):
        class Deferred:
            def submit(self, action):
                self.action=action;self.future=Future();return self.future
        descriptor=replace(WmsDescriptor(),endpoint='https://example.invalid/wms?token=fixture&SRS=old&request=old')
        url=capabilities_request(descriptor)
        self.assertNotIn('SRS',parse_qs(urlsplit(url).query))
        self.assertEqual(['fixture'],parse_qs(urlsplit(url).query)['token'])
        transport=Mock(return_value=Response(200,'text/xml',CAPABILITIES,url))
        executor=Deferred();client=WmsClient(descriptor,transport)
        first=client.submit(executor,url)
        self.assertIs(first,client.submit(executor,url))
        transport.assert_not_called()
        executor.future.set_result(executor.action())
        self.assertEqual('1.3.0',first.result().version)
        self.assertIsNot(first,client.submit(executor,url,cancelled=lambda:True))
        with self.assertRaises(InterruptedError):executor.action()
        self.assertEqual(1,transport.call_count)

    def test_discovery_version_axis_and_unadvertised_layer_rejection(self):
        descriptor=WmsDescriptor()
        caps=parse_capabilities(CAPABILITIES,descriptor)
        self.assertEqual(('synthetic-style',),caps.layers[0].styles)
        for version,expected,key in (('1.3.0','34.0,19.0,42.0,30.0','CRS'),('1.1.1','19.0,34.0,30.0,42.0','SRS')):
            url=map_request(descriptor,replace(caps,version=version),layers=['synthetic-layer'],crs='EPSG:4326',
                bbox=(19,34,30,42),width=256,height=256)
            params=parse_qs(urlsplit(url).query)
            self.assertEqual([expected],params['BBOX'])
            self.assertEqual(['EPSG:4326'],params[key])
        with self.assertRaises(ValueError):
            map_request(descriptor,caps,layers=['invented-layer'],crs='EPSG:4326',bbox=(19,34,30,42),width=256,height=256)
        self.assertEqual(['GetCapabilities'],parse_qs(urlsplit(capabilities_request(descriptor)).query)['REQUEST'])

    def test_xml_entities_and_service_exceptions_rejected(self):
        for payload in (b'<!DOCTYPE feed [<!ENTITY attack SYSTEM "file:///forbidden">]><feed>&attack;</feed>',
                        b'<ServiceExceptionReport><ServiceException>synthetic error</ServiceException></ServiceExceptionReport>'):
            with self.assertRaises((ValueError, DefusedXmlException)):
                parse_capabilities(payload,WmsDescriptor())

    def test_image_errors_and_no_disk_cache(self):
        descriptor=WmsDescriptor()
        transport=Mock(return_value=Response(200,'text/xml',b'<ServiceException/>',descriptor.endpoint))
        client=WmsClient(descriptor,transport)
        with ThreadPoolExecutor(1) as executor:
            with self.assertRaises(ValueError):
                client.submit(executor,descriptor.endpoint,image_format='image/png').result()
        self.assertEqual(0,descriptor.cache_max_bytes)


class OfflineTests(unittest.TestCase):
    # All added/modified ZIP regression tests: NOT EXECUTED locally.
    def raw_zip(self, *names, local_names=None):
        data = raw_archive_bytes(*names, local_names=local_names)
        expected_local = names if local_names is None else local_names
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            self.assertEqual(list(names), [entry.orig_filename for entry in entries])
            for entry, local in zip(entries, expected_local):
                start = entry.header_offset
                self.assertEqual(b'PK\x03\x04', data[start:start+4])
                length = struct.unpack_from('<H', data, start+26)[0]
                self.assertEqual(local.encode('utf-8'), data[start+30:start+30+length])
        return data

    def refuse_raw_zip(self, *names):
        with self.assertRaisesRegex(ValueError, 'Unsafe ZIP member|normalized'):
            inspect_zip(self.raw_zip(*names))

    def test_zip_legitimate_nested_members_and_directory(self):
        self.assertEqual(('folder/', 'folder/nested/', 'folder/nested/valid.txt'),
            inspect_zip(self.raw_zip('folder/', 'folder/nested/', 'folder/nested/valid.txt')))

    def test_zip_parent_traversal_rejected(self):
        self.refuse_raw_zip('../escape.txt')

    def test_zip_nested_parent_traversal_rejected(self):
        self.refuse_raw_zip('folder/../escape.txt')

    def test_zip_absolute_path_rejected(self):
        self.refuse_raw_zip('/absolute.txt')

    def test_zip_drive_relative_path_rejected(self):
        self.refuse_raw_zip('C:escape.txt')

    def test_zip_drive_absolute_path_rejected(self):
        self.refuse_raw_zip('C:/escape.txt')

    def test_zip_original_backslash_rejected(self):
        self.refuse_raw_zip('folder\\escape.txt')

    def test_zip_backslash_traversal_rejected(self):
        self.refuse_raw_zip('folder\\..\\escape.txt')

    def test_zip_unc_path_rejected(self):
        self.refuse_raw_zip('\\\\server\\share\\escape.txt')

    def test_zip_original_nul_suffix_rejected(self):
        self.refuse_raw_zip('valid.txt\x00hidden')

    def test_zip_dot_segment_rejected(self):
        self.refuse_raw_zip('folder/./valid.txt')

    def test_zip_repeated_separator_rejected(self):
        self.refuse_raw_zip('folder//valid.txt')

    def test_zip_duplicate_name_rejected(self):
        self.refuse_raw_zip('valid.txt', 'valid.txt')

    def test_zip_case_collision_rejected(self):
        self.refuse_raw_zip('folder/Valid.txt', 'FOLDER/valid.txt')

    def test_zip_separator_normalization_collision_rejected(self):
        self.refuse_raw_zip('folder/valid.txt', 'folder\\valid.txt')

    def test_zip_nul_normalization_collision_rejected(self):
        self.refuse_raw_zip('valid.txt', 'valid.txt\x00hidden')

    def test_zip_unicode_normalization_collision_rejected(self):
        self.refuse_raw_zip('caf\u00e9.txt', 'cafe\u0301.txt')

    def test_zip_file_directory_alias_rejected(self):
        self.refuse_raw_zip('folder', 'folder/')

    def test_zip_windows_trailing_dot_alias_rejected(self):
        self.refuse_raw_zip('folder/valid.txt', 'folder./valid.txt')

    def test_zip_windows_trailing_space_alias_rejected(self):
        self.refuse_raw_zip('folder/valid.txt', 'folder /valid.txt')

    def test_zip_local_header_name_mismatch_rejected(self):
        data = self.raw_zip('valid.txt', local_names=('other.txt',))
        with self.assertRaisesRegex(zipfile.BadZipFile, 'differ'):
            inspect_zip(data)

    def test_zip_local_header_backslash_not_silently_normalized(self):
        data = self.raw_zip('folder/valid.txt', local_names=('folder\\valid.txt',))
        with self.assertRaisesRegex(zipfile.BadZipFile, 'differ'):
            inspect_zip(data)

    def test_zip_local_header_nul_not_silently_truncated(self):
        data = self.raw_zip('valid.txt', local_names=('valid.txt\x00hidden',))
        with self.assertRaisesRegex(zipfile.BadZipFile, 'differ'):
            inspect_zip(data)

    def test_zip_content_crc_corruption_rejected(self):
        data = bytearray(self.raw_zip('valid.txt'))
        data[30+len('valid.txt')] ^= 1
        with self.assertRaisesRegex(zipfile.BadZipFile, 'CRC'):
            inspect_zip(bytes(data))

    def test_expected_checksum_failure_timeout_and_versioned_availability(self):
        dataset=self.dataset();data=archive_bytes();original=dataset.download_links[0]
        class Stream(io.BytesIO):
            status=200
            headers={}
            def geturl(self):return original.url
        with tempfile.TemporaryDirectory() as directory, closing(OfflineDatasetStore(directory)) as store:
            bad=replace(original,expected_sha256='0'*64);wrong=replace(dataset,download_links=(bad,))
            with self.assertRaisesRegex(ValueError,'checksum'):
                store.download(wrong,bad,initiated_by_user=True,open_stream=lambda url:Stream(data))
            self.assertEqual(('MISSING',None),store.available(wrong,bad))
            self.assertEqual([],list(Path(directory).glob('*.zip')))
            with patch('app.gis.inspire_offline.time.monotonic',side_effect=(0,61)):
                with self.assertRaises(TimeoutError):
                    store.download(dataset,original,initiated_by_user=True,open_stream=lambda url:Stream(data))
            checked=replace(original,expected_sha256=hashlib.sha256(data).hexdigest())
            reviewed=replace(dataset,download_links=(checked,))
            store.download(reviewed,checked,initiated_by_user=True,open_stream=lambda url:Stream(data))
            self.assertEqual('AVAILABLE',store.available(reviewed,checked)[0])
            self.assertEqual(('MISSING',None),store.available(replace(reviewed,version='fixture-v2'),checked))
            self.assertEqual([],list(Path(directory).glob('*.part')))

    def test_feed_license_inheritance_and_entry_override(self):
        feed=FEED.replace(b'<id>urn:synthetic:feed</id>',b'<id>urn:synthetic:feed</id><link rel="license" href="terms.html"/>')
        descriptor=FeedDescriptor('https://example.invalid/atom/feed.xml','source','fallback')
        self.assertEqual('https://example.invalid/atom/terms.html',parse_feed(feed,descriptor,0)[0].terms_reference)
        feed=feed.replace(b'<entry>',b'<entry><link rel="license" href="entry-terms.html"/>')
        self.assertEqual('https://example.invalid/atom/entry-terms.html',parse_feed(feed,descriptor,0)[0].terms_reference)

    def dataset(self):
        return parse_feed(FEED,FeedDescriptor('https://example.invalid/atom/feed.xml','synthetic source','synthetic terms'),0)[0]

    def test_feed_provenance_relative_link_and_security(self):
        entry=self.dataset()
        self.assertEqual('https://example.invalid/atom/region.zip',entry.download_links[0].url)
        self.assertEqual('fixture-v1',entry.version)
        self.assertIn('Test rights',entry.rights)
        self.assertEqual('34 19 42 30',entry.spatial_coverage)
        with self.assertRaises((ValueError, DefusedXmlException)):
            parse_feed(b'<!DOCTYPE feed [<!ENTITY x "attack">]><feed/>',FeedDescriptor('https://example.invalid/feed','source','terms'),0)

    def test_download_is_explicit_atomic_indexed_reused_and_corruption_detected(self):
        dataset=self.dataset();link=dataset.download_links[0];data=archive_bytes()
        class Stream(io.BytesIO):
            status=200
            headers={'Content-Length':str(len(data))}
            def geturl(self):return link.url
        opener=Mock(side_effect=lambda url:Stream(data))
        with tempfile.TemporaryDirectory() as directory, closing(OfflineDatasetStore(directory)) as store:
            with self.assertRaises(PermissionError):
                store.download(dataset,link,initiated_by_user=False,open_stream=opener)
            with self.assertRaises(InterruptedError):
                store.download(dataset,link,initiated_by_user=True,cancelled=lambda:True,open_stream=opener)
            self.assertEqual(0,opener.call_count)
            first=store.download(dataset,link,initiated_by_user=True,open_stream=opener)
            self.assertEqual(first,store.download(dataset,link,initiated_by_user=True,open_stream=opener))
            self.assertEqual(1,opener.call_count)
            self.assertEqual('AVAILABLE',store.available(dataset,link)[0])
            first.write_bytes(b'corrupt synthetic archive')
            self.assertEqual('CORRUPT',store.available(dataset,link)[0])

    def test_corrupt_download_never_becomes_available(self):
        dataset=self.dataset();link=dataset.download_links[0]
        class Broken(io.BytesIO):
            status=200
            headers={}
            def geturl(self):return link.url
        with tempfile.TemporaryDirectory() as directory, closing(OfflineDatasetStore(directory)) as store:
            with self.assertRaises(zipfile.BadZipFile):
                store.download(dataset,link,initiated_by_user=True,open_stream=lambda url:Broken(b'corrupted synthetic archive'))
            self.assertEqual(('MISSING',None),store.available(dataset,link))
            self.assertEqual([],list(Path(directory).glob('*.zip')))
            self.assertEqual([],list(Path(directory).glob('*.part')))

    def test_unsafe_zip_download_never_becomes_available(self):
        dataset=self.dataset();link=dataset.download_links[0]
        data=self.raw_zip('folder\\escape.txt')
        class Stream(io.BytesIO):
            status=200
            headers={}
            def geturl(self):return link.url
        with tempfile.TemporaryDirectory() as directory, closing(OfflineDatasetStore(directory)) as store:
            with self.assertRaisesRegex(ValueError,'Unsafe ZIP member'):
                store.download(dataset,link,initiated_by_user=True,open_stream=lambda url:Stream(data))
            self.assertEqual(('MISSING',None),store.available(dataset,link))
            self.assertEqual([],list(Path(directory).glob('*.zip')))
            self.assertEqual([],list(Path(directory).glob('*.part')))

    def test_zip_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.zip'
            path.write_bytes(archive_bytes())
            with self.assertRaises(InterruptedError):inspect_zip(path,lambda:True)

    def test_zip_invalid_archive_rejected(self):
        with self.assertRaises(zipfile.BadZipFile):inspect_zip(b'not a zip')

    def test_resume_refusal_and_protocol_predicate(self):
        self.assertFalse(resume_is_valid(status=200,content_range=None,strong_etag='"v1"',previous_etag='"v1"',offset=100,expected_total=200))
        self.assertTrue(resume_is_valid(status=206,content_range='bytes 100-199/200',strong_etag='"v1"',previous_etag='"v1"',offset=100,expected_total=200))


class RegionalAdapterTests(unittest.TestCase):
    def test_reuses_existing_verified_format_parser_without_fetch(self):
        # Existing synthetic factory creates SHP/SHX/DBF/PRJ/CPG, no network.
        from tests.test_kaek_lookup import dataset, KAEK
        provider=NorthAegeanProvider('unused-synthetic-cache',opener=Mock(side_effect=AssertionError('No network')))
        reader=GreekCadastreDataset(provider)
        identity=ScopedParcelIdentity(IdentifierScope('GR','kaek','hellenic-cadastre'),KAEK)
        result=reader.read_many(dataset(),[identity])[0]
        self.assertEqual('FOUND',result.status)
        source=reader.source_snapshot('20000000-0000-4000-8000-000000000001',result,dataset_version='fixture')
        self.assertFalse(source.official_source_verified)
        provider.opener.assert_not_called()
