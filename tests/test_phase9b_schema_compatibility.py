"""9B: source-derived schema slices on host SQLite; no application projection/migration.

Only in-memory fixture setup executes existing DDL. Android runtime/onUpgrade is
not executed here; version slices follow its inspected source-table introduction gates.
"""
import ast
import json
from pathlib import Path
import re
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]
JAVA = 'android/app/src/main/java/gr/mastixa/manager/'
SOURCES = [
    ('production', 'entry_date', 'production', 'app/database.py', 'ProductionStore.java', 7),
    ('farm_activities', 'activity_date', 'farm_activity', 'app/activities.py', 'ActivityStore.java', 8),
    ('plant_protection_records', 'application_date', 'plant_protection', 'app/plant_protection.py', 'WorkStore.java', 9),
    ('labor_entries', 'work_date', 'labor_entry', 'app/labor.py', 'WorkStore.java', 9),
    ('planting_batches', 'planting_date', 'planting_batch', 'app/plantings.py', 'WorkStore.java', 10),
]


def literals(path):
    text = (ROOT / path).read_text(encoding='utf-8-sig')
    if path.endswith('.py'):
        return [n.value for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return [json.loads(value) for value in re.findall(r'"(?:\\.|[^"\\])*"', text)]


def declaration(path, table):
    for sql in literals(path):
        match = re.search(r'CREATE TABLE (?:IF NOT EXISTS )?' + table + r'\s*\(', sql)
        if match:
            depth = 1
            for end in range(match.end(), len(sql)):
                depth += (sql[end] == '(') - (sql[end] == ')')
                if depth == 0:
                    return sql[match.start():end + 1]
    raise AssertionError(f'Missing source declaration: {path}:{table}')


def columns(db, table):
    return {row['name']: row for row in db.execute(f'PRAGMA table_info({table})')}


def insert(db, table, **values):
    # Populate required fixture columns while retaining all source SQL constraints.
    for name, col in columns(db, table).items():
        if name not in values and col['notnull'] and col['dflt_value'] is None:
            values[name] = 1 if col['type'] in ('INTEGER', 'REAL') else 'fixture'
    db.execute(f'INSERT INTO {table}({",".join(values)}) VALUES({",".join("?" for _ in values)})', tuple(values.values()))


class Phase9BSchemaCompatibilityTests(unittest.TestCase):
    def database(self, android=False, version=15, windows='current'):
        db = sqlite3.connect(':memory:'); db.row_factory = sqlite3.Row
        self.addCleanup(db.close); db.execute('PRAGMA foreign_keys=ON')
        db.execute(declaration(JAVA + 'FarmStore.java' if android else 'app/database.py', 'fields'))
        if android and version >= 2:
            for sql in literals(JAVA + 'FarmStore.java'):
                if sql.startswith('ALTER TABLE fields ADD COLUMN '): db.execute(sql)
        db.execute(declaration(JAVA + 'WorkStore.java' if android else 'app/labor.py', 'workers'))
        insert(db, 'workers', id='worker' if android else 1)
        for table, _, _, py, java, introduced in SOURCES:
            if (android and version < introduced) or (not android and windows == 'core' and table != 'production'): continue
            db.execute(declaration(JAVA + java if android else py, table))
        if not android and windows == 'current':
            tree = ast.parse((ROOT / 'app/activities.py').read_text(encoding='utf-8-sig'))
            additions = next(ast.literal_eval(n.value) for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'additions' for t in n.targets))
            for name, definition in additions.items(): db.execute(f'ALTER TABLE farm_activities ADD COLUMN {name} {definition}')
        if (android and version >= 13) or (not android and windows == 'current'):
            for table in (['gis_records'] if android else ['parcel_geometry', 'geo_points']):
                db.execute(declaration(JAVA + 'GeoStore.java' if android else 'app/gis/store.py', table))
        if android and version >= 15:
            db.execute(declaration(JAVA + 'CadastralStore.java', 'cadastral_reference'))
        return db

    def probe_sources(self, db, android):
        field = '00000000-0000-0000-0000-000000000001' if android else 1
        insert(db, 'fields', id=field)
        for table, date, source_type, *_ in SOURCES:
            cols = columns(db, table)
            if not cols: continue  # An absent optional source is distinguishable without creating it.
            with self.subTest(table=table, android=android):
                self.assertTrue({'id', 'field_id', date} <= cols.keys()); self.assertTrue(cols['id']['pk'])
                self.assertEqual('TEXT' if android else 'INTEGER', cols['id']['type'])
                identity = '00000000-0000-0000-0000-000000000017' if android else 17
                values = dict(id=identity, field_id=field)
                values[date] = '2026-09-10'
                if table == 'labor_entries': values['worker_id'] = 'worker' if android else 1
                if table == 'farm_activities': values.update(category='Πότισμα', status='Προγραμματισμένη')
                insert(db, table, **values)
                if table == 'farm_activities':
                    db.execute(f"UPDATE {table} SET category='Λίπανση',status='Ακυρώθηκε'")
                    self.assertEqual(('Λίπανση', 'Ακυρώθηκε'), tuple(db.execute(f'SELECT category,status FROM {table}').fetchone()))
                for raw in ('', 'not-a-date', '2026-09-10'):
                    db.execute(f'UPDATE {table} SET {date}=?', (raw,))
                    self.assertEqual((identity, raw), tuple(db.execute(f'SELECT id,{date} FROM {table}').fetchone()))
                # Contract null is read-time fallback, not a request to relax SQL NOT NULL.
                if cols[date]['notnull']:
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(f'UPDATE {table} SET {date}=NULL')
                else:
                    db.execute(f'UPDATE {table} SET {date}=NULL'); self.assertIsNone(db.execute(f'SELECT {date} FROM {table}').fetchone()[0])
                predicate = ' AND s.deleted_at IS NULL AND f.deleted_at IS NULL' if android else ''
                query = f'SELECT s.id FROM {table} s JOIN fields f ON f.id=s.field_id WHERE f.id=?' + predicate
                before = list(db.iterdump()); db.execute('PRAGMA query_only=ON')
                self.assertEqual([identity], [r[0] for r in db.execute(query, (field,))])
                self.assertEqual(before, list(db.iterdump())); db.execute('PRAGMA query_only=OFF')
                if android:
                    for owner in (table, 'fields'):
                        db.execute(f'UPDATE {owner} SET deleted_at=0'); self.assertFalse(db.execute(query, (field,)).fetchall())
                        db.execute(f'UPDATE {owner} SET deleted_at=NULL')
                if not cols['field_id']['notnull'] or android:
                    db.execute(f'UPDATE {table} SET field_id=?', ('' if android else None,))
                    self.assertFalse(db.execute(query, (field,)).fetchall())
                db.execute(f'DELETE FROM {table}'); self.assertFalse(db.execute(query, (field,)).fetchall())
                self.assertTrue(source_type)  # Type comes from the fixed source catalogue, not another DB column.

    def probe_notes(self, db, android):
        table = 'gis_records' if android else 'geo_points'
        if not columns(db, table): return
        field = db.execute('SELECT id FROM fields').fetchone()[0]
        if android:
            insert(db, table, id='point', field_id=field, kind='point', payload=json.dumps({'point_type': 'note', 'title': 'Observation', 'notes': 'Synthetic'}), created_at=1726000000000)
            query = "SELECT s.id,s.created_at,s.payload FROM gis_records s JOIN fields f ON f.id=s.field_id WHERE s.deleted_at IS NULL AND f.deleted_at IS NULL AND s.kind='point'"
        else:
            insert(db, 'parcel_geometry', id='parcel', field_id=field)
            insert(db, table, id='point', parcel_id='parcel', point_type='note', created_at=1726000000000)
            query = 'SELECT s.id,s.created_at,s.point_type FROM geo_points s JOIN parcel_geometry p ON p.id=s.parcel_id JOIN fields f ON f.id=p.field_id WHERE s.deleted_at IS NULL AND p.deleted_at IS NULL'
        row = db.execute(query).fetchone(); self.assertEqual(('point', 1726000000000), tuple(row)[:2])
        self.assertEqual('note', json.loads(row[2])['point_type'] if android else row[2])
        for owner in (table, 'fields' if android else 'parcel_geometry'):
            db.execute(f'UPDATE {owner} SET deleted_at=0'); self.assertFalse(db.execute(query).fetchall())
            db.execute(f'UPDATE {owner} SET deleted_at=NULL')
        if android: db.execute('UPDATE gis_records SET field_id=?', ('missing-field',))
        else: db.execute('UPDATE parcel_geometry SET field_id=NULL')
        self.assertFalse(db.execute(query).fetchall())

    def test_windows_base_legacy_and_current_source_schema_slices(self):
        for variant in ('core', 'pre_activity_additions', 'current'):
            with self.subTest(fixture=variant):
                db = self.database(windows=variant); self.probe_sources(db, False); self.probe_notes(db, False)
                if variant == 'core': self.assertFalse(columns(db, 'farm_activities'))
                else: self.assertEqual(variant == 'current', 'duration_minutes' in columns(db, 'farm_activities'))
                # Separate profile connection may reuse the same integer IDs without sharing rows.
                other = self.database(windows=variant); self.assertEqual(0, other.execute('SELECT count(*) FROM fields').fetchone()[0])

    def test_android_v1_to_v15_source_schema_slices(self):
        source = (ROOT / JAVA / 'FarmStore.java').read_text()
        self.assertIn('super(context, name, null, 15)', source)
        self.assertIn('if(oldVersion<15)CadastralStore.create(db)', source)
        for version in range(1, 16):
            with self.subTest(schema=version):
                db = self.database(android=True, version=version)
                for table, _, _, _, _, introduced in SOURCES: self.assertEqual(version >= introduced, bool(columns(db, table)))
                self.assertEqual(version >= 13, bool(columns(db, 'gis_records')))
                self.assertEqual(version >= 15, bool(columns(db, 'cadastral_reference')))
                self.probe_sources(db, True); self.probe_notes(db, True)
                other = self.database(android=True, version=version); self.assertEqual(0, other.execute('SELECT count(*) FROM fields').fetchone()[0])


if __name__ == '__main__': unittest.main()
