from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QScrollArea,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .localized_messages import _language, _text
from .database import Database
from .field_activity_timeline import load_field_timeline_rows
from .ui_helpers import compact_decimal, format_kg, table_widget
from .gis.cadastral import cadastral_text, cultivated_area_text


class FieldProfilePage(QWidget):
    """Read-only consolidated profile for one field and one year."""


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
        for name in ('timeline', 'cost_table'):
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
        for name in ():
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

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        outer.addWidget(scroll)

        content = QWidget()
        content.setObjectName("fieldProfileContent")
        content.setStyleSheet(
            "QWidget#fieldProfileContent { background: #f5f6f3; }"
        )
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 18, 16, 20)
        layout.setSpacing(14)
        scroll.setWidget(content)

        title = QLabel("Καρτέλα Αγροτεμαχίου")
        title.setObjectName("pageTitle")
        title.setMinimumHeight(42)
        layout.addWidget(title)

        subtitle = QLabel(
            "Συγκεντρωτική εικόνα παραγωγής, κόστους, εργασιών και φυτεύσεων "
            "για ένα αγροτεμάχιο"
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        filter_box = QGroupBox("Επιλογή")
        filter_layout = QHBoxLayout(filter_box)

        filter_layout.addWidget(QLabel("Αγροτεμάχιο"))
        self.field = QComboBox()
        self.field.currentIndexChanged.connect(self.refresh)
        filter_layout.addWidget(self.field, 1)

        filter_layout.addWidget(QLabel("Έτος"))
        self.year = QComboBox()
        self.year.currentIndexChanged.connect(self.refresh)
        filter_layout.addWidget(self.year)

        layout.addWidget(filter_box)

        # Basic field identity
        identity_box = QGroupBox("Στοιχεία αγροτεμαχίου")
        identity = QGridLayout(identity_box)

        self.name_value = QLabel("—")
        self.kaek_value = QLabel("—")
        self.location_value = QLabel("—")
        self.area_value = QLabel("—")
        self.trees_value = QLabel("—")

        fields = [
            ("Όνομα", self.name_value),
            ("ΚΑΕΚ", self.kaek_value),
            ("Τοποθεσία", self.location_value),
            ("Δηλωμένη καλλιεργούμενη έκταση", self.area_value),
            ("Παραγωγικά δέντρα", self.trees_value),
        ]

        for row_index, (caption, value) in enumerate(fields):
            label = QLabel(caption)
            label.setStyleSheet("font-weight: 700; color: #52655B;")
            value.setStyleSheet("color: #24312B;")
            identity.addWidget(label, row_index, 0)
            identity.addWidget(value, row_index, 1)

        identity.setColumnStretch(1, 1)
        self.cadastral_value=QLabel()
        self.cadastral_value.setWordWrap(True)
        self.cadastral_value.setTextFormat(Qt.TextFormat.PlainText)
        self.cadastral_value.setProperty('mastixaI18nSkipText',True)
        identity.addWidget(self.cadastral_value,len(fields),0,1,2)
        lookup=getattr(db,'_kaek_lookup_controller',None)
        if lookup:lookup.changed.connect(self._refresh_cadastral)
        layout.addWidget(identity_box)

        # KPI cards
        metrics = QGridLayout()

        self.production_card = self._metric("Παραγωγή")
        self.income_card = self._metric("Κατανεμημένα έσοδα")
        self.cost_card = self._metric("Άμεσο κόστος")
        self.result_card = self._metric("Άμεσο αποτέλεσμα")
        self.cost_kg_card = self._metric("Κόστος / kg")
        self.survival_card = self._metric("Επιβίωση φυτεύσεων")
        self.activity_card = self._metric("Καλλιεργητικές καταχωρήσεις")
        self.labor_card = self._metric("Ώρες εργατικών")

        cards = [
            self.production_card,
            self.income_card,
            self.cost_card,
            self.result_card,
            self.cost_kg_card,
            self.survival_card,
            self.activity_card,
            self.labor_card,
        ]

        for index, (box, _value) in enumerate(cards):
            metrics.addWidget(box, index // 4, index % 4)

        layout.addLayout(metrics)

        # Cost breakdown
        cost_box = QGroupBox("Ανάλυση άμεσου κόστους")
        cost_layout = QVBoxLayout(cost_box)

        self.cost_table = table_widget(
            ["Κατηγορία", "Κόστος"]
        )
        self.cost_table.setMinimumHeight(220)
        cost_header = self.cost_table.horizontalHeader()
        cost_header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        cost_header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        cost_layout.addWidget(self.cost_table)
        layout.addWidget(cost_box)

        # Recent activity
        timeline_box = QGroupBox("Πρόσφατες κινήσεις")
        timeline_layout = QVBoxLayout(timeline_box)

        self.timeline = table_widget(
            [
                "Ημερομηνία",
                "Ενότητα",
                "Περιγραφή",
                "Ποσότητα / Κόστος",
            ]
        )
        self.timeline.setMinimumHeight(330)
        timeline_header = self.timeline.horizontalHeader()
        timeline_header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        timeline_header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        timeline_header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        timeline_header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        timeline_layout.addWidget(self.timeline)

        layout.addWidget(timeline_box)
        layout.addStretch()

        self._load_fields()
        self._load_years()
        self.refresh()

    @staticmethod
    def _metric(caption: str):
        box = QGroupBox()
        box.setObjectName("metricCard")
        inner = QVBoxLayout(box)

        label = QLabel(caption)
        label.setObjectName("metricCaption")
        value = QLabel("—")
        value.setObjectName("metricValue")

        inner.addWidget(label)
        inner.addWidget(value)
        return box, value

    @staticmethod
    def _money(value: float) -> str:
        return (
            f"{value:,.2f} €"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
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

    def _has_column(self, table_name: str, column_name: str) -> bool:
        if not self._table_exists(table_name):
            return False
        return any(
            row["name"] == column_name
            for row in self.db.query(
                f"PRAGMA table_info({table_name})"
            )
        )

    def _load_fields(self) -> None:
        current = self.field.currentData()

        self.field.blockSignals(True)
        self.field.clear()
        self.field.addItem("Επίλεξε αγροτεμάχιο", None)

        if self._table_exists("fields"):
            for row in self.db.query(
                "SELECT id,name FROM fields ORDER BY name,id"
            ):
                self.field.addItem(
                    row["name"],
                    int(row["id"]),
                )

        index = self.field.findData(current)
        self.field.setCurrentIndex(index if index >= 0 else 0)
        self.field.blockSignals(False)

    def _load_years(self) -> None:
        current = self.year.currentData()
        years: set[str] = set()

        for table_name, date_column in (
            ("production", "entry_date"),
            ("income", "entry_date"),
            ("expenses", "entry_date"),
            ("farm_activities", "activity_date"),
            ("plant_protection_records", "application_date"),
            ("labor_entries", "work_date"),
            ("planting_batches", "planting_date"),
        ):
            if not self._table_exists(table_name):
                continue

            rows = self.db.query(
                f"""
                SELECT DISTINCT SUBSTR({date_column},1,4) AS year
                FROM {table_name}
                WHERE
                    {date_column} IS NOT NULL
                    AND {date_column} <> ''
                """
            )

            for row in rows:
                value = str(row["year"] or "").strip()
                if value:
                    years.add(value)

        self.year.blockSignals(True)
        self.year.clear()
        self.year.addItem("Όλα τα έτη", None)

        for value in sorted(years, reverse=True):
            self.year.addItem(value, value)

        index = self.year.findData(current)
        self.year.setCurrentIndex(index if index >= 0 else 0)
        self.year.blockSignals(False)

    def _sum(
        self,
        *,
        table: str,
        amount_column: str,
        date_column: str,
        field_id: int,
        year: str | None,
    ) -> float:
        if not self._table_exists(table):
            return 0.0
        if not self._has_column(table, "field_id"):
            return 0.0

        if year is None:
            row = self.db.query_one(
                f"""
                SELECT COALESCE(SUM({amount_column}),0) AS total
                FROM {table}
                WHERE field_id=?
                """,
                (field_id,),
            )
        else:
            row = self.db.query_one(
                f"""
                SELECT COALESCE(SUM({amount_column}),0) AS total
                FROM {table}
                WHERE
                    field_id=?
                    AND SUBSTR({date_column},1,4)=?
                """,
                (field_id, year),
            )

        return float(row["total"] or 0) if row else 0.0

    def _count(
        self,
        *,
        table: str,
        date_column: str,
        field_id: int,
        year: str | None,
    ) -> int:
        if not self._table_exists(table):
            return 0
        if not self._has_column(table, "field_id"):
            return 0

        if year is None:
            row = self.db.query_one(
                f"""
                SELECT COUNT(*) AS total
                FROM {table}
                WHERE field_id=?
                """,
                (field_id,),
            )
        else:
            row = self.db.query_one(
                f"""
                SELECT COUNT(*) AS total
                FROM {table}
                WHERE
                    field_id=?
                    AND SUBSTR({date_column},1,4)=?
                """,
                (field_id, year),
            )

        return int(row["total"] or 0) if row else 0

    def _field_row(self, field_id: int):
        return self.db.query_one(
            "SELECT * FROM fields WHERE id=?",
            (field_id,),
        )

    def _planting_survival(
        self,
        field_id: int,
        year: str | None,
    ) -> tuple[int, int]:
        if not self._table_exists("planting_batches"):
            return 0, 0

        if year is None:
            row = self.db.query_one(
                """
                SELECT
                    COALESCE(SUM(trees_planted),0) AS planted,
                    COALESCE(SUM(trees_alive),0) AS alive
                FROM planting_batches
                WHERE field_id=?
                """,
                (field_id,),
            )
        else:
            row = self.db.query_one(
                """
                SELECT
                    COALESCE(SUM(trees_planted),0) AS planted,
                    COALESCE(SUM(trees_alive),0) AS alive
                FROM planting_batches
                WHERE
                    field_id=?
                    AND SUBSTR(planting_date,1,4)=?
                """,
                (field_id, year),
            )

        if row is None:
            return 0, 0

        return (
            int(row["planted"] or 0),
            int(row["alive"] or 0),
        )

    def _load_timeline(
        self,
        field_id: int,
        year: str | None,
    ) -> None:
        rows = load_field_timeline_rows(
            self.db,
            field_id,
            year,
            limit=60,
        )
        self.timeline.setRowCount(len(rows))

        for row_index, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column in (1, 2) or (column == 0 and value == "Άγνωστη ημερομηνία"):
                    self._set_body(item, str(value))
                self.timeline.setItem(row_index, column, item)

    def _refresh_cadastral(self,field_id=0):
        selected=self.field.currentData()
        if selected is not None and field_id in (0,int(selected)):
            self._composed_text(self.cadastral_value,'{value}',value=lambda:cadastral_text(self.db,int(selected)))

    def _clear(self) -> None:
        for label in (
            self.name_value,
            self.kaek_value,
            self.location_value,
            self.area_value,
            self.trees_value,
            self.cadastral_value,
        ):
            self._composed_text(label, "—")

        for _box, value in (
            self.production_card,
            self.income_card,
            self.cost_card,
            self.result_card,
            self.cost_kg_card,
            self.survival_card,
            self.activity_card,
            self.labor_card,
        ):
            value.setText("—")

        self.cost_table.setRowCount(0)
        self.timeline.setRowCount(0)

    def refresh(self, *_args) -> None:
        self._load_fields()
        self._load_years()

        field_id = self.field.currentData()
        year = self.year.currentData()

        if field_id is None:
            self._clear()
            return

        field = self._field_row(int(field_id))
        if field is None:
            self._clear()
            return

        self._composed_text(self.name_value, '{value}', value=field['name'] or '—')
        self._composed_text(self.kaek_value, '{value}', value=field['kaek'] or '—')
        self._composed_text(self.location_value, '{value}', value=field['location'] or '—')
        self._composed_text(self.area_value, '{value}', value=lambda:cultivated_area_text(field['area_stremma']))
        self._composed_text(self.cadastral_value, '{value}', value=lambda:cadastral_text(self.db,int(field_id)))
        self._composed_text(self.trees_value, "{value}", value=str(int(field["productive_trees"] or 0)))

        production = self._sum(
            table="production",
            amount_column="quantity_kg",
            date_column="entry_date",
            field_id=int(field_id),
            year=year,
        )
        income = self._sum(
            table="income",
            amount_column="amount",
            date_column="entry_date",
            field_id=int(field_id),
            year=year,
        )
        expense = self._sum(
            table="expenses",
            amount_column="amount",
            date_column="entry_date",
            field_id=int(field_id),
            year=year,
        )
        activities_cost = self._sum(
            table="farm_activities",
            amount_column="cost",
            date_column="activity_date",
            field_id=int(field_id),
            year=year,
        )
        protection_cost = self._sum(
            table="plant_protection_records",
            amount_column="cost",
            date_column="application_date",
            field_id=int(field_id),
            year=year,
        )
        labor_cost = self._sum(
            table="labor_entries",
            amount_column="cost",
            date_column="work_date",
            field_id=int(field_id),
            year=year,
        )
        planting_cost = self._sum(
            table="planting_batches",
            amount_column="cost",
            date_column="planting_date",
            field_id=int(field_id),
            year=year,
        )

        total_cost = (
            expense
            + activities_cost
            + protection_cost
            + labor_cost
            + planting_cost
        )
        result = income - total_cost
        cost_per_kg = (
            total_cost / production
            if production > 0
            else 0.0
        )

        planted, alive = self._planting_survival(
            int(field_id),
            year,
        )
        survival = (
            (alive / planted) * 100.0
            if planted > 0
            else 0.0
        )

        activities_count = (
            self._count(
                table="farm_activities",
                date_column="activity_date",
                field_id=int(field_id),
                year=year,
            )
            + self._count(
                table="plant_protection_records",
                date_column="application_date",
                field_id=int(field_id),
                year=year,
            )
        )

        labor_hours = self._sum(
            table="labor_entries",
            amount_column="hours",
            date_column="work_date",
            field_id=int(field_id),
            year=year,
        )

        self.production_card[1].setText(
            format_kg(production)
        )
        self.income_card[1].setText(
            self._money(income)
        )
        self.cost_card[1].setText(
            self._money(total_cost)
        )
        self.result_card[1].setText(
            self._money(result)
        )
        self.cost_kg_card[1].setText(
            self._money(cost_per_kg)
        )
        self.survival_card[1].setText(
            (
                f"{compact_decimal(survival, 1)}%"
                if planted > 0
                else "—"
            )
        )
        self.activity_card[1].setText(
            str(activities_count)
        )
        self.labor_card[1].setText(
            f"{compact_decimal(labor_hours, 2)} ώρες"
        )

        breakdown = [
            ("Κατανεμημένα έξοδα", expense),
            ("Άρδευση & Λίπανση", activities_cost),
            ("Φυτοπροστασία", protection_cost),
            ("Εργατικά", labor_cost),
            ("Φυτεύσεις", planting_cost),
            ("ΣΥΝΟΛΟ", total_cost),
        ]

        self.cost_table.setRowCount(len(breakdown))

        for row_index, (caption, value) in enumerate(breakdown):
            item = QTableWidgetItem(caption)
            self._set_body(item, caption)
            self.cost_table.setItem(row_index, 0, item)
            self.cost_table.setItem(
                row_index,
                1,
                QTableWidgetItem(self._money(value)),
            )

        self._load_timeline(
            int(field_id),
            year,
        )
