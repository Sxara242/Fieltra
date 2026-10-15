from __future__ import annotations

from PySide6.QtCore import QDate, QLocale, QTimer
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from .numeric_inputs import NumericDoubleSpinBox


class EntryForm(QWidget):
    def __init__(self, fields: list[tuple[str, QWidget]], on_save, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for label, widget in fields:
            form.addRow(label, widget)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save = QPushButton("Αποθήκευση")
        save.clicked.connect(on_save)
        row.addWidget(save)
        layout.addLayout(row)


class WorkingYearDateEdit(QDateEdit):
    """Date input whose new-record default follows the active/correction year."""

    def __init__(self, parent=None, *, db=None, selection=None) -> None:
        from .year_context import working_context_date, MIN_YEAR, MAX_YEAR

        super().__init__(working_context_date(db), parent)
        self.working_db = db
        self.setDateRange(QDate(MIN_YEAR, 1, 1), QDate(MAX_YEAR, 12, 31))
        self.setDate(working_context_date(db))
        self.setProperty("mastixaWorkingYearDate", True)
        self.setProperty("mastixaWorkingYearSelection", selection)

    def _editing_existing_record(self) -> bool:
        current = self.parent()
        selection = self.property("mastixaWorkingYearSelection")
        while current is not None:
            try:
                values = vars(current)
            except TypeError:
                values = {}
            for name, value in values.items():
                if selection and name != selection:
                    continue
                normalized = name.casefold()
                if (
                    normalized.startswith("selected")
                    and normalized.endswith("id")
                    and value is not None
                ):
                    return True
            current = current.parent()
        return False

    def setDate(self, date: QDate) -> None:
        value = date
        if (
            isinstance(date, QDate)
            and date.isValid()
            and date == QDate.currentDate()
            and not self._editing_existing_record()
        ):
            try:
                from .year_context import working_context_date

                value = working_context_date(self.working_db)
            except Exception:
                value = date
        super().setDate(value)


def date_input(db=None, *, selection=None) -> QDateEdit:
    from .date_preferences import qt_date_format, selected_date_format, DEFAULT_DATE_FORMAT
    widget = WorkingYearDateEdit(db=db, selection=selection)
    widget.setCalendarPopup(True)
    widget.setDisplayFormat(qt_date_format(selected_date_format(db) if db is not None else DEFAULT_DATE_FORMAT))
    return widget


class UnitLineEdit(QLineEdit):
    """A newly focused unit is replaced on typing; custom unit text stays literal."""

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self, self.selectAll)


def _numeric_spinbox(
    *,
    maximum: float,
    decimals: int,
    suffix: str,
    step: float,
) -> QDoubleSpinBox:
    widget = NumericDoubleSpinBox()

    # Σταθερά "." ως δεκαδικός διαχωριστής ανεξάρτητα από τα Windows/Greek locale.
    widget.setLocale(QLocale.c())

    widget.setRange(0, maximum)
    widget.setDecimals(decimals)
    widget.setSuffix(suffix)
    widget.setSingleStep(step)

    # Χωρίς βελάκια: καθαρή αριθμητική εισαγωγή από το πληκτρολόγιο.
    widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    widget.setAccelerated(True)
    widget.setKeyboardTracking(False)

    return widget


def money_input() -> QDoubleSpinBox:
    return _numeric_spinbox(
        maximum=999_999_999,
        decimals=2,
        suffix=" €",
        step=1.00,
    )


class CompactQuantitySpinBox(NumericDoubleSpinBox):
    """Keep 3-decimal precision but hide trailing zeroes."""

    def textFromValue(self, value: float) -> str:
        if value == 0:
            return ''
        text = f"{value:.{self.decimals()}f}".rstrip("0").rstrip(".")
        return text if self.hasFocus() else text + getattr(self, '_unit_suffix', '')


def quantity_input() -> QDoubleSpinBox:
    widget = CompactQuantitySpinBox()
    widget.setRange(0, 999_999_999)
    widget.setDecimals(3)
    widget.setSuffix(" kg")
    widget.setSingleStep(0.100)
    widget.setKeyboardTracking(False)
    widget.setButtonSymbols(
        QAbstractSpinBox.ButtonSymbols.NoButtons
    )
    return widget


def area_input() -> QDoubleSpinBox:
    widget = CompactQuantitySpinBox()
    widget.setLocale(QLocale.c())
    widget.setRange(0, 999_999)
    widget.setDecimals(3)
    widget.setSuffix(" στρ.")
    widget.setSingleStep(0.001)
    widget.setButtonSymbols(
        QAbstractSpinBox.ButtonSymbols.NoButtons
    )
    widget.setAccelerated(True)
    widget.setKeyboardTracking(False)
    return widget


def required_text(widget: QLineEdit, label: str) -> str | None:
    value = widget.text().strip()
    if not value:
        QMessageBox.warning(widget, "Ελλιπή στοιχεία", f"Συμπλήρωσε το πεδίο «{label}».")
        widget.setFocus()
        return None
    return value
