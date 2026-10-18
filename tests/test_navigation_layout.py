"""Real desktop graph, synthetic home and offscreen measured/painted geometry."""
from pathlib import Path
import unittest
from PySide6.QtCore import QEvent, QPointF, Qt, QRect
from PySide6.QtGui import QFontMetrics, QImage, QKeyEvent, QMouseEvent, QPainter, QPalette
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem
from tests import test_ui_revamp_phase1 as fixtures


class NavigationLayoutTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.UiRevampTests.setUpClass.__func__)
    setUp = fixtures.UiRevampTests.setUp
    cleanup_window = fixtures.UiRevampTests.cleanup_window

    def test_sidebar_accessible_name_follows_language_without_losing_selection(self):
        self.nav.open('fields')
        selected = self.nav.tree.currentIndex()
        for language, name in (('en', 'Application navigation'),
                               ('el', 'Πλοήγηση εφαρμογής'),
                               ('en', 'Application navigation')):
            self.controller.set_language(language, persist=False)
            self.controller.apply_to(self.nav.tree)
            self.assertEqual(name, self.nav.tree.accessibleName())
            self.assertEqual(selected, self.nav.tree.currentIndex())

    def option(self, index):
        option = QStyleOptionViewItem()
        option.initFrom(self.nav.tree)
        option.font = self.nav.tree.font()
        option.decorationSize = self.nav.tree.iconSize()
        option.rect = self.nav.tree.visualRect(index)
        return self.nav.tree.itemDelegate().option(option, index)

    def test_every_greek_row_fits_font_metrics_in_both_themes_and_windowed_widths(self):
        self.controller.set_language('el')
        self.window.show()
        self.nav.tree.expandAll()
        for theme in ('light', 'dark'):
            self.theme.set_theme(theme, persist=False)
            for width in (1024, 1280):
                self.window.resize(width, 768)
                self.app.processEvents()
                self.nav.tree.doItemsLayout()
                for row in range(self.nav.model.rowCount()):
                    parent = self.nav.model.item(row)
                    for item in [parent, *(parent.child(i) for i in range(parent.rowCount()))]:
                        opt = self.option(item.index())
                        rect = self.nav.tree.itemDelegate().text_rect(opt)
                        bounds = QFontMetrics(opt.font).boundingRect(rect, self.nav.tree.itemDelegate().text_flags, opt.text)
                        with self.subTest(theme=theme, width=width, text=opt.text):
                            self.assertGreaterEqual(rect.height(), bounds.height())
                            self.assertGreaterEqual(rect.width(), bounds.width())
                            self.assertGreaterEqual(opt.rect.height(), QFontMetrics(opt.font).height() + 16)
                            self.assertTrue(QFontMetrics(opt.font).inFontUcs4(ord('Π')))
                self.assertFalse(self.nav.tree.uniformRowHeights())

    def paint_item(self, index, focused):
        opt = self.option(index)
        opt.rect = QRect(0, 0, 217, 48)
        opt.state |= QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_HasFocus
        self.nav.tree.clearFocus()
        self.nav.tree.setFocus(Qt.FocusReason.TabFocusReason if focused else Qt.FocusReason.MouseFocusReason)
        self.app.processEvents()
        image = QImage(217, 48, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.nav.tree.itemDelegate().paint(painter, opt, index)
        painter.end()
        return image

    def test_rounded_selected_tile_and_keyboard_only_solid_focus(self):
        self.window.show()
        self.nav.tree.expandAll()
        self.nav.open('production')
        self.app.processEvents()
        index = self.nav.items['production'].index()
        for theme in ('light', 'dark'):
            self.theme.set_theme(theme, persist=False)
            opt = self.option(index)
            images = [self.paint_item(index, focus) for focus in (False, True)]
            base = opt.palette.color(QPalette.ColorRole.Base)
            background = opt.palette.color(QPalette.ColorRole.Highlight)
            self.assertEqual(base, images[0].pixelColor(1, 1))
            self.assertEqual(base, images[0].pixelColor(3, 2))
            self.assertEqual(background, images[0].pixelColor(200, 24))
            self.assertGreater(sum(images[0].pixelColor(x, y) != background
                for x in range(8, 180) for y in range(10, 38)), 50)
            self.assertNotEqual(images[0], images[1])
            self.assertEqual(images[0].copy(QRect(8, 8, 201, 32)), images[1].copy(QRect(8, 8, 201, 32)))
            self.assertEqual(images[0], self.paint_item(index, False))
        self.assertTrue(self.nav.tree.focusPolicy() & Qt.FocusPolicy.TabFocus)

    def test_selection_contrast_and_palette_consistent_for_all_groups_and_children(self):
        def luminance(color):
            values = [color.redF(), color.greenF(), color.blueF()]
            values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
            return sum(v * w for v, w in zip(values, (.2126, .7152, .0722)))
        self.window.show()
        self.nav.tree.expandAll()
        colors = []
        for theme in ('light', 'dark', 'light'):
            self.theme.set_theme(theme, persist=False)
            self.app.processEvents()
            expected = None
            for row in range(self.nav.model.rowCount()):
                parent = self.nav.model.item(row)
                for item in [parent, *(parent.child(i) for i in range(parent.rowCount()))]:
                    opt = self.option(item.index())
                    pair = (opt.palette.color(QPalette.ColorRole.Highlight),
                            opt.palette.color(QPalette.ColorRole.HighlightedText))
                    if expected is None:
                        expected = pair
                    self.assertEqual(expected, pair)
                    values = sorted(map(luminance, pair))
                    self.assertGreaterEqual((values[1] + .05) / (values[0] + .05), 4.5)
                    image = self.paint_item(item.index(), False)
                    self.assertEqual(pair[0], image.pixelColor(200, 24))
            colors.append(expected)
        self.assertNotEqual(colors[0], colors[1])
        self.assertEqual(colors[0], colors[2])

    def test_mouse_then_keyboard_then_focus_leave_changes_indicator_only(self):
        self.window.show()
        self.nav.tree.expandAll()
        self.nav.open('fields')
        self.app.processEvents()
        tree = self.nav.tree
        tree.clearFocus()
        tree.setFocus(Qt.FocusReason.TabFocusReason)
        self.app.processEvents()
        self.assertTrue(tree.keyboard_focus_visible())
        point = tree.visualRect(self.nav.items['fields'].index()).center()
        for kind, buttons in ((QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton),
                              (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton)):
            event = QMouseEvent(kind, QPointF(point), QPointF(tree.viewport().mapToGlobal(point)),
                               Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(tree.viewport(), event)
        self.assertEqual(2, self.window._current_page_index())
        self.assertFalse(tree.keyboard_focus_visible())
        self.app.sendEvent(tree, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier))
        self.assertTrue(tree.keyboard_focus_visible())
        self.assertEqual('products', tree.currentIndex().data(Qt.ItemDataRole.UserRole))
        tree.clearFocus()
        self.assertFalse(tree.keyboard_focus_visible())
        self.assertEqual('products', tree.currentIndex().data(Qt.ItemDataRole.UserRole))

    def test_nearby_irrigation_header_and_selector_have_measured_space(self):
        self.window.show()
        self.nav.open('activity')
        for theme in ('light', 'dark'):
            self.theme.set_theme(theme, persist=False)
            self.window.resize(1024, 768)
            self.app.processEvents()
            self.assertEqual(12, self.window._current_page_index())
            self.assertTrue(self.nav.header.isVisible())
            self.assertGreaterEqual(self.nav.selector.width(), self.nav.selector.minimumSizeHint().width())
            page = self.window.pages[12][1].resolved_page()
            title = page.findChild(type(self.nav.selector_label), 'pageTitle')
            self.assertIsNotNone(title)
            content = title.contentsRect()
            self.assertGreaterEqual(content.height(), title.fontMetrics().height())
            self.assertGreaterEqual(content.width(), title.fontMetrics().horizontalAdvance(title.text()))

    def test_narrow_view_and_larger_font_wrap_without_eliding_or_clipping(self):
        self.window.show()
        self.nav.tree.setFixedWidth(180)
        self.nav.tree.setStyleSheet(self.nav.tree.styleSheet() + 'QTreeView#farmNavigation { font-size:22px; }')
        self.nav.tree.expandAll()
        self.app.processEvents()
        self.nav.tree.doItemsLayout()
        opt = self.option(self.nav.items['calendar'].index())
        rect = self.nav.tree.itemDelegate().text_rect(opt)
        metrics = QFontMetrics(opt.font)
        bounds = metrics.boundingRect(rect, self.nav.tree.itemDelegate().text_flags, opt.text)
        self.assertGreater(opt.rect.height(), metrics.height() + 16)
        self.assertGreaterEqual(rect.height(), bounds.height())
        self.assertGreaterEqual(rect.width(), bounds.width())
        self.assertEqual('Πρόγραμμα εργασιών', opt.text)
