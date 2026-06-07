#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QFont, QPen, QBrush
from PyQt6.QtWidgets import QSplashScreen, QApplication


class SplashScreen(QSplashScreen):
    """Uygulama açılışı için yükleme ekranı"""

    VERSION = "v2.3.0"
    WIDTH = 480
    HEIGHT = 300

    def __init__(self):
        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(self.WIDTH, self.HEIGHT)
        pixmap.fill(Qt.GlobalColor.transparent)
        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self._message = "Başlatılıyor..."
        self._render_pixmap()

    def _render_pixmap(self):
        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(self.WIDTH, self.HEIGHT)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Gradient arka plan
        grad = QLinearGradient(0, 0, 0, self.HEIGHT)
        grad.setColorAt(0, QColor("#1a1a2e"))
        grad.setColorAt(1, QColor("#16213e"))
        p.fillRect(0, 0, self.WIDTH, self.HEIGHT, QBrush(grad))

        # İnce border
        p.setPen(QPen(QColor("#0f3460"), 2))
        p.drawRoundedRect(1, 1, self.WIDTH - 2, self.HEIGHT - 2, 12, 12)

        # İkon — mavi daire + ok
        cx, cy, r = 240, 90, 44
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#0078D4")))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        p.setPen(QPen(QColor("white"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawLine(cx, cy - 18, cx, cy + 10)
        arrow_pts = [
            (cx - 14, cy - 2),
            (cx, cy + 16),
            (cx + 14, cy - 2),
        ]
        from PyQt6.QtGui import QPolygon
        from PyQt6.QtCore import QPoint
        poly = QPolygon([QPoint(x, y) for x, y in arrow_pts])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("white")))
        p.drawPolygon(poly)

        # Başlık
        title_font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        p.setFont(title_font)
        p.setPen(QPen(QColor("white")))
        p.drawText(QRect(0, 150, self.WIDTH, 36), Qt.AlignmentFlag.AlignHCenter, "YouTube İndirici")

        # Versiyon
        ver_font = QFont("Segoe UI", 10)
        p.setFont(ver_font)
        p.setPen(QPen(QColor("#888")))
        p.drawText(QRect(0, 186, self.WIDTH, 24), Qt.AlignmentFlag.AlignHCenter, self.VERSION)

        # Mesaj
        msg_font = QFont("Segoe UI", 9)
        p.setFont(msg_font)
        p.setPen(QPen(QColor("#aaa")))
        p.drawText(QRect(0, 250, self.WIDTH, 24), Qt.AlignmentFlag.AlignHCenter, self._message)

        p.end()
        self.setPixmap(pixmap)

    def set_message(self, msg: str):
        self._message = msg
        self._render_pixmap()
        QApplication.processEvents()

    def center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.move(sg.center().x() - self.WIDTH // 2, sg.center().y() - self.HEIGHT // 2)
