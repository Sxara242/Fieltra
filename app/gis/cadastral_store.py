"""Isolated farm-scoped M:N persistence; never creates a business field.
SPDX-License-Identifier: AGPL-3.0-only
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import json
import sqlite3
import time
import threading
from uuid import uuid4

from ..country_extensions import CountryRegistry, IdentifierScope, ValidationState
from .cadastral_migration import canonical, digest, guarded_write, StorageRefused
from .cadastral_protocol import (CadastralParcel, CultivatedFieldRef, FieldCadastralLink,
                                RecordVersion, ScopedParcelIdentity, canonical_uuid)
from .cadastral_fingerprint import fingerprint, input_fingerprint


class RevisionConflict(ValueError):
    pass


@dataclass(frozen=True)
class SourceSnapshot:
    snapshot_uuid: str
    parcel_uuid: str
    provider_id: str
    dataset_id: str
    dataset_version: str
    geometry_json: str
    source_payload: bytes
    source_crs: str
    provenance_json: str
    acquired_at: int
    origin: str
    official_source_verified: bool = False
    snapshot_date: str | None = None
    source_date: str | None = None

    def __post_init__(self):
        canonical_uuid(self.snapshot_uuid)
        canonical_uuid(self.parcel_uuid)
        if not isinstance(self.source_payload, bytes) or type(self.acquired_at) is not int or self.acquired_at < 0:
            raise ValueError('Immutable source bytes and UTC milliseconds required')
        if type(self.official_source_verified) is not bool:
            raise ValueError('Explicit source verification flag required')

    @property
    def content_hash(self):
        return fingerprint('fieltra-cadastral-source-v1', self.geometry_json, self.source_payload, self.source_crs,
            self.provider_id, self.dataset_id, self.dataset_version, self.provenance_json,
            self.origin, '1' if self.official_source_verified else '0', self.snapshot_date, self.source_date)


@dataclass(frozen=True)
class OverlayInput:
    parcel_uuid: str
    link_revision: int
    provider_id: str
    selected_revision: int
    state: str
    snapshot_uuid: str | None
    content_hash: str | None
    geometry_json: str | None
    source_crs: str | None
    provenance_json: str | None


@dataclass(frozen=True)
class InputSnapshot:
    field: CultivatedFieldRef
    configuration_revision: int
    inputs: tuple[OverlayInput, ...]
    fingerprint: str

    def __post_init__(self):
        object.__setattr__(self, 'inputs', tuple(self.inputs))


class CadastralRepository:
    def __init__(self, db: sqlite3.Connection, scope: str, activation: str, clock=None):
        self.db, self.scope, self.activation = db, scope, activation
        self.clock = clock or (lambda: int(time.time() * 1000))
        self._writing = False
        self._owner_thread = threading.get_ident()
        if db.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
            raise StorageRefused('Foreign keys must be enabled by isolated-store owner')
        state = db.execute('SELECT farm_scope,activation_id FROM cadastral_storage_state WHERE id=1').fetchone()
        if state != (scope, activation):
            raise StorageRefused('Selected farm/store identity mismatch')

    @contextmanager
    def _write(self):
        # Only re-enter through this repository's own composite operation. Never
        # join an arbitrary caller transaction or share the connection in workers.
        if threading.get_ident() != self._owner_thread:
            raise StorageRefused('Repository belongs to its connection-owning thread')
        if self._writing:
            yield
            return
        with guarded_write(self.db, self.scope, self.activation):
            self._writing = True
            try:
                yield
            finally:
                self._writing = False

    def _field(self, field):
        if field.farm_scope != self.scope:
            raise StorageRefused('Cross-farm association refused')
        if not self.db.execute('SELECT 1 FROM field_identity i JOIN fields f ON f.id=i.local_field_id '
                               'WHERE i.field_uuid=? AND i.deleted_at IS NULL',
                               (field.field_uuid,)).fetchone():
            raise ValueError('Existing cultivated identity required')

    def _invalidate(self, parcel):
        self.db.execute("UPDATE cadastral_field_overlays SET status='STALE' WHERE field_uuid IN "
                        '(SELECT field_uuid FROM field_cadastral_links WHERE parcel_uuid=?)', (parcel,))

    @staticmethod
    def _parcel(row, scope):
        return CadastralParcel(scope, row[0], ScopedParcelIdentity(IdentifierScope(*row[1:5]), row[5]),
                               row[6], row[7], RecordVersion(row[9], row[10], row[11], row[12]))

    def find_parcel(self, identity):
        s = identity.scope
        row = self.db.execute('SELECT * FROM cadastral_parcels WHERE country_code=? AND system_id=? '
                              'AND authority_id=? AND jurisdiction_key=? AND identifier_key=?',
                              (s.country_code, s.system_id, s.authority_id, s.jurisdiction_key,
                               identity.comparison_key)).fetchone()
        return self._parcel(row, self.scope) if row else None

    def ensure_parcel(self, candidate):
        if candidate.farm_scope != self.scope or candidate.version.deleted_at is not None:
            raise ValueError('Active same-farm parcel required')
        validation = CountryRegistry().get(candidate.identity.scope.country_code).validate(
            candidate.identifier_raw, candidate.identity.scope)
        if (validation.state != ValidationState.VALID or validation.comparison_key != candidate.identity.comparison_key
                or validation.validator_version != candidate.validator_version):
            raise ValueError('Unsupported/unverified identifier')
        with self._write():
            old = self.find_parcel(candidate.identity)
            if old and old.version.deleted_at is not None:
                raise RevisionConflict('Retired scoped identity requires explicit recovery')
            parcel = old or candidate
            alias = self.db.execute('SELECT parcel_uuid FROM cadastral_parcel_aliases WHERE alias_uuid=?',
                                    (candidate.parcel_uuid,)).fetchone()
            if alias and alias[0] != parcel.parcel_uuid:
                raise RevisionConflict('Parcel UUID maps to another scoped identity')
            if not old:
                s, v = candidate.identity.scope, candidate.version
                self.db.execute('INSERT INTO cadastral_parcels VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (candidate.parcel_uuid, s.country_code, s.system_id, s.authority_id, s.jurisdiction_key,
                     candidate.identity.comparison_key, candidate.identifier_raw, candidate.validator_version,
                     'valid', v.revision, v.created_at, v.updated_at, v.deleted_at))
            self.db.execute('INSERT OR IGNORE INTO cadastral_parcel_aliases VALUES(?,?)',
                            (candidate.parcel_uuid, parcel.parcel_uuid))
            self.db.execute('INSERT OR IGNORE INTO cadastral_identifier_spellings VALUES(?,?,?)',
                            (parcel.parcel_uuid, candidate.identifier_raw, 'validated'))
            return parcel

    def _link_row(self, row):
        return FieldCadastralLink(CultivatedFieldRef(self.scope, row[0]), row[1],
                                 RecordVersion(row[4], row[5], row[6], row[7]), bool(row[2]), bool(row[3]))

    def link(self, association, expected_revision):
        self._field(association.field)
        if association.version.deleted_at is not None:
            raise ValueError('Use unlink for tombstones')
        with self._write():
            self._field(association.field)
            key = (association.field.field_uuid, association.parcel_uuid)
            row = self.db.execute('SELECT * FROM field_cadastral_links WHERE field_uuid=? AND parcel_uuid=?', key).fetchone()
            old = self._link_row(row) if row else None
            if old and old.legacy_slot and not association.legacy_slot:
                raise RevisionConflict('Primary slot change requires later confirmed compatibility flow')
            if old and old.version.deleted_at is None and (old.legacy_slot, old.manual_link) == (
                    association.legacy_slot, association.manual_link) and expected_revision in (0, old.version.revision):
                return old
            if (old.version.revision if old else 0) != expected_revision:
                raise RevisionConflict('Stale link revision')
            if association.legacy_slot:
                raw = self.db.execute('SELECT identifier_raw FROM cadastral_parcels WHERE parcel_uuid=?',
                                      (association.parcel_uuid,)).fetchone()
                legacy = self.db.execute('SELECT f.kaek FROM fields f JOIN field_identity i ON i.local_field_id=f.id '
                                         'WHERE i.field_uuid=?', (key[0],)).fetchone()
                if not raw or raw != legacy:
                    raise RevisionConflict('Legacy projection requires exact unchanged primary string')
            now = max(self.clock(), old.version.updated_at if old else 0)
            created = old.version.created_at if old else now
            self.db.execute('INSERT INTO field_cadastral_links VALUES(?,?,?,?,?,?,?,NULL) '
                'ON CONFLICT(field_uuid,parcel_uuid) DO UPDATE SET legacy_slot=excluded.legacy_slot, '
                'manual_link=excluded.manual_link,revision=excluded.revision,updated_at=excluded.updated_at,deleted_at=NULL',
                (*key, int(association.legacy_slot), int(association.manual_link), expected_revision + 1, created, now))
            self._invalidate(association.parcel_uuid)
            return self._link_row(self.db.execute('SELECT * FROM field_cadastral_links WHERE field_uuid=? AND parcel_uuid=?', key).fetchone())

    def unlink(self, field, parcel_uuid, expected_revision):
        self._field(field)
        with self._write():
            self._field(field)
            key = (field.field_uuid, parcel_uuid)
            row = self.db.execute('SELECT * FROM field_cadastral_links WHERE field_uuid=? AND parcel_uuid=?', key).fetchone()
            if not row or row[4] != expected_revision:
                raise RevisionConflict('Stale unlink')
            old = self._link_row(row)
            if old.legacy_slot and old.version.deleted_at is None:
                raise RevisionConflict('Primary slot removal requires later confirmed compatibility flow')
            if old.version.deleted_at is not None:
                return old
            now = max(self.clock(), old.version.updated_at)
            self.db.execute('UPDATE field_cadastral_links SET revision=revision+1,updated_at=?,deleted_at=? '
                            'WHERE field_uuid=? AND parcel_uuid=?', (now, now, *key))
            self._invalidate(parcel_uuid)
            if not self.db.execute('SELECT 1 FROM field_cadastral_links WHERE parcel_uuid=? AND deleted_at IS NULL', (parcel_uuid,)).fetchone():
                self.db.execute("UPDATE cadastral_lookup_jobs SET status='cancelled' WHERE parcel_uuid=? AND status IN('queued','running')", (parcel_uuid,))
            return self._link_row(self.db.execute('SELECT * FROM field_cadastral_links WHERE field_uuid=? AND parcel_uuid=?', key).fetchone())

    def list_links(self, field, *, include_deleted=False):
        self._field(field)
        return tuple(self._link_row(r) for r in self.db.execute('SELECT * FROM field_cadastral_links WHERE field_uuid=?' +
            ('' if include_deleted else ' AND deleted_at IS NULL') + ' ORDER BY parcel_uuid', (field.field_uuid,)))

    def linked_fields(self, parcel_uuid):
        return tuple(CultivatedFieldRef(self.scope, r[0]) for r in self.db.execute(
            'SELECT field_uuid FROM field_cadastral_links WHERE parcel_uuid=? AND deleted_at IS NULL ORDER BY field_uuid', (parcel_uuid,)))

    def add_snapshot(self, snapshot: SourceSnapshot):
        canonical_uuid(snapshot.snapshot_uuid)
        canonical_uuid(snapshot.parcel_uuid)
        if not all((snapshot.provider_id, snapshot.dataset_id, snapshot.source_crs, snapshot.origin)):
            raise ValueError('Source identity/CRS/origin required')
        if len(snapshot.geometry_json.encode()) > 16 * 1024 * 1024 or len(snapshot.source_payload) > 16 * 1024 * 1024:
            raise ValueError('Snapshot too large')
        json.loads(snapshot.geometry_json)
        provenance = json.loads(snapshot.provenance_json)
        if not isinstance(provenance, dict) or not all(isinstance(provenance.get(k), str) and
                0 < len(provenance[k]) <= 4096 for k in ('source_url', 'attribution', 'terms_url')):
            raise ValueError('Source provenance required')
        if snapshot.official_source_verified and snapshot.origin != 'verified_provider':
            raise ValueError('Imported data cannot acquire official provenance')
        with self._write():
            old = self.db.execute('SELECT snapshot_uuid FROM cadastral_snapshots WHERE parcel_uuid=? AND content_hash=?',
                                   (snapshot.parcel_uuid, snapshot.content_hash)).fetchone()
            if old:
                return old[0]
            self.db.execute('INSERT INTO cadastral_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (snapshot.snapshot_uuid, snapshot.parcel_uuid, snapshot.provider_id, snapshot.dataset_id,
                 snapshot.dataset_version, snapshot.geometry_json, snapshot.source_payload, snapshot.source_crs,
                 snapshot.content_hash, digest(snapshot.geometry_json.encode()), snapshot.provenance_json,
                 snapshot.snapshot_date, snapshot.source_date, snapshot.acquired_at, snapshot.origin,
                 int(snapshot.official_source_verified)))
            # A newly competing source cannot leave an old result looking complete.
            self.db.execute("INSERT INTO cadastral_parcel_state VALUES(?,?,NULL,1,'PENDING',NULL) "
                "ON CONFLICT(parcel_uuid,provider_id) DO UPDATE SET selected_snapshot_uuid=NULL, "
                "selected_revision=selected_revision+1,state='CONFLICT'", (snapshot.parcel_uuid, snapshot.provider_id))
            self._invalidate(snapshot.parcel_uuid)
            return snapshot.snapshot_uuid

    def select_snapshot(self, parcel, provider, snapshot, expected_revision):
        with self._write():
            source = self.db.execute('SELECT provider_id FROM cadastral_snapshots WHERE parcel_uuid=? AND snapshot_uuid=?',
                                     (parcel, snapshot)).fetchone()
            if source != (provider,):
                raise ValueError('Snapshot/provider mismatch')
            old = self.db.execute('SELECT selected_snapshot_uuid,selected_revision,state FROM cadastral_parcel_state WHERE parcel_uuid=? AND provider_id=?', (parcel, provider)).fetchone()
            if old and old == (snapshot, expected_revision, 'READY'):
                return
            changed = self.db.execute("UPDATE cadastral_parcel_state SET selected_snapshot_uuid=?,selected_revision=selected_revision+1,"
                "state='READY',last_error=NULL WHERE parcel_uuid=? AND provider_id=? AND selected_revision=?",
                (snapshot, parcel, provider, expected_revision)).rowcount
            if changed != 1:
                raise RevisionConflict('Stale selected source')
            self._invalidate(parcel)

    def enqueue(self, parcel, provider):
        with self._write():
            if not self.linked_fields(parcel):
                raise RevisionConflict('No active association')
            revision = self.db.execute('SELECT COALESCE(MAX(selected_revision),0) FROM cadastral_parcel_state WHERE parcel_uuid=? AND provider_id=?', (parcel, provider)).fetchone()[0]
            old = self.db.execute("SELECT request_uuid,requested_revision FROM cadastral_lookup_jobs WHERE parcel_uuid=? AND provider_id=? AND status IN('queued','running')", (parcel, provider)).fetchone()
            if old and old[1] == revision:
                return old[0]
            if old:
                self.db.execute("UPDATE cadastral_lookup_jobs SET status='superseded' WHERE request_uuid=?", (old[0],))
            request = str(uuid4())
            self.db.execute("INSERT INTO cadastral_lookup_jobs(job_uuid,parcel_uuid,provider_id,requested_revision,request_uuid,status) VALUES(?,?,?,?,?,'queued')",
                            (str(uuid4()), parcel, provider, revision, request))
            return request

    def request_is_current(self, parcel, provider, request):
        row = self.db.execute("SELECT requested_revision FROM cadastral_lookup_jobs WHERE parcel_uuid=? AND provider_id=? AND request_uuid=? AND status IN('queued','running')", (parcel, provider, request)).fetchone()
        revision = self.db.execute('SELECT COALESCE(MAX(selected_revision),0) FROM cadastral_parcel_state WHERE parcel_uuid=? AND provider_id=?', (parcel, provider)).fetchone()[0]
        return bool(row and row[0] == revision and self.linked_fields(parcel))

    def complete_lookup(self, snapshot, request):
        """One transaction: validate token, retain source, select only unambiguous
        initial source, finish job. Competing sources stay CONFLICT, never LWW.
        """
        with self._write():
            if not self.request_is_current(snapshot.parcel_uuid, snapshot.provider_id, request):
                raise RevisionConflict('Stale asynchronous lookup')
            selected = self.add_snapshot(snapshot)
            state = self.db.execute('SELECT selected_revision,state FROM cadastral_parcel_state WHERE parcel_uuid=? AND provider_id=?',
                                     (snapshot.parcel_uuid, snapshot.provider_id)).fetchone()
            if state[1] == 'PENDING':
                self.select_snapshot(snapshot.parcel_uuid, snapshot.provider_id, selected, state[0])
            self.db.execute("UPDATE cadastral_lookup_jobs SET status='done',result_hash=? WHERE request_uuid=?", (snapshot.content_hash, request))
            return selected

    def snapshot_inputs(self, field):
        if threading.get_ident() != self._owner_thread:
            raise StorageRefused('Capture inputs on the connection-owning thread')
        self._field(field)
        own = not self.db.in_transaction
        if own:
            self.db.execute('BEGIN')
        try:
            config = self.db.execute('SELECT revision FROM farm_configuration WHERE id=1').fetchone()[0]
            inputs = []
            for link in self.list_links(field):
                states = self.db.execute('SELECT provider_id,selected_revision,state,selected_snapshot_uuid '
                    'FROM cadastral_parcel_state WHERE parcel_uuid=? ORDER BY provider_id', (link.parcel_uuid,)).fetchall()
                if len(states) != 1:
                    inputs.append(OverlayInput(link.parcel_uuid, link.version.revision, '', 0,
                                               'CONFLICT' if states else 'PENDING', None, None, None, None, None))
                    continue
                provider, revision, state, selected = states[0]
                source = self.db.execute('SELECT content_hash,original_geometry_json,source_crs,provenance_json '
                    'FROM cadastral_snapshots WHERE parcel_uuid=? AND snapshot_uuid=?', (link.parcel_uuid, selected)).fetchone()
                inputs.append(OverlayInput(link.parcel_uuid, link.version.revision, provider, revision,
                                           state, selected, *(source or (None,) * 4)))
            return InputSnapshot(field, config, tuple(inputs), input_fingerprint(self.scope, field.field_uuid, config, inputs))
        finally:
            if own:
                self.db.rollback()

    def publish_overlay(self, inputs, result):
        with self._write():
            if (result.fingerprint != inputs.fingerprint or self.snapshot_inputs(inputs.field) != inputs
                    or result.required_count != len(inputs.inputs)):
                raise RevisionConflict('Stale union worker result')
            self.db.execute('INSERT INTO cadastral_field_overlays VALUES(?,?,?,?,?,?,?,?,?,?,?) '
                'ON CONFLICT(field_uuid) DO UPDATE SET input_fingerprint=excluded.input_fingerprint,engine=excluded.engine, '
                'union_crs=excluded.union_crs,precision_policy=excluded.precision_policy,geometry_json=excluded.geometry_json, '
                'status=excluded.status,required_count=excluded.required_count,usable_count=excluded.usable_count, '
                'diagnostic=excluded.diagnostic,generated_at=excluded.generated_at',
                (inputs.field.field_uuid, inputs.fingerprint, result.engine, 'EPSG:2100', 'unsnapped-floating',
                 result.geometry_json, result.state, result.required_count, result.usable_count, result.diagnostic, self.clock()))
