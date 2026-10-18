"""Keep page scrolling from editing values or changing tabs under the pointer."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractScrollArea, QAbstractSpinBox, QApplication, QComboBox, QDial,
    QScrollArea, QSlider, QTabBar, QTabWidget, QWidget,
)


def _selection_control(widget: QWidget) -> QWidget | None:
    current = widget
    while current is not None:
        if isinstance(current, (QComboBox, QAbstractSpinBox, QSlider, QDial, QTabBar)):
            return current
        # An editable combo's popup list is a real scrolling control, not its
        # closed editor. Other scroll areas also keep their normal wheel rules.
        if isinstance(current, QAbstractScrollArea):
            return None
        current = current.parentWidget()
    return None


def _can_scroll(area: QAbstractScrollArea, event: QWheelEvent) -> bool:
    delta = event.pixelDelta() if not event.pixelDelta().isNull() else event.angleDelta()
    horizontal = abs(delta.x()) > abs(delta.y())
    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
        horizontal = True
    bar = area.horizontalScrollBar() if horizontal else area.verticalScrollBar()
    if delta.isNull() and event.phase() != Qt.ScrollPhase.NoScrollPhase:
        return bar.maximum() > bar.minimum()
    amount = delta.x() if horizontal and delta.x() else delta.y()
    return (amount > 0 and bar.value() > bar.minimum()) or (
        amount < 0 and bar.value() < bar.maximum()
    )


def _page_scroll_target(page: QWidget, event: QWheelEvent) -> QAbstractScrollArea | None:
    if isinstance(page, QTabWidget):
        current = page.currentWidget()
        return _page_scroll_target(current, event) if current is not None else None
    candidates = ([page] if isinstance(page, QAbstractScrollArea) else [])
    candidates += page.findChildren(QAbstractScrollArea)
    candidates = [area for area in candidates if area.isVisible() and _can_scroll(area, event)]
    # Prefer the enclosing page over embedded text editors or tables. If the
    # page only has a table, its visible viewport remains a useful scroll target.
    candidates.sort(key=lambda area: (
        isinstance(area, QScrollArea), area.viewport().width() * area.viewport().height()
    ), reverse=True)
    return candidates[0] if candidates else None


def _scroll_target(control: QWidget, event: QWheelEvent) -> QAbstractScrollArea | None:
    current = control.parentWidget()
    while current is not None:
        if isinstance(current, QAbstractScrollArea) and _can_scroll(current, event):
            return current
        if isinstance(control, QTabBar) and isinstance(current, QTabWidget):
            page = current.currentWidget()
            target = _page_scroll_target(page, event) if page is not None else None
            if target is not None:
                return target
        current = current.parentWidget()
    return None


class _PageWheelFilter(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._forwarding = False

    def eventFilter(self, watched, event) -> bool:
        if self._forwarding or event.type() != QEvent.Type.Wheel or not isinstance(watched, QWidget):
            return False
        popup = QApplication.activePopupWidget()
        if popup is not None and (watched is popup or popup.isAncestorOf(watched)):
            return False
        control = _selection_control(watched)
        if control is None:
            return False
        if isinstance(control, QComboBox) and control.view().isVisible():
            return False
        target = _scroll_target(control, event)
        if target is not None:
            viewport = target.viewport()
            local = QPointF(viewport.mapFromGlobal(event.globalPosition().toPoint()))
            forwarded = QWheelEvent(
                local, event.globalPosition(), event.pixelDelta(), event.angleDelta(),
                event.buttons(), event.modifiers(), event.phase(), event.inverted(),
                event.source(), event.pointingDevice(),
            )
            forwarded.setTimestamp(event.timestamp())
            self._forwarding = True
            try:
                QApplication.sendEvent(viewport, forwarded)
            finally:
                self._forwarding = False
        # Consume even at a page edge: Qt must not turn the original event into
        # a value/tab change or propagate it a second time. Keys/clicks are never
        # filtered, including on controls which already have keyboard focus.
        event.accept()
        return True


def install_wheel_navigation(app: QApplication) -> None:
    """Install once for every page, dialog and widget created now or lazily."""
    if getattr(app, "_fieltra_page_wheel_filter", None) is None:
        wheel_filter = _PageWheelFilter(app)
        app.installEventFilter(wheel_filter)
        app._fieltra_page_wheel_filter = wheel_filter
