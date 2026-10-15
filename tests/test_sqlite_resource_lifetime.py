"""Windows release regression: acquired DB handles close even on partial setup."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from app.backup_manager import BackupError, BackupManager
from app.database import Database, _ClosingConnection
from app.profile_manager import ProfileError, ProfileManager


REAL_CONNECT = sqlite3.connect


class SQLiteResourceLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.db = Database(self.root / 'live.db')
        self.db.execute("INSERT INTO fields(name) VALUES('retained')")
        self.manager = BackupManager(self.db.path, self.root / 'backups')

    def assert_closed(self, connection):
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute('SELECT 1')

    def test_backup_and_restore_copy_close_source_when_destination_open_fails(self):
        for operation in ('backup', 'copy'):
            with self.subTest(operation=operation):
                source = REAL_CONNECT(self.db.path)
                self.addCleanup(source.close)
                with patch('app.backup_manager.sqlite3.connect', side_effect=[
                    source, sqlite3.OperationalError('destination denied'),
                ]):
                    with self.assertRaises((BackupError, sqlite3.OperationalError)):
                        if operation == 'backup':
                            self.manager._backup_to(self.root / 'denied.db')
                        else:
                            self.manager._sqlite_copy(self.db.path, self.root / 'denied.db')
                self.assert_closed(source)
        self.assertEqual('retained', self.db.query_one('SELECT name FROM fields')[0])

    def test_backup_and_restore_copy_close_source_even_if_destination_close_raises(self):
        class CloseFailure(sqlite3.Connection):
            def close(self):
                super().close()
                raise sqlite3.OperationalError('close failed')

        for operation in ('backup', 'copy'):
            with self.subTest(operation=operation):
                source = REAL_CONNECT(self.db.path)
                self.addCleanup(source.close)
                target = REAL_CONNECT(self.root / (operation + '.db'), factory=CloseFailure)
                self.addCleanup(sqlite3.Connection.close, target)
                with patch('app.backup_manager.sqlite3.connect', side_effect=[source, target]):
                    with self.assertRaises((BackupError, sqlite3.OperationalError)):
                        if operation == 'backup':
                            self.manager._backup_to(self.root / 'ignored.db')
                        else:
                            self.manager._sqlite_copy(self.db.path, self.root / 'ignored.db')
                self.assert_closed(source)
                self.assert_closed(target)

    def test_database_setup_failure_closes_acquired_handle(self):
        class SetupFailure(_ClosingConnection):
            def execute(self, sql, *args):
                if sql == 'PRAGMA foreign_keys = ON':
                    raise sqlite3.OperationalError('setup failed')
                return super().execute(sql, *args)

        connection = REAL_CONNECT(self.db.path, factory=SetupFailure)
        self.addCleanup(connection.close)
        with patch('app.database.sqlite3.connect', return_value=connection):
            with self.assertRaisesRegex(sqlite3.OperationalError, 'setup failed'):
                self.db.connect()
        self.assert_closed(connection)
        self.db.execute("UPDATE fields SET name='reopened'")
        self.assertEqual('reopened', self.db.query_one('SELECT name FROM fields')[0])

    def test_profile_export_closes_source_when_snapshot_open_fails(self):
        profiles = ProfileManager(self.root)
        profile = profiles.active_profile
        source = REAL_CONNECT(profile.database_path)
        self.addCleanup(source.close)
        with patch('app.profile_manager.sqlite3.connect', side_effect=[
            source, sqlite3.OperationalError('snapshot denied'),
        ]):
            with self.assertRaisesRegex(ProfileError, 'snapshot denied'):
                profiles.export_profile(profile.id, self.root / 'export.fieltraprofile')
        self.assert_closed(source)
        self.assertFalse((self.root / 'export.fieltraprofile').exists())

    def test_local_context_commit_rollback_reopen_and_windows_handle_release(self):
        with self.db.connect() as connection:
            connection.execute("UPDATE fields SET name='committed'")
        self.assert_closed(connection)
        with self.assertRaisesRegex(ValueError, 'rollback'):
            with self.db.connect() as connection:
                connection.execute('DELETE FROM fields')
                raise ValueError('rollback')
        self.assert_closed(connection)
        self.assertEqual('committed', self.db.query_one('SELECT name FROM fields')[0])
        with self.db.transaction() as transaction:
            transaction.execute('DELETE FROM fields')
        with closing(REAL_CONNECT(self.db.path)) as reopened:
            self.assertEqual(0, reopened.execute('SELECT COUNT(*) FROM fields').fetchone()[0])
        moved = self.root / 'closed.db'
        self.db.path.rename(moved)
        moved.rename(self.db.path)
        self.assertEqual('ok', self.db.query_one('PRAGMA integrity_check')[0])

    def test_failed_restore_recovery_is_logged_and_safety_snapshot_retained(self):
        incoming = self.manager.create_backup()
        with patch.object(self.manager, '_sqlite_copy', side_effect=[
            sqlite3.OperationalError('restore failed'),
            sqlite3.OperationalError('recovery failed'),
        ]):
            with self.assertLogs('mastixa.backup_manager', level='ERROR') as logs:
                with self.assertRaises(BackupError) as caught:
                    self.manager.restore_backup(incoming)
        self.assertTrue(any('recovery failed' in line for line in logs.output))
        self.assertIn('restore failed', str(caught.exception))
        self.assertTrue(list(self.manager.backup_dir.glob('pre_restore_*.db')))

    def test_deferred_commit_failure_rolls_back_and_closes_before_reuse(self):
        self.db.execute('CREATE TABLE deferred_child(field_id INTEGER REFERENCES fields(id) '
                        'DEFERRABLE INITIALLY DEFERRED)')
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect() as connection:
                connection.execute('INSERT INTO deferred_child VALUES(999)')
        self.assert_closed(connection)
        self.assertEqual(0, self.db.query_one('SELECT COUNT(*) FROM deferred_child')[0])
        with self.db.transaction() as transaction:
            transaction.execute('INSERT INTO deferred_child SELECT id FROM fields')
        self.assertEqual(1, self.db.query_one('SELECT COUNT(*) FROM deferred_child')[0])


if __name__ == '__main__':
    unittest.main()
