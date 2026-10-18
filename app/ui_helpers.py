from __future__ import annotations

from functools import wraps

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (QHeaderView, QTableWidget, QScrollArea, QWidget,
    QVBoxLayout, QLayout, QFormLayout, QProxyStyle, QStyle, QStyledItemDelegate, QStyleOptionViewItem)


def scrollable_entry_layout(page):
    """Keep form/actions and a usable table reachable in a small viewport."""
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea(page)
    scroll.setObjectName("entryPageScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
    scroll.setWidget(content)
    outer.addWidget(scroll)
    return layout


def table_widget(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    header = table.horizontalHeader()
    header.setMinimumSectionSize(100)
    header.setResizeContentsPrecision(100)
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return table


def batched_table_refresh(refresh):
    """Resize/paint a populated CRUD table once, keeping model notifications."""
    @wraps(refresh)
    def batched(page, *args, **kwargs):
        table = page.table
        header = table.horizontalHeader()
        modes = [header.sectionResizeMode(column) for column in range(header.count())]
        enabled = table.updatesEnabled()
        table.setUpdatesEnabled(False)
        try:
            # ResizeToContents on a visible table recomputes cell geometry for
            # every replacement item. Keep existing widths during population;
            # restore each column's policy once the full data is available.
            for column in range(header.count()):
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            return refresh(page, *args, **kwargs)
        finally:
            for column, mode in enumerate(modes):
                header.setSectionResizeMode(column, mode)
            table.setUpdatesEnabled(enabled)
    return batched


class _ComboPopupStyle(QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        # Qt's menu mode can defer doHidePopup/resetButton through flashing
        # timers. Use the native scrolling list with synchronous close/reset,
        # so a second arrow click cannot encounter a still-visible container.
        if hint in (QStyle.StyleHint.SH_ComboBox_Popup,
                    QStyle.StyleHint.SH_Menu_FlashTriggeredItem):
            return 0
        return super().styleHint(hint, option, widget, returnData)


class _ComboPopupDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        opt=QStyleOptionViewItem(option)
        # The selected row itself identifies the keyboard's current item.
        # Remove only the duplicate native focus rectangle, never focus/input.
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter,opt,index)


def configure_combo_popup(combo):
    """Prepare Qt's own popup before Show; retain native input/focus handling."""
    if not hasattr(combo, '_fieltra_popup_style'):
        # Do not give QProxyStyle QApplication.style(): the proxy owns its base.
        proxy = _ComboPopupStyle()
        proxy.setParent(combo)
        combo._fieltra_popup_style = proxy
        combo.setStyle(proxy)
    view = combo.view()
    if not isinstance(view.itemDelegate(),_ComboPopupDelegate):
        view.setItemDelegate(_ComboPopupDelegate(view))
    popup = view.window()
    popup.setObjectName('fieltraComboPopup')
    popup.setAutoFillBackground(True)
    view.setAutoFillBackground(True)
    view.viewport().setAutoFillBackground(True)
    theme = combo.window().property('mastixaTheme')
    dark = (theme == 'dark' if theme in ('light','dark') else
            combo.palette().color(QPalette.ColorRole.Window).lightness() < 128)
    background, foreground, border, selected = (
        ('#20272C', '#EDF2F4', '#75838C', '#355F4A') if dark else
        ('#FFFFFF', '#24312B', '#718278', '#315F49'))
    sheet = ('QFrame#fieltraComboPopup { background: '+background+'; border: 1px solid '+border+'; } '
        'QFrame#fieltraComboPopup QAbstractItemView { background: '+background+'; color: '+foreground+'; '
        'border: 0px; selection-background-color: '+selected+'; selection-color: white; } '
        'QFrame#fieltraComboPopup QAbstractItemView::item { background: '+background+'; color: '+foreground+'; } '
        'QFrame#fieltraComboPopup QAbstractItemView::item:selected, '
        'QFrame#fieltraComboPopup QAbstractItemView::item:hover { background: '+selected+'; color: white; }')
    if popup.styleSheet() != sheet:popup.setStyleSheet(sheet)
    palette = QPalette(view.palette())
    for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base):
        palette.setColor(role, QColor(background))
    view.setPalette(palette);view.viewport().setPalette(palette);popup.setPalette(palette)
    popup._mastixa_scoped_theme_generation = getattr(combo, '_mastixa_scoped_theme_generation', -1)
    view.setMouseTracking(True)
    if hasattr(view, "setSpacing"):
        view.setSpacing(2)
    metrics = view.fontMetrics()
    width = max((metrics.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())), default=0)
    screen = combo.screen()
    limit = screen.availableGeometry().width() - 40 if screen else 1000
    view.setMinimumWidth(min(limit, max(combo.width(), width + 40)))


def compact_decimal(value: float | int | None, max_decimals: int = 3) -> str:
    """Up to max_decimals, without forced trailing zeroes."""
    number = float(value or 0)
    threshold = 0.5 * (10 ** (-max_decimals))
    if abs(number) < threshold:
        number = 0.0
    return f"{number:.{max_decimals}f}".rstrip("0").rstrip(".")


def format_kg(value: float | int | None) -> str:
    return f"{compact_decimal(value, 3)} kg"
