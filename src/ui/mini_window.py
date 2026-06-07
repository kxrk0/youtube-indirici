#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mini Yüzen Pencere — aktif indirmeleri küçük, her zaman üstte bir widget'ta gösterir.
Ana pencere kapalıyken bile görünür.
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizeGrip, QApplication
)


class MiniProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self._value = 0

    def setValue(self, v: int):
        self._value = max(0, min(100, v))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        # Background
        p.setBrush(QBrush(QColor(60, 60, 60)))
        p.drawRoundedRect(self.rect(), 2, 2)
        # Fill
        if self._value > 0:
            fill_w = int(self.width() * self._value / 100)
            p.setBrush(QBrush(QColor(0, 120, 212)))
            from PyQt6.QtCore import QRect
            p.drawRoundedRect(QRect(0, 0, fill_w, self.height()), 2, 2)
        p.end()


class MiniDownloadRow(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(3)

        title_lbl = QLabel(title[:42] + ('…' if len(title) > 42 else ''), self)
        title_lbl.setStyleSheet("color:#ddd; font-size:11px;")
        layout.addWidget(title_lbl)

        self._bar = MiniProgressBar(self)
        layout.addWidget(self._bar)

        self._status = QLabel("Bekliyor...", self)
        self._status.setStyleSheet("color:#888; font-size:10px;")
        layout.addWidget(self._status)

    def update_progress(self, pct: int, status_text: str = ''):
        self._bar.setValue(pct)
        if status_text:
            self._status.setText(status_text[:60])


class MiniWindow(QWidget):
    """Her zaman üstte yüzen mini indirme widget'ı."""
    close_requested = pyqtSignal()

    _DRAG_OFFSET = None

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool |
                          Qt.WindowType.FramelessWindowHint |
                          Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(300)
        self.setMaximumWidth(340)

        self._rows: dict[str, MiniDownloadRow] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Container with rounded corners styling
        self._container = QWidget(self)
        self._container.setStyleSheet("""
            QWidget {
                background: rgba(20, 20, 30, 220);
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.08);
            }
        """)
        outer.addWidget(self._container)

        inner = QVBoxLayout(self._container)
        inner.setContentsMargins(12, 8, 12, 10)
        inner.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        self._title_lbl = QLabel("⬇ İndiriliyor", self._container)
        self._title_lbl.setStyleSheet("color:#0078d4; font-size:12px; font-weight:600; background:transparent; border:none;")
        hdr.addWidget(self._title_lbl)
        hdr.addStretch()

        self._close_btn = QPushButton("✕", self._container)
        self._close_btn.setFixedSize(18, 18)
        self._close_btn.setStyleSheet("QPushButton{background:transparent;color:#888;border:none;font-size:11px;}"
                                       "QPushButton:hover{color:#fff;}")
        self._close_btn.clicked.connect(self.hide)
        hdr.addWidget(self._close_btn)
        inner.addLayout(hdr)

        # Rows container
        self._rows_widget = QWidget(self._container)
        self._rows_widget.setStyleSheet("background:transparent; border:none;")
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(4)
        inner.addWidget(self._rows_widget)

        self._empty_lbl = QLabel("Aktif indirme yok.", self._container)
        self._empty_lbl.setStyleSheet("color:#555; font-size:11px; background:transparent; border:none;")
        inner.addWidget(self._empty_lbl)

        # Position: bottom-right
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - 360, screen.bottom() - 200)

    # ── Drag support ──────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._DRAG_OFFSET = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._DRAG_OFFSET:
            self.move(event.globalPosition().toPoint() - self._DRAG_OFFSET)

    # ── Public API ────────────────────────────────────────────────────────────
    def add_or_update(self, key: str, title: str, pct: int, status: str = ''):
        if key not in self._rows:
            row = MiniDownloadRow(title, self._rows_widget)
            self._rows_layout.addWidget(row)
            self._rows[key] = row
        self._rows[key].update_progress(pct, status)
        self._empty_lbl.setVisible(len(self._rows) == 0)
        self._title_lbl.setText(f"⬇ {len(self._rows)} İndiriliyor")
        if not self.isVisible():
            self.show()

    def remove(self, key: str):
        row = self._rows.pop(key, None)
        if row:
            row.deleteLater()
        self._empty_lbl.setVisible(len(self._rows) == 0)
        if len(self._rows) == 0:
            self._title_lbl.setText("⬇ İndiriliyor")

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
