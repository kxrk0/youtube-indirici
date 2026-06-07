#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import platform

from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint
from PyQt6.QtGui import QColor, QPainter, QPen, QPainterPath, QPixmap, QDrag, QCursor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QLabel, QSizePolicy

from qfluentwidgets import (
    ScrollArea, CardWidget, TitleLabel, BodyLabel, StrongBodyLabel,
    ProgressBar, IconWidget, FluentIcon, TransparentToolButton,
)

from src.ui.gpu_widgets import setup_smooth_scroll
from src.utils.helpers import get_os_download_dir


class SpeedGraph(QWidget):
    """Mini hız sparkline grafiği"""
    MAX_POINTS = 40

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 36)
        self._speeds = []

    def add_speed(self, bps: float):
        self._speeds.append(max(0.0, float(bps or 0)))
        if len(self._speeds) > self.MAX_POINTS:
            self._speeds.pop(0)
        self.update()

    def reset(self):
        self._speeds.clear()
        self.update()

    def paintEvent(self, event):
        if len(self._speeds) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        max_v = max(self._speeds) or 1.0
        n = len(self._speeds)
        path = QPainterPath()
        for i, v in enumerate(self._speeds):
            x = i * w / (n - 1)
            y = h - 2 - (v / max_v) * (h - 4)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        painter.setPen(QPen(QColor("#0078D4"), 1.5))
        painter.drawPath(path)
        painter.end()


class DownloadItemCard(CardWidget):
    """İndirme kartı - iptal + sıralama desteği ile"""
    cancel_requested = pyqtSignal()
    move_up_requested   = pyqtSignal(object)  # emits self
    move_down_requested = pyqtSignal(object)  # emits self

    def __init__(self, title, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.download_task = None
        self.is_cancelled = False
        self.file_path = None
        self._is_active = False  # True once download starts — reorder disabled
        self.setFixedHeight(120)
        self.setAcceptDrops(False)

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(16, 12, 16, 12)
        h_layout.setSpacing(16)

        self.thumb_lbl = QLabel(self)
        self.thumb_lbl.setFixedSize(84, 48)
        self.thumb_lbl.setStyleSheet(
            "background-color: #1e1e1e; border-radius: 4px;"
        )
        self.thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_lbl.setScaledContents(False)
        h_layout.addWidget(self.thumb_lbl)

        self.icon_widget = IconWidget(FluentIcon.VIDEO, self)
        self.icon_widget.setFixedSize(24, 24)
        self.icon_widget.hide()
        h_layout.addWidget(self.icon_widget)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.title_lbl = StrongBodyLabel(title, self)
        self.status_lbl = BodyLabel("Hazırlanıyor...", self)
        self.status_lbl.setStyleSheet("color: gray; font-size: 12px;")
        info_layout.addWidget(self.title_lbl)
        info_layout.addWidget(self.status_lbl)
        h_layout.addLayout(info_layout)
        h_layout.addStretch(1)

        self.progress = ProgressBar(self)
        self.progress.setFixedWidth(180)
        h_layout.addWidget(self.progress)
        h_layout.addSpacing(8)

        self.speed_graph = SpeedGraph(self)
        h_layout.addWidget(self.speed_graph)
        h_layout.addSpacing(8)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        # Priority reorder buttons (hidden once active)
        self.up_btn = TransparentToolButton(FluentIcon.UP, self)
        self.up_btn.setToolTip("Yukarı Taşı")
        self.up_btn.setFixedSize(28, 28)
        self.up_btn.clicked.connect(lambda: self.move_up_requested.emit(self))
        btn_layout.addWidget(self.up_btn)

        self.down_btn = TransparentToolButton(FluentIcon.DOWN, self)
        self.down_btn.setToolTip("Aşağı Taşı")
        self.down_btn.setFixedSize(28, 28)
        self.down_btn.clicked.connect(lambda: self.move_down_requested.emit(self))
        btn_layout.addWidget(self.down_btn)

        self.open_folder_btn = TransparentToolButton(FluentIcon.FOLDER, self)
        self.open_folder_btn.clicked.connect(self.open_folder)
        self.open_folder_btn.setEnabled(False)

        self.play_btn = TransparentToolButton(FluentIcon.PLAY, self)
        self.play_btn.clicked.connect(self.open_file)
        self.play_btn.setEnabled(False)

        self.delete_btn = TransparentToolButton(FluentIcon.DELETE, self)
        self.delete_btn.clicked.connect(self.delete_item)
        self.delete_btn.hide()

        self.cancel_btn = TransparentToolButton(FluentIcon.CANCEL, self)
        self.cancel_btn.clicked.connect(self.cancel_download)
        self.cancel_btn.setToolTip("İndirmeyi İptal Et")

        btn_layout.addWidget(self.open_folder_btn)
        btn_layout.addWidget(self.play_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.cancel_btn)
        h_layout.addLayout(btn_layout)

    def set_download_task(self, task):
        self.download_task = task

    def cancel_download(self):
        if self.download_task:
            self.download_task.cancel()
            self.is_cancelled = True
            self.set_cancelled()
        self.cancel_requested.emit()

    def set_cancelled(self):
        self.progress.hide()
        self.speed_graph.hide()
        self.status_lbl.setText("İptal Edildi")
        self.status_lbl.setStyleSheet("color: #ff6b6b;")
        self.icon_widget.setIcon(FluentIcon.CANCEL)
        self.icon_widget.show()
        self.cancel_btn.hide()
        self.delete_btn.show()

    def mark_active(self):
        """Disable reorder once download begins."""
        self._is_active = True
        self.up_btn.hide()
        self.down_btn.hide()

    def update_progress(self, percent, speed, eta, speed_bps: float = 0):
        if self.is_cancelled:
            return
        if not self._is_active:
            self.mark_active()
        self.progress.setValue(percent)
        self.status_lbl.setText(f"{speed} • {eta} kaldı")
        if speed_bps > 0:
            self.speed_graph.add_speed(speed_bps)

    def set_finished(self, filepath=None):
        if self.is_cancelled:
            return
        self.progress.setValue(100)
        self.progress.hide()
        self.speed_graph.hide()
        self.status_lbl.setText("İndirme Tamamlandı")
        self.status_lbl.setStyleSheet("color: #00cc6a;")
        self.icon_widget.setIcon(FluentIcon.COMPLETED)
        self.icon_widget.show()
        self.cancel_btn.hide()
        self.delete_btn.show()
        self.open_folder_btn.setEnabled(True)
        self.play_btn.setEnabled(True)
        if filepath:
            # Gerçek dosyayı doğrula; post-process sonrası uzantı değişmiş olabilir
            if os.path.exists(filepath):
                self.file_path = filepath
            else:
                base = os.path.splitext(filepath)[0]
                for ext in ('.mp3', '.mp4', '.webm', '.mkv', '.m4a'):
                    candidate = base + ext
                    if os.path.exists(candidate):
                        self.file_path = candidate
                        break
                else:
                    self.file_path = filepath  # en azından klasörü bulabilelim

    def set_error(self, error_msg: str):
        self.progress.hide()
        self.speed_graph.hide()
        self.status_lbl.setText(f"Hata: {error_msg[:50]}...")
        self.status_lbl.setStyleSheet("color: #ff6b6b;")
        self.icon_widget.setIcon(FluentIcon.INFO)
        self.icon_widget.show()
        self.cancel_btn.hide()
        self.delete_btn.show()

    def delete_item(self):
        reply = QMessageBox.question(
            self, "Sil", "Silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.file_path and os.path.isfile(self.file_path):
                try:
                    os.remove(self.file_path)
                except Exception:
                    pass
            self.deleteLater()

    def open_folder(self):
        path = self.file_path or get_os_download_dir()
        # Dosya yoksa (örn. geçici webm silindi) → indirme klasörünü aç
        if os.path.isfile(path):
            path = os.path.dirname(path)
        elif not os.path.isdir(path):
            path = get_os_download_dir()
        if platform.system() == 'Windows':
            try:
                os.startfile(path)
            except Exception:
                os.startfile(get_os_download_dir())

    def open_file(self):
        if not self.file_path:
            return
        target = self.file_path
        # Uzantı farklı olabilir (webm→mp3), aynı base ile ara
        if not os.path.exists(target):
            base = os.path.splitext(target)[0]
            for ext in ('.mp3', '.mp4', '.webm', '.mkv', '.m4a'):
                candidate = base + ext
                if os.path.exists(candidate):
                    target = candidate
                    self.file_path = candidate  # güncelle
                    break
        if os.path.exists(target) and platform.system() == 'Windows':
            try:
                os.startfile(target)
            except Exception:
                pass


    def set_thumbnail_url(self, url: str):
        if not url:
            return
        from src.ui.workers import ThumbnailUrlWorker
        self._thumb_worker = ThumbnailUrlWorker(url)
        self._thumb_worker.loaded.connect(self._on_thumb_data)
        self._thumb_worker.start()

    def _on_thumb_data(self, data: bytes):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                84, 48,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.thumb_lbl.setPixmap(scaled)


class QueueInterface(ScrollArea):
    """İndirme kuyruğu sayfası"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("queueInterface")
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.view.setObjectName("queueView")
        self.setStyleSheet("ScrollArea{background: transparent; border: none;}")
        self.view.setStyleSheet("QWidget#queueView{background: transparent;}")
        setup_smooth_scroll(self, enable_kinetic=True)

        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setContentsMargins(36, 36, 36, 36)
        self.v_layout.setSpacing(20)

        self.title = TitleLabel("İndirme Kuyruğu", self.view)
        self.v_layout.addWidget(self.title)

        self.list_layout = QVBoxLayout()
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setSpacing(12)
        self.v_layout.addLayout(self.list_layout)
        self.v_layout.addStretch()

    def add_download_item(self, title, url) -> DownloadItemCard:
        item = DownloadItemCard(title, url, self.view)
        item.move_up_requested.connect(self._move_card_up)
        item.move_down_requested.connect(self._move_card_down)
        self.list_layout.insertWidget(0, item)
        return item

    def _move_card_up(self, card: DownloadItemCard):
        idx = self.list_layout.indexOf(card)
        if idx > 0:
            self.list_layout.removeWidget(card)
            self.list_layout.insertWidget(idx - 1, card)

    def _move_card_down(self, card: DownloadItemCard):
        idx = self.list_layout.indexOf(card)
        count = self.list_layout.count()
        if idx < count - 1:
            self.list_layout.removeWidget(card)
            self.list_layout.insertWidget(idx + 1, card)
