"""Native popup lifecycle regressions. Run only in the approved Sandbox."""
from pathlib import Path
from collections import deque
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QElapsedTimer,QEvent,QObject,Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication,QComboBox,QScrollArea,QStyle,
    QStyleOptionComboBox,QVBoxLayout,QWidget)

from app.appearance_theme import ThemeController
from app.main_window import STYLESHEET,build_app_palette
from app.ui_helpers import configure_combo_popup
from app.wheel_navigation import install_wheel_navigation


class PopupEvents(QObject):
    """Observe dispatch without changing or consuming any native Qt event."""
    def __init__(self,combo):
        super().__init__(combo)
        self.combo=combo;self.events=deque(maxlen=40)
        view=combo.view()
        self.targets={combo:'combo',view:'view',view.viewport():'viewport',view.window():'popup'}
        for target in self.targets:target.installEventFilter(self)

    def eventFilter(self,watched,event):
        if event.type() in (QEvent.Type.MouseMove,QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,QEvent.Type.KeyPress,QEvent.Type.Hide,QEvent.Type.Show):
            position=event.position().toPoint() if hasattr(event,'position') else None
            self.events.append((self.targets[watched],event.type().name,position))
        return False

    def describe(self):
        view=self.combo.view()
        return (f'combo index={self.combo.currentIndex()}, view index={view.currentIndex().row()}, '
                f'popup visible={view.window().isVisible()}, focus={QApplication.focusWidget()}, '
                f'popup geometry={view.window().geometry()}, viewport={view.viewport().rect()}, '
                f'events={list(self.events)}')


def wait_for(condition,message,diagnostic=lambda:'',timeout=1000):
    """Bound event processing; never retry input or alter a selection to pass."""
    timer=QElapsedTimer();timer.start()
    while True:
        QApplication.processEvents()
        if condition():return
        if timer.elapsed()>=timeout:raise AssertionError(message+'; '+diagnostic())
        QTest.qWait(1)


def popup_events(combo):
    if not hasattr(combo,'_test_popup_events'):combo._test_popup_events=PopupEvents(combo)
    return combo._test_popup_events


def click_arrow(combo):
    probe=popup_events(combo);probe.events.clear()
    assert not combo.view().window().isVisible(),'Previous popup was not closed; '+probe.describe()
    option=QStyleOptionComboBox();combo.initStyleOption(option)
    rect=combo.style().subControlRect(QStyle.ComplexControl.CC_ComboBox,option,
                                    QStyle.SubControl.SC_ComboBoxArrow,combo)
    point=rect.center()
    assert combo.rect().contains(point),'Arrow outside combo; '+probe.describe()
    assert combo.style().hitTestComplexControl(QStyle.ComplexControl.CC_ComboBox,option,point,combo)==QStyle.SubControl.SC_ComboBoxArrow
    window=combo.window();handle=window.windowHandle()
    assert handle is not None,'Combo window has no native handle'
    position=combo.mapTo(window,point)
    probe.arrow_position=combo.mapToGlobal(point)
    # QWindow overload uses Qt's QPA dispatch, including native popup routing.
    QTest.mouseMove(handle,position)
    QTest.mouseClick(handle,Qt.MouseButton.LeftButton,pos=position)
    wait_for(lambda:combo.view().isVisible(),'One arrow click did not open popup',probe.describe)
    assert any(target=='combo' and kind=='MouseButtonPress' for target,kind,_ in probe.events),probe.describe()


def select_popup_item(combo,index):
    probe=popup_events(combo);view=combo.view();popup=view.window()
    assert popup.isVisible(),probe.describe()
    item=combo.model().index(index,combo.modelColumn(),combo.rootModelIndex())
    assert item.isValid(),f'Invalid test row {index}'
    view.scrollTo(item);view.doItemsLayout();QApplication.processEvents()
    point=view.visualRect(item).center()
    assert view.viewport().rect().contains(point) and view.indexAt(point)==item,probe.describe()
    assert (view.viewport().mapToGlobal(point)-probe.arrow_position).manhattanLength()>9,probe.describe()
    before=len(probe.events)
    position=view.viewport().mapTo(popup,point)
    # Qt starts blockMouseReleaseTimer on an arrow press. A real pointer move
    # >9px stops it (qcombobox.cpp:945-951); press/release alone does not.
    # The QWidget overload can use QCursor instead of dispatching a move under
    # offscreen. QWindow delivers it, then clicks through the same Qt dispatch.
    QTest.mouseMove(popup.windowHandle(),position)
    expected={'viewport':point,'view':view.viewport().mapTo(view,point)}
    wait_for(lambda:any(target in expected and kind=='MouseMove' and position==expected[target]
                        for target,kind,position in list(probe.events)[before:]),
             'Pointer move was not delivered to the popup list',probe.describe)
    before=len(probe.events)
    QTest.mouseClick(popup.windowHandle(),Qt.MouseButton.LeftButton,pos=position)
    QApplication.processEvents()
    for kind in ('MouseButtonPress','MouseButtonRelease'):
        assert any(target in expected and event==kind for target,event,_ in list(probe.events)[before:]),probe.describe()
    # No wait for the double-click guard or delayed hide: preserve the original
    # immediate-close assertion once real move/press/release have been delivered.
    assert not popup.isVisible(),'Selection did not close popup; '+probe.describe()


def escape_popup(combo):
    probe=popup_events(combo);popup=combo.view().window()
    assert popup.isVisible(),probe.describe()
    before=len(probe.events)
    QTest.keyClick(popup.windowHandle(),Qt.Key.Key_Escape)
    QApplication.processEvents()
    assert any(kind=='KeyPress' for _,kind,_ in list(probe.events)[before:]),probe.describe()
    assert not popup.isVisible(),'Esc did not close popup; '+probe.describe()


class ComboPopupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        install_wheel_navigation(cls.app)

    def setUp(self):
        root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('app.appearance_theme._SETTINGS_FILE',root/'appearance.ini'))
        original_style,original_palette=self.app.styleSheet(),self.app.palette()
        self.addCleanup(self.app.setStyleSheet,original_style)
        self.addCleanup(self.app.setPalette,original_palette)
        self.app.setStyleSheet(STYLESHEET);self.app.setPalette(build_app_palette())
        self.theme=ThemeController(self.app,STYLESHEET,build_app_palette())
        self.addCleanup(self.theme.deleteLater);self.addCleanup(self.app.removeEventFilter,self.theme)
        self.window=QScrollArea();self.window.setWidgetResizable(True)
        body=QWidget();layout=QVBoxLayout(body)
        self.combo=QComboBox();self.combo.addItems(['Χωρίς υπόβαθρο','OpenStreetMap','CDSE'])
        layout.addWidget(self.combo);layout.addStretch();self.window.setWidget(body)
        self.addCleanup(self.window.deleteLater);self.addCleanup(self.window.close)
        self.addCleanup(self.combo.hidePopup)
        self.theme.apply_saved_theme();self.window.resize(420,280);self.window.show()
        self.window.activateWindow();self.combo.setFocus();self.app.processEvents()

    def test_select_same_value_and_immediately_reopen_with_arrow_in_both_themes(self):
        for theme in ('light','dark','light'):
            self.theme.set_theme(theme,persist=False)
            for index in (1,0,0,1,1,0):
                click_arrow(self.combo);self.assertTrue(self.combo.view().isVisible())
                view=self.combo.view();select_popup_item(self.combo,index)
                self.assertEqual(index,self.combo.currentIndex(),popup_events(self.combo).describe())
                self.assertFalse(view.window().isVisible(),popup_events(self.combo).describe())
                self.assertTrue(self.combo.hasFocus())
            click_arrow(self.combo);self.assertTrue(self.combo.view().isVisible());self.combo.hidePopup()

    def test_escape_keeps_value_focus_and_allows_immediate_arrow_reopen(self):
        for theme in ('light','dark'):
            self.theme.set_theme(theme,persist=False)
            self.combo.setCurrentIndex(1)
            for _ in range(3):
                click_arrow(self.combo);self.assertTrue(self.combo.view().isVisible())
                QTest.keyClick(self.combo.view(),Qt.Key.Key_Down)
                escape_popup(self.combo)
                self.assertEqual(1,self.combo.currentIndex())
                self.assertFalse(self.combo.view().window().isVisible())
                self.assertTrue(self.combo.hasFocus())

    def test_keyboard_open_selection_and_reopen_use_native_focus(self):
        self.combo.setCurrentIndex(0);self.combo.setFocus()
        QTest.keyClick(self.combo,Qt.Key.Key_Down,Qt.KeyboardModifier.AltModifier)
        self.app.processEvents();self.assertTrue(self.combo.view().isVisible())
        QTest.keyClick(self.combo.view(),Qt.Key.Key_Down)
        QTest.keyClick(self.combo.view(),Qt.Key.Key_Return);self.app.processEvents()
        self.assertEqual(1,self.combo.currentIndex())
        self.assertFalse(self.combo.view().isVisible());self.assertTrue(self.combo.hasFocus())
        click_arrow(self.combo);self.assertTrue(self.combo.view().isVisible())

    def test_popup_is_opaque_bordered_native_and_not_repolished_during_show(self):
        for theme in ('light','dark','light'):
            self.theme.set_theme(theme,persist=False)
            configure_combo_popup(self.combo)
            proxy=self.combo._fieltra_popup_style
            configure_combo_popup(self.combo);self.assertIs(proxy,self.combo._fieltra_popup_style)
            with patch.object(self.theme,'_apply_widget_style',wraps=self.theme._apply_widget_style) as style:
                click_arrow(self.combo)
            popup=self.combo.view().window()
            self.assertEqual(Qt.WindowType.Popup,popup.windowType())
            self.assertTrue(popup.autoFillBackground())
            self.assertIn('border: 1px solid',popup.styleSheet())
            colour=self.combo.view().palette().color(QPalette.ColorRole.Base)
            self.assertEqual(255,colour.alpha())
            self.assertEqual('#20272c' if theme=='dark' else '#ffffff',colour.name())
            self.assertTrue(all(call.args[0].window() is not popup for call in style.call_args_list))
            self.assertEqual(0,proxy.styleHint(QStyle.StyleHint.SH_Menu_FlashTriggeredItem))
            self.combo.hidePopup()


if __name__=='__main__':unittest.main()
