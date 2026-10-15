from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMessageBox, QVBoxLayout, QWidget

from . import audit as _audit
from . import main_window as _main_window
from .database import Database
from .localized_messages import _message
from .year_context import (
    correction_state,
    finish_year_correction,
    initialize_year_context,
    sync_application_year_context,
)
from .year_context_ui import (
    CorrectionMutationGuard,
    EnhancedYearLockPage,
    YearContextBar,
    apply_effective_year_to_new_forms,
)


def _preload_context(args, kwargs) -> None:
    profiles = kwargs.get("profiles")
    if profiles is None and len(args) >= 2:
        possible = args[1]
        if hasattr(possible, "active_profile"):
            profiles = possible

    try:
        if profiles is not None:
            db = Database(profiles.active_profile.database_path)
        else:
            db = Database()
        initialize_year_context(db, reset_temporary=True)
    except Exception:
        # The real MainWindow construction remains the source of truth for DB
        # errors. Preloading only exists so date_input has the active year before
        # recording pages are constructed.
        return


def install_year_context_ui() -> None:
    current = _main_window.MainWindow
    if getattr(current, "_alpha2_year_context", False):
        return

    _main_window.YearLockPage = EnhancedYearLockPage
    _audit.TABLE_LABELS.setdefault("year_context", "Ενεργό Έτος / Διορθώσεις")

    class YearContextMainWindow(current):
        _alpha2_year_context = True

        def __init__(self, *args, **kwargs) -> None:
            _preload_context(args, kwargs)
            super().__init__(*args, **kwargs)
            initialize_year_context(self.db, reset_temporary=False)

            body = self.takeCentralWidget()
            shell = QWidget(self)
            shell_layout = QVBoxLayout(shell)
            shell_layout.setContentsMargins(0, 0, 0, 0)
            shell_layout.setSpacing(0)

            self.year_context_bar = YearContextBar(
                self.db, shell, initial_installation_year=self.profile_manager.initial_installation_year)
            shell_layout.addWidget(self.year_context_bar)
            if body is not None:
                shell_layout.addWidget(body, 1)
            self.setCentralWidget(shell)

            self._year_correction_guard = CorrectionMutationGuard(self.db, self)
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self._year_correction_guard)

            self._refresh_year_context_ui()

        def _refresh_year_context_ui(self) -> None:
            sync_application_year_context(self.db)
            self.year_context_bar.refresh()
            apply_effective_year_to_new_forms(self, self.db)
            for _title, page in getattr(self, "pages", []):
                callback = getattr(page, "refresh_year_context_ui", None)
                if callable(callback):
                    callback()

        def closeEvent(self, event) -> None:
            state = correction_state(self.db)
            if state is not None:
                answer = _message(
                    self,
                    "warning",
                    "Προσωρινή επεξεργασία παλιού έτους",
                    "Επεξεργάζεσαι ακόμη το κλειδωμένο έτος {year}.\n\n"
                    "Αν κλείσεις τώρα, η λειτουργία προσωρινής διόρθωσης θα τερματιστεί και "
                    "στην επόμενη εκκίνηση θα επιστρέψεις στο ενεργό έτος {active_year}.\n\n"
                    "Οι αλλαγές που έχουν ήδη αποθηκευτεί παραμένουν. Να κλείσει η εφαρμογή;",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                    year=state.year,
                    active_year=state.active_year,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return

            super().closeEvent(event)

            if event.isAccepted():
                if state is not None:
                    finish_year_correction(
                        self.db,
                        outcome="Τερματισμός προσωρινής διόρθωσης κατά το κλείσιμο εφαρμογής",
                    )
                app = QApplication.instance()
                if app is not None:
                    app.removeEventFilter(self._year_correction_guard)

    YearContextMainWindow.__name__ = current.__name__
    YearContextMainWindow.__qualname__ = current.__qualname__
    YearContextMainWindow.__module__ = current.__module__
    _main_window.MainWindow = YearContextMainWindow
