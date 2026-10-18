from __future__ import annotations
from .year_filters import YearFilteredPage, populate_year_filter

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .localized_messages import _text, _language, _message
from .database import Database
from .ui_helpers import compact_decimal, table_widget


class UploadCenterPage(YearFilteredPage):
    """
    Local preparation center for a future external upload.

    This page does NOT contact any server. It only:
    - loads a saved cultivation declaration,
    - lets the user choose which sections are included,
    - shows a human-readable preview,
    - exports the exact payload to JSON for inspection/testing.
    """

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
        self.current_payload: dict = {}
        self.current_validation_errors: list[str] = []
        self.current_validation_warnings: list[str] = []
        self.selected_snapshot_id: int | None = None

        self._ensure_schema()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.viewport().setStyleSheet("background: #f5f6f3;")

        content = QWidget()
        content.setObjectName("uploadCenterContent")
        content.setStyleSheet(
            "QWidget#uploadCenterContent { background: #f5f6f3; }"
        )

        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 10, 12, 16)
        layout.setSpacing(12)

        title = QLabel("Κέντρο Αποστολής")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Έλεγχος και προετοιμασία των δεδομένων πριν από μελλοντική αποστολή"
        )
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        declaration_box = QGroupBox()
        declaration_layout = QVBoxLayout(declaration_box)

        declaration_title = QLabel("Επιλογή δήλωσης")
        declaration_title.setStyleSheet(
            "font-weight: 700; font-size: 15px; color: #26382f;"
        )
        declaration_layout.addWidget(declaration_title)

        form = QFormLayout()
        self.year = QComboBox()
        self.year.currentIndexChanged.connect(self.refresh_preview)
        form.addRow("Έτος", self.year)

        self.product = QComboBox()
        self.product.setMinimumWidth(240)
        self.product.currentIndexChanged.connect(self.refresh_preview)
        form.addRow("Προϊόν", self.product)

        self.declaration_status = QLabel("—")
        form.addRow("Κατάσταση", self.declaration_status)
        declaration_layout.addLayout(form)

        layout.addWidget(declaration_box)

        options_box = QGroupBox()
        options_layout = QVBoxLayout(options_box)

        options_title = QLabel("Τι θα περιλαμβάνει το πακέτο")
        options_title.setStyleSheet(
            "font-weight: 700; font-size: 15px; color: #26382f;"
        )
        options_layout.addWidget(options_title)

        check_row = QHBoxLayout()

        self.include_producer = QCheckBox("Στοιχεία παραγωγού")
        self.include_producer.setChecked(True)
        self.include_producer.stateChanged.connect(self.refresh_preview)
        check_row.addWidget(self.include_producer)

        self.include_declaration = QCheckBox("Στοιχεία δήλωσης")
        self.include_declaration.setChecked(True)
        self.include_declaration.stateChanged.connect(self.refresh_preview)
        check_row.addWidget(self.include_declaration)

        self.include_fields = QCheckBox("Αγροτεμάχια")
        self.include_fields.setChecked(True)
        self.include_fields.stateChanged.connect(self.refresh_preview)
        check_row.addWidget(self.include_fields)

        self.include_production = QCheckBox("Παραγωγή")
        self.include_production.setChecked(True)
        self.include_production.stateChanged.connect(self.refresh_preview)
        check_row.addWidget(self.include_production)

        check_row.addStretch()
        options_layout.addLayout(check_row)

        layout.addWidget(options_box)

        validation_box = QGroupBox()
        validation_layout = QVBoxLayout(validation_box)

        validation_title = QLabel("Έλεγχος πακέτου")
        validation_title.setStyleSheet(
            "font-weight: 700; font-size: 15px; color: #26382f;"
        )
        validation_layout.addWidget(validation_title)

        self.validation_status = QLabel("Δεν έχει γίνει έλεγχος.")
        self.validation_status.setWordWrap(True)
        validation_layout.addWidget(self.validation_status)

        self.validation_details = QLabel("")
        self.validation_details.setWordWrap(True)
        self.validation_details.setStyleSheet("color: #67746d;")
        validation_layout.addWidget(self.validation_details)

        layout.addWidget(validation_box)

        fields_box = QGroupBox()
        fields_layout = QVBoxLayout(fields_box)

        fields_title = QLabel("Αγροτεμάχια της αποθηκευμένης δήλωσης")
        fields_title.setStyleSheet(
            "font-weight: 700; font-size: 15px; color: #26382f;"
        )
        fields_layout.addWidget(fields_title)

        self.fields_table = table_widget(
            [
                "Αγροτεμάχιο",
                "ΚΑΕΚ",
                "Τοποθεσία",
                "Έκταση στρ.",
                "Παραγωγικά δέντρα",
                "Παραγωγή kg",
            ]
        )
        self.fields_table.setMinimumHeight(150)
        fields_header = self.fields_table.horizontalHeader()
        fields_header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        fields_header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        fields_header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        fields_header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        fields_header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        fields_header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        fields_layout.addWidget(self.fields_table)

        layout.addWidget(fields_box)

        preview_box = QGroupBox()
        preview_layout = QVBoxLayout(preview_box)

        preview_title = QLabel("Preview πακέτου")
        preview_title.setStyleSheet(
            "font-weight: 700; font-size: 15px; color: #26382f;"
        )
        preview_layout.addWidget(preview_title)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(260)
        self.preview.setMaximumHeight(360)
        self.preview.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.preview.setStyleSheet(
            "QTextEdit { font-family: Consolas, 'Courier New', monospace; }"
        )
        preview_layout.addWidget(self.preview)

        layout.addWidget(preview_box)

        history_box = QGroupBox()
        history_layout = QVBoxLayout(history_box)

        history_title = QLabel("Ιστορικό προετοιμασμένων πακέτων")
        history_title.setStyleSheet(
            "font-weight: 700; font-size: 15px; color: #26382f;"
        )
        history_layout.addWidget(history_title)

        history_buttons = QHBoxLayout()

        self.save_snapshot_button = QPushButton(
            "Αποθήκευση snapshot πακέτου"
        )
        self.save_snapshot_button.clicked.connect(self.save_snapshot)
        history_buttons.addWidget(self.save_snapshot_button)

        refresh_history_button = QPushButton("Ανανέωση ιστορικού")
        refresh_history_button.clicked.connect(self._refresh_history)
        history_buttons.addWidget(refresh_history_button)

        history_buttons.addStretch()
        history_layout.addLayout(history_buttons)

        self.history_table = table_widget(
            [
                "ID",
                "Έτος",
                "Ημερομηνία",
                "Κατάσταση",
                "SHA-256",
            ]
        )
        self.history_table.setMinimumHeight(155)
        self.history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.history_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.history_table.itemSelectionChanged.connect(
            self._snapshot_selection_changed
        )

        history_header = self.history_table.horizontalHeader()
        history_header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        history_header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        history_header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        history_header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        history_header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )
        history_layout.addWidget(self.history_table)

        snapshot_actions = QHBoxLayout()

        self.verify_snapshot_button = QPushButton("Έλεγχος ακεραιότητας")
        self.verify_snapshot_button.clicked.connect(
            self.verify_selected_snapshot
        )
        snapshot_actions.addWidget(self.verify_snapshot_button)

        self.compare_snapshot_button = QPushButton(
            "Σύγκριση με τρέχον πακέτο"
        )
        self.compare_snapshot_button.clicked.connect(
            self.compare_selected_snapshot
        )
        snapshot_actions.addWidget(self.compare_snapshot_button)

        self.export_snapshot_button = QPushButton(
            "Εξαγωγή επιλεγμένου JSON"
        )
        self.export_snapshot_button.clicked.connect(
            self.export_selected_snapshot
        )
        snapshot_actions.addWidget(self.export_snapshot_button)

        self.delete_snapshot_button = QPushButton("Διαγραφή snapshot")
        self.delete_snapshot_button.clicked.connect(
            self.delete_selected_snapshot
        )
        snapshot_actions.addWidget(self.delete_snapshot_button)

        snapshot_actions.addStretch()
        history_layout.addLayout(snapshot_actions)

        selected_title = QLabel("Προβολή επιλεγμένου snapshot")
        selected_title.setStyleSheet(
            "font-weight: 700; color: #26382f; margin-top: 4px;"
        )
        history_layout.addWidget(selected_title)

        self.snapshot_status = QLabel(
            "Επίλεξε μία γραμμή από το ιστορικό."
        )
        self.snapshot_status.setWordWrap(True)
        self.snapshot_status.setStyleSheet("color: #67746d;")
        history_layout.addWidget(self.snapshot_status)

        self.snapshot_preview = QTextEdit()
        self.snapshot_preview.setReadOnly(True)
        self.snapshot_preview.setMinimumHeight(180)
        self.snapshot_preview.setMaximumHeight(300)
        self.snapshot_preview.setLineWrapMode(
            QTextEdit.LineWrapMode.NoWrap
        )
        self.snapshot_preview.setStyleSheet(
            "QTextEdit { font-family: Consolas, 'Courier New', monospace; }"
        )
        history_layout.addWidget(self.snapshot_preview)

        layout.addWidget(history_box)

        actions_box = QGroupBox()
        actions_layout = QHBoxLayout(actions_box)

        self.server_status = QLabel(
            "Server: δεν έχει ρυθμιστεί — καμία αποστολή δεν γίνεται."
        )
        self.server_status.setStyleSheet("color: #67746d;")
        actions_layout.addWidget(self.server_status)
        actions_layout.addStretch()

        action_button_style = """
            QPushButton {
                background: #52745f;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 9px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #3f604c;
            }
            QPushButton:pressed {
                background: #324f3f;
            }
            QPushButton:disabled {
                background: #c7d0cb;
                color: #6f7d76;
            }
        """

        for button in (
            self.save_snapshot_button,
            self.verify_snapshot_button,
            self.compare_snapshot_button,
            self.export_snapshot_button,
            self.delete_snapshot_button,
        ):
            button.setStyleSheet(action_button_style)

        self.export_json_button = QPushButton("Εξαγωγή πακέτου JSON")
        self.export_json_button.setStyleSheet(action_button_style)
        self.export_json_button.clicked.connect(self.export_json)
        actions_layout.addWidget(self.export_json_button)

        self._set_snapshot_action_state(False)

        layout.addWidget(actions_box)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

        self.refresh()

    def refresh(self) -> None:
        self._ensure_schema()
        self._load_years()
        self._load_products()
        self.refresh_preview()
        self._refresh_history()

    def _load_products(self) -> None:
        current = self.product.currentData()
        rows = self.db.query(
            """SELECT id,name,unit,is_active
               FROM products
               ORDER BY is_active DESC, name COLLATE NOCASE, id"""
        )
        self.product.blockSignals(True)
        self.product.clear()
        for row in rows:
            label = f"{row['name']} ({row['unit']})"
            if not bool(row["is_active"]):
                label += " — ανενεργό"
            self.product.addItem(label, int(row["id"]))
        index = self.product.findData(current)
        self.product.setCurrentIndex(index if index >= 0 else (0 if rows else -1))
        self.product.blockSignals(False)

    def _selected_product_row(self):
        product_id = self.product.currentData()
        if product_id is None:
            return None
        return self.db.query_one(
            "SELECT id,name,unit,is_active FROM products WHERE id=?",
            (int(product_id),),
        )

    def _load_years(self) -> None:
        populate_year_filter(self, self.year, all_years=False)

    def refresh_preview(self, *_args) -> None:
        year = self.year.currentData()
        product_row = self._selected_product_row()
        if product_row is None:
            self.declaration_status.setText("Δεν υπάρχει επιλεγμένο προϊόν")
            self.fields_table.setRowCount(0)
            self.preview.setProperty("mastixaI18nStaticText", True)
            self.preview.setPlainText("Πρόσθεσε ή επίλεξε πρώτα ένα προϊόν.")
            self.current_payload = {}
            self._update_validation(["Δεν υπάρχει επιλεγμένο προϊόν."], [])
            self._update_action_states()
            return

        if year is None:
            self.declaration_status.setText("Δεν υπάρχει αποθηκευμένη δήλωση")
            self.fields_table.setRowCount(0)
            self.preview.setProperty("mastixaI18nStaticText", True)
            self.preview.setPlainText(
                "Αποθήκευσε πρώτα μία πρόχειρη Δήλωση Καλλιέργειας."
            )
            self.current_payload = {}
            self._update_validation([], ["Δεν υπάρχει αποθηκευμένη δήλωση."])
            self._update_action_states()
            return

        declaration = self.db.query_one(
            """
            SELECT *
            FROM cultivation_declarations
            WHERE declaration_year=?
            """,
            (int(year),),
        )

        if declaration is None:
            self.declaration_status.setText("Δεν βρέθηκε")
            self.fields_table.setRowCount(0)
            self.preview.setProperty("mastixaI18nStaticText", True)
            self.preview.setPlainText("Δεν βρέθηκε αποθηκευμένη δήλωση.")
            self.current_payload = {}
            self._update_validation([], ["Δεν βρέθηκε αποθηκευμένη δήλωση."])
            self._update_action_states()
            return

        self.declaration_status.setText(
            "Πρόχειρη — αποθηκευμένη τοπικά"
        )

        product_id = int(product_row["id"])
        fields = self._load_fields(
            int(declaration["id"]), int(year), product_id
        )
        self._populate_fields_table(fields)

        payload: dict = {
            "schema": "mastixa-manager-cultivation-declaration-v2",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "year": int(year),
            "product": {
                "id": product_id,
                "name": product_row["name"] or "",
                "unit": product_row["unit"] or "kg",
            },
        }

        if self.include_producer.isChecked():
            payload["producer"] = {
                "name": declaration["producer_name"] or "",
                "tax_id": declaration["producer_tax_id"] or "",
            }

        if self.include_declaration.isChecked():
            payload["declaration"] = {
                "status": declaration["status"] or "draft",
                "notes": declaration["notes"] or "",
                "updated_at": declaration["updated_at"] or "",
            }

        if self.include_fields.isChecked():
            payload["fields"] = [
                {
                    "id": field["id"],
                    "name": field["name"],
                    "kaek": field["kaek"],
                    "location": field["location"],
                    "area_stremma": field["area_stremma"],
                    "productive_trees": field["productive_trees"],
                }
                for field in fields
            ]

        if self.include_production.isChecked():
            payload["production"] = [
                {
                    "field_id": field["id"],
                    "field_name": field["name"],
                    "quantity_kg": field["production_kg"],
                }
                for field in fields
            ]

        self.current_payload = payload
        self.preview.setProperty("mastixaI18nStaticText", False)
        self.preview.setPlainText(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
        )

        errors, warnings = self._validate_payload(
            payload=payload,
            fields=fields,
        )
        self._update_validation(errors, warnings)
        self._update_action_states()

    def _ensure_schema(self) -> None:
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                declaration_year INTEGER NOT NULL,
                product_id INTEGER,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'prepared',
                validation_warnings TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {
            str(row["name"])
            for row in self.db.query("PRAGMA table_info(upload_packages)")
        }
        if "product_id" not in columns:
            self.db.execute("ALTER TABLE upload_packages ADD COLUMN product_id INTEGER")
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_upload_packages_product ON upload_packages(product_id)"
        )

    def _validate_payload(
        self,
        *,
        payload: dict,
        fields: list[dict],
    ) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []

        sections = {
            key
            for key in (
                "producer",
                "declaration",
                "fields",
                "production",
            )
            if key in payload
        }

        product = payload.get("product")
        if not isinstance(product, dict) or not product.get("id"):
            errors.append("Το πακέτο δεν έχει συνδεδεμένο προϊόν.")

        if not sections:
            errors.append(
                "Δεν έχει επιλεγεί κανένα τμήμα δεδομένων για το πακέτο."
            )

        producer = payload.get("producer")
        if producer is not None:
            name = str(producer.get("name", "")).strip()
            tax_id = str(producer.get("tax_id", "")).strip()

            if not name:
                errors.append("Λείπει το ονοματεπώνυμο / η επωνυμία παραγωγού.")

            if not tax_id:
                errors.append("Λείπει το ΑΦΜ του παραγωγού.")
            elif not (tax_id.isdigit() and len(tax_id) == 9):
                warnings.append(
                    "Το ΑΦΜ δεν έχει τη συνήθη ελληνική μορφή 9 ψηφίων."
                )

        if "fields" in payload and not payload.get("fields"):
            errors.append(
                "Το πακέτο περιλαμβάνει Αγροτεμάχια, αλλά η δήλωση "
                "δεν έχει επιλεγμένο αγροτεμάχιο."
            )

        if "production" in payload and not payload.get("production"):
            errors.append(
                "Το πακέτο περιλαμβάνει Παραγωγή, αλλά δεν υπάρχουν "
                "αγροτεμάχια στη δήλωση."
            )

        if fields:
            missing_kaek = sum(
                1 for field in fields if not str(field["kaek"]).strip()
            )
            missing_location = sum(
                1 for field in fields if not str(field["location"]).strip()
            )
            zero_tree_fields = sum(
                1 for field in fields if int(field["productive_trees"]) <= 0
            )

            if missing_kaek:
                warnings.append(
                    f"{missing_kaek} αγροτεμάχιο/α δεν έχουν συμπληρωμένο ΚΑΕΚ."
                )

            if missing_location:
                warnings.append(
                    f"{missing_location} αγροτεμάχιο/α δεν έχουν συμπληρωμένη "
                    "Τοποθεσία."
                )

            if zero_tree_fields:
                warnings.append(
                    f"{zero_tree_fields} αγροτεμάχιο/α έχουν 0 παραγωγικά δέντρα."
                )

        return errors, warnings

    def _update_validation(
        self,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        self.current_validation_errors = list(errors)
        self.current_validation_warnings = list(warnings)

        if errors:
            self.validation_status.setText(
                "✖ Το πακέτο δεν είναι έτοιμο."
            )
            self.validation_status.setStyleSheet(
                "font-weight: 700; color: #8a3f3f;"
            )
        elif warnings:
            self.validation_status.setText(
                "⚠ Το πακέτο είναι έτοιμο με προειδοποιήσεις."
            )
            self.validation_status.setStyleSheet(
                "font-weight: 700; color: #8a6a2f;"
            )
        else:
            self.validation_status.setText(
                "✔ Το πακέτο είναι έτοιμο για εξαγωγή."
            )
            self.validation_status.setStyleSheet(
                "font-weight: 700; color: #3f604c;"
            )

        details: list[str] = []

        for item in errors:
            details.append(f"Σφάλμα: {item}")

        for item in warnings:
            details.append(f"Προειδοποίηση: {item}")

        if not details:
            details.append("Δεν βρέθηκαν προβλήματα.")

        self.validation_details.setText("\n".join(details))

    def _update_action_states(self) -> None:
        valid = bool(self.current_payload) and not self.current_validation_errors

        self.export_json_button.setEnabled(valid)
        self.save_snapshot_button.setEnabled(valid)

    @staticmethod
    def _canonical_payload_json(payload: dict) -> str:
        # generated_at is intentionally excluded from the hash so that the
        # same business data produces the same fingerprint.
        hash_payload = dict(payload)
        hash_payload.pop("generated_at", None)

        return json.dumps(
            hash_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def _payload_hash(self, payload: dict) -> str:
        canonical = self._canonical_payload_json(payload)
        return hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

    def save_snapshot(self) -> None:
        if not self.current_payload:
            QMessageBox.warning(
                self,
                "Κέντρο Αποστολής",
                "Δεν υπάρχει διαθέσιμο πακέτο.",
            )
            return

        if self.current_validation_errors:
            QMessageBox.warning(
                self,
                "Κέντρο Αποστολής",
                "Το πακέτο έχει σφάλματα και δεν μπορεί να αποθηκευτεί "
                "ως έτοιμο snapshot.",
            )
            return

        payload_json = json.dumps(
            self.current_payload,
            ensure_ascii=False,
            indent=2,
        )
        payload_hash = self._payload_hash(self.current_payload)
        warnings_json = json.dumps(
            self.current_validation_warnings,
            ensure_ascii=False,
        )

        self.db.execute(
            """
            INSERT INTO upload_packages (
                declaration_year,
                product_id,
                payload_json,
                payload_hash,
                status,
                validation_warnings
            )
            VALUES (?, ?, ?, ?, 'prepared', ?)
            """,
            (
                int(self.current_payload["year"]),
                int(self.current_payload.get("product", {}).get("id") or 0) or None,
                payload_json,
                payload_hash,
                warnings_json,
            ),
        )

        self._refresh_history()

        QMessageBox.information(
            self,
            "Κέντρο Αποστολής",
            "Αποθηκεύτηκε snapshot του ακριβούς πακέτου.\n\n"
            f"SHA-256:\n{payload_hash}\n\n"
            "Δεν έγινε καμία αποστολή σε server.",
        )

    def _refresh_history(self) -> None:
        previous_id = self.selected_snapshot_id

        rows = self.db.query(
            """
            SELECT
                id,
                declaration_year,
                created_at,
                status,
                payload_hash
            FROM upload_packages
            ORDER BY id DESC
            LIMIT 100
            """
        )

        self.history_table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            hash_text = str(row["payload_hash"] or "")
            short_hash = (
                hash_text[:16] + "…"
                if len(hash_text) > 16
                else hash_text
            )

            values = [
                str(row["id"]),
                str(row["declaration_year"]),
                row["created_at"] or "",
                row["status"] or "",
                short_hash,
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column_index == 4:
                    item.setToolTip(hash_text)

                self.history_table.setItem(
                    row_index,
                    column_index,
                    item,
                )

        # Restore row selection when possible.
        restored = False
        if previous_id is not None:
            for row_index in range(self.history_table.rowCount()):
                item = self.history_table.item(row_index, 0)
                if item is None:
                    continue

                try:
                    row_id = int(item.text())
                except ValueError:
                    continue

                if row_id == previous_id:
                    self.history_table.selectRow(row_index)
                    restored = True
                    break

        if not restored:
            self.selected_snapshot_id = None
            self.snapshot_preview.clear()
            self._composed_text(self.snapshot_status, 'Επίλεξε μία γραμμή από το ιστορικό.')
            self.snapshot_status.setStyleSheet("color: #67746d;")
            self._set_snapshot_action_state(False)

    def _set_snapshot_action_state(self, enabled: bool) -> None:
        for button in (
            self.verify_snapshot_button,
            self.compare_snapshot_button,
            self.export_snapshot_button,
            self.delete_snapshot_button,
        ):
            button.setEnabled(enabled)

    def _snapshot_selection_changed(self) -> None:
        selected = self.history_table.selectedItems()

        if not selected:
            self.selected_snapshot_id = None
            self._composed_text(self.snapshot_status, 'Επίλεξε μία γραμμή από το ιστορικό.')
            self.snapshot_preview.clear()
            self._set_snapshot_action_state(False)
            return

        row = selected[0].row()
        id_item = self.history_table.item(row, 0)

        if id_item is None:
            self.selected_snapshot_id = None
            self._set_snapshot_action_state(False)
            return

        try:
            snapshot_id = int(id_item.text())
        except ValueError:
            self.selected_snapshot_id = None
            self._set_snapshot_action_state(False)
            return

        snapshot = self.db.query_one(
            """
            SELECT *
            FROM upload_packages
            WHERE id=?
            """,
            (snapshot_id,),
        )

        if snapshot is None:
            self.selected_snapshot_id = None
            self._composed_text(self.snapshot_status, 'Το snapshot δεν βρέθηκε πλέον στη βάση.')
            self.snapshot_preview.clear()
            self._set_snapshot_action_state(False)
            return

        self.selected_snapshot_id = snapshot_id

        payload_text = snapshot["payload_json"] or ""
        stored_hash = snapshot["payload_hash"] or ""

        self.snapshot_preview.setPlainText(payload_text)

        integrity_ok = self._snapshot_integrity_ok(snapshot)

        if integrity_ok:
            self._composed_text(self.snapshot_status, 'Snapshot #{snapshot_id} — ακέραιο — SHA-256: {stored_hash}', snapshot_id=snapshot_id, stored_hash=stored_hash)
            self.snapshot_status.setStyleSheet(
                "font-weight: 700; color: #3f604c;"
            )
        else:
            self._composed_text(self.snapshot_status, 'Snapshot #{snapshot_id} — ΠΡΟΕΙΔΟΠΟΙΗΣΗ: το περιεχόμενο δεν συμφωνεί με το αποθηκευμένο SHA-256.', snapshot_id=snapshot_id)
            self.snapshot_status.setStyleSheet(
                "font-weight: 700; color: #8a3f3f;"
            )

        self._set_snapshot_action_state(True)

    def _snapshot_integrity_ok(self, snapshot) -> bool:
        payload_text = snapshot["payload_json"] or ""
        stored_hash = str(snapshot["payload_hash"] or "")

        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            return False

        actual_hash = self._payload_hash(payload)
        return actual_hash == stored_hash

    def verify_selected_snapshot(self) -> None:
        if self.selected_snapshot_id is None:
            return

        snapshot = self.db.query_one(
            "SELECT * FROM upload_packages WHERE id=?",
            (self.selected_snapshot_id,),
        )

        if snapshot is None:
            QMessageBox.warning(
                self,
                "Κέντρο Αποστολής",
                "Το επιλεγμένο snapshot δεν βρέθηκε.",
            )
            self._refresh_history()
            return

        if self._snapshot_integrity_ok(snapshot):
            _message(self, 'information', 'Έλεγχος ακεραιότητας', 'Το snapshot είναι ακέραιο.\n\nSHA-256:\n{value0}', value0=snapshot['payload_hash'])
        else:
            QMessageBox.critical(
                self,
                "Έλεγχος ακεραιότητας",
                "Το snapshot ΔΕΝ συμφωνεί με το αποθηκευμένο SHA-256.\n\n"
                "Μην το χρησιμοποιήσεις για αποστολή ή επίσημη καταγραφή.",
            )

    def export_selected_snapshot(self) -> None:
        if self.selected_snapshot_id is None:
            return

        snapshot = self.db.query_one(
            "SELECT * FROM upload_packages WHERE id=?",
            (self.selected_snapshot_id,),
        )

        if snapshot is None:
            QMessageBox.warning(
                self,
                "Κέντρο Αποστολής",
                "Το επιλεγμένο snapshot δεν βρέθηκε.",
            )
            return

        if not self._snapshot_integrity_ok(snapshot):
            answer = QMessageBox.warning(
                self,
                "Προειδοποίηση ακεραιότητας",
                "Το snapshot δεν περνά τον έλεγχο SHA-256.\n\n"
                "Να γίνει παρ' όλα αυτά εξαγωγή;",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:
                return

        year = snapshot["declaration_year"]
        snapshot_id = snapshot["id"]

        path, _ = QFileDialog.getSaveFileName(
            self,
            _text("Εξαγωγή επιλεγμένου snapshot"),
            f"fieltra_snapshot_{year}_{snapshot_id}.json",
            "JSON (*.json)",
        )

        if not path:
            return

        if not path.lower().endswith(".json"):
            path += ".json"

        try:
            Path(path).write_text(
                snapshot["payload_json"] or "",
                encoding="utf-8",
            )
        except OSError as exc:
            _message(self, 'critical', 'Κέντρο Αποστολής', 'Η εξαγωγή απέτυχε.\n\n{exc}', exc=exc)
            return

        _message(self, 'information', 'Κέντρο Αποστολής', 'Το snapshot εξήχθη επιτυχώς:\n{path}', path=path)

    def compare_selected_snapshot(self) -> None:
        if self.selected_snapshot_id is None:
            return

        snapshot = self.db.query_one(
            "SELECT * FROM upload_packages WHERE id=?",
            (self.selected_snapshot_id,),
        )

        if snapshot is None:
            QMessageBox.warning(
                self,
                "Κέντρο Αποστολής",
                "Το επιλεγμένο snapshot δεν βρέθηκε.",
            )
            return

        try:
            old_payload = json.loads(snapshot["payload_json"] or "{}")
        except json.JSONDecodeError:
            QMessageBox.critical(
                self,
                "Σύγκριση",
                "Το snapshot δεν περιέχει έγκυρο JSON.",
            )
            return

        new_payload = self.current_payload or {}

        differences = self._diff_payloads(
            old_payload,
            new_payload,
        )

        if not differences:
            QMessageBox.information(
                self,
                "Σύγκριση",
                "Το επιλεγμένο snapshot είναι ίδιο με το τρέχον πακέτο "
                "στα επιχειρησιακά δεδομένα.",
            )
            return

        def comparison_text():
            displayed = self._diff_payloads(old_payload, new_payload)
            message = "\n".join(f"• {item}" for item in displayed[:30])
            if len(displayed) > 30:
                message += _text("\n\n...και ακόμη {count} διαφορές.", count=len(displayed) - 30)
            return message

        _message(
            self, "information",
            "Σύγκριση snapshot",
            "Βρέθηκαν οι παρακάτω διαφορές:\n\n{differences}",
            differences=comparison_text,
        )

    def _diff_payloads(
        self,
        old_payload: dict,
        new_payload: dict,
    ) -> list[str]:
        old_payload = dict(old_payload)
        new_payload = dict(new_payload)

        # generated_at changes every time and is not a business-data change.
        old_payload.pop("generated_at", None)
        new_payload.pop("generated_at", None)

        differences: list[str] = []
        self._diff_values(
            old_payload,
            new_payload,
            path="",
            output=differences,
        )
        return differences

    def _diff_values(
        self,
        old,
        new,
        *,
        path: str,
        output: list[str],
    ) -> None:
        if type(old) is not type(new):
            output.append(
                _text("{path}: αλλαγή τύπου/τιμής ({old!r} → {new!r})", path=path or 'root', old=old, new=new)
            )
            return

        if isinstance(old, dict):
            keys = sorted(set(old) | set(new))

            for key in keys:
                child_path = f"{path}.{key}" if path else key

                if key not in old:
                    output.append(
                        _text("{path}: προστέθηκε {value!r}", path=child_path, value=new[key])
                    )
                    continue

                if key not in new:
                    output.append(
                        _text("{path}: αφαιρέθηκε {value!r}", path=child_path, value=old[key])
                    )
                    continue

                self._diff_values(
                    old[key],
                    new[key],
                    path=child_path,
                    output=output,
                )
            return

        if isinstance(old, list):
            if len(old) != len(new):
                output.append(
                    _text("{path}: πλήθος στοιχείων {old} → {new}", path=path, old=len(old), new=len(new))
                )

            for index, (old_item, new_item) in enumerate(
                zip(old, new)
            ):
                self._diff_values(
                    old_item,
                    new_item,
                    path=f"{path}[{index}]",
                    output=output,
                )
            return

        if old != new:
            output.append(
                f"{path}: {old!r} → {new!r}"
            )

    def delete_selected_snapshot(self) -> None:
        if self.selected_snapshot_id is None:
            return

        snapshot = self.db.query_one(
            """
            SELECT id, declaration_year, created_at, payload_hash
            FROM upload_packages
            WHERE id=?
            """,
            (self.selected_snapshot_id,),
        )

        if snapshot is None:
            self._refresh_history()
            return

        answer = QMessageBox.warning(
            self,
            "Διαγραφή snapshot",
            "Θα διαγραφεί μόνιμα το επιλεγμένο snapshot.\n\n"
            f"ID: {snapshot['id']}\n"
            f"Έτος: {snapshot['declaration_year']}\n"
            f"Ημερομηνία: {snapshot['created_at']}\n"
            f"SHA-256: {snapshot['payload_hash']}\n\n"
            "Να συνεχίσω;",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.db.execute(
            "DELETE FROM upload_packages WHERE id=?",
            (self.selected_snapshot_id,),
        )

        self.selected_snapshot_id = None
        self.snapshot_preview.clear()
        self._composed_text(self.snapshot_status, 'Επίλεξε μία γραμμή από το ιστορικό.')
        self.snapshot_status.setStyleSheet("color: #67746d;")
        self._set_snapshot_action_state(False)
        self._refresh_history()

    def _load_fields(
        self, declaration_id: int, year: int, product_id: int
    ) -> list[dict]:
        rows = self.db.query(
            """
            SELECT
                f.id,
                f.name,
                f.kaek,
                f.location,
                f.area_stremma,
                f.productive_trees,
                COALESCE(SUM(
                    CASE
                        WHEN SUBSTR(p.entry_date, 1, 4)=?
                        THEN p.quantity_kg
                        ELSE 0
                    END
                ), 0) AS production_kg
            FROM cultivation_declaration_fields df
            JOIN fields f ON f.id = df.field_id
            JOIN product_fields pf
              ON pf.field_id=f.id AND pf.product_id=?
            LEFT JOIN production p
              ON p.field_id=f.id AND p.product_id=?
            WHERE df.declaration_id=?
              AND pf.cultivation_status='active'
            GROUP BY
                f.id, f.name, f.kaek, f.location,
                f.area_stremma, f.productive_trees
            ORDER BY f.name, f.id
            """,
            (str(year), int(product_id), int(product_id), declaration_id),
        )

        return [
            {
                "id": int(row["id"]),
                "name": row["name"] or "",
                "kaek": row["kaek"] or "",
                "location": row["location"] or "",
                "area_stremma": float(row["area_stremma"] or 0),
                "productive_trees": int(row["productive_trees"] or 0),
                "production_kg": float(row["production_kg"] or 0),
            }
            for row in rows
        ]

    def _populate_fields_table(self, fields: list[dict]) -> None:
        self.fields_table.setRowCount(len(fields))

        for row_index, field in enumerate(fields):
            values = [
                field["name"],
                field["kaek"],
                field["location"],
                compact_decimal(field["area_stremma"], 3),
                str(field["productive_trees"]),
                compact_decimal(field["production_kg"], 3),
            ]

            for column_index, value in enumerate(values):
                self.fields_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(value),
                )

    def export_json(self) -> None:
        if self.current_validation_errors:
            QMessageBox.warning(
                self,
                "Κέντρο Αποστολής",
                "Διόρθωσε πρώτα τα σφάλματα του πακέτου.",
            )
            return

        if not self.current_payload:
            QMessageBox.warning(
                self,
                "Κέντρο Αποστολής",
                "Δεν υπάρχει διαθέσιμο πακέτο για εξαγωγή.",
            )
            return

        year = self.current_payload.get("year", "declaration")
        path, _ = QFileDialog.getSaveFileName(
            self,
            _text("Εξαγωγή πακέτου JSON"),
            f"fieltra_declaration_{year}.json",
            "JSON (*.json)",
        )

        if not path:
            return

        if not path.lower().endswith(".json"):
            path += ".json"

        try:
            Path(path).write_text(
                json.dumps(
                    self.current_payload,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            _message(self, 'critical', 'Κέντρο Αποστολής', 'Η εξαγωγή απέτυχε.\n\n{exc}', exc=exc)
            return

        _message(self, 'information', 'Κέντρο Αποστολής', 'Το JSON δημιουργήθηκε επιτυχώς:\n{path}\n\nΔεν έγινε καμία αποστολή σε server.', path=path)
