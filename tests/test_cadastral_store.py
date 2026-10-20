"""Real SQLite M:N test source using synthetic memory fixtures only.
SPDX-License-Identifier: AGPL-3.0-only
"""
from dataclasses import replace
import json
import unittest
from uuid import uuid4
from app.country_extensions import IdentifierScope
from app.gis.cadastral_protocol import *
from app.gis.cadastral_store import CadastralRepository, SourceSnapshot, RevisionConflict
from app.gis.cadastral_migration import guarded_write, install_fence
from tests.test_cadastral_migration import isolated, SCOPE, ACTIVATION, FIELD


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.db = isolated()
        self.addCleanup(self.db.close)
        self.repo = CadastralRepository(self.db, SCOPE, ACTIVATION, lambda: 100)
        self.field = CultivatedFieldRef(SCOPE, FIELD)

    def parcel(self, raw='000000000001', jurisdiction=''):
        return self.repo.ensure_parcel(CadastralParcel(SCOPE, str(uuid4()), ScopedParcelIdentity(
            IdentifierScope('GR', 'kaek', 'hellenic-cadastre', jurisdiction), raw), raw,
            'gr-kaek-ascii12-v1', RecordVersion(1, 0, 0)))

    def test_five_links_inverse_sharing_no_business_change(self):
        before = self.db.execute('SELECT * FROM fields').fetchall()
        parcels = [self.parcel(f'{i:012d}') for i in range(1, 6)]
        for p in parcels:
            link = FieldCadastralLink(self.field, p.parcel_uuid, RecordVersion(1,0,0))
            first = self.repo.link(link, 0)
            self.assertEqual(first, self.repo.link(link, 0))
        other = CultivatedFieldRef(SCOPE, str(uuid4()))
        with guarded_write(self.db, SCOPE, ACTIVATION):
            self.db.execute("INSERT INTO fields VALUES(2,'000000000001',9)")
            self.db.execute("INSERT INTO field_identity VALUES(?,2,'2',NULL)", (other.field_uuid,))
        shared = self.parcel()
        self.assertEqual(parcels[0].parcel_uuid, shared.parcel_uuid)
        self.repo.link(FieldCadastralLink(other, shared.parcel_uuid, RecordVersion(1,0,0)), 0)
        self.assertEqual(2, len(self.repo.linked_fields(shared.parcel_uuid)))
        token = self.repo.enqueue(shared.parcel_uuid, 'synthetic')
        self.assertEqual(token, self.repo.enqueue(shared.parcel_uuid, 'synthetic'))
        self.repo.unlink(self.field, shared.parcel_uuid, 1)
        self.assertEqual((other,), self.repo.linked_fields(shared.parcel_uuid))
        self.assertEqual(before[0], self.db.execute('SELECT * FROM fields WHERE id=1').fetchone())
        with self.assertRaises(RevisionConflict):
            self.repo.link(FieldCadastralLink(self.field, shared.parcel_uuid, RecordVersion(1,0,0)), 0)
        self.assertEqual(5, self.db.execute('SELECT COUNT(*) FROM cadastral_parcels').fetchone()[0])

    def test_scoped_identity_and_primary_compatibility(self):
        a, b = self.parcel(), self.parcel(jurisdiction='other')
        self.assertNotEqual(a.parcel_uuid, b.parcel_uuid)
        self.repo.link(FieldCadastralLink(self.field, a.parcel_uuid, RecordVersion(1,0,0), True, False),0)
        with self.assertRaises(RevisionConflict):
            self.repo.unlink(self.field, a.parcel_uuid, 1)
        self.assertEqual(('000000000001',), self.db.execute('SELECT kaek FROM fields').fetchone())

    def test_conflicting_snapshots_are_preserved_and_cas_rejects_stale_selection(self):
        p = self.parcel()
        self.repo.link(FieldCadastralLink(self.field,p.parcel_uuid,RecordVersion(1,0,0)),0)
        s = SourceSnapshot(str(uuid4()),p.parcel_uuid,'synthetic','region','v1',
            '{"type":"Polygon","coordinates":[[[0,0],[20,0],[20,20],[0,20],[0,0]]]}',b'original',
            'EPSG:2100',json.dumps(dict(source_url='https://example.invalid/source', terms_url='synthetic', attribution='synthetic')),0,'synthetic')
        self.repo.add_snapshot(s)
        self.repo.select_snapshot(p.parcel_uuid,'synthetic',s.snapshot_uuid,1)
        inputs = self.repo.snapshot_inputs(self.field)
        other = replace(s,snapshot_uuid=str(uuid4()),source_payload=b'competing source')
        self.repo.add_snapshot(other)
        self.assertEqual('CONFLICT',self.repo.snapshot_inputs(self.field).inputs[0].state)
        self.assertNotEqual(inputs.fingerprint,self.repo.snapshot_inputs(self.field).fingerprint)
        with self.assertRaises(RevisionConflict):
            self.repo.select_snapshot(p.parcel_uuid,'synthetic',s.snapshot_uuid,2)
        self.assertEqual(2,self.db.execute('SELECT COUNT(*) FROM cadastral_snapshots').fetchone()[0])

    def test_stored_agricultural_ledger_and_shared_cache_invalidation(self):
        from app.gis.cadastral_union import build_union
        from shapely.geometry import box, mapping
        business = dict(product_fields=[(1, 'synthetic-crop')], production=[(1,100)],
                        sales=[(1,20)], income=[(1,200)], expenses=[(1,50)],
                        inventory_receipts=[(1,10)], activity_consumption=[(1,2)])
        with guarded_write(self.db,SCOPE,ACTIVATION):
            for table,rows in business.items():
                self.db.execute(f'CREATE TABLE {table}(field_id INTEGER REFERENCES fields(id), value)')
                self.db.executemany(f'INSERT INTO {table} VALUES(?,?)',rows)
            install_fence(self.db)
        def stored():
            return {table:self.db.execute(f'SELECT * FROM {table}').fetchall() for table in ('fields',*business)}
        before=stored();parcels=[]
        for n in range(5):
            p=self.parcel(f'{n+1:012d}');parcels.append(p)
            self.repo.link(FieldCadastralLink(self.field,p.parcel_uuid,RecordVersion(1,0,0)),0)
            token=self.repo.enqueue(p.parcel_uuid,'synthetic')
            source=SourceSnapshot(str(uuid4()),p.parcel_uuid,'synthetic','region','fixture',json.dumps(mapping(box(n*20,0,n*20+20,20))),
                b'synthetic payload','EPSG:2100',json.dumps(dict(source_url='https://example.invalid/source',terms_url='synthetic',attribution='synthetic')),0,'synthetic')
            self.repo.complete_lookup(source,token)
            with self.assertRaises(RevisionConflict):self.repo.complete_lookup(source,token)
        captured=self.repo.snapshot_inputs(self.field);result=build_union(captured)
        self.assertEqual('COMPLETE_DERIVED',result.state);self.repo.publish_overlay(captured,result)
        self.assertEqual(before,stored())
        self.assertEqual((8,),self.db.execute('SELECT (SELECT SUM(value) FROM inventory_receipts)-(SELECT SUM(value) FROM activity_consumption)').fetchone())
        self.assertEqual((150,),self.db.execute('SELECT (SELECT SUM(value) FROM income)-(SELECT SUM(value) FROM expenses)').fetchone())
        p=parcels[0]
        other=CultivatedFieldRef(SCOPE,str(uuid4()))
        with guarded_write(self.db,SCOPE,ACTIVATION):
            self.db.execute("INSERT INTO fields VALUES(2,'000000000001',9)")
            self.db.execute("INSERT INTO field_identity VALUES(?,2,'2',NULL)",(other.field_uuid,))
        self.repo.link(FieldCadastralLink(other,p.parcel_uuid,RecordVersion(1,0,0)),0)
        inverse=self.repo.snapshot_inputs(other);self.repo.publish_overlay(inverse,build_union(inverse))
        competing=replace(source,parcel_uuid=p.parcel_uuid,snapshot_uuid=str(uuid4()),source_payload=b'competing')
        self.repo.add_snapshot(competing)
        self.assertEqual([('STALE',),('STALE',)],self.db.execute('SELECT status FROM cadastral_field_overlays ORDER BY field_uuid').fetchall())
