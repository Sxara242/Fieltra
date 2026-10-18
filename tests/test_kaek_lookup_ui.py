"""Offscreen Save/worker/map tests with only synthetic provider responses."""
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtNetwork import QNetworkInformation
from PySide6.QtWidgets import QApplication

from app.database import Database
from app.fields import FieldsPage
from app.gis.dialog import ParcelMapDialog
from app.gis.geometry import manual_coordinates
from app.gis.kaek_provider import NorthAegeanProvider
from app.gis.kaek_worker import LookupController
from app.gis.store import GeometryStore
from tests.language_fixture import scoped_language
from tests.test_kaek_lookup import KAEK, NOW, Response, dataset


class KaekLookupUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch("app.database.DATA_DIR", self.root / "data"))
        self.enterContext(scoped_language(self.app, "el"))
        self.db = Database(self.root / "farm.db")
        self.page = FieldsPage(self.db)
        self.now = NOW
        self.provider = NorthAegeanProvider(self.root / "cache", Mock(side_effect=lambda *a, **kw: Response(dataset())), lambda: self.now / 1000)
        self.page.lookup.provider = self.provider
        self.page.lookup.store.clock = lambda: self.now
        self.page.name.setText("Synthetic field")
        self.page.kaek.setText(KAEK)
        self.controllers = [self.page.lookup]
        self.addCleanup(self.close_widgets)

    def close_widgets(self):
        for controller in self.controllers:
            controller.stop()
            if controller.active:
                controller.active.join(timeout=3)
                self.assertFalse(controller.active.is_alive())
        self.app.processEvents()
        self.page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def await_status(self, field, expected):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            self.app.processEvents()
            job = self.page.lookup.store.job(field)
            if job and job["status"] == expected:
                return job
            time.sleep(.01)
        self.fail(f"Expected {expected}: {self.page.lookup.store.job(field)}")

    def test_save_is_immediate_worker_responsive_and_map_keeps_both_geometries(self):
        release, entered = threading.Event(), threading.Event()

        def delayed(*args, **kwargs):
            entered.set()
            if not release.wait(2):
                raise TimeoutError("Synthetic worker was not released")
            return Response(dataset())

        self.provider.opener = Mock(side_effect=delayed)
        self.page.save_field()
        field = self.db.query_one("SELECT id FROM fields")[0]
        self.assertEqual("pending", self.page.lookup.store.job(field)["status"])
        self.provider.opener.assert_not_called()  # Save does not wait on the network.
        store = GeometryStore(self.db)
        store.save(field, manual_coordinates("26 38\n26.001 38\n26.001 38.001\n26 38.001", "EPSG:4326"), source="manual")
        before = store.get(field)
        dialog = ParcelMapDialog(self.db, field, self.page)
        try:
            self.await_status(field, "retrieving")
            self.assertTrue(entered.wait(1))
            heartbeat = []
            QTimer.singleShot(0, lambda: heartbeat.append(True))
            self.app.processEvents()
            self.assertTrue(heartbeat)
            release.set()
            self.await_status(field, "retrieved")
            self.assertEqual(before, store.get(field))
            self.assertEqual(1, len(dialog.map.boundaries))
            self.assertIsNotNone(dialog.map.cadastral_item)
            self.assertIn("2026-10-06", dialog.cadastral_info.text())
            self.assertIn("EPSG:2100", dialog.cadastral_info.text())
            self.assertIn("Ανακτήθηκε", self.page.lookup_status.text())
            self.assertEqual("Ανακτήθηκε", self.page.table.item(0, 6).text())
            self.assertFalse(dialog.map.pending)
            with scoped_language(self.app, "en") as language:
                language.apply_to(self.page)
                self.page._lookup_changed()
                dialog._reload_cadastral()
                self.assertIn("Retrieved", self.page.lookup_status.text())
                self.assertIn("Local cultivated-field boundaries remain separate", dialog.cadastral_info.text())
            dialog.map.show_cadastral(False)
            self.assertFalse(dialog.map.cadastral_item.isVisible())
            self.assertTrue(dialog.map.boundaries[0].isVisible())
        finally:
            release.set()
            dialog.map.shutdown()
            dialog.deleteLater()

    def test_offline_queue_automatically_resumes_after_restart_and_backoff(self):
        self.provider.opener = Mock(side_effect=TimeoutError("Synthetic offline"))
        self.page.save_field()
        field = self.db.query_one("SELECT id FROM fields")[0]
        self.await_status(field, "temporary_failure")
        self.page.lookup.stop()
        self.now = self.page.lookup.store.job(field)["next_attempt"]
        self.provider.opener = Mock(side_effect=lambda *a, **kw: Response(dataset()))
        restarted = LookupController(Database(self.db.path), self.provider, self.page, lambda: self.now)
        self.controllers.append(restarted)
        self.await_status(field, "retrieved")
        self.assertEqual(1, self.db.query_one("SELECT count(*) FROM kaek_lookup_jobs")[0])

    def test_queue_error_cannot_undo_successful_field_save(self):
        with patch.object(self.page.lookup.store, "enqueue", side_effect=OSError("Synthetic queue failure")):
            self.page.save_field()
        self.assertEqual(KAEK, self.db.query_one("SELECT kaek FROM fields")[0])
        self.assertIn("αποθηκεύτηκε", self.page.lookup_status.text())
        self.provider.opener.assert_not_called()

    def test_os_connectivity_transition_expedites_once_without_device_transport(self):
        controller = self.page.lookup
        controller.reachability = QNetworkInformation.Reachability.Disconnected
        with patch.object(controller.store, 'connectivity_restored') as restored:
            controller._reachability_changed(QNetworkInformation.Reachability.Online)
            controller._reachability_changed(QNetworkInformation.Reachability.Online)
            restored.assert_called_once()
            controller.stop()
            controller._reachability_changed(QNetworkInformation.Reachability.Disconnected)
            controller._reachability_changed(QNetworkInformation.Reachability.Online)
            restored.assert_called_once()
        self.provider.opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
