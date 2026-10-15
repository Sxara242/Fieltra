from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .localized_messages import _language, _text
from .database import Database
from .ui_helpers import compact_decimal, format_kg, table_widget


class GlobalSearchPage(QWidget):
    """Ενιαία αναζήτηση σε βασικά δεδομένα του Fieltra."""


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
        for name in ('result_label',):
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
        self._results: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(12)

        title = QLabel("Γενική Αναζήτηση")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Αναζήτηση σε αγροτεμάχια, παραγωγή, οικονομικά, καλλιεργητικές "
            "εργασίες, αποθήκη, μηχανήματα, συνεργάτες και έγγραφα"
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        search_box = QGroupBox()
        search_layout = QHBoxLayout(search_box)

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Γράψε όνομα, ΚΑΕΚ, προϊόν, συνεργάτη, εργασία, σημείωση..."
        )
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self.run_search)
        self.search.textChanged.connect(self._search_text_changed)
        search_layout.addWidget(self.search, 1)

        self.search_button = QPushButton("Αναζήτηση")
        self.search_button.clicked.connect(self.run_search)
        search_layout.addWidget(self.search_button)

        layout.addWidget(search_box)

        summary = QHBoxLayout()
        self.result_label = QLabel("0 αποτελέσματα")
        self.result_label.setStyleSheet(
            "font-weight: 700; color: #26382f;"
        )
        summary.addWidget(self.result_label)
        summary.addStretch()

        self.open_button = QPushButton("Άνοιγμα σχετικής ενότητας")
        self.open_button.clicked.connect(self.open_selected)
        self.open_button.setEnabled(False)
        summary.addWidget(self.open_button)

        layout.addLayout(summary)

        self.table = table_widget(
            [
                "Ενότητα",
                "Τίτλος",
                "Λεπτομέρειες",
                "Ημερομηνία",
            ]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.itemSelectionChanged.connect(
            self._selection_changed
        )
        self.table.itemDoubleClicked.connect(
            lambda _item: self.open_selected()
        )
        self.table.setMinimumHeight(440)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        layout.addWidget(self.table)

        hint = QLabel(
            "Συμβουλή: πάτησε Ctrl+K από οπουδήποτε στο πρόγραμμα για να "
            "έρθεις κατευθείαν εδώ."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #67746d;")
        layout.addWidget(hint)

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def set_query(self, text: str) -> None:
        self.search.setText(text)
        self.run_search()

    def _search_text_changed(self, text: str) -> None:
        if not text.strip():
            self._results = []
            self._render_results()
            return

        if len(text.strip()) >= 3:
            self.run_search()

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

    def _columns(self, table_name: str) -> set[str]:
        if not self._table_exists(table_name):
            return set()

        return {
            row["name"]
            for row in self.db.query(
                f"PRAGMA table_info({table_name})"
            )
        }

    def _add(
        self,
        *,
        section: str,
        title: str,
        details: str,
        date: str = "",
        page_index: int,
        record_id: int | None = None,
    ) -> None:
        if not hasattr(self, "_result_specs"):
            self._result_specs = {}
        self._results.append(
            {
                "section": section,
                "title": title,
                "details": details,
                "date": date,
                "page_index": page_index,
                "record_id": record_id,
            }
        )

    @staticmethod
    def _like_params(query: str, count: int) -> tuple[str, ...]:
        token = f"%{query}%"
        return tuple(token for _ in range(count))

    def run_search(self) -> None:
        self._result_specs = {}
        query = self.search.text().strip()

        if not query:
            self._results = []
            self._render_results()
            return

        self._results = []

        self._search_fields(query)
        self._search_production(query)
        self._search_money(query)
        self._search_activities(query)
        self._search_plant_protection(query)
        self._search_inventory(query)
        self._search_equipment(query)
        self._search_partners(query)
        self._search_invoice_documents(query)
        self._search_labor(query)
        self._search_plantings(query)
        self._search_sales(query)

        self._results.sort(
            key=lambda item: (
                item["section"].casefold(),
                item["title"].casefold(),
                item["date"],
            )
        )

        self._render_results()

    def _search_fields(self, query: str) -> None:
        if not self._table_exists("fields"):
            return

        rows = self.db.query(
            """
            SELECT *
            FROM fields
            WHERE
                name LIKE ?
                OR kaek LIKE ?
                OR location LIKE ?
                OR notes LIKE ?
            ORDER BY name,id
            LIMIT 100
            """,
            self._like_params(query, 4),
        )

        for row in rows:
            details = " | ".join(
                part
                for part in (
                    f"ΚΑΕΚ: {row['kaek']}" if row["kaek"] else "",
                    row["location"] or "",
                    f"{compact_decimal(row['area_stremma'], 3)} στρ.",
                )
                if part
            )

            self._add(
                section="Αγροτεμάχια",
                title=row["name"] or f"ID {row['id']}",
                details=details,
                page_index=2,
                record_id=int(row["id"]),
            )
            self._result_specs[id(self._results[-1])] = {2: ("{kaek}{location}{area} {unit}", {"kaek": ("ΚΑΕΚ: " + row["kaek"] + " | ") if row["kaek"] else "", "location": (row["location"] + " | ") if row["location"] else "", "area": compact_decimal(row["area_stremma"], 3)}, {"unit": "στρ."})}
            if row["kaek"]:
                self._result_specs[id(self._results[-1])][2] = ("ΚΑΕΚ: {kaek} | {location}{area} {unit}", {"kaek": row["kaek"], "location": (row["location"] + " | ") if row["location"] else "", "area": compact_decimal(row["area_stremma"], 3)}, {"unit": "στρ."})

    def _search_production(self, query: str) -> None:
        if not self._table_exists("production"):
            return

        columns = self._columns("production")
        product_expr = "p.product" if "product" in columns else "''"

        rows = self.db.query(
            f"""
            SELECT
                p.*,
                f.name AS field_name,
                {product_expr} AS search_product
            FROM production p
            LEFT JOIN fields f ON f.id=p.field_id
            WHERE
                COALESCE(f.name,'') LIKE ?
                OR COALESCE({product_expr},'') LIKE ?
                OR COALESCE(p.notes,'') LIKE ?
            ORDER BY p.entry_date DESC,p.id DESC
            LIMIT 100
            """,
            self._like_params(query, 3),
        )

        for row in rows:
            self._add(
                section="Παραγωγή",
                title=row["field_name"] or "Χωρίς αγροτεμάχιο",
                details=(
                    format_kg(row["quantity_kg"])
                    + (
                        f" | {row['search_product']}"
                        if row["search_product"]
                        else ""
                    )
                    + (
                        f" | {row['notes']}"
                        if row["notes"]
                        else ""
                    )
                ),
                date=row["entry_date"] or "",
                page_index=3,
                record_id=int(row["id"]),
            )
            if not row["field_name"]: self._result_specs[id(self._results[-1])] = {1: ("Χωρίς αγροτεμάχιο", {}, {})}

    def _search_money(self, query: str) -> None:
        for table, section, page_index in (
            ("income", "Έσοδα", 4),
            ("expenses", "Έξοδα", 5),
        ):
            if not self._table_exists(table):
                continue

            columns = self._columns(table)
            optional = []

            for name in (
                "description",
                "partner",
                "supplier",
                "category",
                "payment_method",
                "notes",
            ):
                if name in columns:
                    optional.append(name)

            if not optional:
                continue

            where = " OR ".join(
                f"COALESCE({name},'') LIKE ?"
                for name in optional
            )

            rows = self.db.query(
                f"""
                SELECT *
                FROM {table}
                WHERE {where}
                ORDER BY entry_date DESC,id DESC
                LIMIT 100
                """,
                self._like_params(query, len(optional)),
            )

            for row in rows:
                description = (
                    row["description"]
                    if "description" in columns
                    else ""
                ) or ""
                details = f"{float(row['amount'] or 0):.2f} €"

                if "category" in columns and row["category"]:
                    details += f" | {row['category']}"

                if "partner" in columns and row["partner"]:
                    details += f" | {row['partner']}"

                if "supplier" in columns and row["supplier"]:
                    details += f" | {row['supplier']}"

                self._add(
                    section=section,
                    title=description or f"ID {row['id']}",
                    details=details,
                    date=row["entry_date"] or "",
                    page_index=page_index,
                    record_id=int(row["id"]),
                )

    def _search_activities(self, query: str) -> None:
        if not self._table_exists("farm_activities"):
            return

        rows = self.db.query(
            """
            SELECT
                a.*,
                f.name AS field_name
            FROM farm_activities a
            LEFT JOIN fields f ON f.id=a.field_id
            WHERE
                COALESCE(f.name,'') LIKE ?
                OR COALESCE(a.category,'') LIKE ?
                OR COALESCE(a.description,'') LIKE ?
                OR COALESCE(a.notes,'') LIKE ?
            ORDER BY a.activity_date DESC,a.id DESC
            LIMIT 100
            """,
            self._like_params(query, 4),
        )

        for row in rows:
            self._add(
                section="Άρδευση & Λίπανση",
                title=row["category"] or "Καταχώρηση",
                details=(
                    (row["field_name"] or "Γενική")
                    + (
                        f" | {row['description']}"
                        if row["description"]
                        else ""
                    )
                ),
                date=row["activity_date"] or "",
                page_index=12,
                record_id=int(row["id"]),
            )
            specs = {}
            if (row["category"] or "Καταχώρηση") in ("Πότισμα", "Λίπανση", "Καταχώρηση"): specs[1] = (row["category"] or "Καταχώρηση", {}, {})
            if not row["field_name"]: specs[2] = ("Γενική{description}", {"description": (" | " + row["description"]) if row["description"] else ""}, {})
            self._result_specs[id(self._results[-1])] = specs

    def _search_plant_protection(self, query: str) -> None:
        if not self._table_exists("plant_protection_records"):
            return

        rows = self.db.query(
            """
            SELECT
                p.*,
                f.name AS field_name
            FROM plant_protection_records p
            LEFT JOIN fields f ON f.id=p.field_id
            WHERE
                COALESCE(f.name,'') LIKE ?
                OR COALESCE(p.purpose,'') LIKE ?
                OR COALESCE(p.product_name,'') LIKE ?
                OR COALESCE(p.active_ingredient,'') LIKE ?
                OR COALESCE(p.notes,'') LIKE ?
            ORDER BY p.application_date DESC,p.id DESC
            LIMIT 100
            """,
            self._like_params(query, 5),
        )

        for row in rows:
            self._add(
                section="Φυτοπροστασία",
                title=row["product_name"] or "Επέμβαση",
                details=(
                    (row["field_name"] or "")
                    + (
                        f" | {row['purpose']}"
                        if row["purpose"]
                        else ""
                    )
                    + (
                        f" | {row['active_ingredient']}"
                        if row["active_ingredient"]
                        else ""
                    )
                ),
                date=row["application_date"] or "",
                page_index=19,
                record_id=int(row["id"]),
            )
            if not row["product_name"]: self._result_specs[id(self._results[-1])] = {1: ("Επέμβαση", {}, {})}

    def _search_inventory(self, query: str) -> None:
        if not self._table_exists("inventory_items"):
            return

        rows = self.db.query(
            """
            SELECT *
            FROM inventory_items
            WHERE
                name LIKE ?
                OR category LIKE ?
                OR unit LIKE ?
                OR notes LIKE ?
            ORDER BY name,id
            LIMIT 100
            """,
            self._like_params(query, 4),
        )

        for row in rows:
            self._add(
                section="Αποθήκη & Εφόδια",
                title=row["name"] or f"ID {row['id']}",
                details=(
                    (row["category"] or "")
                    + (
                        f" | μονάδα: {row['unit']}"
                        if row["unit"]
                        else ""
                    )
                ),
                page_index=13,
                record_id=int(row["id"]),
            )
            if row["unit"]: self._result_specs[id(self._results[-1])] = {2: ("{category} | μονάδα: {unit}", {"category": row["category"] or "", "unit": row["unit"]}, {})}

    def _search_equipment(self, query: str) -> None:
        if not self._table_exists("equipment"):
            return

        columns = self._columns("equipment")
        search_columns = [
            name
            for name in (
                "name",
                "category",
                "brand",
                "model",
                "serial_number",
                "notes",
            )
            if name in columns
        ]

        if not search_columns:
            return

        where = " OR ".join(
            f"COALESCE({name},'') LIKE ?"
            for name in search_columns
        )

        rows = self.db.query(
            f"""
            SELECT *
            FROM equipment
            WHERE {where}
            ORDER BY id DESC
            LIMIT 100
            """,
            self._like_params(query, len(search_columns)),
        )

        for row in rows:
            name = (
                row["name"]
                if "name" in columns
                else ""
            ) or f"ID {row['id']}"

            detail_parts = []
            for column in ("brand", "model", "category"):
                if column in columns and row[column]:
                    detail_parts.append(str(row[column]))

            self._add(
                section="Μηχανήματα & Συντήρηση",
                title=name,
                details=" | ".join(detail_parts),
                page_index=16,
                record_id=int(row["id"]),
            )

    def _search_partners(self, query: str) -> None:
        if not self._table_exists("partners"):
            return

        columns = self._columns("partners")
        search_columns = [
            name
            for name in (
                "name",
                "tax_id",
                "contact_person",
                "phone",
                "email",
                "products",
                "notes",
            )
            if name in columns
        ]

        if not search_columns:
            return

        where = " OR ".join(
            f"COALESCE({name},'') LIKE ?"
            for name in search_columns
        )

        rows = self.db.query(
            f"""
            SELECT *
            FROM partners
            WHERE {where}
            ORDER BY name,id
            LIMIT 100
            """,
            self._like_params(query, len(search_columns)),
        )

        for row in rows:
            self._add(
                section="Προμηθευτές & Αγοραστές",
                title=row["name"] or f"ID {row['id']}",
                details=" | ".join(
                    part
                    for part in (
                        row["tax_id"] or "",
                        row["phone"] or "",
                        row["products"] or "",
                    )
                    if part
                ),
                page_index=17,
                record_id=int(row["id"]),
            )

    def _search_invoice_documents(self, query: str) -> None:
        if not self._table_exists("invoice_documents"):
            return

        columns = self._columns("invoice_documents")
        search_columns = [
            name
            for name in (
                "original_name",
                "stored_name",
                "supplier",
                "partner_name",
                "document_type",
                "notes",
            )
            if name in columns
        ]

        if not search_columns:
            return

        where = " OR ".join(
            f"COALESCE({name},'') LIKE ?"
            for name in search_columns
        )

        rows = self.db.query(
            f"""
            SELECT *
            FROM invoice_documents
            WHERE {where}
            ORDER BY id DESC
            LIMIT 100
            """,
            self._like_params(query, len(search_columns)),
        )

        date_column = (
            "document_date"
            if "document_date" in columns
            else ""
        )

        for row in rows:
            title = ""
            for column in ("original_name", "stored_name"):
                if column in columns and row[column]:
                    title = row[column]
                    break

            self._add(
                section="Έγγραφα Τιμολογίων",
                title=title or f"Έγγραφο #{row['id']}",
                details=" | ".join(
                    str(row[column])
                    for column in search_columns
                    if row[column]
                ),
                date=(
                    row[date_column]
                    if date_column and row[date_column]
                    else ""
                ),
                page_index=18,
                record_id=int(row["id"]),
            )
            if not title: self._result_specs[id(self._results[-1])] = {1: ("Έγγραφο #{id}", {"id": row["id"]}, {})}

    def _search_labor(self, query: str) -> None:
        if self._table_exists("workers"):
            rows = self.db.query(
                """
                SELECT *
                FROM workers
                WHERE
                    name LIKE ?
                    OR role LIKE ?
                    OR phone LIKE ?
                    OR notes LIKE ?
                ORDER BY name,id
                LIMIT 100
                """,
                self._like_params(query, 4),
            )

            for row in rows:
                self._add(
                    section="Εργατικά & Προσωπικό",
                    title=row["name"] or f"ID {row['id']}",
                    details=" | ".join(
                        part
                        for part in (
                            row["role"] or "",
                            row["phone"] or "",
                        )
                        if part
                    ),
                    page_index=21,
                    record_id=int(row["id"]),
                )

        if not self._table_exists("labor_entries"):
            return

        rows = self.db.query(
            """
            SELECT
                l.*,
                f.name AS field_name,
                w.name AS worker_name
            FROM labor_entries l
            LEFT JOIN fields f ON f.id=l.field_id
            LEFT JOIN workers w ON w.id=l.worker_id
            WHERE
                COALESCE(l.work_type,'') LIKE ?
                OR COALESCE(l.notes,'') LIKE ?
                OR COALESCE(f.name,'') LIKE ?
                OR COALESCE(w.name,'') LIKE ?
            ORDER BY l.work_date DESC,l.id DESC
            LIMIT 100
            """,
            self._like_params(query, 4),
        )

        for row in rows:
            self._add(
                section="Εργατικά & Προσωπικό",
                title=row["work_type"] or "Εργασία",
                details=" | ".join(
                    part
                    for part in (
                        row["worker_name"] or "",
                        row["field_name"] or "",
                        f"{float(row['hours'] or 0):.2f} ώρες",
                    )
                    if part
                ),
                date=row["work_date"] or "",
                page_index=21,
                record_id=int(row["id"]),
            )
            specs = {2: ("{prefix}{hours} ώρες", {"prefix": "".join(str(v) + " | " for v in (row["worker_name"], row["field_name"]) if v), "hours": f"{float(row['hours'] or 0):.2f}"}, {})}
            if not row["work_type"]: specs[1] = ("Εργασία", {}, {})
            self._result_specs[id(self._results[-1])] = specs

    def _search_plantings(self, query: str) -> None:
        if not self._table_exists("planting_batches"):
            return

        rows = self.db.query(
            """
            SELECT
                p.*,
                f.name AS field_name
            FROM planting_batches p
            LEFT JOIN fields f ON f.id=p.field_id
            WHERE
                COALESCE(f.name,'') LIKE ?
                OR COALESCE(p.material_type,'') LIKE ?
                OR COALESCE(p.source,'') LIKE ?
                OR COALESCE(p.variety,'') LIKE ?
                OR COALESCE(p.spacing,'') LIKE ?
                OR COALESCE(p.notes,'') LIKE ?
            ORDER BY p.planting_date DESC,p.id DESC
            LIMIT 100
            """,
            self._like_params(query, 6),
        )

        for row in rows:
            losses = max(
                int(row["trees_planted"] or 0)
                - int(row["trees_alive"] or 0),
                0,
            )

            self._add(
                section="Φυτεύσεις & Δέντρα",
                title=row["field_name"] or "Φύτευση",
                details=(
                    f"{int(row['trees_planted'] or 0)} φυτεμένα"
                    f" | {int(row['trees_alive'] or 0)} ζωντανά"
                    f" | {losses} απώλειες"
                    + (
                        f" | {row['material_type']}"
                        if row["material_type"]
                        else ""
                    )
                    + (
                        f" | {row['source']}"
                        if row["source"]
                        else ""
                    )
                ),
                date=row["planting_date"] or "",
                page_index=23,
                record_id=int(row["id"]),
            )
            specs = {2: ("{planted} φυτεμένα | {alive} ζωντανά | {losses} απώλειες{material}{source}", {"planted": int(row["trees_planted"] or 0), "alive": int(row["trees_alive"] or 0), "losses": losses, "material": (" | " + row["material_type"]) if row["material_type"] else "", "source": (" | " + row["source"]) if row["source"] else ""}, {})}
            if not row["field_name"]: specs[1] = ("Φύτευση", {}, {})
            self._result_specs[id(self._results[-1])] = specs


    def _search_sales(self, query: str) -> None:
        if not self._table_exists("production_sales"):
            return

        rows = self.db.query(
            """
            SELECT *
            FROM production_sales
            WHERE
                COALESCE(buyer_name,'') LIKE ?
                OR COALESCE(notes,'') LIKE ?
                OR COALESCE(payment_method,'') LIKE ?
            ORDER BY sale_date DESC,id DESC
            LIMIT 100
            """,
            self._like_params(query, 3),
        )

        for row in rows:
            self._add(
                section="Πωλήσεις Παραγωγής",
                title=row["buyer_name"] or f"Πώληση #{row['id']}",
                details=(
                    f"{format_kg(row['quantity_kg'])}"
                    f" | {float(row['price_per_kg'] or 0):.2f} €/kg"
                    f" | {float(row['total_amount'] or 0):.2f} €"
                ),
                date=row["sale_date"] or "",
                page_index=26,
                record_id=int(row["id"]),
            )
            if not row["buyer_name"]: self._result_specs[id(self._results[-1])] = {1: ("Πώληση #{id}", {"id": row["id"]}, {})}


    def _render_results(self) -> None:
        self.table.setRowCount(len(self._results))

        for row_index, result in enumerate(self._results):
            values = [
                result["section"],
                result["title"],
                result["details"],
                result["date"],
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column_index == 0:
                    self._set_body(item, result["section"])
                else:
                    spec = getattr(self, "_result_specs", {}).get(id(result), {}).get(column_index)
                    if spec is not None:
                        self._set_body(item, spec[0], _labels=spec[2], **spec[1])
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    result,
                )

                if column_index == 2:
                    item.setToolTip(item.text())

                self.table.setItem(
                    row_index,
                    column_index,
                    item,
                )

        self._body_label(self.result_label, "{count} αποτελέσματα", count=len(self._results))
        self._selection_changed()

    def _selected_result(self) -> dict | None:
        selected = self.table.selectedItems()

        if not selected:
            return None

        item = self.table.item(
            selected[0].row(),
            0,
        )

        if item is None:
            return None

        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, dict) else None

    def _selection_changed(self) -> None:
        self.open_button.setEnabled(
            self._selected_result() is not None
        )

    def open_selected(self) -> None:
        result = self._selected_result()

        if result is None:
            return

        window = self.window()
        change_page = getattr(window, "change_page", None)

        if callable(change_page):
            change_page(int(result["page_index"]))
