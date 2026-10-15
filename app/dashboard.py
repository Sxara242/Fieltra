from __future__ import annotations

from PySide6.QtCore import Qt

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .localized_messages import _text, _language, _message
from .backup_manager import BackupError, BackupManager
from .backup_error_ui import show_backup_error
from .database import BASE_DIR, Database
from .report_quantities import quantities, quantity_text, money_total
from .year_context import effective_working_year


class DashboardPage(QWidget):
    def _composed_text(self, widget, template, **values):
        if not hasattr(self, "_composed_specs"):
            self._composed_specs = {}
            controller = _language()
            if controller is not None:
                controller.language_changed.connect(self._refresh_composed_text)
        if isinstance(widget, QGroupBox):
            widget.setProperty("mastixaI18nSkipTitle", True)
        else:
            widget.setProperty("mastixaI18nSkipText", True)
            widget.setTextFormat(widget.textFormat().PlainText)
        self._composed_specs[widget] = (template, values)
        self._refresh_composed_text()

    def _refresh_composed_text(self, *_args):
        for widget, (template, values) in self._composed_specs.items():
            text = _text(template, **{key: value() if callable(value) else value
                                     for key, value in values.items()})
            if isinstance(widget, QGroupBox):
                widget.setTitle(text)
            else:
                widget.setText(text)

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.backup_manager = self._build_backup_manager()

        layout = QVBoxLayout(self)

        title = QLabel("Fieltra")
        title.setObjectName("pageTitle")
        self.subtitle = QLabel("Συνολική εικόνα εκμετάλλευσης")
        self.subtitle.setObjectName("pageSubtitle")
        layout.addWidget(title)
        layout.addWidget(self.subtitle)

        grid = QGridLayout()
        self.production = self._card("Παραγωγή", "—")
        self.income = self._card("Έσοδα", "0,00 €")
        self.expenses = self._card("Έξοδα", "0,00 €")
        self.balance = self._card("Καθαρό αποτέλεσμα", "0,00 €")
        grid.addWidget(self.production[0], 0, 0)
        grid.addWidget(self.income[0], 0, 1)
        grid.addWidget(self.expenses[0], 1, 0)
        grid.addWidget(self.balance[0], 1, 1)
        layout.addLayout(grid)

        safety_box = QGroupBox()
        self.safety_box = safety_box
        safety_layout = QVBoxLayout(safety_box)

        safety_title = QLabel("Ασφάλεια δεδομένων")
        safety_title.setStyleSheet(
            "font-weight: 700; font-size: 15px; color: #26382f;"
        )
        safety_layout.addWidget(safety_title)

        self.backup_status = QLabel()
        self.backup_status.setWordWrap(True)
        safety_layout.addWidget(self.backup_status)

        self.auto_backup_status = QLabel()
        self.auto_backup_status.setWordWrap(True)
        self.auto_backup_status.setStyleSheet("color: #67746d;")
        safety_layout.addWidget(self.auto_backup_status)

        buttons = QHBoxLayout()

        create_button = QPushButton("Δημιουργία Backup")
        create_button.clicked.connect(self.create_backup)
        buttons.addWidget(create_button)

        restore_button = QPushButton("Επαναφορά Backup")
        restore_button.clicked.connect(self.restore_backup)
        buttons.addWidget(restore_button)

        open_button = QPushButton("Φάκελος Backups")
        open_button.clicked.connect(self.open_backup_folder)
        buttons.addWidget(open_button)

        buttons.addStretch()
        safety_layout.addLayout(buttons)

        layout.addWidget(safety_box)
        layout.addStretch()

        self.refresh()

    def _build_backup_manager(self) -> BackupManager:
        saved_dir = self.db.get_app_setting("backup_dir", "").strip()
        backup_dir = Path(saved_dir) if saved_dir else BASE_DIR / "backups"
        kwargs = {
            "database_path": self.db.path,
            "auto_keep": self.db.get_app_setting_int(
                "auto_backup_keep", 30, minimum=1, maximum=365
            ),
            "pre_restore_keep": self.db.get_app_setting_int(
                "pre_restore_keep", 10, minimum=1, maximum=100
            ),
        }
        try:
            return BackupManager(backup_dir=backup_dir, **kwargs)
        except OSError:
            # A saved external/network path may be unavailable. Never block
            # the Dashboard; fall back to the local application backup folder.
            return BackupManager(backup_dir=BASE_DIR / "backups", **kwargs)

    def _card(self, caption: str, value: str):
        box = QGroupBox()
        box.setObjectName("metricCard")
        card_layout = QVBoxLayout(box)

        caption_label = QLabel(caption)
        caption_label.setObjectName("metricCaption")

        value_label = QLabel(value)
        value_label.setObjectName("metricValue")

        card_layout.addWidget(caption_label)
        card_layout.addWidget(value_label)
        return box, value_label

    @staticmethod
    def _money(value: float) -> str:
        return (
            f"{value:,.2f} €"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    def refresh(self) -> None:
        self.backup_manager = self._build_backup_manager()
        farm_name = self.db.get_app_setting("farm_name", "").strip()
        self._composed_text(self.subtitle, "Συνολική εικόνα εκμετάλλευσης — {farm_name}" if farm_name else "Συνολική εικόνα εκμετάλλευσης", farm_name=farm_name)

        year = effective_working_year(self.db)
        production = quantities(self.db, year=year)
        income = money_total(self.db, "income", year)
        expenses = money_total(self.db, "expenses", year)
        self.production[1].setProperty("mastixaI18nSkipText", True)
        self.production[1].setTextFormat(Qt.TextFormat.PlainText)
        self.production[1].setWordWrap(True)
        self.production[1].setText(quantity_text(production))

        self.income[1].setText(self._money(income))
        self.expenses[1].setText(self._money(expenses))
        self.balance[1].setText(self._money(income - expenses))

        self._refresh_backup_status()
        if hasattr(self, "farm_home"):
            self.farm_home.refresh()

    def refresh_year_context_ui(self):
        self.refresh()

    def _refresh_backup_status(self) -> None:
        auto_enabled = self.db.get_app_setting_bool(
            "auto_backup_enabled", True
        )
        if auto_enabled:
            self._composed_text(self.auto_backup_status, 'Αυτόματο ημερήσιο backup: ενεργό — κρατούνται έως {value0} αυτόματα backups. Τα χειροκίνητα backups δεν διαγράφονται αυτόματα.', value0=self.backup_manager.auto_keep)
        else:
            self._composed_text(self.auto_backup_status, 'Αυτόματο ημερήσιο backup: απενεργοποιημένο. Τα χειροκίνητα backups παραμένουν διαθέσιμα.')

        backups = self.backup_manager.list_backups()

        if not backups:
            self._composed_text(self.backup_status, 'Δεν υπάρχει ακόμα αποθηκευμένο backup.')
            return

        latest = backups[0]
        modified = latest.stat().st_mtime
        from datetime import datetime

        timestamp = datetime.fromtimestamp(modified).strftime(
            "%d/%m/%Y %H:%M"
        )

        auto_count = len(self.backup_manager.list_auto_backups())

        self._composed_text(self.backup_status, 'Τελευταίο backup: {value0} — {timestamp}\nΑυτόματα ημερήσια backups: {auto_count} / {value3}', value0=latest.name, timestamp=timestamp, auto_count=auto_count, value3=self.backup_manager.auto_keep)

    def create_backup(self) -> None:
        try:
            target = self.backup_manager.create_backup()
        except BackupError as exc:
            show_backup_error(
                self, "critical",
                "Αποτυχία Backup",
                exc,
            )
            return

        self._refresh_backup_status()
        _message(self, 'information', 'Backup', 'Το αντίγραφο δημιουργήθηκε επιτυχώς:\n{target}', target=target)

    def restore_backup(self) -> None:
        backup_dir = self.backup_manager.backup_dir
        backup_dir.mkdir(parents=True, exist_ok=True)

        path, _ = QFileDialog.getOpenFileName(
            self,
            _text("Επίλεξε backup για επαναφορά"),
            str(backup_dir),
            "SQLite Database (*.db);;" + _text("Όλα τα αρχεία") + " (*)",
        )
        if not path:
            return

        answer = QMessageBox.warning(
            self,
            "Επαναφορά Backup",
            "Πρόκειται να αντικατασταθούν τα τρέχοντα δεδομένα "
            "με το επιλεγμένο backup.\n\n"
            "Πριν την επαναφορά θα δημιουργηθεί αυτόματα ένα νέο "
            "αντίγραφο ασφαλείας της τρέχουσας βάσης.\n\n"
            "Θέλεις να συνεχίσεις;",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            restored_from, safety_backup = (
                self.backup_manager.restore_backup(Path(path))
            )

            # Ensure any schema additions are created if restoring an older
            # compatible Fieltra database.
            self.db.initialize()
            self.refresh()

        except BackupError as exc:
            show_backup_error(
                self, "critical",
                "Αποτυχία επαναφοράς",
                exc,
            )
            return

        _message(self, 'information', 'Επαναφορά ολοκληρώθηκε', 'Η βάση δεδομένων επαναφέρθηκε επιτυχώς.\n\nΕπαναφορά από:\n{restored_from}\n\nΑυτόματο backup πριν την επαναφορά:\n{safety_backup}\n\nΟι υπόλοιπες σελίδες θα ανανεωθούν όταν τις ανοίξεις.', restored_from=restored_from, safety_backup=safety_backup)

    def open_backup_folder(self) -> None:
        folder = self.backup_manager.backup_dir
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(folder.resolve()))
        )
