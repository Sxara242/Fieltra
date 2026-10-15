from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .database import Database
from .language import tr
from .localized_messages import _language, _message, _text
from .ui_helpers import table_widget
from .product_registry import ensure_product_links, product_row


EXPORT_SECTIONS = [
    ("producer", "Στοιχεία παραγωγού", ["producer"]),
    ("fields", "Αγροτεμάχια", ["fields"]),
    ("products", "Προϊόντα και καλλιέργειες", ["products", "product_fields", "fields"]),
    ("production", "Παραγωγή", ["production"]),
    ("activities", "Άρδευση & Λίπανση", ["farm_activities"]),
    ("labor", "Εργατικά & Προσωπικό", ["workers", "labor_entries"]),
    ("plantings", "Φυτεύσεις & Δέντρα", ["planting_batches"]),
    ("sales", "Πωλήσεις Παραγωγής", ["production_sales"]),
    ("plant_protection", "Φυτοπροστασία", ["plant_protection_records"]),
    ("inventory", "Αποθήκη & Εφόδια", ["inventory_items", "inventory_movements"]),
    ("equipment", "Μηχανήματα & Συντήρηση", ["equipment", "equipment_maintenance"]),
    ("partners", "Προμηθευτές & Αγοραστές", ["business_partners"]),
    ("invoice_documents", "Έγγραφα Τιμολογίων και συνημμένα", ["invoice_documents"]),
    ("money", "Έσοδα / Έξοδα", ["income", "expenses"]),
    (
        "declarations",
        "Δηλώσεις Καλλιέργειας",
        [
            "cultivation_declarations",
            "cultivation_declaration_fields",
        ],
    ),
    ("snapshots", "Snapshots Κέντρου Αποστολής", ["upload_packages"]),
    ("audit", "Ιστορικό Ενεργειών", ["audit_events"]),
    ("year_locks", "Κλείδωμα Έτους", ["year_locks"]),
]


class _VerificationMessage(str):
    """Keep the canonical diagnostic string; localize owned wording only in UI."""

    def __new__(cls, template: str, **values):
        result = super().__new__(cls, template.format(**values))
        result.template = template
        result.values = values
        return result

    def localized(self) -> str:
        return _text(self.template, **self.values)


class DataExportPage(QWidget):
    """
    Portable, read-only export of Fieltra data.

    The generated ZIP is for inspection, archiving and interoperability.
    It is NOT a replacement for the SQLite backup/restore workflow.
    """


    @staticmethod
    def _body_render(spec):
        template, values, labels = spec
        return _text(template, **dict(values, **{k: _text(v) for k, v in labels.items()}))

    def _set_body(self, item, template, *, _labels=None, **values):
        spec = (template, values, _labels or {})
        item.setData(2367, spec)
        item.setText(self._body_render(spec))

    def _body_label(self, label, template, **values):
        label.setProperty("mastixaI18nSkipText", True)
        label.setTextFormat(label.textFormat().PlainText)
        spec = (template, values, {})
        label.setProperty("mastixaBodyTemplate", spec)
        label.setText(self._body_render(spec))

    def _refresh_body_language(self, *_args):
        # Only explicitly owned cells are projected; canonical rows remain opaque.
        for name in ('summary_table',):
            table = getattr(self, name, None)
            if table is None:
                continue
            blocked = table.blockSignals(True)
            try:
                for row in range(table.rowCount()):
                    for column in range(table.columnCount()):
                        item = table.item(row, column)
                        spec = item.data(2367) if item is not None else None
                        if spec is not None:
                            text = self._body_render(spec)
                            if item.toolTip():
                                item.setToolTip(text)
                            item.setText(text)
            finally:
                table.blockSignals(blocked)
        for name in ('total_label',):
            label = getattr(self, name, None)
            spec = label.property("mastixaBodyTemplate") if label is not None else None
            if spec is not None:
                label.setText(self._body_render(spec))

    def __init__(self, db: Database) -> None:
        super().__init__()
        controller = _language()
        if controller is not None:
            controller.language_changed.connect(self._refresh_body_language)
        self.db = db
        self.section_checks: dict[str, QCheckBox] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        content.setObjectName("dataExportContent")
        content.setStyleSheet(
            "QWidget#dataExportContent { background: #f5f6f3; }"
        )
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 18, 16, 20)
        layout.setSpacing(12)
        scroll.setWidget(content)

        title = QLabel("Εξαγωγή Δεδομένων")
        title.setObjectName("pageTitle")
        title.setMinimumHeight(42)
        layout.addWidget(title)

        subtitle = QLabel(
            "Δημιουργία φορητού ZIP με CSV / JSON χωρίς αλλαγή της βάσης"
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        info_box = QGroupBox()
        info_layout = QVBoxLayout(info_box)

        info = QLabel(
            "Το αρχείο ZIP είναι ανεξάρτητο από το πρόγραμμα και μπορεί να "
            "φυλαχθεί ή να ανοιχτεί με κοινά εργαλεία. "
            "Για πλήρη επαναφορά της εφαρμογής εξακολουθείς να χρησιμοποιείς "
            "Backup / Restore."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #67746d;")
        info_layout.addWidget(info)

        layout.addWidget(info_box)

        select_box = QGroupBox()
        select_layout = QVBoxLayout(select_box)

        select_title = QLabel("Τι θα περιλαμβάνει το ZIP")
        select_title.setStyleSheet(
            "font-weight: 700; font-size: 15px; color: #26382f;"
        )
        select_layout.addWidget(select_title)

        button_row = QHBoxLayout()

        select_all_button = QPushButton("Επιλογή όλων")
        select_all_button.clicked.connect(lambda: self._set_all(True))
        button_row.addWidget(select_all_button)

        clear_button = QPushButton("Καμία επιλογή")
        clear_button.clicked.connect(lambda: self._set_all(False))
        button_row.addWidget(clear_button)

        refresh_button = QPushButton("Ανανέωση")
        refresh_button.clicked.connect(self.refresh)
        button_row.addWidget(refresh_button)

        button_row.addStretch()
        select_layout.addLayout(button_row)

        product_filter_row = QHBoxLayout()
        self.product_filter_check = QCheckBox("Φίλτρο προϊόντος")
        self.product_filter_check.toggled.connect(
            self._product_filter_toggled
        )
        product_filter_row.addWidget(self.product_filter_check)
        self.product_filter = QComboBox()
        self.product_filter.setMinimumWidth(220)
        self.product_filter.currentIndexChanged.connect(self._update_summary)
        product_filter_row.addWidget(self.product_filter)
        product_filter_row.addStretch()
        select_layout.addLayout(product_filter_row)

        for key, label, _tables in EXPORT_SECTIONS:
            check = QCheckBox(label)
            check.setChecked(True)
            check.stateChanged.connect(self._update_summary)
            self.section_checks[key] = check
            select_layout.addWidget(check)

        select_box.setMinimumHeight(select_box.sizeHint().height())
        layout.addWidget(select_box)

        summary_box = QGroupBox()
        summary_layout = QVBoxLayout(summary_box)

        summary_title = QLabel("Προεπισκόπηση εξαγωγής")
        summary_title.setStyleSheet(
            "font-weight: 700; font-size: 15px; color: #26382f;"
        )
        summary_layout.addWidget(summary_title)

        self.summary_table = table_widget(
            [
                "Ενότητα",
                "Πίνακας",
                "Εγγραφές",
                "Κατάσταση",
            ]
        )
        self.summary_table.setMinimumHeight(260)
        summary_layout.addWidget(self.summary_table)

        self.total_label = QLabel("")
        self.total_label.setStyleSheet(
            "font-weight: 700; color: #26382f;"
        )
        summary_layout.addWidget(self.total_label)

        layout.addWidget(summary_box)

        actions_box = QGroupBox()
        actions_layout = QVBoxLayout(actions_box)

        action_buttons = QHBoxLayout()

        self.export_button = QPushButton("Δημιουργία ZIP")
        self.export_button.clicked.connect(self.export_zip)
        action_buttons.addWidget(self.export_button)

        self.verify_button = QPushButton("Έλεγχος τελευταίου ZIP")
        self.verify_button.clicked.connect(self.verify_zip)
        self.verify_button.setEnabled(False)
        action_buttons.addWidget(self.verify_button)

        action_buttons.addStretch()
        actions_layout.addLayout(action_buttons)

        self.last_export_label = QLabel(
            "Δεν έχει δημιουργηθεί ZIP σε αυτή τη συνεδρία."
        )
        self.last_export_label.setProperty("mastixaI18nSkipText", True)
        self.last_export_label.setTextFormat(Qt.TextFormat.PlainText)
        self.last_export_label.setWordWrap(True)
        self.last_export_label.setStyleSheet("color: #67746d;")
        actions_layout.addWidget(self.last_export_label)

        layout.addWidget(actions_box)

        layout.addStretch()

        self.last_export_path: Path | None = None
        controller = _language()
        if controller:
            controller.language_changed.connect(self._refresh_last_export_label)
        self._refresh_last_export_label()
        self.refresh()

    def _refresh_last_export_label(self) -> None:
        self.last_export_label.setText(
            _text("Τελευταίο ZIP: {path}", path=self.last_export_path)
            if self.last_export_path is not None
            else _text("Δεν έχει δημιουργηθεί ZIP σε αυτή τη συνεδρία.")
        )

    def _table_exists(self, table_name: str) -> bool:
        row = self.db.query_one(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name=?
            """,
            (table_name,),
        )
        return row is not None

    def _table_columns(self, table_name: str) -> set[str]:
        if not self._table_exists(table_name):
            return set()
        return {
            str(row["name"])
            for row in self.db.query(f"PRAGMA table_info({table_name})")
        }

    def _refresh_products(self) -> None:
        ensure_product_links(self.db)
        current = self.product_filter.currentData()
        products = self.db.query(
            """SELECT DISTINCT pr.id,pr.name
               FROM products pr JOIN production p ON p.product_id=pr.id
               ORDER BY pr.name,pr.id"""
        ) if self._table_exists("production") else []

        self.product_filter.blockSignals(True)
        self.product_filter.clear()
        for product in products:
            self.product_filter.addItem(product["name"], int(product["id"]))
        index = self.product_filter.findData(current)
        self.product_filter.setCurrentIndex(index if index >= 0 else 0)
        self.product_filter.blockSignals(False)
        available = bool(products)
        self.product_filter_check.setEnabled(available)
        if not available:
            self.product_filter_check.setChecked(False)
        self._product_filter_toggled(self.product_filter_check.isChecked())

    def _product_filter_toggled(self, checked: bool) -> None:
        self.product_filter.setVisible(checked)
        self._update_summary()

    def _selected_product(self) -> int | None:
        if not self.product_filter_check.isChecked():
            return None
        product = self.product_filter.currentData()
        return int(product) if product is not None else None

    def _filtered_query(
        self, table_name: str, product: int | None
    ) -> tuple[str, tuple[object, ...]]:
        if not product:
            return f"SELECT * FROM {table_name}", ()

        if table_name in {"production", "production_sales"}:
            return f"SELECT * FROM {table_name} WHERE product_id=?", (product,)

        if table_name == "products":
            return "SELECT * FROM products WHERE id=?", (product,)
        if table_name == "product_fields":
            return "SELECT * FROM product_fields WHERE product_id=?", (product,)

        registry_product = product_row(self.db, product)
        if registry_product is None:
            return f"SELECT * FROM {table_name} WHERE 0", ()
        product_name = str(registry_product["name"])
        direct_columns = {
            "plant_protection_records": "product_name",
            "inventory_items": "name",
        }
        column = direct_columns.get(table_name)
        if column and column in self._table_columns(table_name):
            return f"SELECT * FROM {table_name} WHERE TRIM({column})=?", (product_name,)

        if table_name == "inventory_movements" and self._table_exists("inventory_items"):
            return (
                "SELECT m.* FROM inventory_movements m "
                "JOIN inventory_items i ON i.id=m.item_id WHERE TRIM(i.name)=?",
                (product_name,),
            )

        if (
            table_name == "farm_activities"
            and "inventory_item_id" in self._table_columns(table_name)
            and self._table_exists("inventory_items")
        ):
            return (
                "SELECT a.* FROM farm_activities a "
                "JOIN inventory_items i ON i.id=a.inventory_item_id "
                "WHERE TRIM(i.name)=?",
                (product_name,),
            )

        # Shared/reference tables remain complete so filtered files retain context.
        return f"SELECT * FROM {table_name}", ()

    def _row_count(self, table_name: str) -> int:
        if not self._table_exists(table_name):
            return 0
        query, params = self._filtered_query(
            table_name, self._selected_product()
        )
        return len(self.db.query(query, params))

    def _set_all(self, checked: bool) -> None:
        for check in self.section_checks.values():
            check.setChecked(checked)

    def refresh(self) -> None:
        self._refresh_products()
        self._update_summary()

    def _selected_sections(self) -> list[tuple[str, str, list[str]]]:
        return [
            section
            for section in EXPORT_SECTIONS
            if self.section_checks[section[0]].isChecked()
        ]

    def _update_summary(self, *_args) -> None:
        rows: list[tuple[str, str, int, str]] = []
        seen_tables: set[str] = set()

        for key, label, tables in self._selected_sections():
            for table_name in tables:
                if table_name in seen_tables:
                    continue
                seen_tables.add(table_name)
                exists = self._table_exists(table_name)
                count = self._row_count(table_name) if exists else 0

                rows.append(
                    (
                        label,
                        table_name,
                        count,
                        "OK" if exists else "Δεν υπάρχει ακόμη",
                    )
                )

        self.summary_table.setRowCount(len(rows))

        total_records = 0

        for row_index, (label, table_name, count, status) in enumerate(rows):
            total_records += count

            values = [
                label,
                table_name,
                str(count),
                status,
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index in (0, 3):
                    self._set_body(item, value)
                self.summary_table.setItem(row_index, column_index, item)

        selected_count = len(self._selected_sections())

        self._body_label(self.total_label, "Επιλεγμένες ενότητες: {selected_count}  |  Συνολικές εγγραφές: {total_records}", selected_count=selected_count, total_records=total_records)

        self.export_button.setEnabled(selected_count > 0)

    @staticmethod
    def _csv_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter=";")
        writer.writerow([tr(header) for header in headers])

        for row in rows:
            writer.writerow(
                ["" if value is None else value for value in row]
            )

        # utf-8-sig gives Excel/LibreOffice a BOM and keeps Greek text readable.
        return stream.getvalue().encode("utf-8-sig")

    def _table_export_bytes(
        self, table_name: str, product: int | None = None
    ) -> tuple[bytes, int]:
        if not self._table_exists(table_name):
            return self._csv_bytes([], []), 0

        columns = self.db.query(f"PRAGMA table_info({table_name})")
        headers = [str(row["name"]) for row in columns]

        if table_name == "products":
            # Explicit portable columns: never include legacy API credentials.
            headers = [header for header in headers if header in {
                "id", "name", "unit", "is_active", "created_at", "updated_at"
            }]

        if table_name == "farm_activities":
            # quantity/unit were removed from the user-facing feature in v0.16.1.
            # Keep legacy DB columns for backward compatibility, but do not
            # expose them in portable exports.
            headers = [
                header
                for header in headers
                if header not in {"quantity", "unit"}
            ]

        query, params = self._filtered_query(table_name, product)
        rows = self.db.query(query, params)

        values = [
            [row[header] for header in headers]
            for row in rows
        ]

        return self._csv_bytes(headers, values), len(values)

    def _build_manifest(
        self,
        *,
        exported_tables: list[dict],
    ) -> dict:
        selected_product_id = self._selected_product()
        selected_product = product_row(self.db, selected_product_id)
        return {
            "schema": "mastixa-manager-portable-export-v1",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "format": "ZIP + UTF-8 CSV + JSON",
            "product_filter": (
                str(selected_product["name"])
                if selected_product is not None
                else None
            ),
            "product_filter_id": selected_product_id,
            "notes": [
                "Portable export for inspection/interoperability.",
                "Use Fieltra Backup/Restore for full application restore.",
                "API keys are intentionally excluded from portable exports.",
            ],
            "tables": exported_tables,
        }

    def export_zip(self) -> None:
        selected = self._selected_sections()
        selected_product = self._selected_product()

        if not selected:
            QMessageBox.warning(
                self,
                "Εξαγωγή Δεδομένων",
                "Δεν έχει επιλεγεί καμία ενότητα.",
            )
            return

        default_name = (
            "fieltra_data_export_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
            + ".zip"
        )

        path, _ = QFileDialog.getSaveFileName(
            self,
            _text("Δημιουργία φορητού ZIP"),
            default_name,
            "ZIP (*.zip)",
        )

        if not path:
            return

        if not path.lower().endswith(".zip"):
            path += ".zip"

        export_path = Path(path)

        exported_tables: list[dict] = []

        try:
            with zipfile.ZipFile(
                export_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                written_tables: set[str] = set()
                for _key, label, tables in selected:
                    for table_name in tables:
                        if table_name in written_tables:
                            continue
                        written_tables.add(table_name)
                        exists = self._table_exists(table_name)

                        if not exists:
                            exported_tables.append(
                                {
                                    "section": label,
                                    "table": table_name,
                                    "rows": 0,
                                    "file": None,
                                    "status": "missing",
                                }
                            )
                            continue

                        data, row_count = self._table_export_bytes(
                            table_name, selected_product
                        )
                        csv_name = f"tables/{table_name}.csv"

                        archive.writestr(csv_name, data)
                        if table_name == "invoice_documents":
                            from .invoice_storage import resolve_file
                            exported_names = set()
                            for document in self.db.query("SELECT stored_filename FROM invoice_documents"):
                                name = str(document["stored_filename"] or "")
                                try:
                                    source = resolve_file(self.db.path, name)
                                except ValueError:
                                    continue  # Preserve this export's unsafe-path exclusion.
                                if name.casefold() not in exported_names and source.is_file():
                                    archive.write(source, "invoice_files/" + source.name)
                                    exported_names.add(name.casefold())


                        exported_tables.append(
                            {
                                "section": label,
                                "table": table_name,
                                "rows": row_count,
                                "file": csv_name,
                                "status": "exported",
                            }
                        )

                # Snapshots are also stored as separate JSON files for readability.
                if (
                    self.section_checks["snapshots"].isChecked()
                    and self._table_exists("upload_packages")
                ):
                    snapshots = self.db.query(
                        """
                        SELECT id, declaration_year, payload_json
                        FROM upload_packages
                        ORDER BY id
                        """
                    )

                    for snapshot in snapshots:
                        payload_text = str(snapshot["payload_json"] or "")

                        try:
                            payload = json.loads(payload_text)
                            payload_text = json.dumps(
                                payload,
                                ensure_ascii=False,
                                indent=2,
                            )
                        except json.JSONDecodeError:
                            # Keep original bytes so the export does not silently
                            # rewrite or hide a damaged historical snapshot.
                            pass

                        archive.writestr(
                            (
                                "snapshots/"
                                f"snapshot_{snapshot['id']}_"
                                f"{snapshot['declaration_year']}.json"
                            ),
                            payload_text.encode("utf-8"),
                        )

                manifest = self._build_manifest(
                    exported_tables=exported_tables
                )

                archive.writestr(
                    "manifest.json",
                    json.dumps(
                        manifest,
                        ensure_ascii=False,
                        indent=2,
                    ).encode("utf-8"),
                )

                readme = (
                    "Fieltra - Portable Data Export\n"
                    "======================================\n\n"
                    "Το ZIP περιέχει CSV αρχεία των επιλεγμένων δεδομένων.\n"
                    "Τα snapshots του Κέντρου Αποστολής υπάρχουν και ως ξεχωριστά JSON.\n\n"
                    "ΣΗΜΑΝΤΙΚΟ:\n"
                    "Αυτό το ZIP δεν αντικαθιστά το Backup / Restore της εφαρμογής.\n"
                    "Για πλήρη επαναφορά χρησιμοποίησε τα κανονικά SQLite backups.\n"
                    "Τα API Keys των προϊόντων δεν εξάγονται στο φορητό ZIP.\n"
                )
                archive.writestr(
                    "README.txt",
                    readme.encode("utf-8"),
                )

        except OSError as exc:
            _message(
                self, "critical", "Εξαγωγή Δεδομένων",
                "Η δημιουργία ZIP απέτυχε.\n\n{error}",
                error=str(exc),
            )
            return

        self.last_export_path = export_path
        self.verify_button.setEnabled(True)
        self._refresh_last_export_label()

        ok, message = self._verify_archive(export_path)

        if ok:
            _message(
                self, "information", "Εξαγωγή Δεδομένων",
                "Το ZIP δημιουργήθηκε και ελέγχθηκε επιτυχώς.\n\n{path}",
                path=export_path,
            )
        else:
            _message(
                self, "warning", "Εξαγωγή Δεδομένων",
                "Το ZIP δημιουργήθηκε, αλλά ο έλεγχος βρήκε πρόβλημα.\n\n{detail}",
                detail=message.localized if isinstance(message, _VerificationMessage) else message,
            )

    def _verify_archive(self, path: Path) -> tuple[bool, str]:
        try:
            with zipfile.ZipFile(path, "r") as archive:
                bad_file = archive.testzip()

                if bad_file is not None:
                    return False, _VerificationMessage("CRC πρόβλημα στο αρχείο: {file}", file=bad_file)

                names = set(archive.namelist())

                if "manifest.json" not in names:
                    return False, _VerificationMessage("Λείπει το manifest.json.")

                if "README.txt" not in names:
                    return False, _VerificationMessage("Λείπει το README.txt.")

                manifest = json.loads(
                    archive.read("manifest.json").decode("utf-8")
                )

                if (
                    manifest.get("schema")
                    != "mastixa-manager-portable-export-v1"
                ):
                    return False, _VerificationMessage("Μη αναμενόμενο schema στο manifest.")

                for table_info in manifest.get("tables", []):
                    file_name = table_info.get("file")
                    status = table_info.get("status")

                    if status == "exported" and file_name not in names:
                        return (
                            False,
                            _VerificationMessage("Λείπει το αναμενόμενο αρχείο: {file}", file=file_name),
                        )

        except (
            OSError,
            zipfile.BadZipFile,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            return False, str(exc)

        return True, "OK"

    def verify_zip(self) -> None:
        if self.last_export_path is None:
            return

        ok, message = self._verify_archive(
            self.last_export_path
        )

        if ok:
            _message(
                self, "information", "Έλεγχος ZIP",
                "Το τελευταίο ZIP είναι ακέραιο και έχει σωστή δομή.",
            )
        else:
            _message(
                self, "critical", "Έλεγχος ZIP",
                "Ο έλεγχος απέτυχε.\n\n{detail}",
                detail=message.localized if isinstance(message, _VerificationMessage) else message,
            )
