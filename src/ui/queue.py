#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import platform

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QMessageBox

from qfluentwidgets import (
    ScrollArea, CardWidget, TitleLabel, BodyLabel, StrongBodyLabel,
    ProgressBar, IconWidget, FluentIcon, TransparentToolButton,
)

from src.ui.gpu_widgets import setup_smooth_scroll
from src.utils.helpers import get_os_download_dir


class DownloadItemCard(CardWidget):
    """İndirme kartı - iptal desteği ile"""
    cancel_requested = pyqtSignal()

    def __init__(self, title, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.download_task = None
        self.is_cancelled = False
        self.file_path = None
        self.setFixedHeight(100)

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(24, 16, 24, 16)
        h_layout.setSpacing(24)

        self.icon_widget = IconWidget(FluentIcon.VIDEO, self)
        self.icon_widget.setFixedSize(40, 40)
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
        self.progress.setFixedWidth(220)
        h_layout.addWidget(self.progress)
        h_layout.addSpacing(16)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

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
        self.status_lbl.setText("İptal Edildi")
        self.status_lbl.setStyleSheet("color: #ff6b6b;")
        self.icon_widget.setIcon(FluentIcon.CANCEL)
        self.cancel_btn.hide()
        self.delete_btn.show()

    def update_progress(self, percent, speed, eta):
        if self.is_cancelled:
            return
        self.progress.setValue(percent)
        self.status_lbl.setText(f"{speed} • {eta} kaldı")

    def set_finished(self, filepath=None):
        if self.is_cancelled:
            return
        self.progress.setValue(100)
        self.progress.hide()
        self.status_lbl.setText("İndirme Tamamlandı")
        self.status_lbl.setStyleSheet("color: #00cc6a;")
        self.icon_widget.setIcon(FluentIcon.COMPLETED)
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
        self.status_lbl.setText(f"Hata: {error_msg[:50]}...")
        self.status_lbl.setStyleSheet("color: #ff6b6b;")
        self.icon_widget.setIcon(FluentIcon.INFO)
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
        self.list_layout.insertWidget(0, item)
        return item
