from __future__ import annotations

from .localized_messages import _message
from .version import APP_NAME, APP_VERSION


from .icon_theme import install_icon_theme
from .appearance_theme import ThemeController
from .language import LanguageController, install_language_controller
from .app_logging import configure_logging, get_logger

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QMessageBox,
    QWidget,
)

from .activities import ActivitiesPage
from .alerts import AlertsPage
from .audit import AuditPage
from .backup_manager import BackupError, BackupManager
from .backup_error_ui import show_backup_error
from .database import BASE_DIR, Database
from .dashboard import DashboardPage
from .data_export import DataExportPage
from .data_quality import DataQualityPage
from .declaration import DeclarationPage
from .field_finance import FieldFinancePage
from .global_search import GlobalSearchPage
from .farm_calendar import FarmCalendarPage
from .field_profile import FieldProfilePage
from .fields import FieldsPage
from .inventory import InventoryPage
from .inventory_report import InventoryReportPage
from .annual_report import AnnualFarmReportPage
from .equipment import EquipmentPage
from .partners import PartnersPage
from .plant_protection import PlantProtectionPage
from .plantings import PlantingsPage
from .invoice_documents import InvoiceDocumentsPage
from .labor import LaborPage
from .money import MoneyPage
from .producer import ProducerPage
from .production import ProductionPage
from .products import ProductsPage
from .settings import ProfileSelectionDialog, SettingsPage
from .profile_manager import ProfileError, ProfileManager
from .upload_center import UploadCenterPage
from .year_lock import YearLockPage
from .ui_help import apply_help_tooltips
from .reports import ReportsPage
from .sales import SalesPage
from .sales_report import SalesReportPage

APP_DIR = Path(__file__).resolve().parent
DOWN_ARROW_ICON = (APP_DIR / "assets" / "chevron_down.png").as_posix()
SPIN_UP_ICON = (APP_DIR / "assets" / "spin_up.svg").as_posix()
SPIN_DOWN_ICON = (APP_DIR / "assets" / "spin_down.svg").as_posix()
CROP_SPIN_UP_ICON = (APP_DIR / "assets" / "crop_spin_up.svg").as_posix()
CROP_SPIN_DOWN_ICON = (APP_DIR / "assets" / "crop_spin_down.svg").as_posix()
APP_ICON = APP_DIR / "assets" / "icons" / "mastixa_menu" / "dashboard.png"
logger = get_logger(__name__)

STYLESHEET = """
QMainWindow { background: #f5f6f3; }
QWidget#sidebar {
    background: #21483A;
}

QListWidget#categoryList {
    background: #21483A;
    color: white;
    border: none;
    outline: none;
    padding: 10px 8px;
    font-size: 14px;
}

QListWidget#categoryList::item {
    padding: 13px 12px;
    margin: 3px 0;
    border-radius: 6px;
    font-weight: 700;
}

QListWidget#categoryList::item:selected {
    background: #3F765B;
    color: white;
}

QListWidget#categoryList::item:hover:!selected {
    background: #2E493E;
}

QTabWidget#mainTabs::pane {
    border: 1px solid #D6E0DA;
    border-radius: 12px;
    background: #f5f6f3;
    top: 0px;
}

QTabWidget#mainTabs::tab-bar {
    left: 8px;
}

QTabBar {
    qproperty-drawBase: 0;
}

QTabBar::tab {
    background: #E8EFEB;
    color: #52655B;
    border: 1px solid #d1d8d3;
    border-bottom: none;
    border-top-left-radius: 11px;
    border-top-right-radius: 11px;
    padding: 10px 18px;
    margin-right: 6px;
    min-width: 120px;
    font-weight: 700;
}

QTabBar::tab:selected {
    background: white;
    color: #21483A;
    border-color: #cfd7d2;
}

QTabBar::tab:hover:!selected {
    background: #F0F5F2;
    color: #21483A;
}

QTabWidget#recordingInnerTabs::pane {
    border: 1px solid #DCE5E0;
    border-radius: 9px;
    background: white;
    top: -1px;
}

QTabWidget#recordingInnerTabs::tab-bar {
    left: 10px;
}

QTabWidget#recordingInnerTabs QTabBar::tab {
    min-width: 105px;
    padding: 8px 14px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    background: #F0F4F1;
    color: #52655B;
}

QTabWidget#recordingInnerTabs QTabBar::tab:selected {
    background: #3F765B;
    color: white;
    border-color: #3F765B;
}

QWidget { font-family: "Segoe UI"; font-size: 14px; }
QLabel {
    color: #21483A;
}

QCheckBox {
    color: #24312B;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
}

QLabel#pageTitle { font-size: 27px; font-weight: 700; color: #1F5A43; }
QLabel#pageSubtitle { color: #6A7A72; margin-bottom: 12px; }

QFrame#yearContextBar[yearContextState="active"] {
    background: #E8F1EC;
    color: #21483A;
    border-bottom: 1px solid #B7CEC1;
}
QFrame#yearContextBar[yearContextState="active"] QLabel {
    color: #21483A;
}
QFrame#yearContextBar[yearContextState="correction"] {
    background: #7C2D12;
    color: white;
    border-bottom: 2px solid #FDBA74;
}
QFrame#yearContextBar[yearContextState="correction"] QLabel {
    color: white;
}
QGroupBox {
    background: white;
    border: 1px solid #D6E0DA;
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px;
    font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #21483A; font-weight: 700; }
QGroupBox#metricCard { min-height: 110px; }
QLabel#metricCaption { color: #6A7A72; font-weight: 600; }
QLabel#metricValue { font-size: 25px; font-weight: 700; color: #21483A; }
QLineEdit,
QTextEdit,
QComboBox,
QDateEdit,
QSpinBox,
QDoubleSpinBox {
    background: white;
    color: #24312B;
    selection-color: white;
    selection-background-color: #3F765B;
    border: 1px solid #C7D3CC;
    border-radius: 5px;
    padding: 7px;
}

QComboBox,
QDateEdit {
    padding-right: 48px;
}

QDateEdit { min-width: 148px; }

QDoubleSpinBox {
    padding-right: 7px;
}

QLineEdit:focus,
QTextEdit:focus,
QComboBox:focus,
QDateEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #4F8068;
}

QLineEdit:disabled,
QTextEdit:disabled,
QComboBox:disabled,
QDateEdit:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled {
    background: #EEF2F0;
    color: #7B8982;
}

QComboBox::drop-down,
QDateEdit::drop-down {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 40px;
    border-left: 1px solid #AEBEB5;
    background: #E1EAE5;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}

QComboBox::drop-down:hover,
QDateEdit::drop-down:hover {
    background: #D0DED6;
}

QComboBox::down-arrow,
QDateEdit::down-arrow {
    image: url("__DOWN_ARROW_ICON__");
    width: 18px;
    height: 12px;
}

QSpinBox::up-button,
QSpinBox::down-button,
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button {
    width: 0px;
    height: 0px;
    border: none;
}

QSpinBox::up-arrow,
QSpinBox::down-arrow,
QDoubleSpinBox::up-arrow,
QDoubleSpinBox::down-arrow {
    width: 0px;
    height: 0px;
    image: none;
}

QSpinBox[mastixaCropStepControl="true"] {
    padding-right: 30px;
}
QSpinBox[mastixaCropStepControl="true"]::up-button,
QSpinBox[mastixaCropStepControl="true"]::down-button {
    subcontrol-origin: border;
    width: 26px;
    height: 16px;
    border-left: 1px solid #35664F;
    background: #3F765B;
}
QSpinBox[mastixaCropStepControl="true"]::up-button {
    subcontrol-position: top right;
    border-top-right-radius: 5px;
}
QSpinBox[mastixaCropStepControl="true"]::down-button {
    subcontrol-position: bottom right;
    border-bottom-right-radius: 5px;
}
QSpinBox[mastixaCropStepControl="true"]::up-button:hover,
QSpinBox[mastixaCropStepControl="true"]::down-button:hover {
    background: #315F49;
}
QSpinBox[mastixaCropStepControl="true"]::up-arrow {
    image: url("__CROP_SPIN_UP_ICON__");
    width: 12px;
    height: 8px;
}
QSpinBox[mastixaCropStepControl="true"]::down-arrow {
    image: url("__CROP_SPIN_DOWN_ICON__");
    width: 12px;
    height: 8px;
}

QComboBox QAbstractItemView {
    background-color: white;
    color: #24312B;
    selection-background-color: #3F765B;
    selection-color: white;
}

QComboBox QAbstractItemView::item {
    color: #24312B;
    padding: 6px 10px;
}
QComboBox QAbstractItemView::item:hover:enabled,
QComboBox QAbstractItemView::item:selected:enabled {
    background: #3F765B;
    color: white;
}
QScrollArea#activitiesScroll {
    background: #f5f6f3;
    border: none;
}

QScrollArea#activitiesScroll QWidget#qt_scrollarea_viewport {
    background: #f5f6f3;
}

QWidget#activitiesContent {
    background: #f5f6f3;
}

QPushButton {
    background: #3F765B;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 9px 16px;
    font-weight: 600;
}
QPushButton:hover { background: #315F49; }
QPushButton:pressed { background: #274D3B; }
QPushButton:disabled {
    background: #D5DDD8;
    color: #58665F;
    border: 1px solid #C4CEC8;
}

QToolButton[appearanceChoice="true"] {
    background: white;
    color: #26382F;
    border: 2px solid #C4CEC8;
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 15px;
    font-weight: 700;
}
QToolButton[appearanceChoice="true"]:hover {
    background: #F3F7F4;
    border-color: #8FA69A;
}
QToolButton[appearanceChoice="true"]:checked {
    background: #EDF6F0;
    color: #21483A;
    border: 3px solid #4F8068;
}

QScrollArea,
QAbstractScrollArea {
    background: #f5f6f3;
    color: #24312B;
}

QScrollArea > QWidget > QWidget,
QAbstractScrollArea > QWidget > QWidget {
    background: #f5f6f3;
}

QMenu {
    background: white;
    color: #24312B;
    border: 1px solid #C7D3CC;
    padding: 4px;
}

QMenu::item {
    padding: 7px 18px;
    border-radius: 4px;
}

QMenu::item:selected {
    background: #3F765B;
    color: white;
}

QCalendarWidget QWidget {
    background: white;
    color: #24312B;
}

QCalendarWidget QToolButton {
    color: #21483A;
    background: transparent;
    font-weight: 700;
}

QCalendarWidget QAbstractItemView {
    background: white;
    color: #24312B;
    selection-background-color: #3F765B;
    selection-color: white;
}

QToolTip {
    background-color: #FFFDF7;
    color: #24312B;
    border: 1px solid #B8C8BF;
    border-radius: 6px;
    padding: 7px 9px;
    font-size: 12px;
}

QMessageBox {
    background-color: #f5f6f3;
}

QMessageBox QLabel {
    background: transparent;
    color: #21483A;
    font-size: 14px;
}

QMessageBox QPushButton {
    background: #3F765B;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    min-width: 78px;
    font-weight: 600;
}

QMessageBox QPushButton:hover {
    background: #315F49;
}

QMessageBox QPushButton:pressed {
    background: #274D3B;
}

QTableWidget {
    background: white;
    color: #24312B;
    alternate-background-color: #f8f9f8;
    selection-background-color: #3F765B;
    selection-color: white;
    border: 1px solid #D6E0DA;
    gridline-color: #E3E9E5;
}

QTableWidget::item {
    color: #24312B;
}

QHeaderView::section {
    background: #E6EDE9;
    color: #21483A;
    padding: 8px;
    border: none;
    font-weight: 700;
}
"""
STYLESHEET = STYLESHEET.replace("__DOWN_ARROW_ICON__", DOWN_ARROW_ICON)
STYLESHEET = STYLESHEET.replace("__SPIN_UP_ICON__", SPIN_UP_ICON)
STYLESHEET = STYLESHEET.replace("__SPIN_DOWN_ICON__", SPIN_DOWN_ICON)
STYLESHEET = STYLESHEET.replace("__CROP_SPIN_UP_ICON__", CROP_SPIN_UP_ICON)
STYLESHEET = STYLESHEET.replace("__CROP_SPIN_DOWN_ICON__", CROP_SPIN_DOWN_ICON)



def build_app_palette() -> QPalette:
    """Consistent high-contrast palette for every Qt widget/page."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#F5F6F3"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#24312B"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F8FAF8"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#21483A"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#24312B"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#3F765B"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#3F765B"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8A9891"))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor("#7B8982"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor("#77847D"),
    )
    return palette


class MainWindow(QMainWindow):
    profile_switch_requested = Signal(str)

    def __init__(
        self,
        theme: ThemeController | None = None,
        profiles: ProfileManager | None = None,
        language: LanguageController | None = None,
    ) -> None:
        super().__init__()
        self._closing = False
        if theme is None:
            app = QApplication.instance()
            if app is None:
                raise RuntimeError("MainWindow requires an active QApplication")
            theme = ThemeController(app, app.styleSheet(), app.palette())
        self.profile_manager = profiles or ProfileManager(BASE_DIR)
        self.language = language or LanguageController(
            QApplication.instance(), self.profile_manager
        )
        install_language_controller(self.language)
        self._profile_default_backup_dir = (
            self.profile_manager.default_backup_dir()
        )
        self.db = (
            Database(self.profile_manager.active_profile.database_path)
            if profiles is not None
            else Database()
        )
        self.backup_manager = self._build_backup_manager()
        active_profile = self.profile_manager.active_profile
        self.setWindowTitle(
            f"{APP_NAME} v{APP_VERSION} — {active_profile.name}"
        )
        self.resize(1200, 780)
        self.setMinimumSize(QSize(950, 650))

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)

        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(205)

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        self.category_list = QListWidget()
        self.category_list.setObjectName("categoryList")
        self.category_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.category_list.setVerticalScrollMode(
            QListWidget.ScrollMode.ScrollPerPixel
        )
        sidebar_layout.addWidget(self.category_list)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)
        self.tabs.setTabsClosable(False)
        self.tabs.setIconSize(QSize(16, 16))

        self._building_tabs = False
        self._current_category_index = -1
        self._current_tab_page_indices: list[int] = []
        self._last_tab_by_category: dict[int, int] = {}

        # Nested navigation used only inside "Καταχωρήσεις".
        self._recording_group_tabs: list[QTabWidget] = []
        self._recording_group_page_indices: list[list[int]] = []
        self._last_recording_group = 0
        self._last_recording_tab_by_group: dict[int, int] = {}

        # Nested navigation used inside "Αναφορές & Έλεγχος".
        self._report_group_tabs: list[QTabWidget] = []
        self._report_group_page_indices: list[list[int]] = []
        self._last_report_group = 0
        self._last_report_tab_by_group: dict[int, int] = {}

        settings_page = SettingsPage(
            self.db, theme, self.profile_manager, self.language
        )
        settings_page.profile_switch_requested.connect(
            self.profile_switch_requested.emit
        )

        self.pages = [
            ("Dashboard", DashboardPage(self.db)),
            ("Παραγωγός", ProducerPage(self.db)),
            ("Αγροτεμάχια", FieldsPage(self.db)),
            ("Παραγωγή", ProductionPage(self.db)),
            ("Έσοδα", MoneyPage(self.db, "income")),
            ("Έξοδα", MoneyPage(self.db, "expenses")),
            ("Δήλωση Καλλιέργειας", DeclarationPage(self.db)),
            ("Προεπισκόπηση Πακέτου", UploadCenterPage(self.db)),
            ("Αναφορές", ReportsPage(self.db)),
            ("Ιστορικό Ενεργειών", AuditPage(self.db)),
            ("Έλεγχος Δεδομένων", DataQualityPage(self.db)),
            ("Εξαγωγή Δεδομένων", DataExportPage(self.db)),
            ("Άρδευση & Λίπανση", ActivitiesPage(self.db)),
            ("Αποθήκη & Εφόδια", InventoryPage(self.db)),
            ("Κλείδωμα Έτους", YearLockPage(self.db)),
            ("Ειδοποιήσεις", AlertsPage(self.db)),
            ("Μηχανήματα & Συντήρηση", EquipmentPage(self.db)),
            ("Προμηθευτές & Αγοραστές", PartnersPage(self.db)),
            ("Έγγραφα Τιμολογίων", InvoiceDocumentsPage(self.db)),
            ("Φυτοπροστασία", PlantProtectionPage(self.db)),
            ("Κόστη ανά Αγροτεμάχιο", FieldFinancePage(self.db)),
            ("Εργατικά & Προσωπικό", LaborPage(self.db)),
            ("Γενική Αναζήτηση", GlobalSearchPage(self.db)),
            ("Φυτεύσεις & Δέντρα", PlantingsPage(self.db)),
            ("Ενιαίο Ημερολόγιο", FarmCalendarPage(self.db)),
            ("Καρτέλα Αγροτεμαχίου", FieldProfilePage(self.db)),
            ("Πωλήσεις Παραγωγής", SalesPage(self.db)),
            ("Αναφορά Πωλήσεων & Stock", SalesReportPage(self.db)),
            ("Αναφορά Αποθήκης & Αξίας Stock", InventoryReportPage(self.db)),
            ("Ετήσια Αναφορά Εκμετάλλευσης", AnnualFarmReportPage(self.db)),
            ("Προϊόντα", ProductsPage(self.db)),
            ("Ρυθμίσεις", settings_page),
        ]

        self.navigation_categories = [
            (
                "Κύρια",
                [
                    ("Dashboard", 0),
                    ("Ειδοποιήσεις", 15),
                    ("Αναζήτηση", 22),
                    ("Ημερολόγιο", 24),
                    ("Παραγωγός", 1),
                    ("Αγροτεμάχια", 2),
                ],
            ),
            (
                "Καταχωρήσεις",
                [],
            ),
            (
                "Δήλωση & Αποστολή",
                [
                    ("Δήλωση Καλλιέργειας", 6),
                    ("Προεπισκόπηση Πακέτου", 7),
                ],
            ),
            (
                "Αναφορές & Έλεγχος",
                [],
            ),
            (
                "Ασφάλεια",
                [
                    ("Κλείδωμα Έτους", 14),
                ],
            ),
            (
                "Προϊόντα",
                [
                    ("Διαχείριση Προϊόντων", 30),
                ],
            ),
            (
                "Ρυθμίσεις",
                [
                    ("Γενικές Ρυθμίσεις", 31),
                ],
            ),
        ]

        self.recording_groups = [
            (
                "Καλλιέργεια",
                [
                    ("Παραγωγή", 3),
                    ("Άρδευση & Λίπανση", 12),
                    ("Φυτοπροστασία", 19),
                    ("Εργατικά", 21),
                    ("Φυτεύσεις & Δέντρα", 23),
                ],
            ),
            (
                "Αποθήκη & Μέσα",
                [
                    ("Αποθήκη & Εφόδια", 13),
                    ("Μηχανήματα & Συντήρηση", 16),
                ],
            ),
            (
                "Οικονομικά",
                [
                    ("Έσοδα", 4),
                    ("Έξοδα", 5),
                    ("Πωλήσεις", 26),
                ],
            ),
            (
                "Συνεργάτες & Έγγραφα",
                [
                    ("Προμηθευτές & Αγοραστές", 17),
                    ("Έγγραφα Τιμολογίων", 18),
                ],
            ),
        ]

        self.report_groups = [
            (
                "Οικονομικά & Παραγωγή",
                [
                    ("Αναφορές", 8),
                    ("Πωλήσεις & Stock", 27),
                    ("Ετήσια Αναφορά", 29),
                    ("Κόστη ανά Αγροτεμάχιο", 20),
                ],
            ),
            (
                "Αποθήκη & Αγροτεμάχια",
                [
                    ("Αποθήκη & Αξία Stock", 28),
                    ("Καρτέλα Αγροτεμαχίου", 25),
                ],
            ),
            (
                "Έλεγχος & Δεδομένα",
                [
                    ("Έλεγχος Δεδομένων", 10),
                    ("Ιστορικό Ενεργειών", 9),
                    ("Εξαγωγή Δεδομένων", 11),
                ],
            ),
        ]

        for category_index, (category_name, _entries) in enumerate(
            self.navigation_categories
        ):
            item = QListWidgetItem(category_name)
            item.setData(
                Qt.ItemDataRole.UserRole,
                category_index,
            )
            self.category_list.addItem(item)

        self.category_list.currentRowChanged.connect(
            self._category_changed
        )
        self.tabs.currentChanged.connect(
            self._tab_changed
        )

        layout.addWidget(self.sidebar)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

        # Only the categories stay on the left.
        # Their pages appear as tabs in the large panel on the right.
        self.category_list.setCurrentRow(0)

        self._disable_spinbox_buttons()
        self._apply_context_help()

        self.search_shortcut = QShortcut(
            QKeySequence("Ctrl+K"),
            self,
        )
        self.search_shortcut.activated.connect(
            self._open_global_search
        )

        # Run after the window has been constructed so any warning can be shown
        # normally. Success is silent.
        QTimer.singleShot(0, self._run_startup_backup)
        install_icon_theme(self)  # MASTIXA_ICON_PATCH

    def _standard_icon(self, name: str):
        fallback = QStyle.StandardPixmap.SP_FileIcon
        pixmap = getattr(QStyle.StandardPixmap, name, fallback)
        return self.style().standardIcon(pixmap)

    def _tab_icon_for_page(self, page_index: int):
        icon_map = {
            0: "SP_DesktopIcon",
            1: "SP_FileDialogInfoView",
            2: "SP_DirOpenIcon",
            3: "SP_FileDialogDetailedView",
            4: "SP_ArrowUp",
            5: "SP_ArrowDown",
            6: "SP_FileIcon",
            7: "SP_DialogOpenButton",
            8: "SP_FileDialogDetailedView",
            9: "SP_BrowserReload",
            10: "SP_DialogApplyButton",
            11: "SP_DialogSaveButton",
            12: "SP_FileDialogListView",
            13: "SP_DriveHDIcon",
            14: "SP_MessageBoxWarning",
            15: "SP_MessageBoxInformation",
            16: "SP_ComputerIcon",
            17: "SP_FileDialogInfoView",
            18: "SP_FileIcon",
            19: "SP_DialogApplyButton",
            20: "SP_FileDialogDetailedView",
            21: "SP_FileDialogInfoView",
            22: "SP_FileDialogContentsView",
            23: "SP_DirHomeIcon",
            24: "SP_FileDialogListView",
            25: "SP_FileDialogInfoView",
            26: "SP_DialogSaveButton",
            27: "SP_FileDialogDetailedView",
            28: "SP_DriveHDIcon",
            29: "SP_FileDialogContentsView",
            30: "SP_DirIcon",
            31: "SP_FileDialogDetailedView",
        }
        return self._standard_icon(
            icon_map.get(page_index, "SP_FileIcon")
        )

    def _apply_context_help(self) -> None:
        # Some pages are not children of MainWindow until their category/tab
        # is opened. Apply help directly to every page instance so KPI cards
        # and fields such as "Άμεσο κόστος" always receive their ⓘ tooltip.
        apply_help_tooltips(self)

        for _page_name, page in self.pages:
            apply_help_tooltips(page)

    def _disable_spinbox_buttons(self) -> None:
        for spinbox in self.findChildren(QAbstractSpinBox):
            spinbox.setButtonSymbols(
                QAbstractSpinBox.ButtonSymbols.NoButtons
            )

    def _open_global_search(self) -> None:
        self.change_page(22)

        page = self.pages[22][1]
        focus_search = getattr(page, "focus_search", None)

        if callable(focus_search):
            QTimer.singleShot(0, focus_search)

    def _category_changed(self, category_index: int) -> None:
        if category_index < 0:
            return

        if self._current_category_index >= 0:
            self._remember_current_navigation()

        self._current_category_index = category_index

        self._building_tabs = True
        try:
            while self.tabs.count():
                self.tabs.removeTab(0)

            self._current_tab_page_indices = []
            self._recording_group_tabs = []
            self._recording_group_page_indices = []
            self._report_group_tabs = []
            self._report_group_page_indices = []

            if category_index == 1:
                self._build_recording_tabs()
            elif category_index == 3:
                self._build_report_tabs()
            else:
                _category_name, entries = self.navigation_categories[
                    category_index
                ]

                for label, page_index in entries:
                    page = self.pages[page_index][1]
                    icon = self._tab_icon_for_page(page_index)
                    self.tabs.addTab(page, icon, label)
                    self._current_tab_page_indices.append(page_index)

                tab_index = self._last_tab_by_category.get(
                    category_index,
                    0,
                )

                if tab_index >= self.tabs.count():
                    tab_index = 0

                if self.tabs.count():
                    self.tabs.setCurrentIndex(tab_index)
        finally:
            self._building_tabs = False

        self._refresh_current_tab()
        self._apply_context_help()

    def _build_recording_tabs(self) -> None:
        signature = tuple(
            (group_name, tuple(entries))
            for group_name, entries in self.recording_groups
        )
        cached = getattr(self, "_recording_tabs_cache", None)

        if cached is not None and cached["signature"] == signature:
            cached_tabs = cached["tabs"]
            cached_page_indices = cached["page_indices"]
            self._recording_group_tabs.extend(cached_tabs)
            self._recording_group_page_indices.extend(
                [list(indices) for indices in cached_page_indices]
            )

            for group_index, (group_name, _entries) in enumerate(
                self.recording_groups
            ):
                inner_tabs = cached_tabs[group_index]
                remembered_inner = self._last_recording_tab_by_group.get(
                    group_index,
                    0,
                )
                if remembered_inner >= inner_tabs.count():
                    remembered_inner = 0
                if inner_tabs.count():
                    inner_tabs.setCurrentIndex(remembered_inner)

                self.tabs.addTab(
                    inner_tabs,
                    self._standard_icon("SP_DirOpenIcon"),
                    group_name,
                )
        else:
            for group_index, (group_name, entries) in enumerate(
                self.recording_groups
            ):
                inner_tabs = QTabWidget()
                inner_tabs.setObjectName("recordingInnerTabs")
                inner_tabs.setProperty("mastixaHiddenNavigation", hasattr(self, "desktop_navigation"))
                inner_tabs.setDocumentMode(True)
                inner_tabs.setMovable(False)
                inner_tabs.setTabsClosable(False)
                inner_tabs.setIconSize(QSize(16, 16))

                page_indices: list[int] = []

                for label, page_index in entries:
                    page = self.pages[page_index][1]
                    icon = self._tab_icon_for_page(page_index)
                    inner_tabs.addTab(page, icon, label)
                    page_indices.append(page_index)

                inner_tabs.currentChanged.connect(
                    self._recording_inner_tab_changed
                )

                remembered_inner = self._last_recording_tab_by_group.get(
                    group_index,
                    0,
                )

                if remembered_inner >= inner_tabs.count():
                    remembered_inner = 0

                if inner_tabs.count():
                    inner_tabs.setCurrentIndex(remembered_inner)

                self._recording_group_tabs.append(inner_tabs)
                self._recording_group_page_indices.append(page_indices)

                self.tabs.addTab(
                    inner_tabs,
                    self._standard_icon("SP_DirOpenIcon"),
                    group_name,
                )

            self._recording_tabs_cache = {
                "signature": signature,
                "tabs": tuple(self._recording_group_tabs),
                "page_indices": tuple(
                    tuple(indices)
                    for indices in self._recording_group_page_indices
                ),
            }

        group_index = self._last_recording_group

        if group_index >= self.tabs.count():
            group_index = 0

        if self.tabs.count():
            self.tabs.setCurrentIndex(group_index)

    def _build_report_tabs(self) -> None:
        for group_index, (group_name, entries) in enumerate(
            self.report_groups
        ):
            inner_tabs = QTabWidget()
            inner_tabs.setObjectName("recordingInnerTabs")
            inner_tabs.setProperty("mastixaHiddenNavigation", hasattr(self, "desktop_navigation"))
            inner_tabs.setDocumentMode(True)
            inner_tabs.setMovable(False)
            inner_tabs.setTabsClosable(False)
            inner_tabs.setIconSize(QSize(16, 16))

            page_indices: list[int] = []
            for label, page_index in entries:
                page = self.pages[page_index][1]
                inner_tabs.addTab(
                    page,
                    self._tab_icon_for_page(page_index),
                    label,
                )
                page_indices.append(page_index)

            inner_tabs.currentChanged.connect(
                self._report_inner_tab_changed
            )
            remembered = self._last_report_tab_by_group.get(group_index, 0)
            if remembered >= inner_tabs.count():
                remembered = 0
            if inner_tabs.count():
                inner_tabs.setCurrentIndex(remembered)

            self._report_group_tabs.append(inner_tabs)
            self._report_group_page_indices.append(page_indices)
            self.tabs.addTab(
                inner_tabs,
                self._standard_icon("SP_DirOpenIcon"),
                group_name,
            )

        group_index = self._last_report_group
        if group_index >= self.tabs.count():
            group_index = 0
        if self.tabs.count():
            self.tabs.setCurrentIndex(group_index)

    def _remember_current_navigation(self) -> None:
        if self._current_category_index == 1:
            group_index = self.tabs.currentIndex()

            if group_index >= 0:
                self._last_recording_group = group_index

                if group_index < len(self._recording_group_tabs):
                    inner_index = self._recording_group_tabs[
                        group_index
                    ].currentIndex()

                    if inner_index >= 0:
                        self._last_recording_tab_by_group[
                            group_index
                        ] = inner_index
        elif self._current_category_index == 3:
            group_index = self.tabs.currentIndex()
            if group_index >= 0:
                self._last_report_group = group_index
                if group_index < len(self._report_group_tabs):
                    inner_index = self._report_group_tabs[
                        group_index
                    ].currentIndex()
                    if inner_index >= 0:
                        self._last_report_tab_by_group[
                            group_index
                        ] = inner_index
        else:
            self._last_tab_by_category[
                self._current_category_index
            ] = max(self.tabs.currentIndex(), 0)

    def _tab_changed(self, _tab_index: int) -> None:
        if self._building_tabs:
            return

        self._remember_current_navigation()
        self._refresh_current_tab()
        self._apply_context_help()

    def _recording_inner_tab_changed(self, _tab_index: int) -> None:
        if self._building_tabs or self._current_category_index != 1:
            return

        group_index = self.tabs.currentIndex()

        if (
            group_index >= 0
            and group_index < len(self._recording_group_tabs)
        ):
            inner_index = self._recording_group_tabs[
                group_index
            ].currentIndex()

            if inner_index >= 0:
                self._last_recording_tab_by_group[
                    group_index
                ] = inner_index

        self._refresh_current_tab()

    def _report_inner_tab_changed(self, _tab_index: int) -> None:
        if self._building_tabs or self._current_category_index != 3:
            return
        group_index = self.tabs.currentIndex()
        if 0 <= group_index < len(self._report_group_tabs):
            inner_index = self._report_group_tabs[group_index].currentIndex()
            if inner_index >= 0:
                self._last_report_tab_by_group[group_index] = inner_index
        self._refresh_current_tab()

    def _current_page_index(self) -> int | None:
        if self._current_category_index == 1:
            group_index = self.tabs.currentIndex()

            if (
                group_index < 0
                or group_index >= len(self._recording_group_tabs)
            ):
                return None

            inner_tabs = self._recording_group_tabs[group_index]
            inner_index = inner_tabs.currentIndex()

            if (
                inner_index < 0
                or inner_index >= len(
                    self._recording_group_page_indices[group_index]
                )
            ):
                return None

            return self._recording_group_page_indices[
                group_index
            ][inner_index]

        if self._current_category_index == 3:
            group_index = self.tabs.currentIndex()
            if group_index < 0 or group_index >= len(self._report_group_tabs):
                return None
            inner_index = self._report_group_tabs[group_index].currentIndex()
            if inner_index < 0 or inner_index >= len(
                self._report_group_page_indices[group_index]
            ):
                return None
            return self._report_group_page_indices[group_index][inner_index]

        tab_index = self.tabs.currentIndex()

        if (
            tab_index < 0
            or tab_index >= len(self._current_tab_page_indices)
        ):
            return None

        return self._current_tab_page_indices[tab_index]

    def _refresh_current_tab(self) -> None:
        page_index = self._current_page_index()

        if page_index is None:
            return

        page = self.pages[page_index][1]

        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()
            return

        load = getattr(page, "load", None)
        if callable(load):
            load()

    def change_page(self, index: int) -> None:
        """
        Navigate by the stable flat page index.

        "Καταχωρήσεις" uses two tab levels, while all other left-side
        categories keep the normal single tab row.
        """
        if index < 0 or index >= len(self.pages):
            return

        # First search the nested Καταχωρήσεις groups.
        for group_index, (_group_name, entries) in enumerate(
            self.recording_groups
        ):
            for inner_index, (_label, page_index) in enumerate(entries):
                if page_index != index:
                    continue

                self._last_recording_group = group_index
                self._last_recording_tab_by_group[
                    group_index
                ] = inner_index

                if self.category_list.currentRow() != 1:
                    self.category_list.setCurrentRow(1)
                else:
                    self.tabs.setCurrentIndex(group_index)

                    if group_index < len(self._recording_group_tabs):
                        self._recording_group_tabs[
                            group_index
                        ].setCurrentIndex(inner_index)

                    self._refresh_current_tab()
                return

        # Then search the nested Αναφορές & Έλεγχος groups.
        for group_index, (_group_name, entries) in enumerate(
            self.report_groups
        ):
            for inner_index, (_label, page_index) in enumerate(entries):
                if page_index != index:
                    continue
                self._last_report_group = group_index
                self._last_report_tab_by_group[group_index] = inner_index
                if self.category_list.currentRow() != 3:
                    self.category_list.setCurrentRow(3)
                else:
                    self.tabs.setCurrentIndex(group_index)
                    if group_index < len(self._report_group_tabs):
                        self._report_group_tabs[group_index].setCurrentIndex(
                            inner_index
                        )
                    self._refresh_current_tab()
                return

        # Normal one-level categories.
        for category_index, (_name, entries) in enumerate(
            self.navigation_categories
        ):
            if category_index in (1, 3):
                continue

            for tab_index, (_label, page_index) in enumerate(entries):
                if page_index != index:
                    continue

                self._last_tab_by_category[
                    category_index
                ] = tab_index

                if self.category_list.currentRow() != category_index:
                    self.category_list.setCurrentRow(
                        category_index
                    )
                else:
                    self.tabs.setCurrentIndex(
                        tab_index
                    )
                    self._refresh_current_tab()
                return


    def _build_backup_manager(self) -> BackupManager:
        saved_dir = self.db.get_app_setting("backup_dir", "").strip()
        default_dir = self._profile_default_backup_dir
        backup_dir = Path(saved_dir) if saved_dir else default_dir
        kwargs = {
            "database_path": self.db.path,
            "auto_keep": self.db.get_app_setting_int(
                "auto_backup_keep", 30, minimum=1, maximum=365
            ),
            "pre_restore_keep": self.db.get_app_setting_int(
                "pre_restore_keep", 10, minimum=1, maximum=100
            ),
        }
        try:
            return BackupManager(backup_dir=backup_dir, **kwargs)
        except OSError:
            # A removable/network backup destination may be unavailable at
            # startup. Fall back to the local folder instead of blocking launch.
            return BackupManager(backup_dir=default_dir, **kwargs)

    def _run_startup_backup(self) -> None:
        if self._closing or not self.db.path.parent.exists():
            return
        self.backup_manager = self._build_backup_manager()
        if not self.db.get_app_setting_bool(
            "auto_backup_enabled", True
        ):
            dashboard = self.pages[0][1]
            refresh = getattr(dashboard, "refresh", None)
            if callable(refresh):
                refresh()
            return

        try:
            self.backup_manager.create_or_update_daily_backup()
        except BackupError as exc:
            show_backup_error(
                self, "warning",
                "Αυτόματο Backup",
                exc,
                "Δεν ήταν δυνατή η δημιουργία του αυτόματου ημερήσιου "
                "backup κατά την εκκίνηση.\n\n{error}",
            )
            return

        dashboard = self.pages[0][1]
        refresh = getattr(dashboard, "refresh", None)
        if callable(refresh):
            refresh()

    def closeEvent(self, event) -> None:
        self._closing = True
        if getattr(self, "_skip_close_backup", False):
            event.accept()
            return
        self.backup_manager = self._build_backup_manager()
        if not self.db.get_app_setting_bool(
            "auto_backup_enabled", True
        ):
            logger.info("Application shutdown (automatic backup disabled)")
            event.accept()
            return

        try:
            self.backup_manager.create_or_update_daily_backup()
        except BackupError as exc:
            answer = show_backup_error(
                self, "warning",
                "Αποτυχία αυτόματου Backup",
                exc,
                "Το αυτόματο backup κατά το κλείσιμο απέτυχε.\n\n"
                "{error}\n\n"
                "Θέλεις να κλείσεις την εφαρμογή χωρίς νέο backup;",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:
                self._closing = False
                event.ignore()
                return

        logger.info("Application shutdown")
        event.accept()


class ApplicationController(QObject):
    """Hot-switch complete windows while keeping one application process."""

    def __init__(
        self,
        app: QApplication,
        theme: ThemeController,
        profiles: ProfileManager,
        language: LanguageController | None = None,
    ) -> None:
        super().__init__(app)
        self.app = app
        self.theme = theme
        self.profiles = profiles
        self.language = language or LanguageController(app, profiles)
        install_language_controller(self.language)
        self.window: MainWindow | None = None

    def start(self) -> None:
        self.window = self._build_window()
        self.window.show()

    def _build_window(self) -> MainWindow:
        window = MainWindow(self.theme, self.profiles, self.language)
        window.profile_switch_requested.connect(self.switch_profile)
        self.theme.apply_to(window)
        return window

    def switch_profile(self, profile_id: str) -> None:
        if self.window is None:
            return
        try:
            target = self.profiles.get(profile_id)
        except ProfileError as exc:
            _message(self.window, 'warning', 'Ενεργοποίηση προφίλ', '{error}', error=str(exc))
            return
        if target.is_active:
            return

        logger.info("Profile switch requested")

        old_window = self.window
        old_profile_id = self.profiles.active_profile.id

        if old_window.db.get_app_setting_bool("auto_backup_enabled", True):
            try:
                old_window.backup_manager = old_window._build_backup_manager()
                old_window.backup_manager.create_or_update_daily_backup()
            except BackupError as exc:
                answer = show_backup_error(
                    old_window, "warning",
                    "Backup πριν την αλλαγή προφίλ",
                    exc,
                    "Δεν δημιουργήθηκε backup του τρέχοντος προφίλ.\n\n"
                    "{error}\n\nΝα συνεχιστεί η αλλαγή προφίλ;",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    logger.warning("Profile switch cancelled after backup failure")
                    return

        try:
            self.profiles.set_active(profile_id)
            self.language.sync_active_profile()
            new_window = self._build_window()
        except Exception as exc:
            logger.exception("Profile switch failed")
            try:
                self.profiles.set_active(old_profile_id)
                self.language.sync_active_profile()
            except ProfileError:
                pass
            _message(old_window, 'critical', 'Ενεργοποίηση προφίλ', 'Δεν ήταν δυνατή η ενεργοποίηση του προφίλ.\n\n{exc}', exc=exc)
            return

        self.window = new_window
        new_window.show()
        new_window.raise_()
        new_window.activateWindow()
        old_window._skip_close_backup = True
        old_window.close()
        old_window.deleteLater()
        logger.info("Profile switch completed")


def run_app() -> None:
    configure_logging(BASE_DIR)
    logger.info("Application startup")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Fieltra")
    app.setWindowIcon(QIcon(str(APP_ICON)))
    light_palette = build_app_palette()
    light_stylesheet = STYLESHEET.replace(
        "__DOWN_ARROW_ICON__", DOWN_ARROW_ICON
    )
    app.setPalette(light_palette)
    app.setStyleSheet(light_stylesheet)
    theme = ThemeController(app, light_stylesheet, light_palette)
    profiles = ProfileManager(BASE_DIR)
    language = LanguageController(app, profiles)
    install_language_controller(language)
    theme.apply_saved_theme()
    available_profiles = profiles.profiles()
    if (
        profiles.ask_on_startup and len(available_profiles) > 1
    ) or profiles.active_profile.has_pin:
        chooser = ProfileSelectionDialog(profiles, language)
        if not chooser.exec():
            return
        profiles.set_active(chooser.selected_profile_id)
        language.sync_active_profile()
    controller = ApplicationController(app, theme, profiles, language)
    controller.start()
    if "--smoke-test" in sys.argv:
        logger.info("Packaged smoke test started")
        QTimer.singleShot(1200, app.quit)
    sys.exit(app.exec())
