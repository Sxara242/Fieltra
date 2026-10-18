from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .database import BASE_DIR, Database
from .language import combo_source_text
from .crud import CrudPage
from .widgets import area_input, date_input, money_input, quantity_input, required_text


def _table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setAlternatingRowColors(True)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return t


class DashboardPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        layout = QVBoxLayout(self)

        title = QLabel("Fieltra")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Συνολική εικόνα εκμετάλλευσης")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        self.production = self._card("Παραγωγή", "0,000 kg")
        self.income = self._card("Έσοδα", "0,00 €")
        self.expenses = self._card("Έξοδα", "0,00 €")
        self.balance = self._card("Καθαρό αποτέλεσμα", "0,00 €")
        grid.addWidget(self.production[0], 0, 0)
        grid.addWidget(self.income[0], 0, 1)
        grid.addWidget(self.expenses[0], 1, 0)
        grid.addWidget(self.balance[0], 1, 1)
        layout.addLayout(grid)

        backup_box = QGroupBox("Ασφάλεια δεδομένων")
        backup_layout = QHBoxLayout(backup_box)
        backup_layout.addWidget(QLabel("Δημιούργησε αντίγραφο της βάσης δεδομένων."))
        backup_layout.addStretch()
        backup = QPushButton("Δημιουργία Backup")
        backup.clicked.connect(self.create_backup)
        backup_layout.addWidget(backup)
        layout.addWidget(backup_box)
        layout.addStretch()

    def _card(self, caption: str, value: str):
        box = QGroupBox()
        box.setObjectName("metricCard")
        l = QVBoxLayout(box)
        cap = QLabel(caption)
        cap.setObjectName("metricCaption")
        val = QLabel(value)
        val.setObjectName("metricValue")
        l.addWidget(cap)
        l.addWidget(val)
        return box, val

    def refresh(self) -> None:
        prod = self.db.query_one("SELECT COALESCE(SUM(quantity_kg), 0) AS total FROM production")
        inc = self.db.query_one("SELECT COALESCE(SUM(amount), 0) AS total FROM income")
        exp = self.db.query_one("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses")
        p = float(prod["total"])
        i = float(inc["total"])
        e = float(exp["total"])
        self.production[1].setText(f"{p:,.3f} kg".replace(",", "X").replace(".", ",").replace("X", "."))
        self.income[1].setText(f"{i:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
        self.expenses[1].setText(f"{e:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
        self.balance[1].setText(f"{i-e:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))

    def create_backup(self) -> None:
        backup_dir = BASE_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        target = backup_dir / f"fieltra_{stamp}.db"
        shutil.copy2(self.db.path, target)
        QMessageBox.information(self, "Backup", f"Το αντίγραφο δημιουργήθηκε:\n{target}")


class ProducerPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        layout = QVBoxLayout(self)
        title = QLabel("Στοιχεία παραγωγού")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.name = QLineEdit()
        self.tax_id = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(120)

        form = QFormLayout()
        form.addRow("Ονοματεπώνυμο / Επωνυμία", self.name)
        form.addRow("ΑΦΜ", self.tax_id)
        form.addRow("Τηλέφωνο", self.phone)
        form.addRow("Email", self.email)
        form.addRow("Σημειώσεις", self.notes)
        layout.addLayout(form)

        save = QPushButton("Αποθήκευση")
        save.clicked.connect(self.save)
        layout.addWidget(save, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addStretch()
        self.load()

    def load(self) -> None:
        row = self.db.query_one("SELECT * FROM producer WHERE id=1")
        if row:
            self.name.setText(row["name"])
            self.tax_id.setText(row["tax_id"])
            self.phone.setText(row["phone"])
            self.email.setText(row["email"])
            self.notes.setPlainText(row["notes"])

    def save(self) -> None:
        self.db.execute(
            "UPDATE producer SET name=?, tax_id=?, phone=?, email=?, notes=? WHERE id=1",
            (self.name.text().strip(), self.tax_id.text().strip(), self.phone.text().strip(),
             self.email.text().strip(), self.notes.toPlainText().strip()),
        )
        QMessageBox.information(self, "Αποθήκευση", "Τα στοιχεία παραγωγού αποθηκεύτηκαν.")


class FieldsPage(CrudPage):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.selected_field_id: int | None = None

        layout = QVBoxLayout(self)

        title = QLabel("Αγροτεμάχια")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.form_box = QGroupBox("Νέο αγροτεμάχιο")
        form = QFormLayout(self.form_box)

        self.name = QLineEdit()
        self.kaek = QLineEdit()
        self.location = QLineEdit()
        self.area = area_input()
        self.trees = QSpinBox()
        self.trees.setRange(0, 1_000_000)
        self.notes = QLineEdit()

        form.addRow("Ονομασία", self.name)
        form.addRow("ΚΑΕΚ", self.kaek)
        form.addRow("Τοποθεσία", self.location)
        form.addRow("Έκταση", self.area)
        form.addRow("Παραγωγικά δέντρα", self.trees)
        form.addRow("Σημειώσεις", self.notes)

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

        self.table = _table(
            ["Ονομασία", "ΚΑΕΚ", "Τοποθεσία", "Έκταση", "Δέντρα", "Σημειώσεις"]
        )
        self.table.cellClicked.connect(self.load_selected)
        layout.addWidget(self.table)

        self.refresh()

    def save_field(self) -> None:
        name = required_text(self.name, "Ονομασία")
        if name is None:
            return

        values = (
            name,
            self.kaek.text().strip(),
            self.location.text().strip(),
            self.area.value(),
            self.trees.value(),
            self.notes.text().strip(),
        )

        if self.selected_field_id is None:
            self.db.execute(
                """
                INSERT INTO fields
                    (name, kaek, location, area_stremma, productive_trees, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                values,
            )
        else:
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

        self.clear_form()
        self.refresh()

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
            QMessageBox.warning(
                self,
                "Αδυναμία διαγραφής",
                "Το αγροτεμάχιο δεν διαγράφηκε. "
                "Ενδέχεται να χρησιμοποιείται σε άλλες καταχωρήσεις.\n\n"
                f"Λεπτομέρειες: {exc}",
            )
            return

        self.clear_form()
        self.refresh()

    def refresh(self) -> None:
        rows = self.db.query("SELECT * FROM fields ORDER BY name, id")
        self.table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            values = [
                row["name"] or "",
                row["kaek"] or "",
                row["location"] or "",
                f'{float(row["area_stremma"] or 0):.3f}',
                str(int(row["productive_trees"] or 0)),
                row["notes"] or "",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, int(row["id"]))
                self.table.setItem(row_index, column_index, item)

        self.filter_table(self.table, self.search.text())


class ProductionPage(CrudPage):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.selected_production_id: int | None = None

        layout = QVBoxLayout(self)

        title = QLabel("Παραγωγή ανά αγροτεμάχιο")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.form_box = QGroupBox("Νέα καταχώρηση παραγωγής")
        form = QFormLayout(self.form_box)

        self.date = date_input()
        self.field = QComboBox()
        self.quantity = quantity_input()
        self.notes = QLineEdit()

        form.addRow("Ημερομηνία", self.date)
        form.addRow("Αγροτεμάχιο", self.field)
        form.addRow("Παραγωγή", self.quantity)
        form.addRow("Παρατηρήσεις", self.notes)

        buttons = QHBoxLayout()

        self.save_button = QPushButton("Προσθήκη")
        self.save_button.clicked.connect(self.save_production)

        self.cancel_button = QPushButton("Ακύρωση")
        self.cancel_button.clicked.connect(self.clear_form)
        self.cancel_button.setEnabled(False)

        self.delete_button = QPushButton("Διαγραφή")
        self.delete_button.clicked.connect(self.delete_production)
        self.delete_button.setEnabled(False)

        buttons.addWidget(self.save_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.delete_button)
        form.addRow("", buttons)

        layout.addWidget(self.form_box)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Αναζήτηση παραγωγής...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(
            lambda text: self.filter_table(self.table, text)
        )
        layout.addWidget(self.search)

        self.table = _table(
            ["Ημερομηνία", "Αγροτεμάχιο", "Παραγωγή kg", "Παρατηρήσεις"]
        )
        self.table.cellClicked.connect(self.load_selected)
        layout.addWidget(self.table)

        self.refresh()

    def refresh_fields(self, preferred_id=None) -> None:
        if preferred_id is None:
            preferred_id = self.field.currentData()

        self.field.blockSignals(True)
        self.field.clear()
        self.field.addItem("Επίλεξε αγροτεμάχιο", None)

        for row in self.db.query("SELECT id, name FROM fields ORDER BY name, id"):
            self.field.addItem(row["name"], row["id"])

        index = self.field.findData(preferred_id)
        if index >= 0:
            self.field.setCurrentIndex(index)

        self.field.blockSignals(False)

    def save_production(self) -> None:
        field_id = self.field.currentData()
        if field_id is None:
            QMessageBox.warning(
                self,
                "Ελλιπή στοιχεία",
                "Επίλεξε αγροτεμάχιο.",
            )
            self.field.setFocus()
            return

        if self.quantity.value() <= 0:
            QMessageBox.warning(
                self,
                "Ελλιπή στοιχεία",
                "Η παραγωγή πρέπει να είναι μεγαλύτερη από 0 kg.",
            )
            self.quantity.setFocus()
            return

        values = (
            self.date.date().toString("yyyy-MM-dd"),
            field_id,
            "Μαστίχα",
            self.quantity.value(),
            self.notes.text().strip(),
        )

        if self.selected_production_id is None:
            self.db.execute(
                """
                INSERT INTO production
                    (entry_date, field_id, product, quantity_kg, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                values,
            )
        else:
            self.db.execute(
                """
                UPDATE production
                SET entry_date=?,
                    field_id=?,
                    product=?,
                    quantity_kg=?,
                    notes=?
                WHERE id=?
                """,
                (*values, self.selected_production_id),
            )

        self.clear_form()
        self.refresh()

    def load_selected(self, row: int, _column: int) -> None:
        first_item = self.table.item(row, 0)
        if first_item is None:
            return

        production_id = first_item.data(Qt.ItemDataRole.UserRole)
        if production_id is None:
            return

        production = self.db.query_one(
            "SELECT * FROM production WHERE id=?",
            (production_id,),
        )
        if production is None:
            self.refresh()
            return

        self.selected_production_id = int(production["id"])

        parsed_date = QDate.fromString(
            production["entry_date"],
            "yyyy-MM-dd",
        )
        if parsed_date.isValid():
            self.date.setDate(parsed_date)

        self.refresh_fields(production["field_id"])
        self.quantity.setValue(float(production["quantity_kg"] or 0))
        self.notes.setText(production["notes"] or "")

        self.form_box.setTitle("Επεξεργασία παραγωγής")
        self.save_button.setText("Αποθήκευση")
        self.cancel_button.setEnabled(True)
        self.delete_button.setEnabled(True)

    def clear_form(self) -> None:
        self.selected_production_id = None

        self.date.setDate(QDate.currentDate())
        self.refresh_fields(None)
        self.field.setCurrentIndex(0)
        self.quantity.setValue(0)
        self.notes.clear()

        self.form_box.setTitle("Νέα καταχώρηση παραγωγής")
        self.save_button.setText("Προσθήκη")
        self.cancel_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.table.clearSelection()

    def delete_production(self) -> None:
        if self.selected_production_id is None:
            return

        if not self.confirm_delete(
            self,
            "Διαγραφή παραγωγής",
            "Να διαγραφεί η επιλεγμένη καταχώρηση παραγωγής;",
        ):
            return

        self.db.execute(
            "DELETE FROM production WHERE id=?",
            (self.selected_production_id,),
        )

        self.clear_form()
        self.refresh()

    def refresh(self) -> None:
        current_field_id = self.field.currentData()
        self.refresh_fields(current_field_id)

        rows = self.db.query(
            """
            SELECT
                p.id,
                p.entry_date,
                COALESCE(f.name, '') AS field_name,
                p.quantity_kg,
                p.notes
            FROM production p
            LEFT JOIN fields f ON f.id = p.field_id
            ORDER BY p.entry_date DESC, p.id DESC
            """
        )

        self.table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            values = [
                row["entry_date"] or "",
                row["field_name"] or "",
                f'{float(row["quantity_kg"] or 0):.3f}',
                row["notes"] or "",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        int(row["id"]),
                    )
                self.table.setItem(row_index, column_index, item)

        self.filter_table(self.table, self.search.text())


class MoneyPage(QWidget):
    def __init__(self, db: Database, kind: str) -> None:
        super().__init__()
        self.db = db
        self.kind = kind
        is_income = kind == "income"
        layout = QVBoxLayout(self)
        title = QLabel("Έσοδα" if is_income else "Έξοδα")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        form_box = QGroupBox("Νέα καταχώρηση")
        form = QFormLayout(form_box)
        self.date = date_input()
        self.category = QComboBox()
        if not is_income:
            self.category.addItems(["Εργασία", "Λίπανση", "Άρδευση", "Εξοπλισμός", "Μεταφορές", "Άλλο"])
        self.description = QLineEdit()
        self.partner = QLineEdit()
        self.payment = QComboBox()
        self.payment.addItems(["Μετρητά", "Τραπεζική μεταφορά", "Κάρτα", "Πίστωση", "Άλλο"])
        self.amount = money_input()
        self.notes = QLineEdit()
        form.addRow("Ημερομηνία", self.date)
        if not is_income:
            form.addRow("Κατηγορία", self.category)
        form.addRow("Περιγραφή", self.description)
        form.addRow("Πελάτης / Συνεργάτης" if is_income else "Προμηθευτής / Συνεργάτης", self.partner)
        form.addRow("Τρόπος πληρωμής", self.payment)
        form.addRow("Ποσό", self.amount)
        form.addRow("Σημειώσεις", self.notes)
        add = QPushButton("Προσθήκη")
        add.clicked.connect(self.add)
        form.addRow("", add)
        layout.addWidget(form_box)

        headers = ["Ημερομηνία", "Περιγραφή", "Συνεργάτης", "Πληρωμή", "Ποσό", "Σημειώσεις"]
        if not is_income:
            headers.insert(1, "Κατηγορία")
        self.table = _table(headers)
        layout.addWidget(self.table)
        self.refresh()

    def add(self) -> None:
        description = required_text(self.description, "Περιγραφή")
        if description is None:
            return
        values = (
            self.date.date().toString("yyyy-MM-dd"),
            description,
            self.partner.text().strip(),
            combo_source_text(self.payment),
            self.amount.value(),
            self.notes.text().strip(),
        )
        if self.kind == "income":
            self.db.execute(
                "INSERT INTO income(entry_date,description,partner,payment_method,amount,notes) VALUES(?,?,?,?,?,?)",
                values,
            )
        else:
            self.db.execute(
                "INSERT INTO expenses(entry_date,category,description,supplier,payment_method,amount,notes) VALUES(?,?,?,?,?,?,?)",
                (values[0], combo_source_text(self.category), *values[1:]),
            )
        self.description.clear(); self.partner.clear(); self.amount.setValue(0); self.notes.clear()
        self.refresh()

    def refresh(self) -> None:
        if self.kind == "income":
            rows = self.db.query("SELECT * FROM income ORDER BY entry_date DESC, id DESC")
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                values = [row["entry_date"], row["description"], row["partner"],
                          row["payment_method"], f'{row["amount"]:.2f} €', row["notes"]]
                for c, value in enumerate(values):
                    self.table.setItem(r, c, QTableWidgetItem(value))
        else:
            rows = self.db.query("SELECT * FROM expenses ORDER BY entry_date DESC, id DESC")
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                values = [row["entry_date"], row["category"], row["description"], row["supplier"],
                          row["payment_method"], f'{row["amount"]:.2f} €', row["notes"]]
                for c, value in enumerate(values):
                    self.table.setItem(r, c, QTableWidgetItem(value))
