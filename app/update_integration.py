from __future__ import annotations

import threading
from shiboken6 import isValid

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .settings import SettingsPage
from .localized_messages import _message
from .update_manager import (
    UpdateError,
    UpdateInfo,
    download_windows_update,
    fetch_update_info,
    launch_windows_installer,
    UPDATE_FEED_MODE,
)
from .version import APP_VERSION, RELEASE_CHANNEL


_INSTALLED = False


class _UpdateSignals(QObject):
    checked = Signal(object)
    failed = Signal(object)
    downloaded = Signal(object, object)

    def deliver(self, name, *values):
        """The page owns this bridge; discard results after its destruction."""
        if not isValid(self):
            return
        try:
            getattr(self, name).emit(*values)
        except RuntimeError:
            # Deletion can race the worker between the validity check and emit.
            if isValid(self):
                raise


def _add_updates_tab(page: SettingsPage) -> None:
    if getattr(page, "_staged", False) and not getattr(page, "_updates_tab_queued", False):
        page._updates_tab_queued = True
        page._add_lazy_settings_tab("Ενημερώσεις", lambda: _add_updates_tab(page))
        return
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(12, 16, 12, 16)
    layout.setSpacing(12)

    box = QGroupBox("Ενημερώσεις εφαρμογής")
    box_layout = QVBoxLayout(box)
    box_layout.setSpacing(10)

    version_label = QLabel(
        f"Εγκατεστημένη έκδοση: {APP_VERSION}   •   Κανάλι: {RELEASE_CHANNEL.capitalize()}"
    )
    page._composed_text(version_label, "Εγκατεστημένη έκδοση: {version}   •   Κανάλι: {channel}", version=APP_VERSION, channel=RELEASE_CHANNEL.capitalize())
    version_label.setStyleSheet("font-weight: 700;")
    box_layout.addWidget(version_label)

    privacy_text = (
        "Ο έλεγχος γίνεται μόνο όταν πατήσεις το κουμπί. Η εφαρμογή διαβάζει ένα "
        "δημόσιο αρχείο ενημερώσεων και δεν στέλνει δεδομένα εκμετάλλευσης, "
        "προφίλ ή χρήσης."
    )
    if UPDATE_FEED_MODE == "staging":
        privacy_text = (
            "Ο έλεγχος γίνεται μόνο όταν πατήσεις το κουμπί. Η εφαρμογή χρησιμοποιεί "
            "τοπικό δοκιμαστικό αρχείο ενημερώσεων και δεν στέλνει δεδομένα "
            "εκμετάλλευσης, προφίλ ή χρήσης."
        )
    privacy_note = QLabel(privacy_text)
    privacy_note.setWordWrap(True)
    box_layout.addWidget(privacy_note)
    if UPDATE_FEED_MODE == "staging":
        staging_note = QLabel("Staging: τοπικό δοκιμαστικό feed · δεν ελέγχονται δημόσιες ενημερώσεις.")
        staging_note.setWordWrap(True)
        box_layout.addWidget(staging_note)

    page._mastixa_update_status = QLabel("Δεν έχει γίνει ακόμη έλεγχος για ενημερώσεις.")
    page._composed_text(page._mastixa_update_status, "Δεν έχει γίνει ακόμη έλεγχος για ενημερώσεις.")
    page._mastixa_update_status.setWordWrap(True)
    box_layout.addWidget(page._mastixa_update_status)

    actions = QHBoxLayout()
    page._mastixa_check_updates_button = QPushButton("Έλεγχος για ενημερώσεις")
    actions.addWidget(page._mastixa_check_updates_button)

    page._mastixa_install_update_button = QPushButton("Λήψη && εγκατάσταση")
    page._mastixa_install_update_button.setVisible(False)
    actions.addWidget(page._mastixa_install_update_button)

    page._mastixa_open_release_button = QPushButton("Άνοιγμα σελίδας έκδοσης")
    page._mastixa_open_release_button.setVisible(False)
    actions.addWidget(page._mastixa_open_release_button)
    actions.addStretch()
    box_layout.addLayout(actions)

    layout.addWidget(box)
    layout.addStretch()
    page.tabs.addTab(tab, "Ενημερώσεις")

    signals = _UpdateSignals(page)
    page._mastixa_update_signals = signals
    page._mastixa_update_info = None

    def set_busy(busy: bool) -> None:
        page._mastixa_check_updates_button.setEnabled(not busy)
        if busy:
            page._composed_text(page._mastixa_update_status, "Έλεγχος για νέα έκδοση…")

    def check_updates() -> None:
        set_busy(True)
        page._mastixa_install_update_button.setVisible(False)
        page._mastixa_open_release_button.setVisible(False)

        def work() -> None:
            try:
                signals.deliver("checked", fetch_update_info())
            except UpdateError as exc:
                signals.deliver("failed", str(exc))
            except Exception as exc:  # defensive UI boundary
                signals.deliver("failed", ("Αποτυχία ελέγχου ενημερώσεων: {error}", str(exc)))

        threading.Thread(target=work, name="mastixa-update-check", daemon=True).start()

    def checked(info: UpdateInfo) -> None:
        page._mastixa_check_updates_button.setEnabled(True)
        page._mastixa_update_info = info
        if not info.is_newer:
            page._composed_text(page._mastixa_update_status, "Έχεις την πιο πρόσφατη διαθέσιμη έκδοση ({version}).", version=APP_VERSION)
            return

        page._composed_text(page._mastixa_update_status, "Νέα έκδοση διαθέσιμη: {version}\n{notes}" if info.notes else "Νέα έκδοση διαθέσιμη: {version}", version=info.version, notes=info.notes)
        page._mastixa_open_release_button.setVisible(True)
        page._mastixa_install_update_button.setVisible(
            info.windows is not None
            and bool(info.windows.url)
            and bool(info.windows.sha256)
        )

    def failed(message) -> None:
        page._mastixa_check_updates_button.setEnabled(True)
        page._mastixa_install_update_button.setEnabled(True)
        template, detail = message if isinstance(message, tuple) else ("Αποτυχία ενημέρωσης: {error}", message)
        page._composed_text(page._mastixa_update_status, template, error=detail)

    def open_release() -> None:
        info = page._mastixa_update_info
        if isinstance(info, UpdateInfo):
            QDesktopServices.openUrl(QUrl(info.release_url))

    def install_update() -> None:
        info = page._mastixa_update_info
        if not isinstance(info, UpdateInfo):
            return
        page._mastixa_install_update_button.setEnabled(False)
        page._composed_text(page._mastixa_update_status, "Λήψη και επαλήθευση Fieltra {version}…", version=info.version)

        def work() -> None:
            try:
                installer = download_windows_update(info)
                signals.deliver("downloaded", info, installer)
            except UpdateError as exc:
                signals.deliver("failed", str(exc))
            except Exception as exc:  # defensive UI boundary
                signals.deliver("failed", ("Αποτυχία λήψης ενημέρωσης: {error}", str(exc)))

        threading.Thread(target=work, name="mastixa-update-download", daemon=True).start()

    def downloaded(info: UpdateInfo, installer) -> None:
        page._mastixa_install_update_button.setEnabled(True)
        answer = _message(
            page, "question",
            "Έτοιμη ενημέρωση",
            "Η έκδοση {version} κατέβηκε και επαληθεύτηκε με SHA-256.\n\n"
            "Να κλείσει τώρα το Fieltra και να ξεκινήσει ο installer;",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
            version=info.version,
        )
        if answer != QMessageBox.StandardButton.Yes:
            page._composed_text(page._mastixa_update_status, "Η έκδοση {version} είναι έτοιμη για εγκατάσταση.", version=info.version)
            return
        try:
            launch_windows_installer(installer)
        except UpdateError as exc:
            failed(str(exc))
            return
        QApplication.instance().quit()

    signals.checked.connect(checked)
    signals.failed.connect(failed)
    signals.downloaded.connect(downloaded)
    page._mastixa_check_updates_button.clicked.connect(check_updates)
    page._mastixa_open_release_button.clicked.connect(open_release)
    page._mastixa_install_update_button.clicked.connect(install_update)


def install_update_ui() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    original_init = SettingsPage.__init__

    def init_with_updates(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        _add_updates_tab(self)

    SettingsPage.__init__ = init_with_updates
    _INSTALLED = True
