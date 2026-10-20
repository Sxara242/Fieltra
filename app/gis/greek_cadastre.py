"""Local regional archive adapter. No network or existing cache mutation.
SPDX-License-Identifier: AGPL-3.0-only
"""
from dataclasses import dataclass, replace
import json
import time
from uuid import uuid4

from ..country_extensions import GreekIdentifierAdapter, ValidationState
from .cadastral_migration import canonical, digest
from .cadastral_store import SourceSnapshot
from .kaek_provider import NorthAegeanProvider


@dataclass(frozen=True)
class RegionalResult:
    identity: object
    geometry_json: str | None
    archive_hash: str
    source_date: str
    status: str
    provenance_json: str = ''


@dataclass(frozen=True)
class OfflineRegionalResult:
    status: str
    parcels: tuple[RegionalResult, ...] = ()


class GreekCadastreDataset:
    """Reuse the verified Windows pyshp/PRJ/CPG parser once for all identifiers.

    Local bytes are not evidence of official acquisition. Verification remains a
    separate caller decision backed by retained acquisition metadata. No cache
    file is opened implicitly and no five per-field fetch calls are made.
    """
    def __init__(self, provider: NorthAegeanProvider):
        self.provider = provider

    def read_many(self, archive: bytes, identities, cancelled=lambda: False):
        from .inspire_offline import inspect_zip
        inspect_zip(archive, cancelled, max_total=self.provider.MAX_UNCOMPRESSED)
        identities = tuple(identities)
        if not 1 <= len(identities) <= 128:
            raise ValueError('Bounded nonempty parcel request required')
        requested = {}
        for identity in identities:
            value = GreekIdentifierAdapter().validate(identity.comparison_key, identity.scope)
            if value.state != ValidationState.VALID or identity.scope.jurisdiction_key or not self.provider.supports(value.raw):
                raise ValueError('Unsupported Greek regional identity')
            requested[value.raw] = identity
        found = {}
        vertices, geometry_bytes = 0, 0
        archive_hash = digest(archive)
        with self.provider._reader(archive) as reader:
            if reader.numRecords > 500_000:
                raise ValueError('Dataset record budget exceeded')
            for row in reader.iterRecords(fields=['KAEK', 'bLfSpnVr']):
                if cancelled():
                    raise InterruptedError('Cancelled')
                if row['KAEK'] not in requested:
                    continue
                if row['KAEK'] in found:
                    raise ValueError('Conflicting duplicate dataset identifier')
                geometry = reader.shape(row.oid).__geo_interface__
                # Existing strict geometry parser, including its per-parcel limit.
                from .geometry import validate
                checked = validate(json.loads(json.dumps(geometry)))
                vertices += sum(len(p.exterior.coords) + sum(len(r.coords) for r in p.interiors)
                    for p in ((checked,) if checked.geom_type == 'Polygon' else checked.geoms))
                encoded = canonical(geometry)
                geometry_bytes += len(encoded.encode('utf-8'))
                if vertices > 100_000 or geometry_bytes > 16*1024*1024:
                    raise ValueError('Selected regional geometry budget exceeded')
                from datetime import date
                stamp = row['bLfSpnVr']
                try:
                    date.fromisoformat(stamp)
                except (ValueError, TypeError):
                    stamp = ''
                found[row['KAEK']] = RegionalResult(requested[row['KAEK']], encoded, archive_hash, stamp, 'FOUND')
        return tuple(found.get(i.comparison_key, RegionalResult(i, None, archive_hash, '', 'NOT_IN_SNAPSHOT')) for i in identities)

    def read_offline(self, store, dataset, link, identities, cancelled=lambda: False):
        """Resolve one indexed immutable ZIP; never acquires a missing dataset."""
        state, path = store.available(dataset, link)
        if state != 'AVAILABLE':
            return OfflineRegionalResult(state)
        metadata = canonical(dict(source_url=link.url, feed_url=dataset.feed_url,
            terms_url=dataset.terms_reference, attribution=dataset.attribution,
            rights=dataset.rights, dataset_version=dataset.version,
            acquisition='explicit_offline_store', official_source_verified=False))
        parcels = self.read_many(path.read_bytes(), identities, cancelled)
        return OfflineRegionalResult('AVAILABLE', tuple(replace(p, provenance_json=metadata) for p in parcels))

    def source_snapshot(self, parcel_uuid, result, *, dataset_version, acquired_at=None):
        if result.status != 'FOUND':
            raise ValueError('Missing source cannot become a snapshot')
        metadata = json.loads(result.provenance_json) if result.provenance_json else dict(
            source_url='urn:sha256:'+result.archive_hash, terms_url='Unverified local archive terms',
            attribution='Local regional-format archive; origin unverified', acquisition='caller_supplied_local_archive')
        metadata.update(archive_hash=result.archive_hash, coverage='Regional adapter only; prefixes 33,43,51',
                        provider_reference_url=self.provider.source_url, provider_terms_reference=self.provider.terms_url)
        provenance = canonical(metadata)
        return SourceSnapshot(str(uuid4()), parcel_uuid, self.provider.identity, self.provider.source_url,
            dataset_version, result.geometry_json, result.geometry_json.encode(), 'EPSG:2100', provenance,
            int(time.time()*1000) if acquired_at is None else acquired_at, 'local_dataset', False,
            source_date=result.source_date or None)
