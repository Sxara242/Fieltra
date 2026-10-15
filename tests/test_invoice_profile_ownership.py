"""Profile attachment lifecycle and untrusted portable archive regressions."""
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
import warnings
import zipfile
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from app.database import Database
from app import invoice_documents as invoices
from app.invoice_storage import owned_file, owned_root
from app.profile_manager import ProfileManager, ProfileError
from tests.language_fixture import scoped_language


class InvoiceOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(scoped_language(self.qt, "el"))
        self.manager = ProfileManager(self.root / "app")
        self.legacy = self.manager.data_dir / "invoice_documents"
        self.legacy.mkdir()
        self.enterContext(patch.object(invoices, "INVOICE_FILES_DIR", self.legacy))
        self.a = self.manager.create("A")
        self.pages = []
        self.addCleanup(self.close_pages)
        self.page = self.page_for(self.a)
        self.add_document()

    def close_pages(self):
        for page in self.pages:
            page.close()
            page.deleteLater()
        self.qt.processEvents()

    def page_for(self, profile):
        page = invoices.InvoiceDocumentsPage(Database(profile.database_path))
        page.confirm_delete = lambda *_: True
        self.pages.append(page)
        return page

    def add_document(self):
        source = self.root / "source.pdf"
        source.write_bytes(b"%PDF-1.4 synthetic managed invoice")
        with patch.object(self.page, "_run_ocr", return_value=("unavailable", "", {"date": None, "supplier": "", "amount": ""})):
            row_id = self.page.import_files([source])[0]
        self.page.db.execute("UPDATE invoice_documents SET invoice_date='2026-01-01' WHERE id=?", (row_id,))
        return row_id

    def row(self, page=None):
        return (page or self.page).db.query_one("SELECT * FROM invoice_documents ORDER BY id LIMIT 1")

    def export(self):
        return self.manager.export_profile(self.a.id, self.root / "profile")

    def entries(self):
        with zipfile.ZipFile(self.export()) as package:
            return [(i.filename, package.read(i)) for i in package.infolist()]

    def package(self, entries):
        target = self.root / "modified.fieltraprofile"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # Deliberate duplicate ZIP fixture.
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as package:
                for name, data in entries:
                    package.writestr(name, data)
        return target

    def v1(self):
        entries = [(n, d) for n, d in self.entries() if not n.startswith("invoice_documents/")]
        return [(n, json.dumps({**json.loads(d), "version": 1}).encode() if n == "manifest.json" else d) for n, d in entries]

    def rejected(self, package):
        registry = self.manager.registry_path.read_bytes()
        before = set(self.manager.data_dir.rglob("*"))
        with self.assertRaises(ProfileError):
            self.manager.import_profile(package)
        self.assertEqual(registry, self.manager.registry_path.read_bytes())
        self.assertEqual(before, set(self.manager.data_dir.rglob("*")))

    def test_round_trip_restart_switch_and_hash(self):
        self.add_document()
        archive = self.export()
        with zipfile.ZipFile(archive) as package:
            self.assertEqual(2, json.loads(package.read("manifest.json"))["version"])
            self.assertEqual(2, len([n for n in package.namelist() if n.startswith("invoice_documents/")]))
        b = self.manager.import_profile(archive)
        for profile in (self.a, b, self.a, b):
            manager = ProfileManager(self.manager.base_dir)
            manager.set_active(profile.id)
            page = self.page_for(manager.active_profile)
            for row in page.db.query("SELECT * FROM invoice_documents"):
                path = page._stored_path(row)
                self.assertEqual(owned_file(profile.database_path, row["stored_filename"]), path)
                self.assertEqual(hashlib.sha256((self.root / "source.pdf").read_bytes()).digest(), hashlib.sha256(path.read_bytes()).digest())
        self.assertNotEqual(owned_root(self.a.database_path), owned_root(b.database_path))

    def delete_direction(self, source):
        b = self.manager.import_profile(self.export())
        page_b = self.page_for(b)
        deleting, keeping = (self.page, page_b) if source == "A" else (page_b, self.page)
        row = self.row(deleting)
        deleting.selected_id = row["id"]
        deleted_path = deleting._stored_path(row)
        keeping_path = keeping._stored_path(self.row(keeping))
        deleting.delete_document()
        self.assertIsNone(self.row(deleting))
        self.assertFalse(deleted_path.exists())
        self.assertIsNotNone(self.row(keeping))
        self.assertEqual((self.root / "source.pdf").read_bytes(), keeping_path.read_bytes())

    def test_delete_a_keeps_b(self): self.delete_direction("A")
    def test_delete_b_keeps_a(self): self.delete_direction("B")

    def test_duplicate_reference_preserves_file_until_last_delete(self):
        row = self.row()
        path = self.page._stored_path(row)
        second = self.page.db.execute("INSERT INTO invoice_documents(original_filename,stored_filename,invoice_date) VALUES('duplicate',?,'2026-01-01')", (row["stored_filename"],))
        self.page.selected_id = row["id"]
        self.page.delete_document()
        self.assertTrue(path.exists())
        self.page.selected_id = second
        self.page.delete_document()
        self.assertFalse(path.exists())

    def make_legacy(self):
        name = self.row()["stored_filename"]
        path = owned_file(self.a.database_path, name)
        (self.legacy / name).write_bytes(path.read_bytes())
        path.unlink()
        return name

    def test_legacy_open_export_and_delete_never_remove_shared_source(self):
        name = self.make_legacy()
        self.assertEqual(self.legacy / name, self.page._stored_path(self.row()))
        with patch.object(invoices.QDesktopServices, "openUrl", return_value=True) as opened:
            self.page.selected_id = self.row()["id"]
            self.page.open_file()
            self.assertEqual((self.legacy / name).resolve(), Path(opened.call_args.args[0].toLocalFile()).resolve())
        b = self.manager.import_profile(self.export())
        self.assertTrue(owned_file(b.database_path, name).is_file())
        self.page.delete_document()
        self.assertTrue((self.legacy / name).is_file())
        self.assertTrue(owned_file(b.database_path, name).is_file())

    def test_v1_copies_only_legacy_then_works_without_legacy(self):
        name = self.make_legacy()
        b = self.manager.import_profile(self.package(self.v1()))
        self.assertTrue((self.legacy / name).exists())
        path = owned_file(b.database_path, name)
        self.assertNotEqual(path, self.legacy / name)
        (self.legacy / name).unlink()  # Simulates a fresh host, not application cleanup.
        self.assertEqual(path, self.page_for(b)._stored_path(self.row()))
        self.assertTrue(path.is_file())

    def test_v1_missing_legacy_rejects_even_when_another_profile_owns_bytes(self):
        self.rejected(self.package(self.v1()))

    def test_v1_without_references_imports(self):
        self.page.db.execute("DELETE FROM invoice_documents")
        self.manager.import_profile(self.package(self.v1()))

    def test_export_only_references_not_orphans(self):
        (owned_root(self.a.database_path) / "orphan.pdf").write_bytes(b"orphan")
        self.assertNotIn("invoice_documents/orphan.pdf", dict(self.entries()))

    def test_missing_export_preserves_existing_destination(self):
        destination = self.export()
        original = destination.read_bytes()
        self.page._stored_path(self.row()).unlink()
        with self.assertRaises(ProfileError): self.export()
        self.assertEqual(original, destination.read_bytes())
        self.assertEqual([], list(self.root.glob(".mastixa-profile-*")))

    def test_v2_missing_or_unreferenced_attachment_rejected(self):
        entries = self.entries()
        self.rejected(self.package([(n,d) for n,d in entries if not n.startswith("invoice_documents/")]))
        self.rejected(self.package(entries + [("invoice_documents/orphan.pdf", b"extra")]))

    def test_duplicate_and_case_conflicting_members_rejected(self):
        entries = self.entries()
        name, data = next((n,d) for n,d in entries if n.startswith("invoice_documents/"))
        for duplicate in (name, name.upper()):
            with self.subTest(name=duplicate): self.rejected(self.package(entries + [(duplicate, data)]))

    def test_unsafe_member_names_rejected(self):
        entries = self.entries()
        for name in ("../escape", "/absolute", "C:/drive", "unknown.txt", "invoice_documents/../escape", "invoice_documents/a/b.pdf", "invoice_documents/", "invoice_documents/C:ads.pdf", "invoice_documents/a\\b.pdf", "invoice_documents/CON.pdf", "invoice_documents/a.pdf.", "invoice_documents/a.exe", "invoice_documents/no_extension"):
            with self.subTest(name=name): self.rejected(self.package(entries + [(name,b"bad")]))

    def test_special_members_rejected(self):
        entries = self.entries()
        for kind in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFDIR):
            item = zipfile.ZipInfo("invoice_documents/special.pdf")
            item.create_system = 3
            item.external_attr = (kind | 0o777) << 16
            with self.subTest(kind=kind): self.rejected(self.package(entries + [(item,b"bad")]))

    def test_attachment_size_total_count_and_ratio_bounds(self):
        archive = self.export()
        for constant in ("PROFILE_ATTACHMENT_MAX_BYTES", "PROFILE_ATTACHMENTS_MAX_BYTES", "PROFILE_TOTAL_MAX_BYTES", "PROFILE_ATTACHMENT_MAX_COUNT"):
            with self.subTest(constant=constant), patch.object(ProfileManager, constant, 0): self.rejected(archive)
        with patch.object(ProfileManager,"PROFILE_MAX_RATIO",1), patch.object(ProfileManager,"PROFILE_RATIO_MIN_BYTES",1): self.rejected(archive)
        size = len((self.root / "source.pdf").read_bytes())
        with patch.object(ProfileManager,"PROFILE_ATTACHMENT_MAX_BYTES",size), patch.object(ProfileManager,"PROFILE_ATTACHMENTS_MAX_BYTES",size), patch.object(ProfileManager,"PROFILE_ATTACHMENT_MAX_COUNT",1):
            self.manager.import_profile(archive)  # Exact limits are accepted.

    def test_corrupt_database_cleanup(self):
        self.rejected(self.package([(n,b"corrupt" if n=="profile.db" else d) for n,d in self.entries()]))

    def test_halfway_extraction_cleanup(self):
        self.add_document()
        archive = self.export()
        original = self.manager._copy_profile_member
        def fail(source, output, limit):
            if str(getattr(output,"name","")).endswith(".pdf"):
                if getattr(fail,"seen",False):
                    output.write(b"partial")
                    raise OSError("injected extraction failure")
                fail.seen=True
            return original(source,output,limit)
        with patch.object(self.manager,"_copy_profile_member",side_effect=fail): self.rejected(archive)

    def test_registry_failure_cleans_imported_files(self):
        archive = self.export()
        with patch.object(self.manager,"_save",side_effect=OSError("registry failure")):
            before=set(self.manager.data_dir.rglob("*"))
            with self.assertRaises(OSError): self.manager.import_profile(archive)
            self.assertEqual(before,set(self.manager.data_dir.rglob("*")))

    def test_profile_archive_moves_only_its_owned_attachments(self):
        name = self.row()["stored_filename"]
        b=self.manager.import_profile(self.export())
        before=owned_file(self.a.database_path,name).read_bytes()
        recovery=self.manager.archive(b.id)
        self.assertTrue((recovery/(b.database_path.name+".attachments")/"invoice_documents"/name).is_file())
        self.assertEqual(before,owned_file(self.a.database_path,name).read_bytes())

    def test_unsafe_db_reference_cannot_open_or_delete_external_file(self):
        outside=self.root/"external.pdf"; outside.write_bytes(b"keep")
        for name in (str(outside),"../external.pdf","C:external.pdf"):
            self.page.db.execute("UPDATE invoice_documents SET stored_filename=?",(name,))
            self.page.selected_id=self.row()["id"]
            with self.assertRaises(ValueError): self.page.delete_document()
            with self.assertRaises(ValueError): self.page._stored_path(self.row())
            self.assertEqual(b"keep",outside.read_bytes())

    def test_streamed_bytes_limit(self):
        output=io.BytesIO()
        with self.assertRaises(ProfileError): self.manager._copy_profile_member(io.BytesIO(b"12345"),output,4)
        self.assertLessEqual(len(output.getvalue()),4)

    def test_default_profile_storage_is_separate_from_legacy_global(self):
        default = self.manager.get(self.manager.DEFAULT_ID)
        page = self.page_for(default)
        self.assertNotEqual(owned_root(default.database_path), self.legacy)
        self.assertNotEqual(owned_root(default.database_path), owned_root(self.a.database_path))

    def test_fresh_host_import_needs_no_source_files(self):
        archive = self.export()
        other = ProfileManager(self.root / "fresh-host")
        imported = other.import_profile(archive)
        name = self.row()["stored_filename"]
        self.page._stored_path(self.row()).unlink()
        self.assertEqual((self.root / "source.pdf").read_bytes(), owned_file(imported.database_path,name).read_bytes())

    def test_v1_partial_legacy_recovery_cleans_all_copies(self):
        self.add_document()
        entries = self.v1()
        name = min(row["stored_filename"] for row in self.page.db.query("SELECT stored_filename FROM invoice_documents"))
        (self.legacy/name).write_bytes(b"legacy copy")
        self.rejected(self.package(entries))
        self.assertEqual(b"legacy copy",(self.legacy/name).read_bytes())

    def test_v1_must_not_supply_new_attachment_members(self):
        entries = self.entries()
        entries = [(n,json.dumps({**json.loads(d),"version":1}).encode() if n=="manifest.json" else d) for n,d in entries]
        self.rejected(self.package(entries))

    def test_export_attachment_limits_preserve_destination(self):
        destination=self.export(); before=destination.read_bytes()
        for limit in ("PROFILE_ATTACHMENT_MAX_BYTES","PROFILE_ATTACHMENTS_MAX_BYTES","PROFILE_ATTACHMENT_MAX_COUNT"):
            with self.subTest(limit=limit), patch.object(ProfileManager,limit,0), self.assertRaises(ProfileError): self.export()
            self.assertEqual(before,destination.read_bytes())

    def test_registry_preparation_failure_cleans_staging(self):
        archive=self.export()
        with patch.object(self.manager,"_unique_import_name",side_effect=ProfileError("name failure")):
            self.rejected(archive)

    def test_redirected_owned_file_never_deleted(self):
        row=self.row(); path=self.page._stored_path(row)
        outside=self.root/"external.pdf"; outside.write_bytes(b"keep")
        original=Path.resolve
        def redirected(candidate,*args,**kwargs):
            return outside if candidate==path else original(candidate,*args,**kwargs)
        self.page.selected_id=row["id"]
        with patch.object(Path,"resolve",redirected), self.assertRaises(ValueError): self.page.delete_document()
        self.assertEqual(b"keep",outside.read_bytes())
        self.assertIsNotNone(self.row())

    def test_database_backup_restore_keeps_owned_file_path(self):
        from app.backup_manager import BackupManager
        backup=BackupManager(self.a.database_path,self.a.backup_dir)
        path=self.page._stored_path(self.row()); before=path.read_bytes()
        snapshot=backup.create_backup()
        self.page.db.execute("UPDATE invoice_documents SET notes='changed'")
        backup.restore_backup(snapshot)
        self.assertEqual("",self.row()["notes"])
        self.assertEqual(path,self.page._stored_path(self.row()))
        self.assertEqual(before,path.read_bytes())

    def test_encrypted_attachment_metadata_rejected(self):
        archive=self.export()
        with zipfile.ZipFile(archive) as package:
            attachment=next(i for i in package.infolist() if i.filename.startswith("invoice_documents/"))
            attachment.flag_bits |= 1
            with self.assertRaises(ProfileError): self.manager._validate_profile_archive(package)

    def test_document_zip_uses_owned_bytes(self):
        archive=self.page.build_export_zip(self.root/"documents.zip",[self.row()["id"]])
        with zipfile.ZipFile(archive) as package:
            name=next(n for n in package.namelist() if n.startswith("invoices/"))
            self.assertEqual((self.root/"source.pdf").read_bytes(),package.read(name))

    def test_portable_data_export_uses_owned_bytes_once(self):
        from app import data_export
        row=self.row()
        self.page.db.execute("INSERT INTO invoice_documents(original_filename,stored_filename) VALUES('duplicate',?)",(row['stored_filename'],))
        page=data_export.DataExportPage(self.page.db)
        self.pages.append(page)
        destination=self.root/"portable.zip"
        for key,check in page.section_checks.items(): check.setChecked(key=="invoice_documents")
        with patch.object(data_export.QFileDialog,"getSaveFileName",return_value=(str(destination),"ZIP")), patch.object(data_export,"_message"):
            page.export_zip()
        with zipfile.ZipFile(destination) as package:
            names=[n for n in package.namelist() if n.startswith("invoice_files/")]
            self.assertEqual(1,len(names))
            self.assertEqual((self.root/"source.pdf").read_bytes(),package.read(names[0]))

    def test_import_destination_collision_never_removes_existing_profile(self):
        from types import SimpleNamespace
        archive=self.export()
        with patch("app.profile_manager.uuid4",return_value=SimpleNamespace(hex=self.a.id)):
            self.rejected(archive)
        self.assertTrue(self.page._stored_path(self.row()).is_file())

    def test_unsafe_and_case_conflicting_database_references_rejected(self):
        entries=self.entries()
        name=self.row()["stored_filename"]
        for value in ("../escape.pdf", str(self.root/"outside.pdf"), name.upper()):
            temporary=self.root/"modified.db"
            temporary.write_bytes(dict(entries)["profile.db"])
            connection=sqlite3.connect(temporary)
            try:
                if value==name.upper():
                    connection.execute("INSERT INTO invoice_documents(original_filename,stored_filename) VALUES('case conflict',?)",(value,))
                else:
                    connection.execute("UPDATE invoice_documents SET stored_filename=?",(value,))
                connection.commit()
            finally:
                connection.close()
            with self.subTest(value=value):
                self.rejected(self.package([(n,temporary.read_bytes() if n=="profile.db" else d) for n,d in entries]))
