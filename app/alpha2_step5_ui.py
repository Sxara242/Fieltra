from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .declaration import DeclarationPage
from .fields import FieldsPage
from .invoice_documents import InvoiceDocumentsPage
from .upload_center import UploadCenterPage


_INSTALLED = False


def _under_construction_panel(title: str, detail: str, parent: QWidget) -> QWidget:
    panel = QWidget(parent)
    panel.setObjectName("alpha2UnderConstructionPanel")
    panel.setProperty("mastixaUnderConstructionPanel", True)

    outer = QVBoxLayout(panel)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    scroll = QScrollArea(panel)
    scroll.setObjectName("underConstructionScroll")
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    outer.addWidget(scroll)

    content = QWidget()
    content.setObjectName("underConstructionContent")
    layout = QVBoxLayout(content)
    layout.setContentsMargins(28, 28, 28, 28)
    layout.setSpacing(12)
    layout.addStretch(1)

    title_label = QLabel(title, content)
    title_label.setObjectName("pageTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_label.setWordWrap(True)
    title_label.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Minimum,
    )
    layout.addWidget(title_label)

    status = QLabel("Υπό κατασκευή", content)
    status.setObjectName("underConstructionStatus")
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    status.setWordWrap(True)
    status.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Minimum,
    )
    status.setStyleSheet("font-size: 22px; font-weight: 700;")
    layout.addWidget(status)

    detail_label = QLabel(detail, content)
    detail_label.setObjectName("underConstructionDetail")
    detail_label.setAlignment(
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
    )
    detail_label.setWordWrap(True)
    detail_label.setMinimumWidth(0)
    detail_label.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Minimum,
    )
    layout.addWidget(detail_label)

    layout.addStretch(1)
    scroll.setWidget(content)
    return panel


def _gate_page(page: QWidget, title: str, detail: str) -> None:
    if page.property("mastixaUnderConstruction"):
        return

    root_layout = page.layout()
    if root_layout is None:
        return

    original_surfaces: list[QWidget] = []
    for index in range(root_layout.count()):
        item = root_layout.itemAt(index)
        widget = item.widget() if item is not None else None
        if widget is not None:
            original_surfaces.append(widget)

    for surface in original_surfaces:
        surface.setEnabled(False)
        surface.hide()

    panel = _under_construction_panel(title, detail, page)
    root_layout.addWidget(panel, 1)

    page._alpha2_original_surfaces = original_surfaces
    page.under_construction_panel = panel
    page.setProperty("mastixaUnderConstruction", True)


def _install_declaration_gate() -> None:
    declaration_init = DeclarationPage.__init__
    upload_init = UploadCenterPage.__init__

    detail = (
        "Η δημιουργία, προεπισκόπηση και αποστολή δηλώσεων θα ενεργοποιηθεί "
        "σε επόμενη έκδοση. Τα υπάρχοντα τοπικά δεδομένα διατηρούνται."
    )

    def declaration_under_construction(self, db) -> None:
        declaration_init(self, db)
        _gate_page(self, "Δήλωση & Αποστολή", detail)

    def upload_under_construction(self, db) -> None:
        upload_init(self, db)
        _gate_page(self, "Δήλωση & Αποστολή", detail)

    DeclarationPage.__init__ = declaration_under_construction
    UploadCenterPage.__init__ = upload_under_construction


def _install_invoice_documents_gate() -> None:
    original_init = InvoiceDocumentsPage.__init__

    def invoice_documents_under_construction(self, db) -> None:
        original_init(self, db)
        _gate_page(
            self,
            "Έγγραφα Τιμολογίων",
            (
                "Η εισαγωγή, OCR, επεξεργασία και οικονομική καταχώριση "
                "τιμολογίων θα ενεργοποιηθούν σε επόμενη έκδοση. "
                "Τα υπάρχοντα δεδομένα διατηρούνται."
            ),
        )

    InvoiceDocumentsPage.__init__ = invoice_documents_under_construction


def _install_fields_ai_import_gate() -> None:
    original_init = FieldsPage.__init__

    def init_with_future_ai_import(self, db) -> None:
        original_init(self, db)
        if self.findChild(QPushButton, "fieldsAiImportButton") is not None:
            return

        form = self.form_box.layout()
        if not isinstance(form, QFormLayout):
            return

        button = QPushButton(
            "AI εισαγωγή από έγγραφο / φωτογραφία — Υπό κατασκευή",
            self.form_box,
        )
        button.setObjectName("fieldsAiImportButton")
        button.setProperty("mastixaFutureOnly", True)
        button.setEnabled(False)
        button.setToolTip(
            "Μελλοντικά θα εξάγει στοιχεία από έγγραφο ή φωτογραφία "
            "για έλεγχο πριν την αποθήκευση."
        )
        form.addRow("", button)
        self.ai_import_button = button

    FieldsPage.__init__ = init_with_future_ai_import


def install_alpha2_step5_ui() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    _install_declaration_gate()
    _install_invoice_documents_gate()
    _install_fields_ai_import_gate()
    # KAEK now has a verified provider/queue. Do not replace the real map
    # handler or disable its action with the historical unverified-API gate.
    _INSTALLED = True
