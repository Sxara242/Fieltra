from __future__ import annotations

from pathlib import Path
import tempfile
import json
import zipfile
from unittest.mock import patch
import unittest

from app.database import Database
from app.profile_manager import ProfileError, ProfileManager


class ProfileManagerTests(unittest.TestCase):
    def test_profiles_use_independent_databases_and_backup_folders(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            legacy = Database(root / "data" / "mastixa_manager.db")
            legacy.execute(
                "INSERT INTO fields(name) VALUES(?)", ("Κύριο χωράφι",)
            )

            manager = ProfileManager(root)
            default = manager.active_profile
            self.assertEqual(legacy.path.resolve(), default.database_path)

            child = manager.create("Παιδί 1")
            child_db = Database(child.database_path)
            self.assertIsNone(child_db.query_one("SELECT id FROM fields"))
            child_db.execute(
                "INSERT INTO fields(name) VALUES(?)", ("Παιδικό χωράφι",)
            )

            self.assertEqual(
                "Κύριο χωράφι",
                legacy.query_one("SELECT name FROM fields")["name"],
            )
            self.assertEqual(
                "Παιδικό χωράφι",
                child_db.query_one("SELECT name FROM fields")["name"],
            )
            self.assertNotEqual(default.backup_dir, child.backup_dir)

            manager.set_active(child.id)
            self.assertEqual(child.id, manager.active_profile.id)
            renamed = manager.rename(child.id, "Μαρία")
            self.assertEqual("Μαρία", renamed.name)

            with self.assertRaises(ProfileError):
                manager.archive(child.id)

            manager.set_active(default.id)
            recovery = manager.archive(child.id)
            self.assertTrue(recovery.exists())
            self.assertEqual([default.id], [p.id for p in manager.profiles()])

    def test_pin_identity_startup_setting_and_export_import(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            manager = ProfileManager(root)
            profile = manager.create("Μαρία")
            database = Database(profile.database_path)
            database.execute(
                "INSERT INTO fields(name, area_stremma) VALUES(?, ?)",
                ("Κτήμα Μαρίας", 5),
            )

            manager.set_pin(profile.id, "1234")
            self.assertTrue(manager.has_pin(profile.id))
            self.assertTrue(manager.verify_pin(profile.id, "1234"))
            self.assertFalse(manager.verify_pin(profile.id, "9999"))
            manager.set_color(profile.id, "#123ABC")
            manager.set_language(profile.id, "en")
            manager.set_ask_on_startup(False)
            self.assertFalse(manager.ask_on_startup)

            avatar = root / "avatar.png"
            avatar.write_bytes(b"test-avatar")
            manager.set_avatar(profile.id, avatar)
            package = manager.export_profile(profile.id, root / "maria")
            self.assertEqual(".fieltraprofile", package.suffix)
            self.assertTrue(package.exists())

            imported = manager.import_profile(package)
            self.assertNotEqual(profile.id, imported.id)
            self.assertEqual("Μαρία (εισαγωγή)", imported.name)
            self.assertEqual("#123ABC", imported.color)
            self.assertEqual("en", imported.language)
            self.assertTrue(imported.avatar_path and imported.avatar_path.exists())
            self.assertTrue(manager.verify_pin(imported.id, "1234"))
            imported_db = Database(imported.database_path)
            row = imported_db.query_one(
                "SELECT name, area_stremma FROM fields WHERE name = ?",
                ("Κτήμα Μαρίας",),
            )
            self.assertIsNotNone(row)
            self.assertEqual(5, row["area_stremma"])

    def test_malformed_manifest_returns_profile_error_without_creating_data(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            manager = ProfileManager(root)
            before = manager.registry_path.read_bytes()
            valid = {"format": "mastixa-profile", "version": 1, "name": "Test"}
            for manifest in (None, [], "text", {**valid, "version": None},
                             {**valid, "pin_rounds": None}):
                with self.subTest(manifest=manifest):
                    package = root / "bad.fieltraprofile"
                    with zipfile.ZipFile(package, "w") as archive:
                        archive.writestr("manifest.json", json.dumps(manifest))
                        archive.writestr("profile.db", b"must not be read")
                    with self.assertRaises(ProfileError):
                        manager.import_profile(package)
                    self.assertEqual(before, manager.registry_path.read_bytes())
                    self.assertEqual([], list(manager.profiles_dir.iterdir()))

    def test_profile_import_under_path_with_uri_characters(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            manager = ProfileManager(Path(tmp) / "Κτήμα #1 %25")
            profile = manager.create("Source")
            db = Database(profile.database_path)
            db.execute("INSERT INTO fields(name) VALUES('retained')")
            package = manager.export_profile(profile.id, Path(tmp) / "source")
            imported = manager.import_profile(package)
            self.assertEqual("retained", Database(imported.database_path).query_one("SELECT name FROM fields")["name"])

    def test_interrupted_profile_export_preserves_previous_destination(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            manager = ProfileManager(root / "profiles")
            profile = manager.create("Source")
            destination = root / "backup.fieltraprofile"
            destination.write_bytes(b"previous complete export")
            before = set(root.iterdir())
            with patch.object(zipfile.ZipFile, "write", side_effect=OSError("destination full")):
                with self.assertRaises(ProfileError):
                    manager.export_profile(profile.id, destination)
            self.assertEqual(b"previous complete export", destination.read_bytes())
            self.assertEqual(before, set(root.iterdir()))


if __name__ == "__main__":
    unittest.main()
