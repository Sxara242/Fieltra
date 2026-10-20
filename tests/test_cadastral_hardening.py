"""Regression specifications for review defects, prepared for hosted execution.
SPDX-License-Identifier: AGPL-3.0-only
"""
import base64
from dataclasses import replace
from pathlib import Path
import sqlite3
import unittest
from uuid import uuid4

from app.country_extensions import IdentifierScope
from app.gis.cadastral_fingerprint import fingerprint, input_fingerprint
from app.gis.cadastral_migration import guarded_write, StorageRefused, verify_fence
from app.gis.cadastral_protocol import FieldCadastralLink, RecordVersion, CadastralParcel, ScopedParcelIdentity
from app.gis.cadastral_store import SourceSnapshot, RevisionConflict
from app.gis.cadastral_union import build_union
from tests import test_cadastral_migration as migration_specs
from tests import test_cadastral_store as repository_specs

FIXTURE=Path(__file__).resolve().parents[1]/'shared/fixtures/cadastral_fingerprints.tsv'


def vectors():
    result={}
    for line in FIXTURE.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        name, fields, expected=line.split('\t')
        result[name]=([None if f=='-' else base64.b64decode(f) for f in fields.split(',')],expected)
    return result


class HardeningTests(unittest.TestCase):
    setUp=repository_specs.RepositoryTests.setUp
    parcel=repository_specs.RepositoryTests.parcel

    def source(self,p):
        fields,_=vectors()['source-snapshot']
        return SourceSnapshot(str(uuid4()),p.parcel_uuid,fields[4].decode(),fields[5].decode(),fields[6].decode(),
            fields[1].decode(),fields[2],fields[3].decode(),fields[7].decode(),0,fields[8].decode(),False,None,fields[11].decode())

    def test_shared_hash_vectors_include_null_empty_utf8_and_raw_binary(self):
        data=vectors()
        self.assertEqual(4,len(data))
        for name,(fields,expected) in data.items():
            with self.subTest(name=name):self.assertEqual(expected,fingerprint(*fields))
        source=self.source(self.parcel())
        self.assertEqual(data['source-snapshot'][1],source.content_hash)
        self.assertNotEqual(fingerprint('x',None),fingerprint('x',''))

    def test_repository_capture_matches_shared_input_golden(self):
        raw='510000000001';scope=IdentifierScope('GR','kaek','hellenic-cadastre')
        parcel=self.repo.ensure_parcel(CadastralParcel(migration_specs.SCOPE,'20000000-0000-4000-8000-000000000001',
            ScopedParcelIdentity(scope,raw),raw,'gr-kaek-ascii12-v1',RecordVersion(1,0,0)))
        self.repo.link(FieldCadastralLink(self.field,parcel.parcel_uuid,RecordVersion(1,0,0)),0)
        source=replace(self.source(parcel),snapshot_uuid='30000000-0000-4000-8000-000000000001')
        self.repo.complete_lookup(source,self.repo.enqueue(parcel.parcel_uuid,'synthetic'))
        self.assertEqual(vectors()['input-snapshot'][1],self.repo.snapshot_inputs(self.field).fingerprint)

    def test_premature_commit_cursor_commit_and_executescript_cannot_persist_permit(self):
        for commit in (self.db.commit,lambda:self.db.execute('COMMIT'),
                       lambda:self.db.cursor().execute('COMMIT'),lambda:self.db.executescript('SELECT 1;')):
            with self.subTest(commit=commit):
                with self.assertRaises(sqlite3.DatabaseError):
                    with guarded_write(self.db,migration_specs.SCOPE,migration_specs.ACTIVATION):
                        self.db.execute('UPDATE fields SET area=99')
                        commit()
                self.assertEqual((0,),self.db.execute('SELECT permit FROM cadastral_storage_state').fetchone())
                self.assertEqual((3.25,),self.db.execute('SELECT area FROM fields').fetchone())

    def test_removed_fence_is_refused_before_permit(self):
        trigger=self.db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='fields' LIMIT 1").fetchone()[0]
        self.db.execute('DROP TRIGGER '+trigger)
        with self.assertRaises(StorageRefused):
            with guarded_write(self.db,migration_specs.SCOPE,migration_specs.ACTIVATION):
                self.fail('Missing fence must reject before callback')
        self.assertEqual((0,),self.db.execute('SELECT permit FROM cadastral_storage_state').fetchone())

    def test_stale_active_lookup_is_superseded_and_same_selection_is_idempotent(self):
        p=self.parcel();self.repo.link(FieldCadastralLink(self.field,p.parcel_uuid,RecordVersion(1,0,0)),0)
        first=self.repo.enqueue(p.parcel_uuid,'synthetic');source=self.source(p);self.repo.add_snapshot(source)
        fresh=self.repo.enqueue(p.parcel_uuid,'synthetic');self.assertNotEqual(first,fresh)
        self.assertFalse(self.repo.request_is_current(p.parcel_uuid,'synthetic',first))
        self.repo.complete_lookup(source,fresh)
        before=self.repo.snapshot_inputs(self.field)
        self.repo.select_snapshot(p.parcel_uuid,'synthetic',source.snapshot_uuid,before.inputs[0].selected_revision)
        self.assertEqual(before,self.repo.snapshot_inputs(self.field))

    def test_truncated_capture_with_copied_fingerprint_cannot_publish(self):
        for n in range(5):
            p=self.parcel(f'{n+1:012d}');self.repo.link(FieldCadastralLink(self.field,p.parcel_uuid,RecordVersion(1,0,0)),0)
            self.repo.complete_lookup(self.source(p),self.repo.enqueue(p.parcel_uuid,'synthetic'))
        captured=self.repo.snapshot_inputs(self.field)
        forged=replace(captured,inputs=captured.inputs[:3])
        result=build_union(forged)
        self.assertEqual('COMPLETE_DERIVED',result.state)  # Three valid inputs alone are geometrically complete.
        with self.assertRaises(RevisionConflict):self.repo.publish_overlay(forged,result)
        self.assertEqual((0,),self.db.execute('SELECT COUNT(*) FROM cadastral_field_overlays').fetchone())

    def test_sql_rejects_null_key_and_missing_field(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with guarded_write(self.db,migration_specs.SCOPE,migration_specs.ACTIVATION):
                self.db.execute("INSERT INTO field_identity VALUES(NULL,NULL,NULL,NULL)")
        with self.assertRaises(sqlite3.IntegrityError):
            with guarded_write(self.db,migration_specs.SCOPE,migration_specs.ACTIVATION):
                self.db.execute("INSERT INTO field_identity VALUES(?,999,'999',NULL)",(str(uuid4()),))
