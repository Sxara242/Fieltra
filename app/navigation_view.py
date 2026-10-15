"""Font-measured sidebar rows, independent of stylesheet item padding."""
from PySide6.QtCore import QEvent, QRectF, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPalette, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOption, QStyleOptionViewItem, QTreeView


class NavigationDelegate(QStyledItemDelegate):
    margin = 8
    gap = 8
    corner_radius = 5
    text_flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap

    def option(self, option, index):
        result = QStyleOptionViewItem(option)
        self.initStyleOption(result, index)
        return result

    def text_rect(self, option):
        rect = option.rect.adjusted(self.margin, self.margin, -self.margin, -self.margin)
        if not option.icon.isNull():
            rect.setLeft(rect.left() + option.decorationSize.width() + self.gap)
        return rect

    def sizeHint(self, option, index):
        opt = self.option(option, index)
        view = self.parent()
        depth, ancestor = 1, index.parent()
        while ancestor.isValid():
            depth += 1
            ancestor = ancestor.parent()
        width = max(1, view.viewport().width() - depth * view.indentation())
        icon_width = opt.decorationSize.width() + self.gap if not opt.icon.isNull() else 0
        metrics = QFontMetrics(opt.font)
        text = metrics.boundingRect(0, 0, max(1, width - 2 * self.margin - icon_width),
                                    10000, self.text_flags, opt.text)
        icon_height = opt.decorationSize.height() if not opt.icon.isNull() else 0
        return QSize(width, max(text.height(), metrics.height(), icon_height) + 2 * self.margin)

    def paint(self, painter, option, index):
        opt = self.option(option, index)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        hovered = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        base = opt.palette.color(QPalette.ColorRole.Base)
        background = opt.palette.color(QPalette.ColorRole.Highlight if selected else QPalette.ColorRole.Base)
        foreground = opt.palette.color(QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text)
        if hovered and not selected:
            background = opt.palette.color(QPalette.ColorRole.AlternateBase)
        painter.save()
        painter.setClipRect(opt.rect)
        painter.fillRect(opt.rect, base)
        tile = QRectF(opt.rect.adjusted(3, 2, -3, -2))
        if selected or hovered:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(tile, self.corner_radius, self.corner_radius)
        if not opt.icon.isNull():
            icon_rect = opt.rect.adjusted(self.margin, 0, 0, 0)
            icon_rect.setWidth(opt.decorationSize.width())
            icon_rect.setTop(opt.rect.center().y() - opt.decorationSize.height() // 2)
            icon_rect.setHeight(opt.decorationSize.height())
            opt.icon.paint(painter, icon_rect)
        painter.setFont(opt.font)
        painter.setPen(foreground)
        painter.drawText(self.text_rect(opt), self.text_flags, opt.text)
        # Input modality is independent of selection. Mouse focus has no ring;
        # keyboard focus gets a solid contrasting outline outside the text.
        if opt.state & QStyle.StateFlag.State_HasFocus and self.parent().keyboard_focus_visible():
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(foreground, 2, Qt.PenStyle.SolidLine))
            painter.drawRoundedRect(tile, self.corner_radius, self.corner_radius)
        painter.restore()


class NavigationTree(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._keyboard_focus = False
        self.setItemDelegate(NavigationDelegate(self))
        self.setUniformRowHeights(False)
        self.setVerticalScrollMode(QTreeView.ScrollMode.ScrollPerPixel)
        self.setAccessibleName("Πλοήγηση εφαρμογής")

    def keyboard_focus_visible(self):
        return self.hasFocus() and self._keyboard_focus

    def drawBranches(self, painter, rect, index):
        # The native view otherwise highlights the indentation gutter separately
        # from our inset tile. Keep it neutral and retain the native expand arrow.
        painter.fillRect(rect, self.palette().color(QPalette.ColorRole.Base))
        if not self.model().hasChildren(index):
            return
        option = QStyleOption()
        option.initFrom(self)
        option.rect = rect.adjusted(max(0, rect.width() - self.indentation()), 0, 0, 0)
        option.state &= ~(QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_HasFocus)
        option.state |= QStyle.StateFlag.State_Children | QStyle.StateFlag.State_Item
        if self.isExpanded(index):
            option.state |= QStyle.StateFlag.State_Open
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorBranch, option, painter, self)

    def focusInEvent(self, event):
        if event.reason() in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
                              Qt.FocusReason.ShortcutFocusReason):
            self._keyboard_focus = True
        elif event.reason() == Qt.FocusReason.MouseFocusReason:
            self._keyboard_focus = False
        super().focusInEvent(event)
        self.viewport().update()

    def keyPressEvent(self, event):
        if event.key() not in (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            self._keyboard_focus = True
            self.viewport().update()
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        self._keyboard_focus = False
        self.viewport().update()
        super().mousePressEvent(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.TouchBegin:
            self._keyboard_focus = False
            self.viewport().update()
        return super().viewportEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scheduleDelayedItemsLayout()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
            self.scheduleDelayedItemsLayout()
