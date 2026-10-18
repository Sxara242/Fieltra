"""Verified official North Aegean snapshot. No browser scraping or private API."""
from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import time
from email.utils import formatdate
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
import zipfile
from datetime import date

import shapefile
from pyproj import CRS
from pyproj.exceptions import CRSError

from .kaek_lookup import valid_kaek, validate_payload


class ProviderFailure(Exception):
    def __init__(self, reason, temporary=True):
        super().__init__(reason)
        self.reason, self.temporary = reason, temporary


class NorthAegeanProvider:
    identity = "hellenic-cadastre-north-aegean"
    source_url = "https://data.gov.gr/dataset/17226281-9e0f-431f-b1a3-c9e807cdd3cd/resource/f7ae8fc0-715f-45c1-86cb-5feb3b7377d0/download/periferia_voriou_egaiou.zip"
    terms_url = "https://data.gov.gr/pages/terms-of-use"
    attribution = "Πηγή δεδομένων: Ν.Π.Δ.Δ. ΕΛΛΗΝΙΚΟ ΚΤΗΜΑΤΟΛΟΓΙΟ · data.gov.gr"
    MAX_ZIP = 32 * 1024 * 1024
    MAX_UNCOMPRESSED = 128 * 1024 * 1024
    CACHE_SECONDS = 7 * 24 * 3600
    REFRESH_RETRY_SECONDS = 3600
    # Verified redirect of the exact official resource on 2026-10-15.
    storage_url = "https://min01rg96sablob01.blob.core.windows.net/new-opendata/resources/f7ae8fc0-715f-45c1-86cb-5feb3b7377d0/periferia_voriou_egaiou.zip"

    def __init__(self, cache_directory, opener=None, clock=None):
        self.cache = Path(cache_directory) / "north-aegean-parcels.zip"
        self.opener = opener or urlopen
        self.clock = clock or time.time

    @staticmethod
    def supports(kaek):
        return valid_kaek(kaek) and kaek[:2] in {"33", "43", "51"}

    def cache_info(self):
        """Small cache-control sidecar; archive mtime is not a proven download date."""
        try:
            value = json.loads(self.cache.with_suffix('.json').read_text(encoding='utf-8'))
            if not isinstance(value, dict):
                return {}
            info = {}
            for key in ('downloaded_at', 'checked_at', 'attempted_at'):
                if type(value.get(key)) in (int, float) and 0 <= value[key] <= self.clock():
                    info[key] = value[key]
            for key in ('etag', 'last_modified', 'refresh_error'):
                text = value.get(key, '')
                if isinstance(text, str) and len(text) <= 512 and '\r' not in text and '\n' not in text:
                    info[key] = text
            return info
        except (OSError, ValueError):
            return {}

    def _write_info(self, info):
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self.cache.parent, mode='w', encoding='utf-8', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(info, stream, ensure_ascii=False)
        temporary.replace(self.cache.with_suffix('.json'))

    def _download(self, info=None, conditional=False):
        try:
            headers = {"User-Agent": "Fieltra/1.0.1 (public cadastral snapshot)"}
            if conditional:
                if info.get('etag'):
                    headers['If-None-Match'] = info['etag']
                modified = info.get('last_modified') or formatdate(self.cache.stat().st_mtime, usegmt=True)
                headers['If-Modified-Since'] = modified
            request = Request(self.source_url, headers=headers)
            with self.opener(request, timeout=30) as response:
                final = urlsplit(response.geturl())
                allowed = [urlsplit(url) for url in (self.source_url, self.storage_url)]
                if response.status not in (200, 304) or not any(
                        final.scheme == url.scheme and final.netloc == url.netloc and final.path == url.path
                        for url in allowed):
                    raise ProviderFailure("unexpected_response", False)
                response_headers = getattr(response, 'headers', {})
                validators = {key: response_headers.get(header, '') for key, header in
                              (('etag', 'ETag'), ('last_modified', 'Last-Modified'))}
                if response.status == 304:
                    if not conditional:
                        raise ProviderFailure('unexpected_response', False)
                    return None, validators
                output = io.BytesIO()
                deadline = time.monotonic() + 60
                while chunk := response.read(256 * 1024):
                    output.write(chunk)
                    if time.monotonic() > deadline:
                        raise ProviderFailure("offline_or_timeout")
                    if output.tell() > self.MAX_ZIP:
                        raise ProviderFailure("dataset_too_large", False)
                return output.getvalue(), validators
        except HTTPError as error:
            if error.code == 304 and conditional and error.geturl() in (self.source_url, self.storage_url):
                error.close()
                return None, {}
            raise ProviderFailure("provider_http_error", error.code == 429 or error.code >= 500) from error
        except (URLError, TimeoutError, OSError) as error:
            raise ProviderFailure("offline_or_timeout") from error

    def _reader(self, data):
        if len(data) > self.MAX_ZIP:
            raise ValueError("Dataset too large")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) != 5 or sum(m.file_size for m in members) > self.MAX_UNCOMPRESSED:
                raise ValueError("Unexpected archive size/members")
            files = {Path(m.filename).suffix.lower(): m.filename for m in members}
            if set(files) != {".shp", ".shx", ".dbf", ".prj", ".cpg"}:
                raise ValueError("Unexpected archive schema")
            if CRS(archive.read(files[".prj"]).decode("utf-8")).to_epsg() != 2100:
                raise ValueError("Unexpected source CRS")
            if archive.read(files[".cpg"]).decode("ascii").strip().upper() != "UTF-8":
                raise ValueError("Unexpected text encoding")
            reader = shapefile.Reader(shp=io.BytesIO(archive.read(files[".shp"])),
                                      shx=io.BytesIO(archive.read(files[".shx"])),
                                      dbf=io.BytesIO(archive.read(files[".dbf"])), encoding="utf-8")
            fields = {field[0]: field[1] for field in reader.fields[1:]}
            if fields != {"KAEK": "C", "bLfSpnVr": "C"}:
                reader.close()
                raise ValueError("Unexpected parcel attributes")
            return reader

    def _lookup(self, data, request):
        with self._reader(data) as reader:
            matches = [row for row in reader.iterRecords(fields=['KAEK', 'bLfSpnVr'])
                       if row['KAEK'] == request['kaek']]
            if len(matches) > 1:
                raise ValueError('Ambiguous parcel identifier')
            if not matches:
                return None
            row = matches[0]
            updated = row['bLfSpnVr']
            try:date.fromisoformat(updated)
            except (ValueError,TypeError):updated=''
            geometry = json.loads(json.dumps(reader.shape(row.oid).__geo_interface__))
            return validate_payload(dict(request, kind='kaek-result', geometry=geometry,
                source_crs='EPSG:2100', provider=self.identity, source_url=self.source_url,
                terms_url=self.terms_url, attribution=self.attribution, source_date=updated,
                retrieved_at=int(self.clock()*1000)))

    def fetch(self, request):
        request = validate_payload(request)
        if request['kind'] != 'kaek-request' or not self.supports(request['kaek']):
            raise ProviderFailure('unsupported_region', False)
        try:
            info = self.cache_info()
            cached = self.cache.read_bytes() if self.cache.is_file() else None
            result = self._lookup(cached, request) if cached is not None else None
            checked = info.get('checked_at', self.cache.stat().st_mtime if cached is not None else 0)
            fresh = cached is not None and self.clock()-checked < self.CACHE_SECONDS
            cooling = cached is not None and self.clock()-info.get('attempted_at', 0) < self.REFRESH_RETRY_SECONDS
            if not fresh and not cooling:
                try:
                    data, validators = self._download(info, conditional=cached is not None)
                    if data is not None:
                        # Validate before replacing the working regional snapshot.
                        result = self._lookup(data, request)
                        info.pop('etag', None)
                        info.pop('last_modified', None)
                    else:
                        data = cached
                    info.update({key: value for key, value in validators.items() if value})
                    info.update(checked_at=self.clock(), attempted_at=self.clock(), refresh_error='')
                    if data is not cached:
                        info['downloaded_at'] = self.clock()
                except ProviderFailure as error:
                    if cached is None or not error.temporary:
                        raise
                    info.update(attempted_at=self.clock(), refresh_error=error.reason)
                    self._write_info(info)
                    if result is not None:
                        return result
                    raise ProviderFailure('not_in_cached_snapshot') from error
                if data is not cached:
                    # One canonical provider cache; never extract arbitrary archive paths.
                    self.cache.parent.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile(dir=self.cache.parent, delete=False) as stream:
                        temporary = Path(stream.name)
                        stream.write(data)
                    temporary.replace(self.cache)
                self._write_info(info)
            if result is None:
                if not fresh and info.get('refresh_error'):
                    raise ProviderFailure('not_in_cached_snapshot')
                raise ProviderFailure("not_in_snapshot", False)
            return result
        except ProviderFailure:
            raise
        except (ValueError, KeyError, IndexError, OSError, CRSError, zipfile.BadZipFile, shapefile.ShapefileException) as error:
            raise ProviderFailure("invalid_dataset_response") from error
