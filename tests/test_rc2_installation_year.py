"""Stable installation metadata; synthetic registry/database migrations only."""
from datetime import datetime
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from app.database import Database
from app.profile_manager import ProfileManager


class FirstStartDate(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 12)


class UpgradeDate(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2029, 1, 1)


class InstallationYearTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('app.profile_manager.datetime', FirstStartDate))

    def test_fresh_start_persists_across_upgrade_and_reinstallation(self):
        manager = ProfileManager(self.root)
        self.assertEqual(2026, manager.initial_installation_year)
        original = manager.registry_path.read_bytes()
        with patch('app.profile_manager.datetime', UpgradeDate):
            reopened = ProfileManager(self.root)
        self.assertEqual(2026, reopened.initial_installation_year)
        self.assertEqual(original, reopened.registry_path.read_bytes())

    def test_profile_creation_switch_and_archiving_child_do_not_reset_year(self):
        manager = ProfileManager(self.root)
        with patch('app.profile_manager.datetime', UpgradeDate):
            child = manager.create('Synthetic child')
        manager.set_active(child.id)
        manager.set_active(manager.DEFAULT_ID)
        manager.archive(child.id)
        self.assertEqual(2026, ProfileManager(self.root).initial_installation_year)

    def test_installation_marker_precedes_delayed_first_application_start(self):
        data_dir = self.root / 'data'
        data_dir.mkdir()
        marker = data_dir / 'installation-year.json'
        marker.write_text('{"schema":1,"year":2024}')
        original = marker.read_bytes()
        manager = ProfileManager(self.root)
        self.assertEqual(2024, manager.initial_installation_year)
        self.assertEqual(original, marker.read_bytes())
        self.assertEqual('installer-first-install', json.loads(manager.registry_path.read_text())['initial_installation_year_source'])

    def test_corrupt_marker_remains_unknown_without_overwrite(self):
        data_dir = self.root / 'data'
        data_dir.mkdir()
        marker = data_dir / 'installation-year.json'
        marker.write_text('{corrupt historical metadata')
        original = marker.read_bytes()
        manager = ProfileManager(self.root)
        self.assertIsNone(manager.initial_installation_year)
        self.assertEqual(original, marker.read_bytes())

    def test_legacy_default_created_at_migrates_without_changing_profile_record(self):
        manager = ProfileManager(self.root)
        data = json.loads(manager.registry_path.read_text())
        data.pop('initial_installation_year')
        data['profiles'][0]['created_at'] = '2021-04-03T14:00:00'
        manager.registry_path.write_text(json.dumps(data))
        records = data['profiles']
        reopened = ProfileManager(self.root)
        self.assertEqual(2021, reopened.initial_installation_year)
        migrated = json.loads(manager.registry_path.read_text())
        self.assertEqual(records, migrated['profiles'])
        self.assertEqual('default-profile-created-at', migrated['initial_installation_year_source'])

    def test_unknown_legacy_date_is_not_replaced_with_current_year(self):
        manager = ProfileManager(self.root)
        data = json.loads(manager.registry_path.read_text())
        data.pop('initial_installation_year')
        data['profiles'][0].pop('created_at')
        manager.registry_path.write_text(json.dumps(data))
        reopened = ProfileManager(self.root)
        self.assertIsNone(reopened.initial_installation_year)
        original = reopened.registry_path.read_bytes()
        with patch('app.profile_manager.datetime', UpgradeDate):
            self.assertIsNone(ProfileManager(self.root).initial_installation_year)
        self.assertEqual(original, reopened.registry_path.read_bytes())

    def test_database_without_registry_keeps_unknown_year_and_historical_records(self):
        db = Database(self.root / 'data/mastixa_manager.db')
        db.execute("INSERT INTO production(entry_date,product,quantity_kg) VALUES('1903-01-01','Synthetic',1)")
        before = db.path.read_bytes()
        manager = ProfileManager(self.root)
        self.assertIsNone(manager.initial_installation_year)
        self.assertEqual(before, db.path.read_bytes())
        self.assertEqual('1903-01-01', db.query_one('SELECT entry_date FROM production')['entry_date'])

    def test_importing_older_profile_does_not_change_global_year(self):
        manager = ProfileManager(self.root)
        donor = ProfileManager(self.root / 'donor')
        Database(donor.active_profile.database_path)
        data = json.loads(donor.registry_path.read_text())
        data['profiles'][0]['created_at'] = '2010-01-01T00:00:00'
        donor.registry_path.write_text(json.dumps(data))
        package = donor.export_profile(donor.DEFAULT_ID, self.root / 'import-fixture')
        imported = manager.import_profile(package)
        manager.set_active(imported.id)
        self.assertEqual(2026, ProfileManager(self.root).initial_installation_year)
