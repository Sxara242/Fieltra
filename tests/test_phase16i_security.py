import io
import json
import logging
import sqlite3
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

from app.profile_manager import ProfileManager, ProfileError


class ProfileArchiveSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manager = ProfileManager(self.root / "app")
        self.profile = self.manager.create("Synthetic")
        self.valid = self.manager.export_profile(self.profile.id, self.root / "valid")
        self.registry = self.manager.registry_path.read_bytes()
        with zipfile.ZipFile(self.valid) as z:
            self.entries = [(i.filename, z.read(i)) for i in z.infolist()]

    def package(self, extra):
        path = self.root / "untrusted.fieltraprofile"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for name, data in self.entries + extra:
                    z.writestr(name, data)
        return path

    def rejected(self, path):
        before = set(self.manager.profiles_dir.iterdir())
        with self.assertRaises(ProfileError):
            self.manager.import_profile(path)
        self.assertEqual(self.registry, self.manager.registry_path.read_bytes())
        self.assertEqual(before, set(self.manager.profiles_dir.iterdir()))

    def test_ambiguous_duplicate_members_rejected(self):
        self.rejected(self.package([self.entries[0]]))

    def test_untrusted_names_never_accepted_or_extracted(self):
        for name in ("../escape", "/absolute", "C:/drive", "\\\\server\\share", "..\\escape", "a/..\\escape"):
            with self.subTest(name=name):
                self.rejected(self.package([(name, b"unexpected")]))
        self.assertFalse((self.root / "escape").exists())

    def test_symlink_entry_rejected(self):
        link = zipfile.ZipInfo("avatar.png")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.rejected(self.package([(link, b"/external/target")]))

    def test_large_member_rejected_before_database_copy(self):
        with patch.object(ProfileManager, "PROFILE_DB_MAX_BYTES", 1, create=True):
            self.rejected(self.valid)

    def test_stream_copy_enforces_actual_limit(self):
        output = io.BytesIO()
        with self.assertRaises(ProfileError):
            ProfileManager._copy_profile_member(io.BytesIO(b"12345"), output, 4)
        self.assertLessEqual(len(output.getvalue()), 4)

    def test_compression_and_total_limits(self):
        with patch.object(ProfileManager, "PROFILE_MAX_RATIO", 1, create=True), patch.object(ProfileManager, "PROFILE_RATIO_MIN_BYTES", 1, create=True):
            self.rejected(self.valid)
        with patch.object(ProfileManager, "PROFILE_TOTAL_MAX_BYTES", 1, create=True):
            self.rejected(self.valid)

    def test_valid_unicode_profile_remains_importable(self):
        imported = self.manager.import_profile(self.valid)
        self.assertNotEqual(self.profile.id, imported.id)
        self.assertEqual("Synthetic (εισαγωγή)", imported.name)

    def test_nested_manifest_and_corrupt_database_cleanup(self):
        for manifest, database in ((b"[" * 2000 + b"0" + b"]" * 2000, b"unused"),
                (json.dumps({"format":"mastixa-profile","version":1,"name":"Test"}).encode(), b"not sqlite")):
            with self.subTest(nested=manifest.startswith(b"[")):
                path = self.root / "invalid.fieltraprofile"
                with zipfile.ZipFile(path,"w") as z:
                    z.writestr("manifest.json",manifest)
                    z.writestr("profile.db",database)
                self.rejected(path)

    def test_excessive_member_count_is_rejected(self):
        self.rejected(self.package([("avatar.png", b"image"), ("avatar.jpg", b"image")]))

    def test_unsupported_compression_rejected_without_extraction(self):
        path = self.root / "bzip.fieltraprofile"
        with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_BZIP2) as z:
            for name,data in self.entries:
                z.writestr(name,data)
        self.rejected(path)
