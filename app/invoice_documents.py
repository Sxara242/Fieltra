from __future__ import annotations

import csv
import io
import json
import re
import shutil
import subprocess
import unicodedata
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDate, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QFileDialog, QFormLayout, QFrame,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .localized_messages import _text, _language, _message
from .crud import CrudPage
from .widgets import date_input
from .database import BASE_DIR, Database
from .language import combo_source_text
from .invoice_storage import owned_root, owned_file, resolve_file
from .ui_helpers import table_widget
from .year_lock import warn_locked_year
from .year_context import is_year_write_blocked as is_year_locked, working_context_date
from .partner_links import (
    PartnerComboBox,
    canonical_partner_name,
    ensure_partner_link_schema,
    match_partner_id,
)


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".pdf"}
INVOICE_FILES_DIR = BASE_DIR / "data" / "invoice_documents"  # Legacy read/copy source only.
APP_TESSDATA_DIR = BASE_DIR / "data" / "tessdata"
DATE_PATTERNS = (
    re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](20\d{2})(?!\d)"),
    re.compile(r"(?<!\d)(20\d{2})[./-](\d{1,2})[./-](\d{1,2})(?!\d)"),
)
TOTAL_PATTERN = re.compile(
    r"(?:ΓΕΝΙΚΟ\s+ΣΥΝΟΛΟ|ΣΥΝΟΛΟ\s+ΠΛΗΡΩΤΕΟ|ΠΛΗΡΩΤΕΟ|GRAND\s+TOTAL|AMOUNT\s+DUE|TOTAL)"
    r"[^\d]{0,20}(\d{1,3}(?:[. ]\d{3})*(?:,\d{2})|\d+(?:[.,]\d{2})?)",
    re.IGNORECASE,
)
SUPPLIER_LABEL_PATTERN = re.compile(
    r"(?:ΕΠΩΝΥΜΙΑ|ΠΡΟΜΗΘΕΥΤΗΣ|ΕΚΔΟΤΗΣ|COMPANY|SUPPLIER)\s*[:\-]\s*(.{3,100})",
    re.IGNORECASE,
)
COMPANY_FORM_PATTERN = re.compile(
    r"\b(?:Α\.?Ε\.?|Ε\.?Π\.?Ε\.?|Ι\.?Κ\.?Ε\.?|Ο\.?Ε\.?|Ε\.?Ε\.?|"
    r"A\.?E\.?|S\.?A\.?|LTD\.?|LIMITED|LLC|INC\.?)\b",
    re.IGNORECASE,
)


_OCR_BODY_LABELS = {"unavailable": "μη διαθέσιμο — χειροκίνητη καταχώριση", "failed": "αποτυχία — χειροκίνητη καταχώριση", "no_metadata": "δεν βρέθηκαν ασφαλή μεταδεδομένα", "metadata_found": "προτάθηκαν ασφαλή μεταδεδομένα"}


class InvoiceDocumentsPage(CrudPage):
    """Managed invoice images with date filtering, OCR hints and ZIP export."""


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
        for name in ('table',):
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
        for name in ('financial_status',):
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
        self.selected_id: int | None = None
        self._ensure_schema()
        ensure_partner_link_schema(self.db)
        owned_root(self.db.path).mkdir(parents=True, exist_ok=True)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); outer.addWidget(scroll)
        content = QWidget(); layout = QVBoxLayout(content); layout.setContentsMargins(12, 18, 12, 12); layout.setSpacing(10); scroll.setWidget(content)
        title = QLabel("Έγγραφα Τιμολογίων"); title.setObjectName("pageTitle"); layout.addWidget(title)
        subtitle = QLabel("Φωτογραφίες και αρχεία τιμολογίων, OCR ημερομηνίας και πακέτα αποστολής"); subtitle.setObjectName("pageSubtitle"); layout.addWidget(subtitle)

        metrics = QHBoxLayout(); self.total_metric = self._metric("Τιμολόγια"); self.selected_metric = self._metric("Επιλεγμένα"); self.missing_date_metric = self._metric("Χωρίς ημερομηνία")
        for card, _value in (self.total_metric, self.selected_metric, self.missing_date_metric): metrics.addWidget(card, 1)
        layout.addLayout(metrics)

        import_box = QGroupBox("Εισαγωγή φωτογραφιών / αρχείων")
        import_layout = QVBoxLayout(import_box)
        import_help = QLabel("Τα αρχεία αντιγράφονται σε διαχειριζόμενο φάκελο της εφαρμογής. Όταν υπάρχει Tesseract, το OCR προτείνει ημερομηνία, προμηθευτή και τελικό ποσό μόνο από ασφαλείς ενδείξεις. Έλεγξε και διόρθωσε ελεύθερα τις προτάσεις.")
        import_help.setWordWrap(True); import_help.setStyleSheet("color:#66766E;background:transparent;"); import_layout.addWidget(import_help)
        import_row = QHBoxLayout(); self.import_button = QPushButton("Προσθήκη εικόνων / PDF..."); self.import_button.clicked.connect(self.choose_files); import_row.addWidget(self.import_button); import_row.addStretch(); import_layout.addLayout(import_row); layout.addWidget(import_box)

        self.form_box = QGroupBox("Στοιχεία τιμολογίου")
        form = QFormLayout(self.form_box)
        self.original_name = QLineEdit(); self.original_name.setReadOnly(True)
        self.supplier = PartnerComboBox(self.db); self.supplier.setPlaceholderText("Προμηθευτής / εκδότης")
        self.invoice_number = QLineEdit(); self.invoice_number.setPlaceholderText("Αριθμός τιμολογίου")
        self.date_enabled = QCheckBox("Καταχώριση ημερομηνίας τιμολογίου")
        self.invoice_date = date_input(self.db); self.invoice_date.setCalendarPopup(True); self.invoice_date.setDisplayFormat("dd/MM/yyyy"); self.invoice_date.setEnabled(False)
        self.date_enabled.toggled.connect(self.invoice_date.setEnabled)
        date_row = QHBoxLayout(); date_row.addWidget(self.date_enabled); date_row.addWidget(self.invoice_date)
        self.amount = QLineEdit(); self.amount.setPlaceholderText("Προαιρετικό ποσό")
        self.document_type = QComboBox()
        self.document_type.addItem("Αδιευκρίνιστο — επίλεξε πριν την καταχώριση", "unknown")
        self.document_type.addItem("Αγορά — καταχώριση στα Έξοδα", "purchase")
        self.document_type.addItem("Πώληση — καταχώριση στα Έσοδα", "sale")
        self.category = QComboBox(); self.category.setEditable(True); self.category.setProperty("mastixaI18nStaticItems", True); self.category.addItems(["Αγορές εφοδίων", "Καύσιμα", "Service / επισκευές", "Υπηρεσίες", "Εξοπλισμός", "Άλλο"])
        self.notes = QLineEdit()
        self.ocr_status = QLabel("OCR: δεν εκτελέστηκε"); self.ocr_status.setWordWrap(True); self.ocr_status.setStyleSheet("color:#66766E;background:transparent;")
        self.preview = QLabel("Χωρίς προεπισκόπηση"); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.preview.setMinimumHeight(180); self.preview.setStyleSheet("background:#F1F4F2;border:1px solid #D6E0DA;border-radius:6px;color:#66766E;")
        self.financial_status = QLabel("Δεν έχει δημιουργηθεί οικονομική εγγραφή.")
        self.financial_status.setWordWrap(True); self.financial_status.setStyleSheet("color:#66766E;background:transparent;")
        form.addRow("Αρχείο", self.original_name); form.addRow("Συνεργάτης", self.supplier); form.addRow("Αριθμός", self.invoice_number); form.addRow("Ημερομηνία", date_row); form.addRow("Ποσό", self.amount); form.addRow("Τύπος παραστατικού", self.document_type); form.addRow("Κατηγορία", self.category); form.addRow("Σημειώσεις", self.notes); form.addRow("", self.ocr_status); form.addRow("Οικονομική σύνδεση", self.financial_status); form.addRow("Προεπισκόπηση", self.preview)
        buttons = QHBoxLayout(); self.save_button = QPushButton("Αποθήκευση στοιχείων"); self.save_button.clicked.connect(self.save_metadata); self.save_button.setEnabled(False)
        self.clear_button = QPushButton("Καθαρισμός"); self.clear_button.clicked.connect(self.clear_form); self.open_button = QPushButton("Άνοιγμα αρχείου"); self.open_button.clicked.connect(self.open_file); self.open_button.setEnabled(False)
        self.delete_button = QPushButton("Διαγραφή"); self.delete_button.clicked.connect(self.delete_document); self.delete_button.setEnabled(False)
        self.post_button = QPushButton("Καταχώριση σε Έσοδα / Έξοδα"); self.post_button.clicked.connect(self.post_to_financials); self.post_button.setEnabled(False)
        for button in (self.save_button, self.clear_button, self.open_button, self.post_button, self.delete_button): buttons.addWidget(button)
        buttons.addStretch(); form.addRow("", buttons); layout.addWidget(self.form_box)

        list_box = QGroupBox("Αρχείο τιμολογίων")
        list_layout = QVBoxLayout(list_box)
        filters = QHBoxLayout(); self.year_filter = QComboBox(); self.year_filter.currentIndexChanged.connect(self.refresh); self.search = QLineEdit(); self.search.setPlaceholderText("Αναζήτηση προμηθευτή, αριθμού ή αρχείου..."); self.search.setClearButtonEnabled(True); self.search.textChanged.connect(self.refresh)
        filters.addWidget(QLabel("Έτος")); filters.addWidget(self.year_filter); filters.addWidget(self.search, 1); list_layout.addLayout(filters)
        select_row = QHBoxLayout(); all_button = QPushButton("Επιλογή όλων των ορατών"); all_button.clicked.connect(lambda: self._set_visible_selected(True)); none_button = QPushButton("Καμία επιλογή"); none_button.clicked.connect(lambda: self._set_visible_selected(False)); self.export_button = QPushButton("Εξαγωγή επιλεγμένων σε ZIP"); self.export_button.clicked.connect(self.export_selected)
        select_row.addWidget(all_button); select_row.addWidget(none_button); select_row.addWidget(self.export_button); select_row.addStretch(); list_layout.addLayout(select_row)
        self.table = table_widget(["Επιλογή", "Ημερομηνία", "Προμηθευτής", "Αριθμός", "Ποσό", "Κατηγορία", "Αρχείο", "OCR"])
        self.table.setSelectionMode(self.table.SelectionMode.SingleSelection); self.table.cellClicked.connect(self.load_document); self.table.itemChanged.connect(self._selection_changed); self.table.setMinimumHeight(310)
        header = self.table.horizontalHeader(); header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch); header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        for column in (0, 1, 3, 4, 5, 7): header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        list_layout.addWidget(self.table); layout.addWidget(list_box); layout.addStretch(); self.refresh()

    @staticmethod
    def _metric(caption: str):
        box = QGroupBox(); box.setObjectName("metricCard"); row = QVBoxLayout(box); label = QLabel(caption); label.setObjectName("metricCaption"); value = QLabel("0"); value.setObjectName("metricValue"); row.addWidget(label); row.addWidget(value); return box, value

    def _ensure_schema(self) -> None:
        self.db.execute("""CREATE TABLE IF NOT EXISTS invoice_documents(id INTEGER PRIMARY KEY AUTOINCREMENT,original_filename TEXT NOT NULL,stored_filename TEXT NOT NULL,invoice_date TEXT,supplier TEXT NOT NULL DEFAULT '',invoice_number TEXT NOT NULL DEFAULT '',amount_text TEXT NOT NULL DEFAULT '',document_type TEXT NOT NULL DEFAULT 'unknown',category TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',ocr_status TEXT NOT NULL DEFAULT 'unavailable',ocr_text TEXT NOT NULL DEFAULT '',ocr_suggested_date TEXT,ocr_suggested_supplier TEXT NOT NULL DEFAULT '',ocr_suggested_amount TEXT NOT NULL DEFAULT '',ocr_source TEXT NOT NULL DEFAULT '',financial_entry_type TEXT,financial_entry_id INTEGER,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        columns = {row["name"] for row in self.db.query("PRAGMA table_info(invoice_documents)")}
        for name, definition in {
            "ocr_suggested_date": "TEXT",
            "ocr_suggested_supplier": "TEXT NOT NULL DEFAULT ''",
            "ocr_suggested_amount": "TEXT NOT NULL DEFAULT ''",
            "ocr_source": "TEXT NOT NULL DEFAULT ''",
            "document_type": "TEXT NOT NULL DEFAULT 'unknown'",
            "financial_entry_type": "TEXT",
            "financial_entry_id": "INTEGER",
            "partner_id": "INTEGER",
        }.items():
            if name not in columns:
                self.db.execute(
                    f"ALTER TABLE invoice_documents ADD COLUMN {name} {definition}"
                )
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_invoice_documents_date ON invoice_documents(invoice_date)")
        if self.db.query_one("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_events'") is None: return
        for sql in (
            """CREATE TRIGGER IF NOT EXISTS audit_invoice_documents_insert AFTER INSERT ON invoice_documents BEGIN INSERT INTO audit_events(event_time,table_name,action,record_id,details) VALUES(datetime('now','localtime'),'invoice_documents','INSERT',CAST(NEW.id AS TEXT),'Τιμολόγιο: '||NEW.original_filename); END""",
            """CREATE TRIGGER IF NOT EXISTS audit_invoice_documents_update AFTER UPDATE ON invoice_documents BEGIN INSERT INTO audit_events(event_time,table_name,action,record_id,details) VALUES(datetime('now','localtime'),'invoice_documents','UPDATE',CAST(NEW.id AS TEXT),'Τιμολόγιο: '||NEW.original_filename); END""",
            """CREATE TRIGGER IF NOT EXISTS audit_invoice_documents_delete AFTER DELETE ON invoice_documents BEGIN INSERT INTO audit_events(event_time,table_name,action,record_id,details) VALUES(datetime('now','localtime'),'invoice_documents','DELETE',CAST(OLD.id AS TEXT),'Τιμολόγιο: '||OLD.original_filename); END""",
        ): self.db.execute(sql)

    @staticmethod
    def _safe_original_name(path: Path) -> str:
        name = re.sub(r"[^\w.() -]+", "_", path.name, flags=re.UNICODE).strip(" .")
        return name[:180] or f"invoice{path.suffix.lower()}"

    @staticmethod
    def _match_key(value: str) -> str:
        folded = unicodedata.normalize("NFD", value.strip().casefold())
        return "".join(ch for ch in folded if not unicodedata.combining(ch))

    @staticmethod
    def _extract_date(text: str) -> QDate | None:
        for pattern_index, pattern in enumerate(DATE_PATTERNS):
            for match in pattern.finditer(text):
                values = [int(value) for value in match.groups()]
                day, month, year = values if pattern_index == 0 else (values[2], values[1], values[0])
                date = QDate(year, month, day)
                if date.isValid() and QDate(2000, 1, 1) <= date <= QDate.currentDate().addYears(1): return date
        return None

    @staticmethod
    def _normalize_amount(raw: str) -> str | None:
        value = raw.strip().replace(" ", "")
        if "," in value:
            value = value.replace(".", "").replace(",", ".")
        elif value.count(".") > 1:
            value = value.replace(".", "")
        try:
            number = float(value)
        except ValueError:
            return None
        if number < 0 or number > 999999999:
            return None
        return f"{number:.2f}"

    @classmethod
    def _extract_amount(cls, text: str) -> str | None:
        matches = list(TOTAL_PATTERN.finditer(text))
        if not matches:
            return None
        # Totals near an explicit label are safer than arbitrary currency values.
        return cls._normalize_amount(matches[-1].group(1))

    @staticmethod
    def _clean_supplier(value: str) -> str | None:
        value = re.sub(r"\s+", " ", value).strip(" :-|\t")
        value = re.split(r"(?:ΑΦΜ|VAT|TAX\s+ID|ΔΙΕΥΘΥΝΣΗ|ADDRESS)", value, 1, flags=re.IGNORECASE)[0].strip()
        if len(value) < 3 or len(value) > 100 or sum(ch.isalpha() for ch in value) < 3:
            return None
        return value

    @classmethod
    def _extract_supplier(cls, text: str) -> str | None:
        labelled = SUPPLIER_LABEL_PATTERN.search(text)
        if labelled:
            return cls._clean_supplier(labelled.group(1))
        for line in text.splitlines()[:15]:
            if COMPANY_FORM_PATTERN.search(line):
                candidate = cls._clean_supplier(line)
                if candidate:
                    return candidate
        return None

    @classmethod
    def _extract_metadata(cls, text: str) -> dict[str, object]:
        return {
            "date": cls._extract_date(text),
            "supplier": cls._extract_supplier(text),
            "amount": cls._extract_amount(text),
        }

    @classmethod
    def _run_ocr(cls, path: Path) -> tuple[str, str, dict[str, object]]:
        executable = shutil.which("tesseract")
        if executable is None:
            for candidate in (
                Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
                Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
            ):
                if candidate.is_file():
                    executable = str(candidate)
                    break
        if executable is None: return "unavailable", "", {"date": None, "supplier": None, "amount": None}
        try:
            tessdata_args = ["--tessdata-dir", str(APP_TESSDATA_DIR)] if APP_TESSDATA_DIR.is_dir() else []
            languages = subprocess.run(
                [executable, *tessdata_args, "--list-langs"], capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=10, check=False,
            ).stdout.casefold()
            language = "ell+eng" if "ell" in languages and "eng" in languages else "eng" if "eng" in languages else None
            command = [executable, str(path), "stdout"]
            if language:
                command.extend(["-l", language])
            command.extend(tessdata_args)
            result = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=45, check=False,
            )
        except (OSError, subprocess.SubprocessError): return "failed", "", {"date": None, "supplier": None, "amount": None}
        text = result.stdout.strip()
        metadata = cls._extract_metadata(text)
        found = sum(value is not None for value in metadata.values())
        return ("metadata_found" if found else "no_metadata", text, metadata)

    def choose_files(self) -> None:
        paths, _filter = QFileDialog.getOpenFileNames(self, _text("Εισαγωγή τιμολογίων"), "", _text("Τιμολόγια") + " (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp *.pdf);;" + _text("Όλα") + " (*.*)")
        if paths: self.import_files([Path(path) for path in paths])

    def import_files(self, paths: list[Path]) -> list[int]:
        inserted: list[int] = []; rejected: list[str] = []
        for source in paths:
            if not source.is_file() or source.suffix.lower() not in SUPPORTED_EXTENSIONS: rejected.append(source.name); continue
            safe_name = self._safe_original_name(source); stored_name = f"{uuid.uuid4().hex}{source.suffix.lower()}"; target = owned_file(self.db.path, stored_name)
            try: shutil.copy2(source, target)
            except OSError: rejected.append(source.name); continue
            status, text, metadata = self._run_ocr(target)
            suggested_date = metadata["date"]
            suggested_supplier = str(metadata["supplier"] or "")
            suggested_amount = str(metadata["amount"] or "")
            sources = []
            if suggested_date: sources.append("date:pattern")
            if suggested_supplier: sources.append("supplier:label/company-form")
            if suggested_amount: sources.append("amount:labelled-total")
            try:
                suggested_partner_id = match_partner_id(
                    self.db,
                    suggested_supplier,
                )
                document_id = self.db.execute(
                    """INSERT INTO invoice_documents(
                        original_filename,stored_filename,invoice_date,
                        supplier,partner_id,amount_text,ocr_status,ocr_text,
                        ocr_suggested_date,ocr_suggested_supplier,
                        ocr_suggested_amount,ocr_source
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        safe_name,
                        stored_name,
                        suggested_date.toString("yyyy-MM-dd") if suggested_date else None,
                        suggested_supplier,
                        suggested_partner_id,
                        suggested_amount,
                        status,
                        text,
                        suggested_date.toString("yyyy-MM-dd") if suggested_date else None,
                        suggested_supplier,
                        suggested_amount,
                        ";".join(sources),
                    ),
                )
            except Exception:
                target.unlink(missing_ok=True); raise
            inserted.append(document_id)
        self.refresh()
        if inserted: self._load_by_id(inserted[-1])
        if rejected: _message(self, "warning", "Μερική εισαγωγή", "Δεν εισήχθησαν:\n{filenames}", filenames="\n".join(rejected))
        return inserted

    def _stored_path(self, record) -> Path:
        return resolve_file(self.db.path, str(record["stored_filename"]), INVOICE_FILES_DIR)

    def _load_by_id(self, document_id: int) -> None:
        record = self.db.query_one("SELECT * FROM invoice_documents WHERE id=?", (document_id,))
        if record is None: return
        self.selected_id = int(record["id"]); self.original_name.setText(record["original_filename"]); self.supplier.setText(record["supplier"] or "", record["partner_id"] if "partner_id" in record.keys() else None); self.invoice_number.setText(record["invoice_number"] or ""); self.amount.setText(record["amount_text"] or ""); self.category.setEditText(record["category"] or ""); self.notes.setText(record["notes"] or "")
        type_index = self.document_type.findData(record["document_type"] or "unknown"); self.document_type.setCurrentIndex(max(0, type_index))
        date = QDate.fromString(record["invoice_date"] or "", "yyyy-MM-dd"); self.date_enabled.setChecked(date.isValid()); self.invoice_date.setDate(date if date.isValid() else working_context_date(self.db))
        labels = {"unavailable":"μη διαθέσιμο — χειροκίνητη καταχώριση","failed":"αποτυχία — χειροκίνητη καταχώριση","no_metadata":"δεν βρέθηκαν ασφαλή μεταδεδομένα","metadata_found":"προτάθηκαν ασφαλή μεταδεδομένα"}
        def ocr_detail():
            suggestions = []
            if record["ocr_suggested_date"]:
                suggestions.append(_text("ημερομηνία {date}", date=record["ocr_suggested_date"]))
            if record["ocr_suggested_supplier"]:
                suggestions.append(_text("προμηθευτής «{supplier}»", supplier=record["ocr_suggested_supplier"]))
            if record["ocr_suggested_amount"]:
                suggestions.append(_text("σύνολο {amount}", amount=record["ocr_suggested_amount"]))
            status = _text(labels[record["ocr_status"]]) if record["ocr_status"] in labels else record["ocr_status"]
            if suggestions:
                return _text("OCR: {status} — {detail}. Έλεγξε/διόρθωσε πριν αποθήκευση.", status=status, detail="; ".join(suggestions))
            return _text("OCR: {status}", status=status)
        self._composed_text(self.ocr_status, "{value}", value=ocr_detail)
        path = self._stored_path(record); pixmap = QPixmap(str(path))
        if not pixmap.isNull(): self.preview.setPixmap(pixmap.scaled(520, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else: self.preview.setText("PDF ή αρχείο χωρίς ενσωματωμένη προεπισκόπηση")
        linked_type, linked_id = record["financial_entry_type"], record["financial_entry_id"]
        if linked_type and linked_id:
            label = "Έσοδο" if linked_type == "income" else "Έξοδο"
            self._body_label(self.financial_status, "Συνδεδεμένο με Έσοδο #{id}. Δεν θα δημιουργηθεί δεύτερη εγγραφή." if linked_type == "income" else "Συνδεδεμένο με Έξοδο #{id}. Δεν θα δημιουργηθεί δεύτερη εγγραφή.", id=linked_id)
        else: self._body_label(self.financial_status, "Δεν έχει δημιουργηθεί οικονομική εγγραφή.")
        year = date.year() if date.isValid() else None; locked = bool(year and is_year_locked(self.db, year)); self._composed_text(self.form_box, "Προβολή τιμολογίου — ΚΛΕΙΔΩΜΕΝΟ {year}" if locked else "Επεξεργασία τιμολογίου", year=year); self.save_button.setEnabled(not locked); self.delete_button.setEnabled(not locked and not bool(linked_type and linked_id)); self.post_button.setEnabled(not locked and not bool(linked_type and linked_id)); self.open_button.setEnabled(path.is_file())

    def load_document(self, row: int, column: int) -> None:
        if column == 0: return
        item = self.table.item(row, 1); document_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if document_id: self._load_by_id(int(document_id))

    def save_metadata(self) -> None:
        if self.selected_id is None: return
        date_text = self.invoice_date.date().toString("yyyy-MM-dd") if self.date_enabled.isChecked() else None
        original = self.db.query_one("SELECT invoice_date FROM invoice_documents WHERE id=?", (self.selected_id,)); original_date = QDate.fromString(original["invoice_date"] if original else "", "yyyy-MM-dd")
        if date_text:
            year = self.invoice_date.date().year()
            if is_year_locked(self.db, year): warn_locked_year(self, self.db, year); return
        if original_date.isValid() and (not date_text or original_date.year() != self.invoice_date.date().year()) and is_year_locked(self.db, original_date.year()): warn_locked_year(self, self.db, original_date.year()); return
        partner_id = self.supplier.selected_partner_id()
        partner_name = canonical_partner_name(
            self.db,
            partner_id,
            self.supplier.text(),
        )
        self.db.execute(
            """UPDATE invoice_documents
            SET invoice_date=?,supplier=?,partner_id=?,invoice_number=?,
                amount_text=?,document_type=?,category=?,notes=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (
                date_text,
                partner_name,
                partner_id,
                self.invoice_number.text().strip(),
                self.amount.text().strip(),
                self.document_type.currentData(),
                combo_source_text(self.category).strip(),
                self.notes.text().strip(),
                self.selected_id,
            ),
        )
        self.refresh()
        self._load_by_id(self.selected_id)

    def create_financial_entry(self, require_confirmation: bool = True) -> int | None:
        """Create one explicitly confirmed income/expense and link it to this document."""
        if self.selected_id is None: return None
        record = self.db.query_one("SELECT * FROM invoice_documents WHERE id=?", (self.selected_id,))
        if record is None: return None
        if record["financial_entry_type"] and record["financial_entry_id"]:
            QMessageBox.information(self, "Οικονομική εγγραφή", "Το έγγραφο είναι ήδη συνδεδεμένο με οικονομική εγγραφή.")
            return None
        document_type = str(self.document_type.currentData() or "unknown")
        if document_type not in {"purchase", "sale"}:
            QMessageBox.warning(self, "Τύπος παραστατικού", "Επίλεξε Αγορά ή Πώληση πριν από την καταχώριση.")
            return None
        if not self.date_enabled.isChecked():
            QMessageBox.warning(self, "Ημερομηνία", "Χρειάζεται ημερομηνία τιμολογίου."); return None
        date = self.invoice_date.date()
        if is_year_locked(self.db, date.year()): warn_locked_year(self, self.db, date.year()); return None
        amount = self._normalize_amount(self.amount.text())
        if amount is None or float(amount) <= 0:
            QMessageBox.warning(self, "Ποσό", "Χρειάζεται έγκυρο συνολικό ποσό μεγαλύτερο από μηδέν."); return None
        destination = "Έξοδα" if document_type == "purchase" else "Έσοδα"
        if require_confirmation and QMessageBox.question(self, "Επιβεβαίωση καταχώρισης", f"Να δημιουργηθεί εγγραφή {amount} € στα {destination};\nΗ ενέργεια δεν γίνεται αυτόματα και το έγγραφο θα συνδεθεί με την εγγραφή.") != QMessageBox.StandardButton.Yes: return None
        partner_id = self.supplier.selected_partner_id()
        if partner_id is None:
            partner_id = match_partner_id(
                self.db,
                self.supplier.text(),
            )
        partner = canonical_partner_name(
            self.db,
            partner_id,
            self.supplier.text(),
        )
        filename = str(record["original_filename"])
        invoice_number = self.invoice_number.text().strip()
        reference = f"Έγγραφο τιμολογίου #{self.selected_id}: {filename}"
        description = f"Τιμολόγιο {invoice_number}" if invoice_number else f"Τιμολόγιο — {filename}"
        notes = " · ".join(value for value in (reference, self.notes.text().strip()) if value)
        with self.db.transaction() as tx:
            if document_type == "purchase":
                entry_id = tx.execute(
                    """INSERT INTO expenses(
                        entry_date,category,description,supplier,partner_id,
                        payment_method,amount,notes
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        date.toString("yyyy-MM-dd"),
                        combo_source_text(self.category).strip() or "Τιμολόγιο αγοράς",
                        description,
                        partner,
                        partner_id,
                        "",
                        float(amount),
                        notes,
                    ),
                )
                entry_type = "expense"
            else:
                entry_id = tx.execute(
                    """INSERT INTO income(
                        entry_date,description,partner,partner_id,
                        payment_method,amount,notes
                    ) VALUES(?,?,?,?,?,?,?)""",
                    (
                        date.toString("yyyy-MM-dd"),
                        description,
                        partner,
                        partner_id,
                        "",
                        float(amount),
                        notes,
                    ),
                )
                entry_type = "income"
            tx.execute(
                """UPDATE invoice_documents
                SET invoice_date=?,supplier=?,partner_id=?,invoice_number=?,
                    amount_text=?,document_type=?,category=?,notes=?,
                    financial_entry_type=?,financial_entry_id=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND financial_entry_id IS NULL""",
                (
                    date.toString("yyyy-MM-dd"),
                    partner,
                    partner_id,
                    invoice_number,
                    amount,
                    document_type,
                    combo_source_text(self.category).strip(),
                    self.notes.text().strip(),
                    entry_type,
                    entry_id,
                    self.selected_id,
                ),
            )
        self._load_by_id(self.selected_id)
        return entry_id

    def post_to_financials(self) -> None:
        entry_id = self.create_financial_entry(require_confirmation=True)
        if entry_id: QMessageBox.information(self, "Ολοκληρώθηκε", "Η οικονομική εγγραφή δημιουργήθηκε και συνδέθηκε με το τιμολόγιο.")

    def clear_form(self) -> None:
        self.selected_id = None; self.original_name.clear(); self.supplier.clear(); self.invoice_number.clear(); self.date_enabled.setChecked(False); self.invoice_date.setDate(working_context_date(self.db)); self.amount.clear(); self.document_type.setCurrentIndex(0); self.category.setCurrentIndex(0); self.notes.clear(); self._composed_text(self.ocr_status, "OCR: δεν εκτελέστηκε"); self._body_label(self.financial_status, "Δεν έχει δημιουργηθεί οικονομική εγγραφή."); self.preview.clear(); self.preview.setText("Χωρίς προεπισκόπηση"); self._composed_text(self.form_box, 'Στοιχεία τιμολογίου'); self.save_button.setEnabled(False); self.open_button.setEnabled(False); self.post_button.setEnabled(False); self.delete_button.setEnabled(False); self.table.clearSelection()

    def open_file(self) -> None:
        record = self.db.query_one("SELECT stored_filename FROM invoice_documents WHERE id=?", (self.selected_id,)) if self.selected_id else None
        path = self._stored_path(record) if record else Path()
        if path.is_file(): QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
        else: QMessageBox.warning(self, "Αρχείο", "Το αποθηκευμένο αρχείο δεν βρέθηκε.")

    def delete_document(self) -> None:
        if self.selected_id is None: return
        record = self.db.query_one("SELECT stored_filename,invoice_date,financial_entry_id FROM invoice_documents WHERE id=?", (self.selected_id,)); date = QDate.fromString(record["invoice_date"] if record else "", "yyyy-MM-dd")
        if record and record["financial_entry_id"]:
            QMessageBox.warning(self, "Συνδεδεμένο τιμολόγιο", "Το έγγραφο διατηρείται επειδή παραπέμπεται από οικονομική εγγραφή."); return
        if date.isValid() and is_year_locked(self.db, date.year()): warn_locked_year(self, self.db, date.year()); return
        if not self.confirm_delete(self, "Διαγραφή τιμολογίου", "Να διαγραφεί η καταχώριση και το διαχειριζόμενο αντίγραφο αρχείου;"): return
        if record is None: return
        # Never unlink the legacy fallback. Multiple rows may share a filename.
        path = owned_file(self.db.path, record["stored_filename"])
        self.db.execute("DELETE FROM invoice_documents WHERE id=?", (self.selected_id,))
        remaining = self.db.query("SELECT stored_filename FROM invoice_documents")
        if not any(str(row["stored_filename"]).casefold() == path.name.casefold() for row in remaining):
            path.unlink(missing_ok=True)
        self.clear_form(); self.refresh()

    def _selected_ids(self) -> list[int]:
        selected = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked: selected.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return selected

    def _set_visible_selected(self, checked: bool) -> None:
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()): self.table.item(row, 0).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.table.blockSignals(False); self._selection_changed()

    def _selection_changed(self, *_args) -> None:
        count = len(self._selected_ids()); self.selected_metric[1].setText(str(count)); self.export_button.setEnabled(count > 0)

    def build_export_zip(self, target: Path, document_ids: list[int]) -> Path:
        if not document_ids: raise ValueError("No invoice documents selected")
        placeholders = ",".join("?" for _ in document_ids); rows = self.db.query(f"SELECT * FROM invoice_documents WHERE id IN ({placeholders}) ORDER BY invoice_date,id", document_ids)
        manifest = []; used_names: set[str] = set()
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for row in rows:
                source = self._stored_path(row)
                if not source.is_file(): continue
                base = self._safe_original_name(Path(row["original_filename"])); archive_name = base; counter = 2
                while archive_name.casefold() in used_names: archive_name = f"{Path(base).stem}_{counter}{Path(base).suffix}"; counter += 1
                used_names.add(archive_name.casefold()); archive.write(source, f"invoices/{archive_name}")
                manifest.append({"id":row["id"],"invoice_date":row["invoice_date"],"supplier":row["supplier"],"invoice_number":row["invoice_number"],"amount":row["amount_text"],"category":row["category"],"filename":archive_name,"notes":row["notes"]})
            csv_stream = io.StringIO(newline=""); writer = csv.DictWriter(csv_stream, fieldnames=["id","invoice_date","supplier","invoice_number","amount","category","filename","notes"], delimiter=";"); writer.writeheader(); writer.writerows(manifest)
            archive.writestr("manifest.csv", csv_stream.getvalue().encode("utf-8-sig")); archive.writestr("manifest.json", json.dumps({"schema":"mastixa-invoice-package-v1","generated_at":datetime.now().isoformat(timespec="seconds"),"count":len(manifest),"invoices":manifest}, ensure_ascii=False, indent=2).encode("utf-8"))
        return target

    def export_selected(self) -> None:
        ids = self._selected_ids()
        if not ids: return
        default = f"fieltra_invoices_{datetime.now():%Y%m%d_%H%M%S}.zip"; filename, _filter = QFileDialog.getSaveFileName(self, _text("Εξαγωγή επιλεγμένων τιμολογίων"), default, "ZIP (*.zip)")
        if not filename: return
        target = Path(filename); target = target if target.suffix.lower() == ".zip" else target.with_suffix(".zip")
        try: self.build_export_zip(target, ids)
        except (OSError, ValueError, zipfile.BadZipFile) as exc: _message(self, 'critical', 'Αποτυχία εξαγωγής', '{error}', error=str(exc)); return
        _message(self, 'information', 'Εξαγωγή', 'Το πακέτο δημιουργήθηκε:\n{target}', target=target)

    def _refresh_years(self) -> None:
        current = self.year_filter.currentData(); years = [row["year"] for row in self.db.query("SELECT DISTINCT SUBSTR(invoice_date,1,4) year FROM invoice_documents WHERE invoice_date IS NOT NULL ORDER BY year DESC")]
        self.year_filter.blockSignals(True); self.year_filter.clear(); self.year_filter.addItem("Όλα τα έτη", None); self.year_filter.addItem("Χωρίς ημερομηνία", "missing")
        for year in years: self.year_filter.addItem(str(year), str(year))
        index = self.year_filter.findData(current); self.year_filter.setCurrentIndex(index if index >= 0 else 0); self.year_filter.blockSignals(False)

    def refresh(self, *_args) -> None:
        self._ensure_schema(); self._refresh_years(); selected_before = set(self._selected_ids()); year = self.year_filter.currentData(); search = self.search.text().strip(); where = ["1=1"]; params: list[object] = []
        if year == "missing": where.append("invoice_date IS NULL")
        elif year: where.append("SUBSTR(invoice_date,1,4)=?"); params.append(year)
        if search: where.append("(supplier LIKE ? OR invoice_number LIKE ? OR original_filename LIKE ? OR category LIKE ?)"); token = f"%{search}%"; params.extend([token] * 4)
        rows = self.db.query(f"SELECT * FROM invoice_documents WHERE {' AND '.join(where)} ORDER BY CASE WHEN invoice_date IS NULL THEN 1 ELSE 0 END,invoice_date DESC,id DESC", params)
        self.table.blockSignals(True); self.table.setRowCount(len(rows)); missing = 0
        for row_index, row in enumerate(rows):
            missing += row["invoice_date"] is None; date = QDate.fromString(row["invoice_date"] or "", "yyyy-MM-dd"); values = ["", date.toString("dd/MM/yyyy") if date.isValid() else "—", row["supplier"], row["invoice_number"], row["amount_text"], row["category"], row["original_filename"], row["ocr_status"]]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                if column == 0: item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable); item.setData(Qt.ItemDataRole.UserRole, int(row["id"])); item.setCheckState(Qt.CheckState.Checked if int(row["id"]) in selected_before else Qt.CheckState.Unchecked)
                if column == 1: item.setData(Qt.ItemDataRole.UserRole, int(row["id"]))
                if column == 7 and row["ocr_status"] in _OCR_BODY_LABELS:
                    self._set_body(item, _OCR_BODY_LABELS[row["ocr_status"]])
                self.table.setItem(row_index, column, item)
        self.table.blockSignals(False); total = self.db.query_one("SELECT COUNT(*) total,SUM(CASE WHEN invoice_date IS NULL THEN 1 ELSE 0 END) missing FROM invoice_documents"); self.total_metric[1].setText(str(int(total["total"] or 0) if total else 0)); self.missing_date_metric[1].setText(str(int(total["missing"] or 0) if total else 0)); self._selection_changed()
