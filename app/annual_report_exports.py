"""Annual-report presentation only; all formats consume the same raw snapshot."""
from dataclasses import dataclass
import csv
from html import escape
from pathlib import Path

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QFont, QPageLayout, QPageSize, QTextDocument, QTextOption
from PySide6.QtPrintSupport import QPrinter

from .language import tr
from .localized_messages import _text
from .report_quantities import quantity_text, average_price_text
from .report_export_io import export_destination, write_sheet
from .ui_helpers import compact_decimal


@dataclass(frozen=True)
class AnnualProduct:
    product: str
    product_id: int | None
    key: tuple
    unit: str
    produced: float
    sold: float
    revenue: float
    avg: float
    stock: float


@dataclass(frozen=True)
class AnnualSnapshot:
    year: int
    product_id: int | None
    product_name: str
    products: tuple[AnnualProduct, ...]
    total_income: float
    other_income: float
    expenses: float

    @property
    def sales_revenue(self):
        return sum(row.revenue for row in self.products)

    @property
    def net_result(self):
        return self.total_income - self.expenses if self.product_id is None else None

    def groups(self, column):
        return [dict(key=row.key, product=row.product, unit=row.unit,
                     quantity=getattr(row, column), revenue=row.revenue) for row in self.products]


def scope_label(snapshot):
    return tr("Όλα τα προϊόντα") if snapshot.product_id is None else snapshot.product_name


def scope_note(snapshot):
    if snapshot.product_id is None:
        return _text("Προβολή όλων των προϊόντων: το Καθαρό αποτέλεσμα είναι "
                     "Σύνολο εσόδων − Σύνολο εξόδων για ολόκληρη την εκμετάλλευση.")
    return _text("Προβολή προϊόντος «{product_name}»: Παραγωγή, Πωλήσεις, Stock και "
                 "Έσοδα πωλήσεων αφορούν μόνο το προϊόν. Τα Λοιπά έσοδα και "
                 "Έξοδα εμφανίζονται ως γενικά / μη κατανεμημένα και ΔΕΝ "
                 "επιμερίζονται αυθαίρετα στο προϊόν. Για αυτό δεν υπολογίζεται "
                 "ψευδές «καθαρό αποτέλεσμα προϊόντος».", product_name=snapshot.product_name)


def finance_rows(snapshot):
    selected = snapshot.product_id is not None
    return [
        (tr("Έσοδα πωλήσεων"), snapshot.sales_revenue,
         tr("Περιλαμβάνονται στο προϊόν" if selected else "Περιλαμβάνονται στο αποτέλεσμα")),
        (tr("Λοιπά έσοδα"), snapshot.other_income,
         tr("Μη κατανεμημένα — δεν αποδίδονται στο προϊόν" if selected else "Περιλαμβάνονται στο αποτέλεσμα")),
        (tr("Έξοδα"), snapshot.expenses,
         tr("Μη κατανεμημένα — δεν αφαιρούνται από προϊόν" if selected else "Περιλαμβάνονται στο αποτέλεσμα")),
    ]


PRODUCT_HEADERS = ("Προϊόν", "Παραγωγή", "Πωλημένα", "Έσοδα πωλήσεων",
                   "Μέση τιμή / μονάδα", "Stock τέλους έτους", "Μονάδα")


def product_average_text(row):
    return f'{compact_decimal(row.revenue / row.sold, 2)} €/{row.unit}' if row.sold > 0 and row.unit else '—'


def export_annual_csv(path: Path, snapshot: AnnualSnapshot) -> None:
    # Preserve the existing BOM, delimiter, metadata rows and product columns.
    with export_destination(path) as staging:
        with staging.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow([tr("Ετήσια Αναφορά Εκμετάλλευσης")])
            writer.writerow([tr("Έτος"), snapshot.year])
            writer.writerow([tr("Προϊόν"), scope_label(snapshot)])
            writer.writerow([])
            writer.writerow([tr(value) for value in PRODUCT_HEADERS])
            for row in snapshot.products:
                writer.writerow([row.product, compact_decimal(row.produced, 3),
                                 compact_decimal(row.sold, 3), compact_decimal(row.revenue, 2),
                                 compact_decimal(row.avg, 2) if row.sold > 0 else '—', compact_decimal(row.stock, 3),
                                 row.unit or "[?]"])


def export_annual_xlsx(path: Path, snapshot: AnnualSnapshot) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.remove(workbook.active)
    try:
        summary = [(tr("Έτος"), "", snapshot.year, ""),
                   (tr("Προϊόν"), scope_label(snapshot), None, "")]
        for label, column in (("Παραγωγή", "produced"), ("Πωλημένα", "sold"),
                              ("Υπόλοιπο stock τέλους έτους", "stock")):
            for row in snapshot.products:
                summary.append((tr(label), row.product, getattr(row, column), row.unit or "[?]"))
        for label, value in (("Έσοδα πωλήσεων", snapshot.sales_revenue),
                             ("Λοιπά έσοδα", snapshot.other_income),
                             ("Έξοδα", snapshot.expenses), ("Καθαρό αποτέλεσμα", snapshot.net_result)):
            summary.append((tr(label), "", value, "EUR"))
        summary.append((tr("Σημείωση"), scope_note(snapshot), None, ""))
        summary.append((tr("Σημείωση"), tr("Το stock τέλους έτους περιλαμβάνει το αδιάθετο υπόλοιπο προηγούμενων ετών."), None, ""))
        write_sheet(workbook, tr("Σύνοψη"), [tr(v) for v in ("Μέγεθος", "Προϊόν / πεδίο αναφοράς", "Τιμή", "Μονάδα")],
                    summary, (35, 85, 22, 20))
        rows = [(row.product, row.produced, row.sold, row.revenue, row.avg if row.sold > 0 else None, row.stock, row.unit or "[?]")
                for row in snapshot.products]
        write_sheet(workbook, tr("Προϊόντα"), [tr(v) for v in PRODUCT_HEADERS], rows, (45, 18, 18, 22, 24, 23, 22))
        write_sheet(workbook, tr("Οικονομικά"), [tr(v) for v in ("Κατηγορία", "Ποσό EUR", "Χειρισμός στην αναφορά προϊόντος")],
                    finance_rows(snapshot), (30, 20, 70))
        with export_destination(path) as staging:
            workbook.save(staging)
    finally:
        workbook.close()


def annual_html(snapshot: AnnualSnapshot) -> str:
    def table(headers, rows, widths):
        head = "".join(f'<th width="{width}%">{escape(str(value))}</th>' for value, width in zip(headers, widths))
        body = "".join('<tr>' + ''.join(f'<td>{escape(str(value))}</td>' for value in row) + '</tr>' for row in rows)
        return f'<table width="100%" cellspacing="0" cellpadding="5"><thead><tr>{head}</tr></thead>{body}</table>'
    money = lambda value: "—" if value is None else f"{compact_decimal(value, 2)} EUR"
    metrics = [(tr(label), quantity_text(snapshot.groups(column))) for label, column in
               (("Παραγωγή", "produced"), ("Πωλημένα", "sold"), ("Υπόλοιπο stock τέλους έτους", "stock"))]
    metrics += [(tr("Έσοδα πωλήσεων"), money(snapshot.sales_revenue)),
                (tr("Μέση τιμή / μονάδα"), average_price_text(snapshot.groups("sold"))),
                (tr("Λοιπά έσοδα"), money(snapshot.other_income)), (tr("Έξοδα"), money(snapshot.expenses)),
                (tr("Καθαρό αποτέλεσμα"), money(snapshot.net_result))]
    products = [(row.product, compact_decimal(row.produced, 3), compact_decimal(row.sold, 3),
                 compact_decimal(row.revenue, 2), product_average_text(row), compact_decimal(row.stock, 3), row.unit or "[?]")
                for row in snapshot.products]
    title = escape(tr("Ετήσια Αναφορά Εκμετάλλευσης"))
    return (f'<html><head><style>body {{color:#26382f; font-family:"Segoe UI"; font-size:10pt;}} '
            'h1 {font-size:19pt;} h2 {font-size:13pt;} th {background:#e9eee9;} '
            'td,th {border:1px solid #cad5ce; text-align:left; vertical-align:top;}</style></head><body>'
            f'<h1>Fieltra - {title}</h1><p>{escape(tr("Έτος"))}: {snapshot.year}<br/>'
            f'{escape(tr("Προϊόν"))}: {escape(scope_label(snapshot))}</p><p>{escape(scope_note(snapshot))}</p>'
            f'<p>{escape(tr("Το stock τέλους έτους περιλαμβάνει το αδιάθετο υπόλοιπο προηγούμενων ετών."))}</p>'
            + table([tr("Μέγεθος"), tr("Τιμή")], metrics, (35, 65))
            + f'<h2>{escape(tr("Ανάλυση προϊόντων"))}</h2>'
            + table([tr(v) for v in PRODUCT_HEADERS], products, (27, 11, 10, 13, 13, 15, 11))
            + f'<h2>{escape(tr("Οικονομική εικόνα έτους"))}</h2>'
            + table([tr(v) for v in ("Κατηγορία", "Ποσό", "Χειρισμός στην αναφορά προϊόντος")],
                    [(label, money(amount), handling) for label, amount, handling in finance_rows(snapshot)], (25, 20, 55))
            + '</body></html>')


def export_annual_pdf(path: Path, snapshot: AnnualSnapshot) -> None:
    with export_destination(path) as staging:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(staging))
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        printer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)
        document = QTextDocument()
        document.setDefaultFont(QFont("Segoe UI", 10))
        option = document.defaultTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        document.setDefaultTextOption(option)
        document.setHtml(annual_html(snapshot))
        document.print_(printer)
        with staging.open("rb") as handle:
            header = handle.read(5)
            handle.seek(max(0, staging.stat().st_size - 1024))
            complete = handle.read().rstrip().endswith(b"%%EOF")
            if printer.printerState() == QPrinter.PrinterState.Error or header != b"%PDF-" or not complete:
                raise OSError(tr("Δεν ήταν δυνατή η εγγραφή του PDF."))
