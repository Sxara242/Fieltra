"""Native Qt regressions; execute only in the approved isolated test guest."""
import unittest

from PySide6.QtCore import QDate, QEvent, QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QDial, QScrollArea, QSlider, QSpinBox,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from app.wheel_navigation import install_wheel_navigation
from app.ui_helpers import configure_combo_popup


class WheelNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        install_wheel_navigation(cls.app)

    def setUp(self):
        self.windows = []

    def tearDown(self):
        for widget in reversed(self.windows):
            widget.close()
            widget.deleteLater()
        self.app.processEvents()

    def show(self, widget):
        self.windows.append(widget)
        widget.resize(440, 280)
        widget.show()
        self.app.processEvents()
        return widget

    def scroll_page(self, *controls):
        area = QScrollArea()
        area.setWidgetResizable(True)
        content = QWidget()
        content.setMinimumHeight(2000)
        layout = QVBoxLayout(content)
        for control in controls:
            layout.addWidget(control)
        layout.addStretch()
        area.setWidget(content)
        return area

    def wheel(self, widget, *, pixels=None, phase=Qt.ScrollPhase.NoScrollPhase):
        local = QPointF(widget.rect().center())
        event = QWheelEvent(
            local, QPointF(widget.mapToGlobal(local.toPoint())), pixels or QPoint(),
            QPoint() if pixels is not None else QPoint(0, -120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, phase, False,
        )
        QApplication.sendEvent(widget, event)

    def test_closed_focused_combo_scrolls_page_once_without_changing_value(self):
        combo = QComboBox()
        combo.addItems(["one", "two", "three"])
        configure_combo_popup(combo)
        area = self.show(self.scroll_page(combo))
        combo.setFocus()
        self.wheel(area.viewport())
        expected = area.verticalScrollBar().value()
        self.assertGreater(expected, 0)
        area.verticalScrollBar().setValue(0)
        self.wheel(combo)
        self.assertEqual(0, combo.currentIndex())
        self.assertEqual(expected, area.verticalScrollBar().value())

    def test_dynamic_spin_date_and_editable_combo_children_preserve_values(self):
        area = self.show(self.scroll_page())
        spin, date, combo = QSpinBox(), QDateEdit(QDate(2026, 10, 16)), QComboBox()
        spin.setValue(10)
        combo.setEditable(True)
        combo.addItems(["one", "two"])
        for control in (spin, date, combo):
            area.widget().layout().insertWidget(0, control)
        self.app.processEvents()
        for editor in (spin.lineEdit(), date.lineEdit(), combo.lineEdit()):
            area.verticalScrollBar().setValue(0)
            self.wheel(editor)
            self.assertGreater(area.verticalScrollBar().value(), 0)
        self.assertEqual(10, spin.value())
        self.assertEqual(QDate(2026, 10, 16), date.date())
        self.assertEqual("one", combo.currentText())

    def test_page_edge_never_changes_combo_or_spins(self):
        combo, spin = QComboBox(), QSpinBox()
        combo.addItems(["one", "two"])
        spin.setValue(10)
        area = self.show(self.scroll_page(combo, spin))
        bar = area.verticalScrollBar()
        bar.setValue(bar.maximum())
        for control in (combo, spin):
            self.wheel(control)
        self.assertEqual(0, combo.currentIndex())
        self.assertEqual(10, spin.value())
        self.assertEqual(bar.maximum(), bar.value())

    def test_slider_and_dial_values_do_not_change_during_page_scroll(self):
        slider, dial = QSlider(Qt.Orientation.Horizontal), QDial()
        slider.setValue(20)
        dial.setValue(30)
        area = self.show(self.scroll_page(slider, dial))
        for control in (slider, dial):
            before = area.verticalScrollBar().value()
            self.wheel(control)
            self.assertGreater(area.verticalScrollBar().value(), before)
        self.assertEqual(20, slider.value())
        self.assertEqual(30, dial.value())

    def test_nested_scroll_at_inner_edge_uses_outer_page_once(self):
        combo = QComboBox()
        combo.addItems(["one", "two"])
        inner = self.scroll_page(combo)
        inner.setFixedHeight(150)
        outer = self.show(self.scroll_page(inner))
        inner.verticalScrollBar().setValue(inner.verticalScrollBar().maximum())
        self.wheel(outer.viewport())
        expected = outer.verticalScrollBar().value()
        outer.verticalScrollBar().setValue(0)
        self.wheel(combo)
        self.assertGreater(expected, 0)
        self.assertEqual(expected, outer.verticalScrollBar().value())
        self.assertEqual(0, combo.currentIndex())

    def test_tab_bar_scrolls_current_page_without_changing_tab(self):
        tabs = QTabWidget()
        first = self.scroll_page()
        tabs.addTab(first, "First")
        tabs.addTab(self.scroll_page(), "Second")
        self.show(tabs)
        self.wheel(tabs.tabBar())
        self.assertEqual(0, tabs.currentIndex())
        self.assertGreater(first.verticalScrollBar().value(), 0)
        self.assertEqual(0, tabs.widget(1).verticalScrollBar().value())

    def test_open_combo_popup_still_receives_scroll(self):
        combo = QComboBox()
        combo.addItems([str(index) for index in range(80)])
        combo.setMaxVisibleItems(6)
        configure_combo_popup(combo)
        self.show(self.scroll_page(combo))
        combo.showPopup()
        self.app.processEvents()
        self.assertTrue(combo.view().isVisible())
        bar = combo.view().verticalScrollBar()
        bar.setValue(0)
        self.wheel(combo.view().viewport())
        self.assertGreater(bar.value(), 0)
        combo.hidePopup()

    def test_keyboard_and_deliberate_mouse_selection_remain_available(self):
        combo = QComboBox()
        combo.addItems(["one", "two", "three"])
        self.show(self.scroll_page(combo))
        combo.setFocus()
        QTest.keyClick(combo, Qt.Key.Key_Down)
        self.assertEqual(1, combo.currentIndex())
        combo.showPopup()
        self.app.processEvents()
        index = combo.model().index(2, 0)
        QTest.mouseClick(combo.view().viewport(), Qt.MouseButton.LeftButton,
                         pos=combo.view().visualRect(index).center())
        self.assertEqual(2, combo.currentIndex())
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "First")
        tabs.addTab(QWidget(), "Second")
        self.show(tabs)
        QTest.mouseClick(tabs.tabBar(), Qt.MouseButton.LeftButton,
                         pos=tabs.tabBar().tabRect(1).center())
        self.assertEqual(1, tabs.currentIndex())
        tabs.tabBar().setFocus()
        QTest.keyClick(tabs.tabBar(), Qt.Key.Key_Left)
        self.assertEqual(0, tabs.currentIndex())

    def test_touchpad_pixel_delta_and_phase_forward_exactly_once(self):
        combo = QComboBox()
        area = self.show(self.scroll_page(combo))
        captured = []

        class Capture(QObject):
            def eventFilter(self, watched, event):
                if event.type() == QEvent.Type.Wheel:
                    captured.append((event.pixelDelta(), event.angleDelta(), event.phase()))
                    return True
                return False

        capture = Capture(area)
        area.viewport().installEventFilter(capture)
        self.wheel(combo, pixels=QPoint(), phase=Qt.ScrollPhase.ScrollBegin)
        self.wheel(combo, pixels=QPoint(0, -17), phase=Qt.ScrollPhase.ScrollUpdate)
        self.wheel(combo, pixels=QPoint(), phase=Qt.ScrollPhase.ScrollEnd)
        self.assertEqual([
            (QPoint(), QPoint(), Qt.ScrollPhase.ScrollBegin),
            (QPoint(0, -17), QPoint(), Qt.ScrollPhase.ScrollUpdate),
            (QPoint(), QPoint(), Qt.ScrollPhase.ScrollEnd),
        ], captured)

    def test_text_editor_keeps_its_normal_scrolling_and_install_is_idempotent(self):
        previous = self.app._fieltra_page_wheel_filter
        install_wheel_navigation(self.app)
        self.assertIs(previous, self.app._fieltra_page_wheel_filter)
        editor = QTextEdit()
        editor.setPlainText("\n".join(str(i) for i in range(200)))
        editor.setFixedHeight(150)
        area = self.show(self.scroll_page(editor))
        self.wheel(editor.viewport())
        self.assertGreater(editor.verticalScrollBar().value(), 0)
        self.assertEqual(0, area.verticalScrollBar().value())


if __name__ == "__main__":
    unittest.main()
