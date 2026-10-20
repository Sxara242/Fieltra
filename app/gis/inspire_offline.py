"""Explicit Atom discovery and content-addressed offline vector datasets.

No endpoint is guessed, no feed is fetched at import, no WMS bulk acquisition.
SPDX-License-Identifier: AGPL-3.0-only
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import io
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unicodedata
from urllib.parse import urljoin
from urllib.request import build_opener, Request
import zipfile

from .provider_io import safe_xml, public_url, _NoRedirect
from .cadastral_migration import canonical, digest
from .cadastral_fingerprint import fingerprint

ATOM = '{http://www.w3.org/2005/Atom}'
XML_BASE = '{http://www.w3.org/XML/1998/namespace}base'
DCT = '{http://purl.org/dc/terms/}'
GEORSS = '{http://www.georss.org/georss}'
INSPIRE = '{http://inspire.ec.europa.eu/schemas/inspire_dls/1.0}'


@dataclass(frozen=True)
class FeedDescriptor:
    source_url: str
    attribution: str
    terms_reference: str

    def __post_init__(self):
        public_url(self.source_url)
        if not self.attribution or not self.terms_reference:
            raise ValueError('Explicit feed provenance required')


@dataclass(frozen=True)
class DownloadLink:
    url: str
    media_type: str
    length: int | None
    expected_sha256: str | None = None

    def __post_init__(self):
        import re
        public_url(self.url)
        if self.length is not None and (type(self.length) is not int or self.length < 0):
            raise ValueError('Nonnegative dataset length required')
        if self.expected_sha256 is not None and not re.fullmatch('[0-9a-f]{64}', self.expected_sha256):
            raise ValueError('Explicit reviewed SHA256 required')


@dataclass(frozen=True)
class Dataset:
    identifier: str
    title: str
    version: str | None
    updated: str | None
    spatial_coverage: str | None
    download_links: tuple[DownloadLink, ...]
    feed_url: str
    attribution: str
    rights: str
    terms_reference: str
    retrieved_at: int
    spatial_identifiers: tuple[tuple[str, str], ...] = ()
    feed_hash: str = ''


def _text(parent, tag):
    child = parent.find(tag)
    return ''.join(child.itertext()).strip() if child is not None else ''


def parse_feed(data: bytes, descriptor: FeedDescriptor, retrieved_at: int) -> tuple[Dataset, ...]:
    root = safe_xml(data)
    if root.tag != ATOM+'feed' or type(retrieved_at) is not int or retrieved_at < 0:
        raise ValueError('Atom feed and retrieval timestamp required')
    entries = root.findall(ATOM+'entry')
    if len(entries) > 512:
        raise ValueError('Feed entry budget exceeded')
    feed_base = public_url(urljoin(descriptor.source_url, root.attrib.get(XML_BASE, '')))
    rights = _text(root, ATOM+'rights')
    feed_terms = descriptor.terms_reference
    for link in root.findall(ATOM+'link'):
        if link.attrib.get('rel') == 'license':
            if not link.attrib.get('href'):
                raise ValueError('Feed license has no URL')
            feed_terms = public_url(urljoin(public_url(urljoin(feed_base, link.attrib.get(XML_BASE, ''))), link.attrib['href']))
    result, seen = [], set()
    for entry in entries:
        identifier = _text(entry, ATOM+'id')
        if not identifier or identifier in seen:
            raise ValueError('Missing/duplicate dataset identifier')
        seen.add(identifier)
        base = public_url(urljoin(feed_base, entry.attrib.get(XML_BASE, '')))
        stamp = _text(entry, ATOM+'updated')
        if stamp:
            parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                raise ValueError('Dataset date requires timezone')
        links = []
        terms = feed_terms
        for link in entry.findall(ATOM+'link'):
            rel, media = link.attrib.get('rel', 'alternate'), link.attrib.get('type', '')
            if rel not in ('enclosure', 'alternate', 'license'):
                continue
            href = link.attrib.get('href')
            if not href:
                raise ValueError('Dataset link has no URL')
            link_base = public_url(urljoin(base, link.attrib.get(XML_BASE, '')))
            url = public_url(urljoin(link_base, href))
            if rel == 'license':
                terms = url
                continue
            if rel == 'alternate' and media in ('application/atom+xml', 'text/html', ''):
                continue  # Discovery/viewer is not a dataset download.
            length = link.attrib.get('length')
            if length is not None and (not length.isascii() or not length.isdecimal() or len(length) > 18):
                raise ValueError('Invalid declared dataset size')
            links.append(DownloadLink(url, media, int(length) if length is not None else None))
        if len(links) > 32:
            raise ValueError('Dataset link budget exceeded')
        coverage = _text(entry, GEORSS+'box') or None
        if coverage:
            import math
            box = [float(v) for v in coverage.split()]
            if len(box) != 4 or not all(math.isfinite(v) for v in box) or not (
                    -90 <= box[0] < box[2] <= 90 and -180 <= box[1] < box[3] <= 180):
                raise ValueError('Invalid GeoRSS lat/lon coverage')
        codes = [e.text or '' for e in entry.iter(INSPIRE+'spatial_dataset_identifier_code')]
        namespaces = [e.text or '' for e in entry.iter(INSPIRE+'spatial_dataset_identifier_namespace')]
        if len(codes) != len(namespaces):
            raise ValueError('Ambiguous INSPIRE spatial identifiers')
        result.append(Dataset(identifier, _text(entry, ATOM+'title'), _text(entry, DCT+'hasVersion') or None,
            stamp or None, coverage, tuple(links), descriptor.source_url, descriptor.attribution,
            _text(entry, ATOM+'rights') or rights, terms, retrieved_at, tuple(zip(codes, namespaces)), digest(data)))
    return tuple(result)


def _zip_member_key(entry):
    # ZipInfo.filename may have lost NUL suffixes or Windows separators. Never
    # use that normalization as proof that the decoded central name was safe.
    original, name = entry.orig_filename, entry.filename
    for candidate in (original, name):
        parts = candidate.split('/')
        if candidate.endswith('/'):
            parts = parts[:-1]  # One explicit directory marker is permitted.
        if (not candidate or candidate.startswith('/') or '\\' in candidate
                or ':' in candidate or '\x00' in candidate or not parts
                or any(not p or p in ('.', '..') or p.endswith((' ', '.')) for p in parts)):
            raise ValueError('Unsafe ZIP member name')
    if original != name:
        raise ValueError('ZIP member name was normalized')
    # Comparison only, never repair/rename archive members. Include directory/
    # file aliases, Unicode canonical equivalence and the existing case folding.
    return unicodedata.normalize('NFC', name.rstrip('/')).casefold()


def inspect_zip(path, cancelled=lambda: False, *, max_total=64*1024*1024):
    """Validate every entry, without extracting any path or trusting suffix alone."""
    data = io.BytesIO(path) if isinstance(path, bytes) else path
    if (len(path) if isinstance(path, bytes) else Path(path).stat().st_size) > 32*1024*1024:
        raise ValueError('ZIP compressed budget exceeded')
    total, names, member_keys = 0, set(), set()
    with zipfile.ZipFile(data) as archive:
        entries = archive.infolist()
        if not entries or len(entries) > 256:
            raise ValueError('ZIP entry budget exceeded')
        for entry in entries:
            key = _zip_member_key(entry)
            if (key in member_keys
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000 or entry.flag_bits & 1):
                raise ValueError('Unsafe ZIP member')
            member_keys.add(key)
            names.add(entry.filename.casefold())
            total += entry.file_size
            if entry.file_size > max_total or total > max_total or entry.file_size > max(1, entry.compress_size)*1000:
                raise ValueError('ZIP expansion budget exceeded')
            consumed = 0
            # open(ZipInfo) checks the decoded local-header name against
            # orig_filename; do not look up by a potentially colliding string.
            with archive.open(entry) as stream:
                while chunk := stream.read(65536):
                    if cancelled():
                        raise InterruptedError('Cancelled')
                    consumed += len(chunk)
                    if consumed > entry.file_size:
                        raise ValueError('ZIP length mismatch')
            if consumed != entry.file_size:
                raise ValueError('Truncated ZIP member')
    return tuple(sorted(names))


def resume_is_valid(*, status, content_range, strong_etag, previous_etag, offset, expected_total):
    """Protocol predicate only; downloader always starts fresh, never appends."""
    import re
    match = re.fullmatch(r'bytes ([0-9]+)-([0-9]+)/([0-9]+)', content_range or '')
    return bool(status == 206 and match and strong_etag and not strong_etag.startswith('W/')
        and strong_etag == previous_etag and int(match[1]) == offset
        and offset <= int(match[2]) < expected_total and int(match[3]) == expected_total)


def _open_download(url):
    public_url(url)
    return build_opener(_NoRedirect()).open(Request(url, headers={'Accept-Encoding':'identity', 'User-Agent':'Fieltra/1.0.1'}), timeout=15)


class OfflineDatasetStore:
    """Explicit root, immutable SHA256.zip files and transactional local index.

    File publication and index commit are recoverable separate steps. A crash can
    leave a verified orphan blob; it cannot make a partial file AVAILABLE. No
    automatic orphan cleanup or traversal outside the selected store is provided.
    """
    def __init__(self, root):
        if Path(root).is_symlink():
            raise ValueError('Offline root cannot be a symbolic link')
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        index = self.root/'dataset-index.sqlite'
        if index.is_symlink():
            raise ValueError('Offline index cannot be a symbolic link')
        self.db = sqlite3.connect(index)
        foreign = self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='offline_datasets'").fetchone()
        if foreign:
            self.db.close()
            raise ValueError('Dedicated offline index required')
        self.db.execute('CREATE TABLE IF NOT EXISTS offline_datasets(dataset_key TEXT PRIMARY KEY, identifier TEXT NOT NULL, '
            'version TEXT, sha256 TEXT NOT NULL, byte_count INTEGER NOT NULL, provenance_json TEXT NOT NULL, stored_at INTEGER NOT NULL)')
        self.db.commit()

    def close(self):
        self.db.close()

    @staticmethod
    def key(dataset, link):
        return fingerprint('fieltra-offline-dataset-v1',dataset.feed_url,dataset.identifier,
                           dataset.version,dataset.updated,link.url,link.expected_sha256)

    def available(self, dataset, link):
        row = self.db.execute('SELECT sha256,byte_count FROM offline_datasets WHERE dataset_key=?', (self.key(dataset,link),)).fetchone()
        if not row:
            return 'MISSING', None
        if len(row[0]) != 64 or any(c not in '0123456789abcdef' for c in row[0]):
            raise ValueError('Corrupt offline index')
        path = self.root/(row[0]+'.zip')
        if path.is_symlink() or link.expected_sha256 is not None and row[0] != link.expected_sha256:
            return 'CORRUPT', None
        if not path.is_file():
            return 'MISSING', None
        if path.stat().st_size != row[1] or path.stat().st_size > 32*1024*1024 or path.is_symlink():
            return 'CORRUPT', None
        if digest(path.read_bytes()) != row[0]:
            return 'CORRUPT', None
        return 'AVAILABLE', path

    def download(self, dataset, link, *, initiated_by_user: bool, cancelled=lambda: False,
                 open_stream=_open_download, validate_dataset=None):
        if not initiated_by_user or link not in dataset.download_links:
            raise PermissionError('Explicit user-selected dataset/link required')
        public_url(link.url)
        if link.media_type not in ('application/zip', 'application/x-zip-compressed'):
            raise ValueError('Unsupported offline dataset format')
        if link.length is not None and link.length > 32*1024*1024:
            raise ValueError('Dataset exceeds download budget')
        state, cached = self.available(dataset, link)
        if state == 'AVAILABLE':
            return cached
        if state == 'CORRUPT':
            raise ValueError('Corrupt offline data requires explicit recovery')
        if cancelled():
            raise InterruptedError('Cancelled')
        deadline = time.monotonic()+60
        temporary = None
        try:
            with open_stream(link.url) as response, tempfile.NamedTemporaryFile(dir=self.root, suffix='.part', delete=False) as output:
                temporary = Path(output.name)
                if response.status != 200 or response.geturl() != link.url or response.headers.get('Content-Encoding','identity') != 'identity':
                    raise ValueError('Unexpected download response; resume/redirect not approved')
                length = response.headers.get('Content-Length')
                if length is not None and (not length.isdecimal() or int(length) > 32*1024*1024):
                    raise ValueError('Download length exceeds budget')
                count, checksum = 0, hashlib.sha256()
                while chunk := response.read(65536):
                    if cancelled():
                        raise InterruptedError('Cancelled')
                    if time.monotonic() > deadline:
                        raise TimeoutError('Download time budget')
                    count += len(chunk)
                    if count > 32*1024*1024:
                        raise ValueError('Download exceeds budget')
                    output.write(chunk)
                    checksum.update(chunk)
                output.flush()
                os.fsync(output.fileno())
                if length is not None and count != int(length) or link.length is not None and count != link.length:
                    raise ValueError('Truncated/mismatched dataset download')
            inspect_zip(temporary, cancelled)
            if validate_dataset:
                validate_dataset(temporary)  # Optional B02.4 verified-format reader.
            if cancelled():
                raise InterruptedError('Cancelled')
            fingerprint = checksum.hexdigest()
            if link.expected_sha256 is not None and fingerprint != link.expected_sha256:
                raise ValueError('Dataset checksum mismatch')
            target = self.root/(fingerprint+'.zip')
            try:
                os.link(temporary, target)  # Atomic exclusive publication, never overwrite.
            except FileExistsError:
                if target.is_symlink() or target.stat().st_size != count or digest(target.read_bytes()) != fingerprint:
                    raise ValueError('Existing content-addressed file is corrupt')
            metadata = dict(dataset=dict(vars(dataset)), selected_link=dict(vars(link)), sha256=fingerprint,
                            source_url=link.url, retrieval_timestamp=int(time.time()*1000),
                            format='application/zip', category='offline-vector-candidate',
                            official_source_verified=False)
            # dataclass nested links are converted explicitly, retaining every source.
            metadata['dataset']['download_links'] = [vars(l) for l in dataset.download_links]
            with self.db:
                self.db.execute('INSERT INTO offline_datasets VALUES(?,?,?,?,?,?,?) ON CONFLICT(dataset_key) '
                    'DO UPDATE SET sha256=excluded.sha256,byte_count=excluded.byte_count,provenance_json=excluded.provenance_json,stored_at=excluded.stored_at',
                    (self.key(dataset,link),dataset.identifier,dataset.version,fingerprint,count,canonical(metadata),int(time.time()*1000)))
            return target
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)  # Only this operation's own temporary file.
