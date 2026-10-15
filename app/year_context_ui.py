from __future__ import annotations

from functools import wraps
import re

from PySide6.QtCore import QDate, QEvent, QObject, QRegularExpression, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QDateEdit,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import year_lock as legacy
from .year_context import (
    MAX_YEAR,
    MIN_YEAR,
    active_working_year,
    audit_correction_action,
    begin_year_correction,
    correction_state,
    effective_working_year,
    finish_year_correction,
    is_year_physically_locked,
    qdate_in_year,
    set_active_working_year,
    sync_application_year_context,
    permanently_unlock_year,
    require_writable_years,
)


from .localized_messages import _language, _text, _message


def working_year_mutation(*, selection=None, reset=None):
    """Guard direct catalog mutations using the existing effective-year lock.

    Catalog rows have no annual date; their interactive writes belong to the
    effective working context. Guard the callable, not just its button. Existing
    record drafts remain visible; rejected new entries return to their defaults.
    """
    def decorate(action):
        @wraps(action)
        def guarded(page, *args, **kwargs):
            year = effective_working_year(page.db)
            try:
                require_writable_years(page.db, (year,))
            except ValueError:
                legacy.warn_locked_year(page, page.db, year)
                if reset and selection and getattr(page, selection) is None:
                    getattr(page, reset)()
                return
            return action(page, *args, **kwargs)
        return guarded
    return decorate


def _editing_ancestor(widget: QWidget) -> bool:
    current: QObject | None = widget
    selection = widget.property("mastixaWorkingYearSelection")
    while current is not None:
        try:
            values = vars(current)
        except TypeError:
            values = {}
        for name, value in values.items():
            if selection and name != selection:
                continue
            if name.startswith("selected_") and name.endswith("_id") and value is not None:
                return True
        current = current.parent()
    return False


def apply_effective_year_to_new_forms(root: QWidget, db) -> None:
    """Move new-entry date controls to the effective working year.

    Only date controls created by app.widgets.date_input opt in through the
    mastixaWorkingYearDate property. Existing records currently being edited are
    deliberately left untouched.
    """

    target_year = effective_working_year(db)
    for edit in root.findChildren(QDateEdit):
        if not edit.property("mastixaWorkingYearDate"):
            continue
        if _editing_ancestor(edit):
            continue
        current = edit.date()
        if not current.isValid():
            continue
        edit.setDate(qdate_in_year(target_year, current))


def refresh_transaction_controls(page) -> None:
    """Re-evaluate a cached edit without reloading or discarding its draft."""
    specs = {
        'ProductionPage': ('selected_production_id', 'date', 'save_button', 'delete_button'),
        'MoneyPage': ('selected_money_id', 'date', 'save_button', 'delete_button'),
        'SalesPage': ('selected_sale_id', 'sale_date', 'save_button', 'delete_button'),
        'ActivitiesPage': ('selected_activity_id', 'date', 'save_button', 'delete_button'),
        'LaborPage': ('selected_entry_id', 'work_date', 'entry_save_button', 'entry_delete_button'),
        'InventoryPage': ('selected_movement_id', 'movement_date', 'movement_save_button', 'movement_delete_button'),
        'EquipmentPage': ('selected_service_id', 'service_date', 'service_save', 'service_delete'),
        'PlantProtectionPage': ('selected_id', 'date', 'save_button', 'delete_button'),
        'PlantingsPage': ('selected_id', 'planting_date', 'save_button', 'delete_button'),
    }
    spec = specs.get(type(page).__name__)
    if spec is None:
        return
    selected, date, save, delete = spec
    if not hasattr(page, date):
        # Inventory's movement form may still await its visible-paint phase.
        return
    record_id = getattr(page, selected)
    # The form date alone is insufficient for an edit moved to another year.
    record_year = None
    for method in ('_record_year', '_entry_year', '_movement_record_year', '_service_year'):
        callback = getattr(page, method, None)
        if record_id is not None and callable(callback):
            record_year = callback(record_id)
            break
    from .year_context import is_year_write_blocked
    blocked = is_year_write_blocked(page.db, getattr(page, date).date().year())
    if record_year is not None:
        blocked = blocked or is_year_write_blocked(page.db, record_year)
    automatic = False
    if type(page).__name__ == 'MoneyPage' and record_id is not None:
        row = page.db.query_one(f'SELECT * FROM {page._money_table_name()} WHERE id=?', (record_id,))
        automatic = bool(row and 'source_type' in row.keys() and row['source_type'])
    if type(page).__name__ == 'InventoryPage' and record_id is not None:
        row = page.db.query_one('SELECT * FROM inventory_movements WHERE id=?', (record_id,))
        automatic = bool(row and 'source_type' in row.keys() and row['source_type'])
    for attr, enabled in ((save, not blocked and not automatic), (delete, record_id is not None and not blocked and not automatic)):
        button = getattr(page, attr, None)
        if button is not None:
            button.setEnabled(enabled)
    button = getattr(page, save, None)
    if button is not None:
        button.setText(_text('Αυτόματο' if automatic else 'Κλειδωμένο' if blocked else 'Αποθήκευση' if record_id is not None else 'Προσθήκη'))
    box = next((getattr(page, attr) for attr in ('form_box', 'entry_box', 'movement_box', 'service_box')
                if hasattr(page, attr)), None)
    if box is not None and hasattr(page, '_composed_text') and not automatic:
        if blocked:
            page._composed_text(box, 'Κλειδωμένο έτος {year} — Μόνο προβολή', year=record_year or getattr(page, date).date().year())
        elif correction_state(page.db) is not None:
            page._composed_text(box, 'Προσωρινή διόρθωση — Έτος {year}', year=effective_working_year(page.db))
        else:
            page._composed_text(box, 'Επεξεργασία καταχώρησης' if record_id is not None else 'Νέα καταχώρηση')


def change_active_year(parent, db, year: int, notify, *, confirmed=False) -> bool:
    if correction_state(db) is not None or year == active_working_year(db):
        return False
    if not confirmed:
        previous = active_working_year(db)
        answer = _message(
            parent, "question", "Αλλαγή ενεργού έτους εργασίας",
            "Να αλλάξει το ενεργό έτος από {current_year} σε {destination_year};\n\n"
            "Οι φόρμες θα ενημερωθούν για το νέο έτος.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
            current_year=previous, destination_year=year,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
    set_active_working_year(db, year)
    notify()
    _message(parent, "information", "Ενεργό έτος εργασίας",
             "Το ενεργό έτος άλλαξε επιτυχώς σε {year}.", year=year)
    return True


class YearContextBar(QFrame):
    def __init__(self, db, parent: QWidget | None = None, *, initial_installation_year=None) -> None:
        super().__init__(parent)
        self.db = db
        self.initial_installation_year = initial_installation_year
        self._offered_year_range = None
        self.setObjectName("yearContextBar")
        self.setMinimumHeight(48)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 7, 14, 7)
        row.setSpacing(8)

        self.context_label = QLabel("Ενεργό έτος εργασίας:")
        self.context_label.setStyleSheet("font-weight: 700;")
        row.addWidget(self.context_label)

        self.year_selector = QComboBox()
        self.year_selector.setEditable(True)
        # Four digits plus editing/caret space; the global combo arrow padding
        # makes content-only sizing scroll the first digit out of the editor.
        self.year_selector.setMinimumContentsLength(6)
        self.year_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.year_selector.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.year_selector.setMaxVisibleItems(6)
        self.year_selector.setView(QListView(self.year_selector))
        self.year_selector.view().setUniformItemSizes(True)
        self.year_selector.setCompleter(None)
        self.year_selector.lineEdit().setValidator(QRegularExpressionValidator(
            QRegularExpression('[1-9][0-9]{3}'), self.year_selector))
        self.year_selector.setProperty("mastixaYearContextControl", True)
        self.context_label.setBuddy(self.year_selector)
        # Only a user activation requests a change; refreshes are silent.
        self.year_selector.activated.connect(self._apply_year)
        self.year_selector.lineEdit().returnPressed.connect(self._apply_year)
        row.addWidget(self.year_selector)

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("font-weight: 800;")
        row.addWidget(self.warning_label, 1)

        row.addStretch()

        self.return_button = QPushButton("Έξοδος από προσωρινή διόρθωση")
        self.return_button.setProperty("mastixaYearContextControl", True)
        self.return_button.clicked.connect(self._finish_correction)
        row.addWidget(self.return_button)
        self.return_active_button = QPushButton()
        self.return_active_button.setProperty("mastixaYearContextControl", True)
        self.return_active_button.setProperty("mastixaI18nSkipText", True)
        self.return_active_button.clicked.connect(lambda: self._finish_correction(return_active=True))
        row.addWidget(self.return_active_button)

        for widget in (self.context_label, self.warning_label, self.return_button):
            widget.setProperty("mastixaI18nSkipText", True)
        if _language():
            _language().language_changed.connect(self.refresh)
        self.refresh()

    def _set_visual_state(self, state: str) -> None:
        """Switch semantic banner state without writing theme colours inline."""
        if self.property("yearContextState") == state:
            return
        self.setProperty("yearContextState", state)

        # Dynamic-property selectors are evaluated by the application stylesheet.
        # Re-polish this small banner tree immediately so the state change is
        # visible without waiting for another show/layout event.
        widgets = [self, *self.findChildren(QWidget)]
        for widget in widgets:
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)
            widget.update()

    def _notify_window(self) -> None:
        window = self.window()
        callback = getattr(window, "_refresh_year_context_ui", None)
        if callable(callback):
            callback()
        else:
            sync_application_year_context(self.db)

    def _apply_year(self, _index=None) -> None:
        if correction_state(self.db) is not None:
            self.refresh()
            return
        raw = self.year_selector.currentText().strip()
        if re.fullmatch('[1-9][0-9]{3}', raw) is None:
            _message(self, 'warning', 'Ενεργό έτος εργασίας',
                     'Πληκτρολόγησε έγκυρο τετραψήφιο έτος (1000–9999).')
            self.refresh()
            return
        target = int(raw)
        try:
            change_active_year(self, self.db, target, self._notify_window)
        finally:
            # Refusal or a failed database write restores the persisted year.
            self.refresh()

    def _finish_correction(self, *, return_active=False) -> None:
        state = correction_state(self.db)
        if state is None:
            return
        answer = _message(
            self, "question",
            "Ολοκλήρωση διορθώσεων",
            ("Να ολοκληρωθούν οι διορθώσεις στο {year} και να επιστρέψεις "
             "στο ενεργό έτος {active_year};\n\nΤο παλιό έτος παραμένει κλειδωμένο.")
            if return_active else
            "Να τερματιστεί η προσωρινή διόρθωση; Θα παραμείνεις στο έτος {year} — Μόνο προβολή.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
            year=state.year, active_year=state.active_year,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        finish_year_correction(self.db, stay_on_year=not return_active)
        self._notify_window()
        self.refresh()

    def refresh(self) -> None:
        sync_application_year_context(self.db)
        active = active_working_year(self.db)
        state = correction_state(self.db)

        blocked = self.year_selector.blockSignals(True)
        current = QDate.currentDate().year()
        first = self.initial_installation_year
        offered = (max(MIN_YEAR, first - 2), min(MAX_YEAR, current + 1)) if type(first) is int else None
        if offered != self._offered_year_range:
            self.year_selector.clear()
            # Unknown legacy dates are never replaced by today's installation year.
            # Implausibly broad ranges use manual entry instead of a huge popup.
            if offered and 0 < offered[1] - offered[0] + 1 < 100:
                for year in range(offered[0], offered[1] + 1):
                    self.year_selector.addItem(str(year), year)
            self._offered_year_range = offered
        self.year_selector.setCurrentIndex(self.year_selector.findData(active))
        self.year_selector.setEditText(str(active))
        self.year_selector.view().setMaximumHeight(
            max(self.fontMetrics().height() + 6, self.year_selector.view().sizeHintForRow(0)) * 6
            + 2 * self.year_selector.view().frameWidth())
        self.year_selector.blockSignals(blocked)
        self.year_selector.setAccessibleName(_text("Ενεργό έτος εργασίας:"))
        self.year_selector.setToolTip(_text('Πληκτρολόγησε έτος και πάτησε Enter.'))
        if first is None:
            self.year_selector.setToolTip(_text(
                'Η αρχική χρονολογία εγκατάστασης δεν είναι γνωστή. Πληκτρολόγησε έτος και πάτησε Enter.'))
        self.return_active_button.setVisible(state is not None)

        if state is None:
            self.context_label.setText(_text("Ενεργό έτος εργασίας:"))
            self.year_selector.setVisible(True)
            self.warning_label.clear()
            self.warning_label.setVisible(False)
            self.return_button.setVisible(False)
            self._set_visual_state("active")
            if is_year_physically_locked(self.db, active):
                self.warning_label.setText(_text("Κλειδωμένο έτος {year} — Μόνο προβολή", year=active))
                self.warning_label.setVisible(True)
            return

        self.context_label.setText(_text("Επεξεργασία έτους: {year} — προσωρινό mode", year=state.year))
        self.year_selector.setVisible(False)
        self.warning_label.setText(
            _text("ΠΡΟΣΟΧΗ: Επεξεργάζεσαι το κλειδωμένο έτος {year} — "
                  "Τρέχον έτος: {active_year}", year=state.year, active_year=state.active_year)
        )
        self.warning_label.setVisible(True)
        self.return_button.setText(_text("Έξοδος από προσωρινή διόρθωση"))
        self.return_active_button.setText(_text("Επιστροφή στο ενεργό έτος {active_year}", active_year=state.active_year))
        self.return_button.setVisible(True)
        self._set_visual_state("correction")


class CorrectionMutationGuard(QObject):
    """Warn immediately before a mutating UI action during old-year correction."""

    _TOKENS = (
        "προσθή",
        "αποθήκε",
        "διαγραφ",
        "καταχώ",
        "ενημέρ",
        "ολοκληρώ",
        "παραλείφ",
        "εκκρεμότητα",
        "add",
        "save",
        "delete",
        "post",
        "update",
        "complete",
        "skip",
        "pending",
    )

    def __init__(self, db, window: QWidget) -> None:
        super().__init__(window)
        self.db = db
        self.window = window
        self._prompting = False

    @classmethod
    def is_mutating_text(cls, text: str) -> bool:
        value = str(text or "").strip().casefold()
        if not value:
            return False
        if "ρυθμίσεων" in value or "settings" in value:
            return False
        return any(token in value for token in cls._TOKENS)

    def eventFilter(self, watched, event) -> bool:
        if self._prompting:
            return False
        # Most application events cannot activate a mutation. Keep the existing
        # mouse AND keyboard routes, but resolve context only for eligible
        # buttons. Resolve it afresh so profile/correction changes stay visible.
        relevant = False
        # Confirm before Qt starts the button gesture. Opening a modal on
        # release clears QAbstractButton's pressed state, losing an accepted
        # mouse click; Return can emit clicked() on key press before release.
        if event.type() == QEvent.Type.MouseButtonPress:
            relevant = event.button() == Qt.MouseButton.LeftButton
        elif event.type() == QEvent.Type.KeyPress:
            relevant = event.key() in {
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
                Qt.Key.Key_Space,
            }
        if not relevant:
            return False

        if not isinstance(watched, QAbstractButton):
            return False
        if watched.property("mastixaYearContextControl"):
            return False
        if watched.window() is not self.window:
            return False
        if not watched.isEnabled() or not self.is_mutating_text(watched.text()):
            return False

        state = correction_state(self.db)
        if state is None:
            return False

        self._prompting = True
        try:
            answer = _message(
                self.window, "warning",
                "Προσωρινή επεξεργασία παλιού έτους",
                "Επεξεργάζεσαι το κλειδωμένο έτος {year}.\n\n"
                "Ενέργεια: {action}\n"
                "Αιτιολογία: {reason}\n\n"
                "Να συνεχιστεί η ενέργεια;",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
                year=state.year, action=watched.text, reason=state.reason,
            )
        finally:
            self._prompting = False

        if answer != QMessageBox.StandardButton.Yes:
            return True
        audit_correction_action(self.db, watched.text())
        return False


class EnhancedYearLockPage(legacy.YearLockPage):
    """Year-lock UI with a safe in-memory correction mode."""

    def __init__(self, db) -> None:
        self._management_year_initialized = False
        self._management_active_year = None
        super().__init__(db)

        box = QGroupBox("Ενέργειες κλειδωμένου έτους")
        box_layout = QVBoxLayout(box)

        self.correction_banner = QLabel()
        self.correction_banner.setProperty("mastixaI18nSkipText", True)
        self.correction_banner.setTextFormat(Qt.TextFormat.PlainText)
        self.correction_banner.setWordWrap(True)
        self.correction_banner.setStyleSheet(
            "font-weight: 800; padding: 8px; background: #7c2d12; color: white;"
        )
        box_layout.addWidget(self.correction_banner)

        reason_row = QHBoxLayout()
        reason_row.addWidget(QLabel("Αιτία ενέργειας"))
        self.correction_reason = QLineEdit()
        self.correction_reason.setPlaceholderText(
            "Π.χ. Ξεχασμένο έξοδο ή διόρθωση παραστατικού"
        )
        reason_row.addWidget(self.correction_reason, 1)
        box_layout.addLayout(reason_row)

        buttons = QHBoxLayout()
        self.edit_locked_button = QPushButton("Επεξεργασία κλειδωμένου έτους")
        self.edit_locked_button.setProperty("mastixaYearContextControl", True)
        self.edit_locked_button.clicked.connect(self.begin_correction)
        buttons.addWidget(self.edit_locked_button)
        self.unlock_button.setText("Μόνιμο ξεκλείδωμα έτους")
        buttons.addWidget(self.unlock_button)

        self.finish_correction_button = QPushButton(
            "Ολοκλήρωση διορθώσεων & επανακλείδωμα"
        )
        self.finish_correction_button.setProperty("mastixaYearContextControl", True)
        self.finish_correction_button.clicked.connect(self.finish_correction)
        buttons.addWidget(self.finish_correction_button)
        buttons.addStretch()
        box_layout.addLayout(buttons)

        root = getattr(self, "content_layout", self.layout())
        root.insertWidget(max(0, root.count() - 2), box)

        # Lock state and active working year are separate concepts.
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Έτος",
                "Κατάσταση",
                "Κλειδώθηκε",
                "Ξεκλειδώθηκε",
                "Αιτιολογία",
                "Ενεργό έτος",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        if _language():
            _language().language_changed.connect(self._refresh_correction_controls)
        self.refresh()

    def _available_years(self) -> list[int]:
        years = set(super()._available_years())
        active = active_working_year(self.db)
        years.add(active)
        if active < MAX_YEAR:
            years.add(active + 1)
        state = correction_state(self.db)
        if state is not None:
            years.add(state.year)
        return sorted(years, reverse=True)

    def _update_button_state(self) -> None:
        year = self.year.currentData()
        if year is None:
            self.lock_button.setEnabled(False)
            self.unlock_button.setEnabled(False)
            if hasattr(self, "edit_locked_button"):
                self.edit_locked_button.setEnabled(False)
            return

        value = int(year)
        physical_lock = is_year_physically_locked(self.db, value)
        state = correction_state(self.db)
        in_correction = state is not None

        self.lock_button.setEnabled(not physical_lock and not in_correction)
        self.unlock_button.setEnabled(physical_lock and not in_correction)
        if hasattr(self, "edit_locked_button"):
            self.edit_locked_button.setEnabled(physical_lock and not in_correction)
            self.finish_correction_button.setEnabled(in_correction)
            self._refresh_correction_controls()

    def refresh(self) -> None:
        had_selection = (
            hasattr(self, "year")
            and self.year.currentData() is not None
            and self._management_year_initialized
        )
        previous = self.year.currentData() if had_selection else None

        super().refresh()

        active = active_working_year(self.db)
        for row in range(self.table.rowCount()):
            year_item = self.table.item(row, 0)
            if year_item is None:
                continue
            raw_year = year_item.data(Qt.ItemDataRole.UserRole)
            try:
                row_year = int(raw_year)
            except (TypeError, ValueError):
                continue
            active_item = QTableWidgetItem("✓" if row_year == active else "")
            active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            active_item.setToolTip(
                "Ενεργό έτος εργασίας" if row_year == active else ""
            )
            self.table.setItem(row, 5, active_item)

        if not self._management_year_initialized or self._management_active_year != active:
            active = active_working_year(self.db)
            index = self.year.findData(active)
            if index >= 0:
                self.year.setCurrentIndex(index)
            self._management_year_initialized = True
            self._management_active_year = active
        elif previous is not None:
            index = self.year.findData(previous)
            if index >= 0:
                self.year.setCurrentIndex(index)

        if hasattr(self, "correction_banner"):
            self._refresh_correction_controls()

    def _refresh_correction_controls(self) -> None:
        state = correction_state(self.db)
        if state is None:
            self.correction_banner.setText(
                _text("Για ξεχασμένη εγγραφή ή διόρθωση, άνοιξε προσωρινά μόνο το "
                      "κλειδωμένο έτος που χρειάζεσαι. Το κανονικό ενεργό έτος δεν αλλάζει.")
            )
            selected = self.year.currentData()
            active = active_working_year(self.db)
            if selected is not None and int(selected) != active:
                self.correction_banner.setText(self.correction_banner.text() + '\n' +
                    _text('Έτος προς διαχείριση: {year} — Ενεργό έτος εργασίας: {active_year}',
                          year=selected, active_year=active))
            self.finish_correction_button.setVisible(False)
            self.edit_locked_button.setVisible(True)
            self.correction_reason.setEnabled(True)
            return

        self.correction_banner.setText(
            _text("ΠΡΟΣΟΧΗ: Επεξεργάζεσαι προσωρινά το κλειδωμένο έτος {year}. "
                  "Το ενεργό έτος παραμένει {active_year}. Αιτιολογία: {reason}",
                  year=state.year, active_year=state.active_year, reason=state.reason)
        )
        self.edit_locked_button.setVisible(False)
        self.finish_correction_button.setVisible(True)
        self.correction_reason.setEnabled(False)

    def _notify_context_changed(self) -> None:
        window = self.window()
        callback = getattr(window, "_refresh_year_context_ui", None)
        if callable(callback):
            callback()
        else:
            sync_application_year_context(self.db)

    def lock_year(self) -> None:
        year = self.year.currentData()
        if year is None:
            return
        value = int(year)
        if is_year_physically_locked(self.db, value):
            return
        super().lock_year()
        if not is_year_physically_locked(self.db, value):
            return

        if value == active_working_year(self.db) and value < MAX_YEAR:
            next_year = value + 1
            answer = _message(self, 'question', 'Μετάβαση στο επόμενο έτος', 'Το {value} κλειδώθηκε. Να μεταβείς στο ενεργό έτος {next_year};', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes, value=value, next_year=next_year)
            if answer == QMessageBox.StandardButton.Yes:
                # The preceding existing Yes/No dialog already names both
                # years and explicitly confirms this exact transition.
                change_active_year(self, self.db, next_year, self._notify_context_changed, confirmed=True)
        self.refresh()

    def unlock_year(self) -> None:
        if correction_state(self.db) is not None:
            _message(
                self, "warning",
                "Προσωρινή διόρθωση",
                "Ολοκλήρωσε πρώτα την προσωρινή διόρθωση πριν κάνεις μόνιμο ξεκλείδωμα.",
            )
            return
        year = self.year.currentData()
        if year is None or not is_year_physically_locked(self.db, int(year)):
            return
        note = self.correction_reason.text()
        if not note.strip():
            _message(self, "warning", "Ξεκλείδωμα έτους", "Συμπλήρωσε αιτία ενέργειας.")
            self.correction_reason.setFocus()
            return
        answer = _message(self, "warning", "Μόνιμο ξεκλείδωμα έτους",
                          "Να ξεκλειδωθεί μόνιμα το έτος {year};\n\nΑιτία ενέργειας: {reason}",
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                          QMessageBox.StandardButton.No, year=int(year), reason=note)
        if answer != QMessageBox.StandardButton.Yes:
            return
        permanently_unlock_year(self.db, int(year), note)
        self._notify_context_changed()
        self.refresh()

    def begin_correction(self) -> None:
        year = self.year.currentData()
        if year is None:
            return
        value = int(year)
        if not is_year_physically_locked(self.db, value):
            _message(
                self, "warning",
                "Προσωρινή διόρθωση",
                "Επίλεξε κλειδωμένο έτος.",
            )
            return
        note = self.correction_reason.text().strip()
        if not note:
            _message(
                self, "warning",
                "Προσωρινή διόρθωση",
                "Συμπλήρωσε αιτιολογία διόρθωσης.",
            )
            self.correction_reason.setFocus()
            return

        active = active_working_year(self.db)
        answer = _message(
            self, "warning",
            "Επεξεργασία κλειδωμένου έτους",
            "Θα ανοίξει προσωρινά για διορθώσεις το κλειδωμένο έτος {year}.\n\n"
            "Το ενεργό έτος {active_year} θα παραμείνει αποθηκευμένο και θα επανέλθει "
            "μόλις ολοκληρώσεις τις διορθώσεις.\n\n"
            "Κάθε ενέργεια αλλαγής θα εμφανίζει προειδοποίηση. Συνέχεια;",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
            year=value, active_year=active,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            begin_year_correction(self.db, value, note)
        except ValueError:
            existing = correction_state(self.db)
            if existing is not None and existing.year != value:
                _message(self, "warning", "Προσωρινή διόρθωση",
                         "Υπάρχει ήδη προσωρινή επεξεργασία για το έτος {year}.", year=existing.year)
            else:
                _message(self, "warning", "Προσωρινή διόρθωση",
                         "Δεν ήταν δυνατή η έναρξη της προσωρινής διόρθωσης. Έλεγξε το κλειδωμένο έτος και την αιτιολογία.")
            return
        self._notify_context_changed()
        self.refresh()

    def finish_correction(self) -> None:
        state = correction_state(self.db)
        if state is None:
            return
        answer = _message(
            self, "question",
            "Ολοκλήρωση διορθώσεων",
            "Να ολοκληρωθούν οι διορθώσεις στο {year};\n\n"
            "Θα επιστρέψεις στο ενεργό έτος {active_year}. Το {year} "
            "παραμένει κλειδωμένο.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
            year=state.year, active_year=state.active_year,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        finish_year_correction(self.db)
        self.correction_reason.clear()
        self._notify_context_changed()
        self.refresh()

    def refresh_year_context_ui(self) -> None:
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self._management_year_initialized = False
        self.refresh()
