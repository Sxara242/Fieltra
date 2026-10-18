from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re

from PySide6.QtCore import QEvent, QObject, QSettings, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QComboBox, QMessageBox, QWidget

from .runtime_paths import BASE_DIR

APP_DIR = Path(__file__).resolve().parent
ICON_DIR = APP_DIR / "assets" / "icons" / "mastixa_menu"
LIGHT_ICON = ICON_DIR / "light_mode.png"
DARK_ICON = ICON_DIR / "dark_mode.png"

_SETTINGS_ORG = "Fieltra"
_SETTINGS_APP = "Fieltra"
_SETTINGS_KEY = "appearance/theme"
_SETTINGS_FILE = BASE_DIR / "data" / "appearance.ini"


NAVIGATION_LIGHT_STYLESHEET = """
QTreeView#farmNavigation {
    border: 0; outline: 0;
    background: #F1F4F2; color: #21483A;
    alternate-background-color: #E1EAE5;
    selection-background-color: #DFEEE3; selection-color: #244C37;
}
QTreeView#farmNavigation::item { padding: 0; border: 0; }
"""


DARK_STYLESHEET = """
QTreeView#farmNavigation {
    background: #20272C; color: #E7ECEF;
    alternate-background-color: #2B3338;
    selection-background-color: #314B3C; selection-color: #E5F0E8;
}
QMainWindow, QDialog { background: #151A1E; color: #E7ECEF; }
QWidget { color: #E7ECEF; }
QWidget#sidebar, QListWidget#categoryList {
    background: #101815;
    color: #F3F7F5;
}
QListWidget#categoryList {
    border: none;
    outline: none;
}
QListWidget#categoryList::item:selected {
    background: #3F765B;
    color: white;
}
QListWidget#categoryList::item:hover:!selected { background: #202D28; }

QLabel { color: #E7ECEF; background: transparent; }
QLabel#pageTitle { color: #F2F6F4; }
DashboardPage QLabel#metricValue { color: #E7ECEF; }
QGroupBox#metricCard QLabel#metricValue { color: #E7ECEF; }
QGroupBox#metricCard QLabel#metricCaption { color: #BDC8C2; }
QLabel#pageSubtitle, QLabel#mutedLabel { color: #AAB6B0; }

QFrame#yearContextBar[yearContextState="active"] {
    background: #1F2B25;
    color: #EAF3EE;
    border-bottom: 1px solid #496657;
}
QFrame#yearContextBar[yearContextState="active"] QLabel {
    color: #EAF3EE;
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
    background: #20272C;
    color: #E7ECEF;
    border: 1px solid #4A565E;
}
QGroupBox::title { color: #EEF3F5; }
QFrame { border-color: #4A565E; }

QTabWidget::pane {
    background: #1B2227;
    border-color: #3A454C;
}
QTabWidget#mainTabs::pane,
QTabWidget#recordingInnerTabs::pane {
    background: #171D21;
    border-color: #3A454C;
}
QTabBar::tab {
    background: #242C32;
    color: #DDE5E1;
    border-color: #3A454C;
}
QTabBar::tab:selected {
    background: #355F4A;
    color: white;
    border-color: #628D76;
}
QTabBar::tab:hover:!selected { background: #2D3934; color: white; }
QTabWidget#mainTabs QTabBar::tab,
QTabWidget#recordingInnerTabs QTabBar::tab {
    background: #242C32;
    color: #DDE5E1;
    border-color: #3A454C;
}
QTabWidget#mainTabs QTabBar::tab:selected,
QTabWidget#recordingInnerTabs QTabBar::tab:selected {
    background: #355F4A;
    color: white;
    border-color: #628D76;
}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox,
QDateEdit, QTimeEdit, QDateTimeEdit, QSpinBox, QDoubleSpinBox {
    background: #252D33;
    color: #EEF2F4;
    border-color: #4A565E;
    selection-background-color: #4F8068;
    selection-color: white;
}
QLineEdit:read-only, QTextEdit:read-only, QPlainTextEdit:read-only {
    background: #20272C;
    color: #B9C3BE;
}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QComboBox:disabled, QDateEdit:disabled, QTimeEdit:disabled,
QDateTimeEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background: #20272C;
    color: #89968F;
    border-color: #3D474D;
}
QComboBox::drop-down, QDateEdit::drop-down, QTimeEdit::drop-down,
QDateTimeEdit::drop-down, QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background: #313B43;
    border-color: #4A565E;
}
QComboBox QAbstractItemView, QAbstractItemView {
    background: #20272C;
    color: #EDF2F4;
    border-color: #4A565E;
    selection-background-color: #4F8068;
    selection-color: white;
    alternate-background-color: #1B2227;
}
QComboBox QAbstractItemView::item {
    background: #20272C;
    color: #EDF2F4;
    min-height: 28px;
    padding: 4px 8px;
}
QComboBox QAbstractItemView::item:hover:enabled,
QComboBox QAbstractItemView::item:selected:enabled {
    background: #4F8068;
    color: white;
}
QComboBox QAbstractItemView::item:disabled {
    background: #20272C;
    color: #AAB6B0;
}

QTableView, QTableWidget, QTreeView, QTreeWidget,
QListView, QListWidget {
    background: #1C2328;
    color: #E9EEF0;
    alternate-background-color: #222B30;
    gridline-color: #3A454C;
    border-color: #3A454C;
    selection-background-color: #4F8068;
    selection-color: white;
}
QHeaderView::section {
    background: #283139;
    color: #EDF2F4;
    border-color: #3A454C;
}
QTableView::item, QTableWidget::item,
QTreeView::item, QTreeWidget::item,
QListView::item, QListWidget::item {
    color: #E9EEF0;
}
QTableView::item:selected, QTableWidget::item:selected,
QTreeView::item:selected, QTreeWidget::item:selected,
QListView::item:selected, QListWidget::item:selected {
    background: #4F8068;
    color: white;
}

QPushButton, QToolButton {
    background: #263139;
    color: #EEF2F4;
    border-color: #4A565E;
}
QPushButton:hover, QToolButton:hover { background: #303C44; }
QPushButton:pressed, QToolButton:pressed,
QPushButton:checked, QToolButton:checked {
    background: #355F4A;
    color: white;
    border-color: #6A967E;
}
QPushButton:disabled, QToolButton:disabled {
    background: #2B3338;
    color: #7F898F;
    border-color: #3D474D;
}
QToolButton[appearanceChoice="true"] {
    background: #252E34;
    color: #E7ECEF;
    border: 2px solid #4A565E;
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 15px;
    font-weight: 700;
}
QToolButton[appearanceChoice="true"]:hover {
    background: #2D383F;
    border-color: #6B7880;
}
QToolButton[appearanceChoice="true"]:checked {
    background: #304F40;
    color: white;
    border: 3px solid #78A88C;
}
QCheckBox, QRadioButton { color: #E7ECEF; background: transparent; }

QMenuBar, QMenu { background: #20272C; color: #E7ECEF; }
QMenu::item { background: transparent; color: #E7ECEF; }
QMenu::item:disabled { color: #AAB6B0; }
QMenu::item:selected { background: #4F8068; color: white; }
QToolTip { background: #263038; color: #F3F6F7; border: 1px solid #53616A; }
QStatusBar { background: #151A1E; color: #DCE3E6; }
QScrollArea, QScrollArea > QWidget > QWidget, QAbstractScrollArea::viewport {
    background: #171D21;
}
QScrollBar:vertical, QScrollBar:horizontal { background: #1B2227; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #4A565E;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: #607079;
}
"""


# Several pages use small local stylesheets with hard-coded light colours. A
# single conversion per unique stylesheet keeps those widgets readable while
# preserving the full-tree coverage that prevents mixed light/dark sections.
_DARK_MESSAGE_BOX_STYLE = """
QMessageBox {
    background: #20272C;
    color: #E7ECEF;
}
QMessageBox QLabel {
    background: transparent;
    color: #F2F6F4;
}
QMessageBox QPushButton {
    background: #263139;
    color: #EEF2F4;
    border: 1px solid #4A565E;
    border-radius: 5px;
    padding: 6px 16px;
    min-width: 72px;
}
QMessageBox QPushButton:hover {
    background: #303C44;
}
QMessageBox QPushButton:pressed {
    background: #355F4A;
    color: white;
    border-color: #6A967E;
}
"""


_DARK_COLOUR_MAP = {
    "#f5f6f3": "#171d21",
    "#f1f4f2": "#20272c",
    "#f0f4f1": "#20272c",
    "#f0f5f2": "#242c32",
    "#f8f9f8": "#1c2328",
    "#f8faf8": "#1c2328",
    "#fffdf7": "#252d33",
    "#e8efeb": "#242c32",
    "#eef2f0": "#242c32",
    "#e1eae5": "#2b3338",
    "#e6ede9": "#283139",
    "#e9eee9": "#283139",
    "#ffffff": "#20272c",
    "background: white": "background: #20272c",
    "background-color: white": "background-color: #20272c",
    "#24312b": "#e7ecef",
    "#26382f": "#e7ecef",
    "#21483a": "#e7ecef",
    "#1f5a43": "#f2f6f4",
    "#52655b": "#bdc8c2",
    "#66766e": "#aab6b0",
    "#67746d": "#aab6b0",
    "#6a7a72": "#aab6b0",
    "#d6e0da": "#3a454c",
    "#dce5e0": "#3a454c",
    "#c7d3cc": "#4a565e",
    "#cfd7d2": "#4a565e",
    "#d1d8d3": "#4a565e",
    "#e3e9e5": "#3a454c",
    "#d5ddd8": "#2b3338",
    "#c7d0cb": "#2b3338",
    "#c4cec8": "#3d474d",
    "#f4f4f4": "#89968f",
    "#58665f": "#89968f",
}


@lru_cache(maxsize=512)
def _dark_local_style(original: str) -> str:
    converted = original
    for light, dark in _DARK_COLOUR_MAP.items():
        converted = converted.replace(light, dark)
        converted = converted.replace(light.upper(), dark)
    return converted


@lru_cache(maxsize=1)
def _scoped_dark_stylesheet(stylesheet: str) -> str:
    """Keep the existing dark rules installed without replacing the Qt cascade."""
    def scope(match):
        selectors, body = match.groups()
        rules = []
        for selector in selectors.split(","):
            selector = selector.strip()
            rules.append('[mastixaTheme="dark"] ' + selector)
            if re.fullmatch(r"\w+", selector):
                rules.append(selector + '[mastixaTheme="dark"]')
        return ", ".join(rules) + " {" + body + "}"
    return re.sub(r"([^{}]+)\{([^{}]*)\}", scope, stylesheet)


def _settings() -> QSettings:
    # QSettings creates the parent on sync and reports write failures via status,
    # rather than blocking startup when the user-data directory is unavailable.
    return QSettings(str(_SETTINGS_FILE), QSettings.Format.IniFormat)


def _saved_theme() -> str:
    settings = _settings()
    if _SETTINGS_FILE.exists():
        return str(settings.value(_SETTINGS_KEY, "light")).casefold()

    return "light"


def _dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#171D21"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#E7ECEF"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1C2328"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#222B30"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#263038"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#F3F6F7"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#E7ECEF"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#263139"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#EEF2F4"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#4F8068"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#89968F"))
    return palette


class ThemeController(QObject):
    theme_changed = Signal(str)
    _uses_scoped_styles = True

    def __init__(
        self,
        app: QApplication,
        light_stylesheet: str,
        light_palette: QPalette,
    ) -> None:
        super().__init__(app)
        self.app = app
        self.light_stylesheet = light_stylesheet + "\n" + NAVIGATION_LIGHT_STYLESHEET
        self.light_palette = QPalette(light_palette)
        saved = _saved_theme()
        self._theme = "dark" if saved == "dark" else "light"
        self._applying = False
        self._theme_generation = 0
        app.installEventFilter(self)

    @property
    def theme(self) -> str:
        return self._theme

    def apply_saved_theme(self) -> None:
        requested = self._theme
        self._theme = ""
        self.set_theme(requested, persist=False)

    def apply_to(self, root: QWidget) -> None:
        """Prepare newly constructed pages before their first visible paint."""
        self._style_exposed_tree(root, include_hidden=True)

    def set_theme(self, theme: str, persist: bool = True) -> None:
        theme = "dark" if theme == "dark" else "light"
        if self._applying or theme == self._theme:
            return

        self._applying = True
        windows = self.app.topLevelWidgets()
        for window in windows:
            window.setUpdatesEnabled(False)
        try:
            # Replacing QApplication's stylesheet recursively restyles every
            # cached page, including hidden pages. Install both existing skins
            # once, then polish exposed widgets; hidden pages catch up on Show.
            sheet = self.light_stylesheet + "\n" + _scoped_dark_stylesheet(DARK_STYLESHEET)
            if self.app.styleSheet() != sheet:
                self.app.setStyleSheet(sheet)
            self._theme_generation += 1
            self._theme = theme
            self.app.setPalette(_dark_palette() if theme == "dark" else self.light_palette)
            for window in windows:
                window.setProperty("mastixaTheme", theme)
            window_set = set(windows)
            for window in windows:
                # Parented dialogs are top-level windows too, but the parent's
                # recursive pass already includes them. Style each tree once.
                ancestor = window.parent()
                while ancestor is not None and ancestor not in window_set:
                    ancestor = ancestor.parent()
                if ancestor is None:
                    self._style_exposed_tree(
                        window, include_hidden=not hasattr(window, "desktop_navigation"))
        finally:
            for window in windows:
                window.setUpdatesEnabled(True)
                window.update()
            self._applying = False

        if persist:
            settings = _settings()
            settings.setValue(_SETTINGS_KEY, theme)
            settings.sync()
        self.theme_changed.emit(theme)

    def _style_exposed_tree(self, root: QWidget, *, include_hidden=False) -> None:
        # Qt is already opening this native popup. Re-polishing its container
        # or viewport during Show interferes with popup painting/input state.
        # configure_combo_popup prepares it while its owning combo is styled.
        if root.window().objectName() == 'fieltraComboPopup':
            return
        root.window().setProperty("mastixaTheme", self._theme)
        for widget in (root, *root.findChildren(QWidget)):
            if widget.window().objectName() == 'fieltraComboPopup':
                continue
            if widget is not root and not include_hidden and not widget.isVisible():
                continue
            if getattr(widget, "_mastixa_scoped_theme_generation", -1) == self._theme_generation:
                continue
            self._apply_widget_style(widget)
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)
            widget.update()
            widget._mastixa_scoped_theme_generation = self._theme_generation

    def _apply_widget_style(self, widget: QWidget) -> None:
        if isinstance(widget, QComboBox):
            from .ui_helpers import configure_combo_popup
            configure_combo_popup(widget)
        current = widget.styleSheet()
        if not hasattr(widget, "_mastixa_light_local_style"):
            widget._mastixa_light_local_style = current
        original = widget._mastixa_light_local_style
        converted = _dark_local_style(original) if self._theme == "dark" else original
        if self._theme == "dark" and isinstance(widget, QMessageBox):
            converted += "\n" + _DARK_MESSAGE_BOX_STYLE
        if current != converted:
            widget.setStyleSheet(converted)

    def _apply_local_styles(self, root: QWidget) -> None:
        widgets = [root, *root.findChildren(QWidget)]
        for widget in widgets:
            self._apply_widget_style(widget)

    def eventFilter(self, watched, event):
        if (
            not self._applying
            and event.type() == QEvent.Type.Show
            and isinstance(watched, QWidget)
        ):
            if getattr(watched, "_mastixa_scoped_theme_generation", -1) != self._theme_generation:
                # Show precedes the first paint. Catch up synchronously in both
                # directions, styling only this newly exposed subtree once.
                self._style_exposed_tree(watched)
        return False

    def _style_new_widget(self, widget: QWidget) -> None:
        try:
            if not self._applying:
                self._apply_local_styles(widget)
        except RuntimeError:
            pass
