"""Backup error UI translates owned wrappers, never paths or exception details."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget
from app.backup_manager import BackupError, BackupManager
from app.database import Database
from app.dashboard import DashboardPage
from app.language import LanguageController
from app.main_window import MainWindow, ApplicationController


class BackupLocalizationTests(unittest.TestCase):
    RAW = "Παραγωγή <b>Ναι</b> & Αποθήκευση {path}\n raw SQLite detail Ω"

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "Παραγωγή Ναι Αποθήκευση"
        self.root.mkdir()
        self.db = Database(self.root / "live.db")
        self.manager = BackupManager(self.db.path, self.root / "backups")
        self.language = LanguageController(self.app, SimpleNamespace(active_profile=SimpleNamespace(language="el")))
        self.page = QWidget()
        self.page.backup_manager = Mock()

    def tearDown(self):
        self.page.close()
        self.page.deleteLater()
        self.app.removeEventFilter(self.language)
        self.language._enabled = False
        self.app.processEvents()
        self.temp.cleanup()

    def capture(self, action):
        with self.assertRaises(BackupError) as caught:
            action()
        self.assertIs(type(caught.exception), BackupError)
        return caught.exception

    def files(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def check_dialog(self, error, greek, english, restore=False):
        before = self.files()
        args, cause = error.args, error.__cause__
        self.assertEqual(greek, str(error))
        self.page.backup_manager.create_backup.side_effect = error
        self.page.backup_manager.restore_backup.side_effect = error
        self.page.backup_manager.backup_dir = self.manager.backup_dir
        errors = []
        for language in ("el", "en", "el"):
            self.language.set_language(language, persist=False)
            def inspect():
                box = QApplication.activeModalWidget()
                try:
                    self.assertIsInstance(box, QMessageBox)
                    self.language.apply_to(box)
                    self.assertEqual(greek if language == "el" else english, box.text())
                    self.assertEqual(QMessageBox.Icon.Critical, box.icon())
                except BaseException as exc:
                    errors.append(exc)
                finally:
                    if isinstance(box, QMessageBox):
                        box.button(QMessageBox.StandardButton.Ok).click()
            QTimer.singleShot(0, inspect)
            if restore:
                with patch("app.dashboard.QFileDialog.getOpenFileName", return_value=(str(self.root / "selected.db"), "")), patch("app.dashboard.QMessageBox.warning", return_value=QMessageBox.StandardButton.Yes):
                    DashboardPage.restore_backup(self.page)
            else:
                DashboardPage.create_backup(self.page)
            self.assertEqual(before, self.files())
            self.assertEqual(args, error.args)
            self.assertIs(cause, error.__cause__)
        if errors:
            raise errors[0]

    def test_missing_selected_backup_path(self):
        path = self.root / "missing Ναι.db"
        error = self.capture(lambda: self.manager.restore_backup(path))
        self.check_dialog(error, f"Δεν βρέθηκε το αρχείο backup:\n{path}", f"Backup file not found:\n{path}", restore=True)

    def test_missing_live_database_path(self):
        path = self.root / "missing Αποθήκευση.db"
        manager = BackupManager(path, self.manager.backup_dir)
        error = self.capture(manager.create_backup)
        self.check_dialog(error, f"Δεν βρέθηκε η βάση δεδομένων:\n{path}", f"Database not found:\n{path}")

    def test_creation_failure_keeps_raw_cause(self):
        cause = sqlite3.OperationalError(self.RAW)
        with patch("app.backup_manager.sqlite3.connect", side_effect=cause):
            error = self.capture(lambda: self.manager._backup_to(self.root / "target.db"))
        self.assertIs(cause, error.__cause__)
        self.check_dialog(error, f"Αποτυχία δημιουργίας backup:\n{cause}", f"Backup creation failed:\n{cause}")

    def test_restore_failure_keeps_raw_cause_and_safety_path(self):
        selected = self.manager.create_backup()
        safety = self.manager.create_backup(prefix="pre_restore_Ναι")
        cause = sqlite3.OperationalError(self.RAW)
        with patch.object(self.manager, "create_backup", return_value=safety), patch.object(self.manager, "_sqlite_copy", side_effect=[cause, None]) as copy:
            error = self.capture(lambda: self.manager.restore_backup(selected))
        self.assertEqual(2, copy.call_count)
        self.assertEqual(safety, copy.call_args.kwargs["source_path"])
        self.assertIs(cause, error.__cause__)
        self.check_dialog(error, f"Η επαναφορά απέτυχε.\n\n{cause}\n\nΔημιουργήθηκε αντίγραφο ασφαλείας πριν την επαναφορά:\n{safety}", f"Restore failed.\n\n{cause}\n\nA safety backup was created before restoring:\n{safety}", restore=True)

    def test_unknown_error_is_verbatim_even_when_it_matches_catalog_words(self):
        self.check_dialog(BackupError(self.RAW), self.RAW, self.RAW)

    def test_invalid_sqlite_preserves_path_and_sqlite_detail(self):
        path = self.root / "invalid Παραγωγή.db"
        path.write_bytes(b"not sqlite")
        error = self.capture(lambda: self.manager.restore_backup(path))
        self.assertIsInstance(error.__cause__, sqlite3.Error)
        self.check_dialog(error, f"Το αρχείο δεν είναι έγκυρη βάση SQLite:\n{path}\n\n{error.__cause__}", f"The file is not a valid SQLite database:\n{path}\n\n{error.__cause__}", restore=True)

    def test_integrity_error_preserves_result(self):
        connection = Mock()
        connection.execute.return_value.fetchone.return_value = (self.RAW,)
        with patch("app.backup_manager.sqlite3.connect", return_value=connection):
            error = self.capture(lambda: self.manager._validate_database(self.db.path))
        connection.close.assert_called_once()
        self.check_dialog(error, f"Η βάση δεδομένων απέτυχε στον έλεγχο ακεραιότητας:\n{self.db.path}\n\nΑποτέλεσμα: {self.RAW}", f"Database integrity check failed:\n{self.db.path}\n\nResult: {self.RAW}")

    def test_missing_tables_preserve_schema_identifiers(self):
        path = self.root / "empty.db"
        connection = sqlite3.connect(path)
        connection.close()
        error = self.capture(lambda: self.manager.restore_backup(path))
        tables = "expenses, fields, income, producer, production"
        self.check_dialog(error, f"Το αρχείο SQLite δεν φαίνεται να είναι backup του Fieltra.\n\nΛείπουν πίνακες: {tables}", f"The SQLite file does not appear to be a Fieltra backup.\n\nMissing tables: {tables}", restore=True)

    def test_lifecycle_error_dialogs_live_switch_and_keep_no_semantics(self):
        path = self.root / "missing Ναι.db"
        error = self.capture(lambda: self.manager.restore_backup(path))
        self.page.backup_manager.create_or_update_daily_backup.side_effect = error
        self.page._build_backup_manager = lambda: self.page.backup_manager
        self.page.db = self.db
        self.page._skip_close_backup = False
        profiles = Mock()
        profiles.get.return_value.is_active = False
        controller = SimpleNamespace(window=self.page, profiles=profiles)
        event = QCloseEvent()
        before = self.files()
        cases = (
            (lambda: MainWindow._run_startup_backup(self.page),
             "Δεν ήταν δυνατή η δημιουργία του αυτόματου ημερήσιου backup κατά την εκκίνηση.\n\n", "Could not create the automatic daily backup at startup.\n\n", "", "", QMessageBox.StandardButton.Ok),
            (lambda: MainWindow.closeEvent(self.page, event),
             "Το αυτόματο backup κατά το κλείσιμο απέτυχε.\n\n", "The automatic backup at shutdown failed.\n\n", "\n\nΘέλεις να κλείσεις την εφαρμογή χωρίς νέο backup;", "\n\nClose the application without a new backup?", QMessageBox.StandardButton.No),
            (lambda: ApplicationController.switch_profile(controller, "other"),
             "Δεν δημιουργήθηκε backup του τρέχοντος προφίλ.\n\n", "No backup was created for the current profile.\n\n", "\n\nΝα συνεχιστεί η αλλαγή προφίλ;", "\n\nContinue switching profiles?", QMessageBox.StandardButton.No),
        )
        for action, el_prefix, en_prefix, el_suffix, en_suffix, answer in cases:
            self.page._closing = False
            errors = []
            def inspect():
                box = QApplication.activeModalWidget()
                try:
                    for language in ("el", "en", "el"):
                        self.language.set_language(language, persist=False)
                        self.language.apply_to(box)
                        expected = (en_prefix + f"Backup file not found:\n{path}" + en_suffix if language == "en" else el_prefix + str(error) + el_suffix)
                        self.assertEqual(expected, box.text())
                        if answer == QMessageBox.StandardButton.No:
                            self.assertIs(box.button(answer), box.defaultButton())
                except BaseException as exc:
                    errors.append(exc)
                finally:
                    box.button(answer).click()
            QTimer.singleShot(0, inspect)
            action()
            if errors:
                raise errors[0]
            self.assertEqual(before, self.files())
        self.assertFalse(event.isAccepted())
        profiles.set_active.assert_not_called()
