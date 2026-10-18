from __future__ import annotations

from .year_filters import populate_year_filter, YearFilteredPage

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .charts import BarChartWidget
from .report_quantities import quantities, quantity_text, money_total, grams_per_tree
from .database import Database
from .localized_messages import _message, _text
from .exporters import export_report_pdf, export_report_xlsx
from .ui_helpers import compact_decimal, table_widget


class ReportsPage(YearFilteredPage):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("reportsContent")
        content.setStyleSheet("QWidget#reportsContent { background: #f5f6f3; }")
        scroll.viewport().setStyleSheet("background: #f5f6f3;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 20)
        layout.setSpacing(14)

        title = QLabel("Αναφορές & Στατιστικά")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Συνοπτική εικόνα ανά έτος και ανάλυση παραγωγής ανά αγροτεμάχιο"
        )
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        filters = QGroupBox()
        filters_outer = QVBoxLayout(filters)

        filters_title = QLabel("Φίλτρα")
        filters_title.setStyleSheet(
            "font-weight: 700; font-size: 15px; color: #26382f;"
        )
        filters_outer.addWidget(filters_title)

        filters_layout = QHBoxLayout()
        filters_outer.addLayout(filters_layout)

        filters_layout.addWidget(QLabel("Έτος"))
        self.year = QComboBox()
        self.year.currentIndexChanged.connect(self.refresh)
        filters_layout.addWidget(self.year)
        filters_layout.addStretch()

        export_button_style = """
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
        """

        self.export_pdf_button = QPushButton("Εξαγωγή PDF")
        self.export_pdf_button.setEnabled(True)
        self.export_pdf_button.setMinimumWidth(130)
        self.export_pdf_button.setStyleSheet(export_button_style)
        self.export_pdf_button.clicked.connect(self.export_pdf)
        filters_layout.addWidget(self.export_pdf_button)

        self.export_excel_button = QPushButton("Εξαγωγή Excel")
        self.export_excel_button.setEnabled(True)
        self.export_excel_button.setMinimumWidth(130)
        self.export_excel_button.setStyleSheet(export_button_style)
        self.export_excel_button.clicked.connect(self.export_excel)
        filters_layout.addWidget(self.export_excel_button)

        layout.addWidget(filters)

        metrics = QGridLayout()

        self.production_card = self._metric_card("Παραγωγή", "—")
        self.income_card = self._metric_card("Έσοδα", "0,00 €")
        self.expenses_card = self._metric_card("Έξοδα", "0,00 €")
        self.balance_card = self._metric_card("Καθαρό αποτέλεσμα", "0,00 €")

        metrics.addWidget(self.production_card[0], 0, 0)
        metrics.addWidget(self.income_card[0], 0, 1)
        metrics.addWidget(self.expenses_card[0], 1, 0)
        metrics.addWidget(self.balance_card[0], 1, 1)

        layout.addLayout(metrics)

        charts_box = QGroupBox()
        charts_outer = QVBoxLayout(charts_box)
        charts_title = QLabel("Γραφήματα ανά έτος")
        charts_title.setStyleSheet("font-weight: 700; font-size: 15px; color: #26382f;")
        charts_outer.addWidget(charts_title)
        self.chart_product = QComboBox()
        self.chart_product.setProperty("mastixaI18nSkipItems", True)
        self.chart_product.currentIndexChanged.connect(self.refresh)
        charts_outer.addWidget(QLabel("Προϊόν"))
        charts_outer.addWidget(self.chart_product)
        charts_layout = QHBoxLayout()
        charts_outer.addLayout(charts_layout)

        self.production_chart = BarChartWidget(
            "Παραγωγή ανά έτος",
            "",
        )
        self.balance_chart = BarChartWidget(
            "Καθαρό αποτέλεσμα ανά έτος",
            "€",
        )

        charts_layout.addWidget(self.production_chart, 1)
        charts_layout.addWidget(self.balance_chart, 1)
        layout.addWidget(charts_box)

        yearly_box = QGroupBox()
        yearly_layout = QVBoxLayout(yearly_box)
        yearly_title = QLabel("Σύνοψη ανά έτος")
        yearly_title.setStyleSheet("font-weight: 700; font-size: 15px; color: #26382f;")
        yearly_layout.addWidget(yearly_title)
        self.yearly_table = table_widget(
            ["Έτος", "Παραγωγή", "Έσοδα", "Έξοδα", "Καθαρό αποτέλεσμα"]
        )
        yearly_layout.addWidget(self.yearly_table)
        layout.addWidget(yearly_box)

        fields_box = QGroupBox()
        fields_layout = QVBoxLayout(fields_box)
        fields_title = QLabel("Παραγωγή ανά αγροτεμάχιο")
        fields_title.setStyleSheet("font-weight: 700; font-size: 15px; color: #26382f;")
        fields_layout.addWidget(fields_title)
        self.fields_table = table_widget(
            [
                "Αγροτεμάχιο",
                "Έκταση στρ.",
                "Παραγωγικά δέντρα",
                "Παραγωγή",
                "g / δέντρο",
            ]
        )
        fields_layout.addWidget(self.fields_table)
        layout.addWidget(fields_box)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

        self._load_years()
        self.refresh()

    def _metric_card(self, caption: str, value: str):
        box = QGroupBox()
        box.setObjectName("metricCard")

        card_layout = QVBoxLayout(box)

        caption_label = QLabel(caption)
        caption_label.setObjectName("metricCaption")

        value_label = QLabel(value)
        value_label.setObjectName("metricValue")

        card_layout.addWidget(caption_label)
        card_layout.addWidget(value_label)

        return box, value_label

    def _load_years(self) -> None:
        populate_year_filter(self, self.year, strings=True)

    def refresh(self) -> None:
        self._load_years()
        year = self.year.currentData()
        production = quantities(self.db, year=year)
        income = money_total(self.db, "income", year)
        expenses = money_total(self.db, "expenses", year)
        self.production_card[1].setProperty("mastixaI18nSkipText", True)
        self.production_card[1].setTextFormat(Qt.TextFormat.PlainText)
        self.production_card[1].setWordWrap(True)
        self.production_card[1].setText(quantity_text(production))
        self.income_card[1].setText(self._money(income))
        self.expenses_card[1].setText(self._money(expenses))
        self.balance_card[1].setText(self._money(income - expenses))
        yearly = self._yearly_rows()
        self._refresh_charts(yearly)
        self._refresh_yearly_table(yearly)
        self._refresh_fields_table(year)
        self._snapshot = dict(
            production=production, income=income, expenses=expenses,
            balance=income-expenses, yearly_rows=[dict(
                year=r["year"], production=r["production"], income=r["income_total"],
                expenses=r["expense_total"], balance=r["income_total"]-r["expense_total"]
            ) for r in reversed(yearly)], field_rows=self._field_rows,
        )

    @staticmethod
    def _money(value: float) -> str:
        return (
            f"{value:,.2f} €"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )


    @staticmethod
    def _fit_table_height(table, row_count: int, max_visible_rows: int = 8) -> None:
        """Keep table headers and rows fully visible without making the page huge."""
        visible_rows = max(1, min(row_count, max_visible_rows))
        header_height = max(32, table.horizontalHeader().height())
        row_height = max(30, table.verticalHeader().defaultSectionSize())
        table.setMinimumHeight(header_height + visible_rows * row_height + 18)
        table.setMaximumHeight(header_height + visible_rows * row_height + 18)

    def _yearly_rows(self):
        years = self.db.query("""SELECT SUBSTR(entry_date,1,4) year FROM production
            UNION SELECT SUBSTR(entry_date,1,4) FROM income
            UNION SELECT SUBSTR(entry_date,1,4) FROM expenses ORDER BY year""")
        return [dict(year=r["year"], production=quantities(self.db, year=r["year"]),
                     income_total=money_total(self.db, "income", r["year"]),
                     expense_total=money_total(self.db, "expenses", r["year"]))
                for r in years if r["year"]]

    def _refresh_charts(self, rows):
        selected = self.chart_product.currentData()
        groups = {str(g["key"]): g for r in rows for g in r["production"]}
        self.chart_product.blockSignals(True)
        self.chart_product.clear()
        for key, group in groups.items():
            self.chart_product.addItem(f"{group['product']} ({group['unit'] or '[?]'})", key)
        index = self.chart_product.findData(selected)
        self.chart_product.setCurrentIndex(index if index >= 0 else 0)
        self.chart_product.blockSignals(False)
        selected = self.chart_product.currentData()
        group = groups.get(selected)
        self.production_chart.unit = group["unit"] if group else ""
        labels = [str(r["year"]) for r in rows]
        self.production_chart.set_data(labels if group and group["unit"] else [], [
            sum(g["quantity"] for g in r["production"] if str(g["key"]) == selected) for r in rows
        ] if group and group["unit"] else [])
        self.balance_chart.set_data(labels, [r["income_total"]-r["expense_total"] for r in rows])

    def _refresh_yearly_table(self, rows) -> None:
        display_rows = list(reversed(rows))
        self.yearly_table.setRowCount(len(display_rows))

        for row_index, row in enumerate(display_rows):
            production = row["production"]
            income = float(row["income_total"] or 0)
            expenses = float(row["expense_total"] or 0)

            values = [
                str(row["year"]),
                quantity_text(production),
                self._money(income),
                self._money(expenses),
                self._money(income - expenses),
            ]

            for column_index, value in enumerate(values):
                self.yearly_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(value),
                )

        self._fit_table_height(self.yearly_table, len(display_rows), 8)


    def _report_snapshot(self) -> dict:
        # Exports consume the same typed values, never numbers parsed from labels.
        year = self.year.currentData()
        return dict(self._snapshot, year_label=_text("Έτος: {year}", year=year) if year is not None else _text("Όλα τα έτη"), font=self.font())

    def export_pdf(self) -> None:
        year = self.year.currentData()
        suffix = str(year) if year is not None else "ola_ta_eti"
        path, _ = QFileDialog.getSaveFileName(
            self,
            _text("Εξαγωγή αναφοράς σε PDF"),
            f"fieltra_report_{suffix}.pdf",
            "PDF (*.pdf)",
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        try:
            export_report_pdf(path, self._report_snapshot())
        except Exception as exc:
            _message(
                self, "critical", "Αποτυχία εξαγωγής PDF",
                "Η εξαγωγή απέτυχε.\n\n{error}", error=str(exc),
            )
            return

        _message(
            self, "information", "Εξαγωγή PDF",
            "Το PDF δημιουργήθηκε:\n{path}", path=path,
        )

    def export_excel(self) -> None:
        year = self.year.currentData()
        suffix = str(year) if year is not None else "ola_ta_eti"
        path, _ = QFileDialog.getSaveFileName(
            self,
            _text("Εξαγωγή αναφοράς σε Excel"),
            f"fieltra_report_{suffix}.xlsx",
            "Excel (*.xlsx)",
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            export_report_xlsx(path, self._report_snapshot())
        except Exception as exc:
            _message(
                self, "critical", "Αποτυχία εξαγωγής Excel",
                "Η εξαγωγή απέτυχε.\n\n{error}", error=str(exc),
            )
            return

        _message(
            self, "information", "Εξαγωγή Excel",
            "Το Excel δημιουργήθηκε:\n{path}", path=path,
        )

    def _refresh_fields_table(self, year):
        self._field_rows = []
        for row in self.db.query("SELECT * FROM fields ORDER BY name,id"):
            production = quantities(self.db, year=year, field_id=row["id"])
            trees = int(row["productive_trees"] or 0)
            self._field_rows.append(dict(name=row["name"], area=float(row["area_stremma"] or 0),
                trees=trees, production=production, grams_per_tree=grams_per_tree(production, trees)))
        self.fields_table.setRowCount(len(self._field_rows))
        for index, row in enumerate(self._field_rows):
            values = [row["name"], compact_decimal(row["area"],3), str(row["trees"]),
                      quantity_text(row["production"]),
                      "—" if row["grams_per_tree"] is None else f"{row['grams_per_tree']:.1f}"]
            for column, value in enumerate(values):
                self.fields_table.setItem(index, column, QTableWidgetItem(value))
        self._fit_table_height(self.fields_table, len(self._field_rows), 10)
