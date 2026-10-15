from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .language import tr


class BarChartWidget(QWidget):
    """Simple dependency-free bar chart for Fieltra."""

    def __init__(
        self,
        title: str,
        unit: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.labels: list[str] = []
        self.values: list[float] = []

        self.setMinimumHeight(260)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

    def set_data(self, labels: list[str], values: list[float]) -> None:
        self.labels = labels
        self.values = values
        self.update()

    def translated_title(self) -> str:
        return tr(self.title)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        palette = self.palette()
        background = palette.color(QPalette.ColorRole.Base)
        text = palette.color(QPalette.ColorRole.Text)
        muted = palette.color(QPalette.ColorRole.PlaceholderText)
        grid = QColor(
            "#3A454C" if background.lightness() < 128 else "#E5E9E6"
        )
        bar = QColor("#52745f")
        positive = QColor("#52745f")
        negative = QColor("#8a4d4d")

        painter.fillRect(self.rect(), background)

        title_font = QFont("Segoe UI", 11)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(text)
        painter.drawText(
            QRectF(14, 10, width - 28, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.translated_title(),
        )

        if not self.labels or not self.values:
            painter.setFont(QFont("Segoe UI", 10))
            painter.setPen(muted)
            painter.drawText(
                QRectF(0, 45, width, height - 45),
                Qt.AlignmentFlag.AlignCenter,
                tr("Δεν υπάρχουν δεδομένα"),
            )
            return

        chart_left = 58
        chart_right = width - 18
        chart_top = 48
        chart_bottom = height - 42

        chart_width = max(1, chart_right - chart_left)
        chart_height = max(1, chart_bottom - chart_top)

        maximum = max(max(self.values), 0.0)
        minimum = min(min(self.values), 0.0)

        all_zero = all(abs(value) < 1e-12 for value in self.values)
        if all_zero:
            maximum = 1.0
            minimum = 0.0

        span = maximum - minimum
        if span <= 0:
            span = 1.0

        zero_y = chart_top + (maximum / span) * chart_height

        painter.setPen(QPen(grid, 1))
        if all_zero:
            y = chart_bottom
            painter.drawLine(chart_left, int(y), chart_right, int(y))
            painter.setPen(muted)
            painter.setFont(QFont("Segoe UI", 8))
            label = "0.0"
            if self.unit:
                label += f" {self.unit}"
            painter.drawText(
                QRectF(2, y - 9, chart_left - 8, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
        else:
            for i in range(5):
                y = chart_top + (chart_height * i / 4)
                painter.drawLine(chart_left, int(y), chart_right, int(y))

                value = maximum - (span * i / 4)
                painter.setPen(muted)
                painter.setFont(QFont("Segoe UI", 8))
                label = f"{value:.1f}"
                if self.unit:
                    label += f" {self.unit}"
                painter.drawText(
                    QRectF(2, y - 9, chart_left - 8, 18),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    label,
                )
                painter.setPen(QPen(grid, 1))

        painter.setPen(QPen(muted, 1))
        painter.drawLine(
            chart_left,
            int(zero_y),
            chart_right,
            int(zero_y),
        )

        count = len(self.values)
        slot = chart_width / max(count, 1)
        bar_width = max(12.0, min(48.0, slot * 0.58))

        label_font = QFont("Segoe UI", 8)
        value_font = QFont("Segoe UI", 8)
        value_font.setBold(True)

        for index, (label, value) in enumerate(zip(self.labels, self.values)):
            center_x = chart_left + slot * (index + 0.5)

            value_y = chart_top + ((maximum - value) / span) * chart_height

            if value >= 0:
                rect_top = value_y
                rect_bottom = zero_y
                current_color = positive if minimum < 0 else bar
            else:
                rect_top = zero_y
                rect_bottom = value_y
                current_color = negative

            rect_height = max(1.0, abs(rect_bottom - rect_top))
            bar_rect = QRectF(
                center_x - bar_width / 2,
                min(rect_top, rect_bottom),
                bar_width,
                rect_height,
            )

            painter.fillRect(bar_rect, current_color)

            painter.setFont(value_font)
            painter.setPen(text)
            value_text = f"{value:.1f}"
            if self.unit:
                value_text += f" {self.unit}"

            value_text_y = (
                bar_rect.top() - 20
                if value >= 0
                else bar_rect.bottom() + 3
            )
            painter.drawText(
                QRectF(
                    center_x - slot / 2,
                    value_text_y,
                    slot,
                    18,
                ),
                Qt.AlignmentFlag.AlignCenter,
                value_text,
            )

            painter.setFont(label_font)
            painter.setPen(muted)
            painter.drawText(
                QRectF(
                    center_x - slot / 2,
                    chart_bottom + 6,
                    slot,
                    22,
                ),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )
