from __future__ import annotations

from .localized_messages import _message, _text

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
)

from .numeric_inputs import NumericSpinBox
from .crud import CrudPage
from .database import Database
from .year_context_ui import working_year_mutation
from .ui_helpers import compact_decimal, table_widget
from .widgets import area_input, required_text
from .gis.kaek_lookup import valid_kaek
from .gis.kaek_worker import controller_for, STATUS_TEXT, REASON_TEXT
from .gis.cadastral import cultivated_area_text


class FieldsPage(CrudPage):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.selected_field_id: int | None = None
        self._lookup_field_id: int | None = None
        self.lookup = controller_for(db, self)

        self._ensure_money_cleanup_trigger()

        layout = QVBoxLayout(self)

        title = QLabel("Αγροτεμάχια")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.form_box = QGroupBox("Νέο αγροτεμάχιο")
        form = QFormLayout(self.form_box)

        self.name = QLineEdit()
        self.kaek = QLineEdit()
        # Do not mask/truncate existing identifiers: legacy data stays readable.
        self.kaek.setPlaceholderText("Προαιρετικό · 12 ψηφία")
        self.kaek.setToolTip("Τυπικός ΚΑΕΚ γεωτεμαχίου: 12 ψηφία, μαζί με τα αρχικά μηδενικά.")
        self.location = QLineEdit()
        self.area = area_input()
        self.area.setSpecialValueText('Δεν έχει δηλωθεί')
        self.trees = NumericSpinBox()
        self.trees.setRange(0, 1_000_000)
        self.notes = QLineEdit()

        form.addRow("Ονομασία", self.name)
        form.addRow("ΚΑΕΚ", self.kaek)
        form.addRow("Τοποθεσία", self.location)
        form.addRow("Δηλωμένη καλλιεργούμενη έκταση", self.area)
        form.addRow("Παραγωγικά δέντρα", self.trees)
        form.addRow("Σημειώσεις", self.notes)

        self.lookup_status = QLabel()
        self.lookup_status.setWordWrap(True)
        self.lookup_status.setProperty("mastixaI18nSkipText", True)
        self.lookup_retry = QPushButton("Επανάληψη ανάκτησης ΚΑΕΚ")
        self.lookup_retry.setEnabled(False)
        self.lookup_retry.clicked.connect(self.retry_kaek)
        lookup_row = QHBoxLayout()
        lookup_row.addWidget(self.lookup_status, 1)
        lookup_row.addWidget(self.lookup_retry)
        form.addRow("Ανάκτηση ΚΑΕΚ", lookup_row)

        buttons = QHBoxLayout()

        self.save_button = QPushButton("Προσθήκη")
        self.save_button.clicked.connect(self.save_field)

        self.cancel_button = QPushButton("Ακύρωση")
        self.cancel_button.clicked.connect(self.clear_form)
        self.cancel_button.setEnabled(False)

        self.delete_button = QPushButton("Διαγραφή")
        self.delete_button.clicked.connect(self.delete_field)
        self.delete_button.setEnabled(False)

        buttons.addWidget(self.save_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.delete_button)
        form.addRow("", buttons)

        layout.addWidget(self.form_box)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Αναζήτηση αγροτεμαχίου...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda text: self.filter_table(self.table, text))
        layout.addWidget(self.search)

        self.table = table_widget(
            ["Ονομασία", "ΚΑΕΚ", "Τοποθεσία", "Δηλωμένη καλλιεργούμενη έκταση", "Δέντρα", "Σημειώσεις", "Ανάκτηση ΚΑΕΚ"]
        )
        self.table.cellClicked.connect(self.load_selected)
        layout.addWidget(self.table)

        self.map_button = QPushButton("Χάρτης αγροτεμαχίου")
        self.map_button.clicked.connect(self.open_map)
        layout.addWidget(self.map_button)
        self.coordinates_button = QPushButton("Εξαγωγή κορυφών / συντεταγμένων")
        self.coordinates_button.clicked.connect(self.export_coordinates)
        layout.addWidget(self.coordinates_button)

        self.cadastre_button = QPushButton("Επίσημος χάρτης Ελληνικού Κτηματολογίου (διαδίκτυο)")
        self.cadastre_button.setToolTip(
            "Ανοίγει στον προεπιλεγμένο περιηγητή. Δεν προσθέτει ΚΑΕΚ ή συντεταγμένες στον σύνδεσμο."
        )
        self.cadastre_button.clicked.connect(self.open_cadastre_map)
        layout.addWidget(self.cadastre_button)
        self.boundary_notice = QLabel(
            "Τα όρια καλλιέργειας μπορεί να διαφέρουν από τα επίσημα κτηματολογικά όρια. "
            "Η καταχώρηση ΚΑΕΚ δεν επαληθεύει τα τοπικά όρια."
        )
        self.boundary_notice.setWordWrap(True)
        layout.addWidget(self.boundary_notice)

        self.lookup.changed.connect(self._lookup_changed)
        from PySide6.QtWidgets import QApplication
        language = getattr(QApplication.instance(), "_mastixa_language_controller", None)
        if language:
            language.language_changed.connect(self._lookup_changed)
        self.refresh()

    def _lookup_changed(self, *_):
        self.refresh()
        self._update_lookup_status()

    def _update_lookup_status(self):
        job = self.lookup.store.job(self._lookup_field_id) if self._lookup_field_id is not None else None
        self.lookup_retry.setEnabled(bool(job and self.lookup.provider
            and self.lookup.provider.supports(job["kaek"]) and job["status"] != "retrieving"))
        if self.lookup.last_error:
            self.lookup_status.setText(_text(self.lookup.last_error))
        elif job:
            status = _text(STATUS_TEXT[job["status"]])
            reason = _text(REASON_TEXT.get(job["reason"], ""))
            self.lookup_status.setText(_text("ΚΑΕΚ {kaek}: {status}", kaek=job["kaek"], status=status) + ("\n" + reason if reason else ""))
        else:
            self.lookup_status.setText("")

    def retry_kaek(self):
        if self._lookup_field_id is not None:
            self.lookup.retry(self._lookup_field_id)

    def open_cadastre_map(self) -> None:
        # User-initiated browser navigation only; no parcel data or lookup API.
        if not QDesktopServices.openUrl(QUrl("https://maps.ktimatologio.gr/")):
            _message(self, "warning", "Αγροτεμάχια",
                     "Δεν ήταν δυνατό να ανοίξει ο περιηγητής. Άνοιξε το https://maps.ktimatologio.gr/ χειροκίνητα.")

    def open_map(self) -> None:
        if self.selected_field_id is None:
            QMessageBox.information(self, "Αγροτεμάχια", "Επίλεξε πρώτα αγροτεμάχιο.")
            return
        from .gis.dialog import ParcelMapDialog
        ParcelMapDialog(self.db, self.selected_field_id, self).exec()

    def export_coordinates(self) -> None:
        from .gis.export_dialog import CoordinateExportDialog
        CoordinateExportDialog(self.db,self.selected_field_id,self).exec()

    def _ensure_money_cleanup_trigger(self) -> None:
        income_columns = {
            row["name"]
            for row in self.db.query("PRAGMA table_info(income)")
        }
        expense_columns = {
            row["name"]
            for row in self.db.query("PRAGMA table_info(expenses)")
        }

        if "field_id" not in income_columns or "field_id" not in expense_columns:
            return

        self.db.execute(
            """
            CREATE TRIGGER IF NOT EXISTS money_field_delete_cleanup
            BEFORE DELETE ON fields
            BEGIN
                UPDATE income
                SET field_id=NULL
                WHERE field_id=OLD.id;

                UPDATE expenses
                SET field_id=NULL
                WHERE field_id=OLD.id;
            END
            """
        )

    @working_year_mutation(selection="selected_field_id", reset="clear_form")
    def save_field(self) -> None:
        name = required_text(self.name, "Ονομασία")
        if name is None:
            return

        kaek = self.kaek.text().strip()
        if kaek and not valid_kaek(kaek):
            _message(self, "warning", "Αγροτεμάχια",
                     "Ο ΚΑΕΚ γεωτεμαχίου πρέπει να περιέχει ακριβώς 12 ψηφία (0–9) ή να μείνει κενός.")
            self.kaek.setFocus()
            return

        values = (
            name,
            kaek,
            self.location.text().strip(),
            self.area.value(),
            self.trees.value(),
            self.notes.text().strip(),
        )

        if self.selected_field_id is None:
            saved_field_id = self.db.execute(
                """
                INSERT INTO fields
                    (name, kaek, location, area_stremma, productive_trees, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                values,
            )
        else:
            saved_field_id = self.selected_field_id
            self.db.execute(
                """
                UPDATE fields
                SET name=?,
                    kaek=?,
                    location=?,
                    area_stremma=?,
                    productive_trees=?,
                    notes=?
                WHERE id=?
                """,
                (*values, self.selected_field_id),
            )

        self._lookup_field_id = saved_field_id
        self.lookup.schedule(saved_field_id)  # Local field commit precedes all network work.
        self.clear_form()
        self.refresh()
        self._update_lookup_status()

    def load_selected(self, row: int, _column: int) -> None:
        first_item = self.table.item(row, 0)
        if first_item is None:
            return

        field_id = first_item.data(Qt.ItemDataRole.UserRole)
        if field_id is None:
            return

        field = self.db.query_one("SELECT * FROM fields WHERE id=?", (field_id,))
        if field is None:
            self.refresh()
            return

        self.selected_field_id = int(field["id"])
        self._lookup_field_id = self.selected_field_id
        self.name.setText(field["name"] or "")
        self.kaek.setText(field["kaek"] or "")
        self.location.setText(field["location"] or "")
        self.area.setValue(float(field["area_stremma"] or 0))
        self.trees.setValue(int(field["productive_trees"] or 0))
        self.notes.setText(field["notes"] or "")

        self.form_box.setTitle("Επεξεργασία αγροτεμαχίου")
        self.save_button.setText("Αποθήκευση")
        self.cancel_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self._update_lookup_status()

    def clear_form(self) -> None:
        self.selected_field_id = None

        self.name.clear()
        self.kaek.clear()
        self.location.clear()
        self.area.setValue(0)
        self.trees.setValue(0)
        self.notes.clear()

        self.form_box.setTitle("Νέο αγροτεμάχιο")
        self.save_button.setText("Προσθήκη")
        self.cancel_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.table.clearSelection()
        self.name.setFocus()

    @working_year_mutation()
    def delete_field(self) -> None:
        if self.selected_field_id is None:
            return

        field_name = self.name.text().strip() or "το επιλεγμένο αγροτεμάχιο"
        if not self.confirm_delete(
            self,
            "Διαγραφή αγροτεμαχίου",
            f'Να διαγραφεί το αγροτεμάχιο «{field_name}»;',
        ):
            return

        try:
            self.db.execute(
                "DELETE FROM fields WHERE id=?",
                (self.selected_field_id,),
            )
        except Exception as exc:
            _message(self, 'warning', 'Αδυναμία διαγραφής', 'Το αγροτεμάχιο δεν διαγράφηκε. Ενδέχεται να χρησιμοποιείται σε άλλες καταχωρήσεις.\n\nΛεπτομέρειες: {exc}', exc=exc)
            return

        self.clear_form()
        self.refresh()

    def refresh(self) -> None:
        rows = self.db.query("SELECT * FROM fields ORDER BY name, id")
        jobs = {row["field_id"]: row["status"] for row in self.db.query(
            "SELECT i.field_id,j.status FROM kaek_lookup_jobs j JOIN kaek_field_identity i USING(field_uuid)"
        )}
        self.table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            values = [
                row["name"] or "",
                row["kaek"] or "",
                row["location"] or "",
                cultivated_area_text(row['area_stremma']),
                str(int(row["productive_trees"] or 0)),
                row["notes"] or "",
                _text(STATUS_TEXT[jobs[row["id"]]]) if row["id"] in jobs else "",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, int(row["id"]))
                self.table.setItem(row_index, column_index, item)

        self.filter_table(self.table, self.search.text())
