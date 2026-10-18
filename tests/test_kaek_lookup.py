"""Synthetic official-format fixtures; CI never contacts cadastral services."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid
import zipfile
from urllib.error import HTTPError

import shapefile
from pyproj import CRS

from app.database import Database
from app.gis.kaek_lookup import (
    ANDROID_KAEK_SYNC_ENABLED, LookupStore, LookupConflict, StaleLookup,
    MAX_ATTEMPTS, MAX_BACKOFF_MS, LEASE_MS, apply_device_result, deserialize, serialize,
)
from app.gis.kaek_provider import NorthAegeanProvider, ProviderFailure
from app.gis.geometry import manual_coordinates, normalize
from app.gis.store import GeometryStore

NOW = 1792098000000
KAEK = "510000000001"  # Synthetic identifier, not a live fixture query.


def dataset(crs=2100, parcel_date='2026-10-06'):
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON) as writer:
        writer.field("KAEK", "C", size=80)
        writer.field("bLfSpnVr", "C", size=80)
        writer.poly([[[500000, 4200000], [500000, 4200100], [500100, 4200100],
                      [500100, 4200000], [500000, 4200000]]])
        writer.record(KAEK, parcel_date)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for ext, content in (("shp", shp.getvalue()), ("shx", shx.getvalue()), ("dbf", dbf.getvalue()),
                             ("prj", CRS(crs).to_wkt().encode()), ("cpg", b"UTF-8")):
            archive.writestr("synthetic." + ext, content)
    return output.getvalue()


class Response(io.BytesIO):
    status = 200

    def __init__(self, data, headers=None):
        super().__init__(data)
        self.headers = headers or {}

    def geturl(self):
        return NorthAegeanProvider.source_url


class KaekLookupTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch("app.database.DATA_DIR", self.root / "data"))
        self.db = Database(self.root / "farm.db")
        self.now = NOW
        self.store = LookupStore(self.db, clock=lambda: self.now)
        self.opener = Mock(side_effect=lambda *a, **kw: Response(dataset()))
        self.provider = NorthAegeanProvider(self.root / "cache", self.opener, lambda: self.now / 1000)
        self.field = self.db.execute("INSERT INTO fields(name,kaek) VALUES(?,?)", ("Synthetic field", KAEK))

    def request(self):
        self.store.enqueue(self.field, self.provider)
        return self.store.claim(self.provider)

    def result(self):
        return self.provider.fetch(self.request())

    def test_request_result_serialization_and_source_coordinates_roundtrip(self):
        request = self.request()
        self.assertEqual(request, deserialize(serialize(request)))
        result = self.provider.fetch(request)
        self.assertEqual(result, deserialize(serialize(result)))
        self.assertEqual("EPSG:2100", result["source_crs"])
        self.assertEqual([500000, 4200000], result["geometry"]["coordinates"][0][0])
        self.assertEqual(KAEK, result["kaek"])
        self.assertEqual("2026-10-06", result["source_date"])
        self.assertIn("ΚΤΗΜΑΤΟΛΟΓΙΟ", result["attribution"])

    def test_canonical_cache_works_without_network_after_restart(self):
        request = self.request()
        first = self.provider.fetch(request)
        self.opener.assert_called_once()
        offline = Mock(side_effect=AssertionError("Network must not be required"))
        provider = NorthAegeanProvider(self.root / "cache", offline, lambda: self.now / 1000)
        self.assertEqual(first, provider.fetch(request))
        offline.assert_not_called()

    def test_expired_valid_cache_survives_offline_restart_without_download_loop(self):
        request = self.request()
        first = self.provider.fetch(request)
        original = self.provider.cache.read_bytes()
        self.now += 8 * 24 * 3600 * 1000
        offline = Mock(side_effect=TimeoutError('Synthetic offline'))
        provider = NorthAegeanProvider(self.provider.cache.parent, offline, lambda: self.now/1000)
        result = provider.fetch(request)
        self.assertEqual(first['geometry'], result['geometry'])
        self.assertEqual(first['source_date'], result['source_date'])
        self.assertEqual(original, provider.cache.read_bytes())
        self.assertEqual('offline_or_timeout', provider.cache_info()['refresh_error'])
        self.assertEqual(NOW/1000, provider.cache_info()['downloaded_at'])
        self.assertEqual(1, offline.call_count)
        restarted = NorthAegeanProvider(provider.cache.parent, offline, lambda: self.now/1000)
        self.assertEqual(result, restarted.fetch(request))
        self.assertEqual(1, offline.call_count)

    def test_legacy_expired_zip_remains_usable_with_unknown_download_date(self):
        request = self.request()
        self.provider.cache.parent.mkdir()
        self.provider.cache.write_bytes(dataset())
        old = self.now/1000-8*24*3600
        os.utime(self.provider.cache, (old, old))
        self.opener.side_effect = TimeoutError('Synthetic offline')
        result = self.provider.fetch(request)
        self.assertEqual(KAEK, result['kaek'])
        self.assertNotIn('downloaded_at', self.provider.cache_info())
        self.assertIn('If-modified-since', self.opener.call_args.args[0].headers)

    def test_conditional_304_keeps_archive_bytes_and_original_download_time(self):
        request = self.request()
        self.opener.side_effect = lambda *a, **kw: Response(dataset(), {'ETag': '"snapshot-1"'})
        self.provider.fetch(request)
        original = self.provider.cache.read_bytes()
        original_mtime = self.provider.cache.stat().st_mtime_ns
        self.now += 8*24*3600*1000
        self.opener.side_effect = HTTPError(self.provider.source_url, 304, 'Not Modified', {}, None)
        result = self.provider.fetch(request)
        self.assertEqual(KAEK, result['kaek'])
        self.assertEqual('"snapshot-1"', self.opener.call_args.args[0].get_header('If-none-match'))
        self.assertEqual(original, self.provider.cache.read_bytes())
        self.assertEqual(original_mtime, self.provider.cache.stat().st_mtime_ns)
        self.assertEqual(NOW/1000, self.provider.cache_info()['downloaded_at'])
        self.assertEqual(self.now/1000, self.provider.cache_info()['checked_at'])

    def test_invalid_refresh_cannot_replace_working_archive(self):
        request = self.request()
        self.provider.fetch(request)
        original = self.provider.cache.read_bytes()
        self.now += 8*24*3600*1000
        self.opener.side_effect = lambda *a, **kw: Response(b'not a ZIP')
        with self.assertRaises(ProviderFailure):
            self.provider.fetch(request)
        self.assertEqual(original, self.provider.cache.read_bytes())

    def test_exact_official_storage_redirect_is_allowed_but_unrelated_hosts_are_not(self):
        request = self.request()
        response = Response(dataset())
        response.geturl = lambda: "https://example.invalid/injected.zip"
        self.provider.opener = lambda *a, **kw: response
        with self.assertRaises(ProviderFailure) as failure:
            self.provider.fetch(request)
        self.assertEqual("unexpected_response", failure.exception.reason)
        response = Response(dataset())
        response.geturl = lambda: NorthAegeanProvider.storage_url
        self.provider.opener = lambda *a, **kw: response
        self.assertEqual(KAEK, self.provider.fetch(request)["kaek"])

    def test_wgs84_payload_and_missing_parcel_are_explicit(self):
        request = self.request()
        result = self.provider.fetch(request)
        geometry = normalize(result["geometry"], result["source_crs"])
        wgs84 = dict(result, source_crs="EPSG:4326", geometry=geometry.wgs84)
        self.assertEqual(wgs84, deserialize(serialize(wgs84)))
        self.assertTrue(self.store.complete(wgs84, self.provider))
        self.assertEqual("EPSG:4326", self.store.geometry(self.field)["source_crs"])
        with self.assertRaises(ProviderFailure) as failure:
            self.provider.fetch(dict(request, kaek="510000000002"))
        self.assertEqual("not_in_snapshot", failure.exception.reason)
        self.assertFalse(failure.exception.temporary)

    def test_pending_queue_and_stable_ids_survive_restart_without_duplicates(self):
        first = self.store.enqueue(self.field, self.provider)
        again = self.store.enqueue(self.field, self.provider)
        self.assertEqual(first, again)
        reopened = LookupStore(Database(self.db.path), lambda: self.now)
        self.assertEqual(first, reopened.job(self.field))
        self.assertEqual(self.store.request(first), reopened.request(first))
        self.assertEqual(1, self.db.query_one("SELECT count(*) FROM kaek_lookup_jobs")[0])
        self.assertNotEqual(str(self.field), first["field_uuid"])

    def test_prolonged_outage_keeps_bounded_retries_and_recovers_without_manual_reset(self):
        self.opener.side_effect = TimeoutError("synthetic offline")
        request = self.request()
        with self.assertRaises(ProviderFailure) as failure:
            self.provider.fetch(request)
        self.assertTrue(failure.exception.temporary)
        for attempt in range(1, 13):
            self.store.fail(request, "offline_or_timeout")
            job = self.store.job(self.field)
            self.assertEqual(attempt, job["attempts"])
            self.assertIsNone(self.store.claim(self.provider))
            self.assertEqual('temporary_failure', job['status'])
            self.assertEqual(min(30_000 * 2 ** (attempt-1), MAX_BACKOFF_MS), job['next_attempt']-self.now)
            self.now = job['next_attempt']
            request = self.store.claim(self.provider)
            self.assertIsNotNone(request)
        self.assertEqual(KAEK, self.db.query_one("SELECT kaek FROM fields")[0])
        self.opener.side_effect = lambda *a, **kw: Response(dataset())
        self.assertTrue(self.store.complete(self.provider.fetch(request), self.provider))
        self.assertEqual('retrieved', self.store.job(self.field)['status'])

    def test_crash_lease_recovery_rejects_old_attempt(self):
        old = self.request()
        self.assertIsNone(self.store.claim(self.provider))
        self.now += LEASE_MS
        current = self.store.claim(self.provider)
        self.assertEqual(old["job_id"], current["job_id"])
        self.assertNotEqual(old["request_id"], current["request_id"])
        with self.assertRaises(StaleLookup):
            self.store.complete(self.provider.fetch(old), self.provider)

    def test_crashed_attempt_after_legacy_limit_remains_recoverable(self):
        self.request()
        self.db.execute("UPDATE kaek_lookup_jobs SET attempts=?", (MAX_ATTEMPTS,))
        self.now += LEASE_MS
        self.assertIsNotNone(self.store.claim(self.provider))
        self.assertEqual('retrieving', self.store.job(self.field)['status'])
        self.assertEqual(MAX_ATTEMPTS+1, self.store.job(self.field)['attempts'])

    def test_legacy_stranded_jobs_reactivate_but_permanent_failures_do_not(self):
        self.request()
        self.db.execute("UPDATE kaek_lookup_jobs SET status='unavailable',reason='retry_limit',attempts=6,next_attempt=?", (self.now+MAX_BACKOFF_MS,))
        self.assertIsNone(self.store.claim(self.provider))
        self.assertEqual('temporary_failure', self.store.job(self.field)['status'])
        self.store.connectivity_restored()
        request = self.store.claim(self.provider)
        self.assertIsNotNone(request)
        self.assertEqual(7, self.store.job(self.field)['attempts'])
        self.store.fail(request, 'not_in_snapshot', temporary=False)
        self.store.connectivity_restored()
        self.now += MAX_BACKOFF_MS
        self.assertIsNone(self.store.claim(self.provider))
        self.assertEqual('unavailable', self.store.job(self.field)['status'])

    def test_result_is_idempotent_and_never_overwrites_cultivation_geometry(self):
        cultivated = GeometryStore(self.db)
        cultivated.save(self.field, manual_coordinates("26 38\n26.001 38\n26.001 38.001\n26 38.001", "EPSG:4326"), source="manual")
        before = cultivated.get(self.field)
        result = self.result()
        self.assertTrue(self.store.complete(result, self.provider))
        self.assertFalse(self.store.complete(result, self.provider))
        self.assertEqual(before, cultivated.get(self.field))
        self.assertEqual(result, self.store.geometry(self.field))
        changed = dict(result, source_date="2026-10-07")
        with self.assertRaises(LookupConflict):
            self.store.complete(changed, self.provider)
        self.assertEqual(result, self.store.geometry(self.field))

    def test_changed_kaek_deleted_field_and_other_dataset_results_are_rejected(self):
        result = self.result()
        for key in ("dataset_id", "field_id", "job_id"):
            with self.subTest(key=key), self.assertRaises(StaleLookup):
                self.store.complete(dict(result, **{key: str(uuid.uuid4())}), self.provider)
        self.db.execute("UPDATE fields SET kaek=? WHERE id=?", ("510000000002", self.field))
        self.store.enqueue(self.field, self.provider)
        with self.assertRaises(StaleLookup):
            self.store.complete(result, self.provider)
        self.db.execute("UPDATE fields SET kaek=? WHERE id=?", (KAEK, self.field))
        self.store.enqueue(self.field, self.provider)
        with self.assertRaises(StaleLookup):
            self.store.complete(result, self.provider)
        self.db.execute("DELETE FROM fields WHERE id=?", (self.field,))
        with self.assertRaises(StaleLookup):
            self.store.complete(result, self.provider)
        self.assertEqual(0, self.db.query_one("SELECT count(*) FROM cadastral_geometry")[0])

    def test_invalid_missing_or_unsupported_identifiers_do_not_access_provider(self):
        for kaek in ("", "123", "１２３４５６７８９０１２", "001234567890"):
            self.db.execute("UPDATE fields SET kaek=? WHERE id=?", (kaek, self.field))
            job = self.store.enqueue(self.field, self.provider)
            if len(kaek) == 12 and kaek.isascii():
                self.assertEqual("unavailable", job["status"])
                self.assertEqual("unsupported_region", job["reason"])
            else:
                self.assertIsNone(job)
            self.assertIsNone(self.store.claim(self.provider))
        self.opener.assert_not_called()

    def test_unverified_provider_keeps_job_without_network(self):
        job = self.store.enqueue(self.field, None)
        self.assertEqual("provider_unavailable", job["reason"])
        self.assertIsNone(self.store.claim(None))
        self.assertEqual(job, LookupStore(Database(self.db.path)).job(self.field))

    def test_malformed_data_crs_and_provenance_are_rejected(self):
        request = self.request()
        for data in (b"<html>not geometry</html>", dataset(4326)):
            with self.subTest(data=data[:10]), self.assertRaises(ProviderFailure):
                self.provider.opener = lambda *a, **kw: Response(data)
                self.provider.fetch(request)
        self.provider.opener = lambda *a, **kw: Response(dataset())
        result = self.provider.fetch(request)
        for override in ({"source_url": "https://example.invalid/injected"},
                         {"provider": "untrusted"}, {"retrieved_at": self.now + 999999}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.store.complete(dict(result, **override), self.provider)
        bad = dict(result, geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 0]]]})
        with self.assertRaises(ValueError):
            serialize(bad)
        with self.assertRaises(ValueError):
            deserialize('{"schema":1,"schema":1}')
        with self.assertRaises(ValueError):
            deserialize(serialize(request).replace('"schema":1', '"schema":true'))

    def test_disabled_device_sync_cannot_mutate_application_data(self):
        result = self.result()
        with self.db.connect() as con:
            before = list(con.iterdump())
        self.assertFalse(ANDROID_KAEK_SYNC_ENABLED)
        with self.assertRaises(PermissionError):
            apply_device_result(self.store, result)
        with self.db.connect() as con:
            self.assertEqual(before, list(con.iterdump()))


if __name__ == "__main__":
    unittest.main()
