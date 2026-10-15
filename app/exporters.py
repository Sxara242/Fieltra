from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape as xml_escape

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter

from .ui_helpers import compact_decimal
from .language import tr
from .report_quantities import quantity_text


def export_report_pdf(path: str, snapshot: dict) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(output))
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(
        QMarginsF(12, 12, 12, 12),
        QPageLayout.Unit.Millimeter,
    )

    document = QTextDocument()
    document.setDefaultFont(snapshot["font"])

    yearly_rows = "".join(
        f"""
        <tr>
            <td>{escape(str(row["year"]))}</td>
            <td class="num">{escape(quantity_text(row["production"]))}</td>
            <td class="num">{row["income"]:.2f} €</td>
            <td class="num">{row["expenses"]:.2f} €</td>
            <td class="num">{row["balance"]:.2f} €</td>
        </tr>
        """
        for row in snapshot["yearly_rows"]
    ) or f'<tr><td colspan="5">{escape(tr("Δεν υπάρχουν δεδομένα."))}</td></tr>'

    field_rows = "".join(
        f"""
        <tr>
            <td>{escape(str(row["name"]))}</td>
            <td class="num">{compact_decimal(row["area"], 3)}</td>
            <td class="num">{row["trees"]}</td>
            <td class="num">{escape(quantity_text(row["production"]))}</td>
            <td class="num">{"—" if row["grams_per_tree"] is None else compact_decimal(row["grams_per_tree"], 1)}</td>
        </tr>
        """
        for row in snapshot["field_rows"]
    ) or f'<tr><td colspan="5">{escape(tr("Δεν υπάρχουν δεδομένα."))}</td></tr>'

    generated = datetime.now().strftime("%d/%m/%Y %H:%M")
    year_label = escape(tr(snapshot["year_label"]))
    report_title = escape(tr("Fieltra - Αναφορά"))
    report_subtitle = escape(tr("Αναφορές & Στατιστικά"))
    generated_label = escape(tr("Δημιουργήθηκε"))
    production_label = escape(tr("Παραγωγή"))
    income_label = escape(tr("Έσοδα"))
    expenses_label = escape(tr("Έξοδα"))
    balance_label = escape(tr("Καθαρό αποτέλεσμα"))
    yearly_label = escape(tr("Σύνοψη ανά έτος"))
    year_header = escape(tr("Έτος"))
    field_production_label = escape(tr("Παραγωγή ανά αγροτεμάχιο"))
    field_label = escape(tr("Αγροτεμάχιο"))
    area_label = escape(tr("Έκταση στρ."))
    trees_label = escape(tr("Παραγωγικά δέντρα"))
    grams_label = escape(tr("g / δέντρο"))

    html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: "Segoe UI"; color: #26382f; font-size: 10pt; }}
        h1 {{ font-size: 20pt; margin-bottom: 2px; }}
        h2 {{ font-size: 13pt; margin-top: 18px; margin-bottom: 6px; }}
        .subtitle {{ color: #67746d; margin-bottom: 14px; }}
        .meta {{ color: #67746d; font-size: 8.5pt; margin-bottom: 12px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; }}
        th {{
            background: #e9eee9;
            color: #26382f;
            border: 1px solid #d9dedb;
            padding: 6px;
            font-weight: bold;
        }}
        td {{ border: 1px solid #d9dedb; padding: 6px; }}
        .num {{ text-align: right; }}
        .metrics td {{ width: 25%; background: #f8f9f8; vertical-align: top; }}
        .metric-label {{ color: #67746d; font-size: 8.5pt; }}
        .metric-value {{ font-size: 15pt; font-weight: bold; margin-top: 4px; }}
    </style>
    </head>
    <body>
        <h1>{report_title}</h1>
        <div class="subtitle">{report_subtitle} - {year_label}</div>
        <div class="meta">{generated_label}: {generated}</div>

        <table class="metrics">
            <tr>
                <td><div class="metric-label">{production_label}</div><div class="metric-value">{escape(quantity_text(snapshot["production"]))}</div></td>
                <td><div class="metric-label">{income_label}</div><div class="metric-value">{snapshot["income"]:.2f} €</div></td>
                <td><div class="metric-label">{expenses_label}</div><div class="metric-value">{snapshot["expenses"]:.2f} €</div></td>
                <td><div class="metric-label">{balance_label}</div><div class="metric-value">{snapshot["balance"]:.2f} €</div></td>
            </tr>
        </table>

        <h2>{yearly_label}</h2>
        <table>
            <tr>
                <th>{year_header}</th><th>{production_label}</th><th>{income_label}</th><th>{expenses_label}</th><th>{balance_label}</th>
            </tr>
            {yearly_rows}
        </table>

        <h2>{field_production_label}</h2>
        <table>
            <tr>
                <th>{field_label}</th><th>{area_label}</th><th>{trees_label}</th><th>{production_label}</th><th>{grams_label}</th>
            </tr>
            {field_rows}
        </table>
    </body>
    </html>
    """

    document.setHtml(html)
    document.print_(printer)


def _inline_cell(ref: str, value: str, style: int = 0) -> str:
    safe = xml_escape(str(value))
    return (
        f'<c r="{ref}" t="inlineStr" s="{style}">'
        f"<is><t>{safe}</t></is></c>"
    )


def _number_cell(
    ref: str,
    value: float | int,
    style: int = 0,
    formula: str | None = None,
) -> str:
    formula_xml = f"<f>{xml_escape(formula)}</f>" if formula else ""
    return f'<c r="{ref}" s="{style}">{formula_xml}<v>{value}</v></c>'


def _row_xml(row_index: int, cells: list[str], height: int | None = None) -> str:
    height_attrs = ""
    if height is not None:
        height_attrs = f' ht="{height}" customHeight="1"'
    return f'<row r="{row_index}"{height_attrs}>{"".join(cells)}</row>'


def _sheet_xml(rows: list[str], widths: list[float], freeze_row: int | None = None) -> str:
    cols = "".join(
        f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>'
        for i, width in enumerate(widths, start=1)
    )

    if freeze_row:
        views = (
            '<sheetViews><sheetView workbookViewId="0">'
            f'<pane ySplit="{freeze_row}" topLeftCell="A{freeze_row + 1}" '
            'activePane="bottomLeft" state="frozen"/>'
            '</sheetView></sheetViews>'
        )
    else:
        views = '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'{views}<cols>{cols}</cols><sheetData>{"".join(rows)}</sheetData>'
        '<pageMargins left="0.4" right="0.4" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>'
        '</worksheet>'
    )


def export_report_xlsx(path: str, snapshot: dict) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="3">
    <numFmt numFmtId="164" formatCode="0.000"/>
    <numFmt numFmtId="165" formatCode="#,##0.00 [$€-x-euro2]"/>
    <numFmt numFmtId="166" formatCode="0.0"/>
  </numFmts>
  <fonts count="3">
    <font><sz val="11"/><name val="Segoe UI"/></font>
    <font><b/><sz val="18"/><color rgb="FF26382F"/><name val="Segoe UI"/></font>
    <font><b/><sz val="11"/><color rgb="FF26382F"/><name val="Segoe UI"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE9EEE9"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFD9DEDB"/></left>
      <right style="thin"><color rgb="FFD9DEDB"/></right>
      <top style="thin"><color rgb="FFD9DEDB"/></top>
      <bottom style="thin"><color rgb="FFD9DEDB"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="8">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>
    <xf numFmtId="166" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""

    summary_rows = [
        _row_xml(1, [_inline_cell("A1", tr("Fieltra - Αναφορά"), 1)], 26),
        _row_xml(2, [_inline_cell("A2", tr(snapshot["year_label"]), 2)]),
        _row_xml(4, [
            _inline_cell("A4", tr("Παραγωγή"), 3),
            _inline_cell("B4", tr("Έσοδα"), 3),
            _inline_cell("C4", tr("Έξοδα"), 3),
            _inline_cell("D4", tr("Καθαρό αποτέλεσμα"), 3),
        ]),
        _row_xml(5, [
            _inline_cell("A5", quantity_text(snapshot["production"]), 6),
            _number_cell("B5", snapshot["income"], 5),
            _number_cell("C5", snapshot["expenses"], 5),
            _number_cell("D5", snapshot["balance"], 5, formula="B5-C5"),
        ]),
        _row_xml(7, [_inline_cell("A7", tr("Σύνοψη ανά έτος"), 2)]),
        _row_xml(8, [
            _inline_cell("A8", tr("Έτος"), 3),
            _inline_cell("B8", tr("Παραγωγή"), 3),
            _inline_cell("C8", tr("Έσοδα"), 3),
            _inline_cell("D8", tr("Έξοδα"), 3),
            _inline_cell("E8", tr("Καθαρό αποτέλεσμα"), 3),
        ]),
    ]

    r = 9
    for row in snapshot["yearly_rows"]:
        summary_rows.append(_row_xml(r, [
            _inline_cell(f"A{r}", row["year"], 6),
            _inline_cell(f"B{r}", quantity_text(row["production"]), 6),
            _number_cell(f"C{r}", row["income"], 5),
            _number_cell(f"D{r}", row["expenses"], 5),
            _number_cell(f"E{r}", row["balance"], 5, formula=f"C{r}-D{r}"),
        ]))
        r += 1

    fields_rows = [
        _row_xml(1, [_inline_cell("A1", tr("Παραγωγή ανά αγροτεμάχιο"), 1)], 26),
        _row_xml(2, [_inline_cell("A2", tr(snapshot["year_label"]), 2)]),
        _row_xml(4, [
            _inline_cell("A4", tr("Αγροτεμάχιο"), 3),
            _inline_cell("B4", tr("Έκταση στρ."), 3),
            _inline_cell("C4", tr("Παραγωγικά δέντρα"), 3),
            _inline_cell("D4", tr("Παραγωγή"), 3),
            _inline_cell("E4", tr("g / δέντρο"), 3),
        ]),
    ]

    r = 5
    for row in snapshot["field_rows"]:
        fields_rows.append(_row_xml(r, [
            _inline_cell(f"A{r}", row["name"], 6),
            _number_cell(f"B{r}", row["area"], 4),
            _number_cell(f"C{r}", row["trees"], 6),
            _inline_cell(f"D{r}", quantity_text(row["production"]), 6),
            (_inline_cell(f"E{r}", "—", 6) if row["grams_per_tree"] is None
             else _number_cell(f"E{r}", row["grams_per_tree"], 7)),
        ]))
        r += 1

    sheet1 = _sheet_xml(summary_rows, [20, 18, 18, 22, 22], freeze_row=8)
    sheet2 = _sheet_xml(fields_rows, [28, 16, 20, 18, 18], freeze_row=4)

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

    workbook = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="{xml_escape(tr('Σύνοψη'))}" sheetId="1" r:id="rId1"/>
    <sheet name="{xml_escape(tr('Αγροτεμάχια'))}" sheetId="2" r:id="rId2"/>
  </sheets>
  <calcPr calcId="191029" fullCalcOnLoad="1" forceFullCalc="1"/>
</workbook>"""

    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    now_iso = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    core = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties
 xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Fieltra Report</dc:title>
  <dc:creator>Fieltra</dc:creator>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:modified>
</cp:coreProperties>"""

    app = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Fieltra</Application>
</Properties>"""

    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", styles_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet1)
        archive.writestr("xl/worksheets/sheet2.xml", sheet2)
        archive.writestr("docProps/core.xml", core)
        archive.writestr("docProps/app.xml", app)
