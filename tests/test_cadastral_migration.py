"""Synthetic isolated storage specifications; NOT RUN locally.
SPDX-License-Identifier: AGPL-3.0-only
"""
from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest
from app.gis.cadastral_migration import (SyntheticField, prepare_synthetic, resolve_activation,
    create_schema, install_fence, guarded_write, StorageRefused, connect_synthetic)

SCOPE = 'synthetic-farm-A'
ACTIVATION = '30000000-0000-4000-8000-000000000001'
FIELD = '10000000-0000-4000-8000-000000000001'


def isolated():
    db = connect_synthetic(':memory:')
    db.execute('CREATE TABLE fields(id INTEGER PRIMARY KEY,kaek TEXT,area REAL)')
    db.execute("INSERT INTO fields VALUES(1,'000000000001',3.25)")
    db.commit()
    create_schema(db, SCOPE, ACTIVATION, 'synthetic')
    with guarded_write(db, SCOPE, ACTIVATION):
        db.execute('INSERT INTO field_identity VALUES(?,1,\'1\',NULL)', (FIELD,))
        install_fence(db)
    return db


class MigrationTests(unittest.TestCase):
    def test_alias_collision_rolls_back_partial_stage_and_preserves_source(self):
        other='10000000-0000-4000-8000-000000000002';alias='40000000-0000-4000-8000-000000000001'
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'fixture.db';target=Path(directory)/'stage.db'
            with closing(sqlite3.connect(source)) as db, db:
                db.execute('CREATE TABLE cadastral_synthetic_input(farm_scope TEXT)')
                db.execute('INSERT INTO cadastral_synthetic_input VALUES(?)',(SCOPE,))
                db.execute('CREATE TABLE fields(id INTEGER PRIMARY KEY,kaek TEXT,area REAL)')
                db.executemany('INSERT INTO fields VALUES(?,?,3.25)',((1,'000000000001'),(2,'000000000002')))
            before=source.read_bytes();aliases=(('fixture','dataset',alias),)
            plan=(SyntheticField(1,FIELD,'000000000001',aliases=aliases),SyntheticField(2,other,'000000000002',aliases=aliases))
            with self.assertRaises(sqlite3.IntegrityError):prepare_synthetic(source,target,SCOPE,plan)
            self.assertEqual(before,source.read_bytes())
            with closing(sqlite3.connect(target)) as db:
                self.assertEqual((0,),db.execute('SELECT COUNT(*) FROM field_identity').fetchone())
                self.assertEqual(('PREPARED',0,''),db.execute('SELECT phase,permit,receipt_hash FROM cadastral_storage_state').fetchone())
            with self.assertRaises(StorageRefused):prepare_synthetic(source,target,SCOPE,plan)

    def test_default_deny_and_crashed_permit_rolls_back(self):
        with closing(isolated()) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('UPDATE fields SET area=2')
            db.rollback()
            with self.assertRaises(RuntimeError):
                with guarded_write(db, SCOPE, ACTIVATION):
                    db.execute('UPDATE fields SET area=99')
                    raise RuntimeError('synthetic interruption')
            self.assertEqual((3.25,), db.execute('SELECT area FROM fields').fetchone())
            self.assertEqual((0,), db.execute('SELECT permit FROM cadastral_storage_state').fetchone())
            with self.assertRaises(StorageRefused):
                with guarded_write(db, 'other-farm', ACTIVATION):
                    pass

    def test_prepared_active_and_old_restore_protocol(self):
        marker = dict(activation_id=ACTIVATION, farm_scope=SCOPE, source_hash='source', receipt_hash='receipt')
        target = dict(marker, schema_version=2, min_writer=2, permit=0, phase='PREPARED')
        self.assertEqual('PREPARED_REQUIRES_SOURCE_LOCK', resolve_activation(marker, None, target))
        self.assertEqual('RECOVER_ACTIVATION', resolve_activation(marker, marker, target))
        target['phase']='ACTIVE'
        self.assertEqual('ACTIVE', resolve_activation(marker, marker, target))
        self.assertEqual('RESTORE_DETECTED', resolve_activation(marker, None, target))
        self.assertEqual('RECOVERY_REQUIRED', resolve_activation(marker, marker, dict(target, source_hash='changed')))
        self.assertEqual('RECOVERY_REQUIRED', resolve_activation(marker, marker, dict(target, min_writer=999)))

    def test_other_connection_cannot_borrow_an_uncommitted_permit(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic-fenced.db'
            original=isolated()
            with closing(sqlite3.connect(path)) as staged:original.backup(staged)
            original.close()
            first=connect_synthetic(path);second=sqlite3.connect(path,timeout=0)
            try:
                with guarded_write(first,SCOPE,ACTIVATION):
                    first.execute('UPDATE fields SET area=3.25')
                    with self.assertRaises(sqlite3.OperationalError):second.execute('UPDATE fields SET area=99')
                with self.assertRaises(sqlite3.IntegrityError):second.execute('UPDATE fields SET area=99')
                second.rollback()
            finally:first.close();second.close()

    def test_synthetic_copy_preserves_raw_business_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory)/'fixture.db', Path(directory)/'stage.db'
            with closing(sqlite3.connect(source)) as db, db:
                db.execute('CREATE TABLE cadastral_synthetic_input(farm_scope TEXT)')
                db.execute('INSERT INTO cadastral_synthetic_input VALUES(?)', (SCOPE,))
                db.execute('CREATE TABLE fields(id INTEGER PRIMARY KEY,kaek TEXT,area REAL)')
                db.execute("INSERT INTO fields VALUES(1,'  legacy/00  ',3.25)")
            original = source.read_bytes()
            receipt = prepare_synthetic(source, target, SCOPE, (SyntheticField(1, FIELD, '  legacy/00  '),))
            self.assertEqual(receipt, prepare_synthetic(source, target, SCOPE, (SyntheticField(1, FIELD, '  legacy/00  '),)))
            self.assertEqual(original, source.read_bytes())
            with closing(sqlite3.connect(target)) as db:
                self.assertEqual(('  legacy/00  ', 'unclassified'), db.execute('SELECT raw_kaek,classification FROM cadastral_legacy_bindings').fetchone())
                self.assertEqual((3.25,), db.execute('SELECT area FROM fields').fetchone())
                self.assertEqual(('PREPARED', receipt['receipt_hash']), db.execute('SELECT phase,receipt_hash FROM cadastral_storage_state').fetchone())
            with self.assertRaises(StorageRefused):
                prepare_synthetic(source, target, SCOPE, ())
