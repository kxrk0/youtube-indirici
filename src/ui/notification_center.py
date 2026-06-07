#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bildirim Merkezi — son 30 bildirimi saklar, sağ kenar panelinde gösterir.
"""

from __future__ import annotations
import time
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton
)
from qfluentwidgets import CardWidget, BodyLabel, StrongBodyLabel, FluentIcon, TransparentToolButton

MAX_NOTIFICATIONS = 30


class NotificationItem(QFrame):
    def __init__(self, level: str, title: str, body: str, ts: float, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        colors = {'success': '#00cc6a', 'error': '#ff4444', 'warning': '#f0ad4e', 'info': '#0078d4'}
        color  = colors.get(level, '#888')
        icons  = {'success': '✅', 'error': '❌', 'warning': '⚠', 'info': 'ℹ'}
        icon   = icons.get(level, '•')

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        dot = QLabel(icon, self)
        dot.setStyleSheet(f"color:{color}; font-size:13px;")
        dot.setFixedWidth(18)
        layout.addWidget(dot)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        t_lbl = QLabel(title, self)
        t_lbl.setStyleSheet("font-weight:600; font-size:12px; color:#ddd;")
        text_col.addWidget(t_lbl)
        if body:
            b_lbl = QLabel(body[:80], self)
            b_lbl.setStyleSheet("font-size:11px; color:#999;")
            b_lbl.setWordWrap(True)
            text_col.addWidget(b_lbl)
        layout.addLayout(text_col, 1)

        time_str = time.strftime('%H:%M', time.localtime(ts))
        time_lbl = QLabel(time_str, self)
        time_lbl.setStyleSheet("font-size:10px; color:#555;")
        layout.addWidget(time_lbl)

        self.setStyleSheet("QFrame{background: rgba(255,255,255,0.04); border-radius:6px;}")


class NotificationPanel(QWidget):
    """Sağ kenar bildirimi paneli — toggle ile açılır/kapanır."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool |
                          Qt.WindowType.FramelessWindowHint |
                          Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(320)
        self._notifications: list[dict] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card = CardWidget(self)
        self._card.setStyleSheet("CardWidget{background:rgba(22,22,35,230); border-radius:10px;}")
        outer.addWidget(self._card)

        inner = QVBoxLayout(self._card)
        inner.setContentsMargins(14, 12, 14, 14)
        inner.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        title = StrongBodyLabel("Bildirim Merkezi")
        hdr.addWidget(title)
        hdr.addStretch()
        self._count_lbl = BodyLabel("0")
        self._count_lbl.setStyleSheet("color:#888; font-size:11px;")
        hdr.addWidget(self._count_lbl)
        clear_btn = TransparentToolButton(FluentIcon.DELETE, self._card)
        clear_btn.setToolTip("Temizle")
        clear_btn.clicked.connect(self.clear)
        hdr.addWidget(clear_btn)
        inner.addLayout(hdr)

        # Scroll area
        scroll = QScrollArea(self._card)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(480)
        scroll.setStyleSheet("QScrollArea{background:transparent; border:none;}")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background:transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_widget)
        inner.addWidget(scroll)

        self._empty_lbl = BodyLabel("Henüz bildirim yok.")
        self._empty_lbl.setStyleSheet("color:#555; font-size:11px;")
        inner.addWidget(self._empty_lbl)

        self.hide()

    def push(self, level: str, title: str, body: str = ''):
        entry = {'level': level, 'title': title, 'body': body, 'ts': time.time()}
        self._notifications.insert(0, entry)
        if len(self._notifications) > MAX_NOTIFICATIONS:
            self._notifications.pop()
        self._rebuild()

    def clear(self):
        self._notifications.clear()
        self._rebuild()

    def _rebuild(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for n in self._notifications:
            item = NotificationItem(n['level'], n['title'], n['body'], n['ts'], self._list_widget)
            self._list_layout.addWidget(item)
        self._count_lbl.setText(str(len(self._notifications)))
        self._empty_lbl.setVisible(len(self._notifications) == 0)

    def toggle(self, anchor_pos=None):
        if self.isVisible():
            self.hide()
        else:
            if anchor_pos:
                self.move(max(0, anchor_pos.x() - self.width()), anchor_pos.y())
            self.show()
            self.raise_()

    def unread_count(self) -> int:
        return len(self._notifications)
