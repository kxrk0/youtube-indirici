#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import platform

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox, QMenu
)

from qfluentwidgets import (
    ScrollArea, CardWidget, TitleLabel, BodyLabel, PushButton,
    FluentIcon, TransparentToolButton, FlowLayout, InfoBar
)

from src.ui.gpu_widgets import setup_smooth_scroll
from src.ui.workers import ThumbnailWorker, FormatConverterWorker
from src.utils.helpers import get_os_download_dir


class LibraryItem(CardWidget):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.setFixedSize(200, 180)
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.v_layout.setSpacing(0)

        self.thumb_label = QLabel(self)
        self.thumb_label.setFixedSize(200, 112)
        self.thumb_label.setStyleSheet(
            "background-color: #202020; border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setPixmap(FluentIcon.VIDEO.icon().pixmap(48, 48))
        self.v_layout.addWidget(self.thumb_label)

        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(10, 5, 10, 10)

        self.name_label = BodyLabel(os.path.basename(path), self)
        self.name_label.setWordWrap(False)

        btn_layout = QHBoxLayout()
        self.open_btn = TransparentToolButton(FluentIcon.PLAY, self)
        self.open_btn.clicked.connect(self.open_file)
        self.folder_btn = TransparentToolButton(FluentIcon.FOLDER, self)
        self.folder_btn.clicked.connect(self.open_folder)
        self.delete_btn = TransparentToolButton(FluentIcon.DELETE, self)
        self.delete_btn.clicked.connect(self.delete_file)

        btn_layout.addStretch()
        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.folder_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()

        info_layout.addWidget(self.name_label)
        info_layout.addLayout(btn_layout)
        self.v_layout.addWidget(info_widget)

        self._converter_worker = None

    def set_thumbnail(self, image_path):
        if image_path == "AUDIO":
            self.thumb_label.setPixmap(FluentIcon.MUSIC.icon().pixmap(48, 48))
        elif os.path.exists(image_path):
            self.thumb_label.setPixmap(QPixmap(image_path))

    def contextMenuEvent(self, event):
        """Sağ tık menüsü - format dönüştürücü"""
        menu = QMenu(self)
        ext = os.path.splitext(self.path)[1].lower()

        if ext != '.mp3':
            act_mp3 = menu.addAction("MP3'e Dönüştür")
            act_mp3.triggered.connect(lambda: self._convert_to('mp3'))
        if ext != '.mp4':
            act_mp4 = menu.addAction("MP4'e Dönüştür")
            act_mp4.triggered.connect(lambda: self._convert_to('mp4'))
        if ext not in ('.mkv',):
            act_mkv = menu.addAction("MKV'ye Dönüştür (kopyala)")
            act_mkv.triggered.connect(lambda: self._convert_to('mkv'))

        menu.addSeparator()
        act_open = menu.addAction("Dosyayı Aç")
        act_open.triggered.connect(self.open_file)
        act_folder = menu.addAction("Klasörü Aç")
        act_folder.triggered.connect(self.open_folder)
        act_del = menu.addAction("Sil")
        act_del.triggered.connect(self.delete_file)

        menu.exec(event.globalPos())

    def _convert_to(self, fmt: str):
        if self._converter_worker and self._converter_worker.isRunning():
            InfoBar.warning(title="Uyarı", content="Dönüştürme devam ediyor...", duration=2000, parent=self.window())
            return
        self.name_label.setText("Dönüştürülüyor...")
        self._converter_worker = FormatConverterWorker(self.path, fmt)
        self._converter_worker.completed_signal.connect(self._on_conversion_done)
        self._converter_worker.start()

    def _on_conversion_done(self, success: bool, result: str):
        self.name_label.setText(os.path.basename(self.path))
        if success:
            InfoBar.success(
                title="Dönüştürme Tamamlandı",
                content=f"Kaydedildi: {os.path.basename(result)}",
                duration=4000, parent=self.window()
            )
        else:
            InfoBar.error(
                title="Dönüştürme Hatası",
                content=result[:100],
                duration=5000, parent=self.window()
            )

    def delete_file(self):
        reply = QMessageBox.question(
            self, "Sil", "Silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.exists(self.path):
                    os.remove(self.path)
                self.deleteLater()
            except Exception:
                pass

    def open_file(self):
        if platform.system() == 'Windows':
            os.startfile(self.path)

    def open_folder(self):
        folder = os.path.dirname(self.path)
        if platform.system() == 'Windows':
            os.startfile(folder)


class LibraryInterface(ScrollArea):
    """Kütüphane sayfası"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("libraryInterface")
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.view.setObjectName("libraryView")
        self.setStyleSheet("ScrollArea{background: transparent; border: none;}")
        self.view.setStyleSheet("QWidget#libraryView{background: transparent;}")
        setup_smooth_scroll(self, enable_kinetic=True)

        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setContentsMargins(30, 30, 30, 30)
        self.v_layout.setSpacing(20)

        header = QHBoxLayout()
        self.title = TitleLabel("Kütüphane", self.view)
        self.refresh_btn = PushButton(FluentIcon.SYNC, "Yenile", self.view)
        self.refresh_btn.setFixedWidth(100)
        self.refresh_btn.clicked.connect(self.load_files)
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.refresh_btn)
        self.v_layout.addLayout(header)

        self.flow_layout = FlowLayout()
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.setSpacing(20)
        self.v_layout.insertLayout(1, self.flow_layout)
        self.v_layout.addStretch()

        self.thumb_queue = []
        self.thumb_worker = ThumbnailWorker(self.thumb_queue)
        self.thumb_worker.thumbnail_ready.connect(self.on_thumbnail_ready)
        self.thumb_worker.start()
        self.library_items = {}
        self.is_loaded = False

    def showEvent(self, event):
        if not self.is_loaded:
            self.load_files()
            self.is_loaded = True
        super().showEvent(event)

    def load_files(self):
        self.library_items.clear()
        self.thumb_queue.clear()

        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.flow_layout.deleteLater()

        self.flow_layout = FlowLayout()
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.setSpacing(20)
        self.v_layout.insertLayout(1, self.flow_layout)

        download_dir = get_os_download_dir()
        exts = ('.mp4', '.mp3', '.webm', '.mkv')
        if os.path.exists(download_dir):
            files = sorted(
                [f for f in os.listdir(download_dir) if f.lower().endswith(exts)],
                key=lambda x: os.path.getmtime(os.path.join(download_dir, x)),
                reverse=True
            )
            for f in files:
                full_path = os.path.join(download_dir, f)
                item = LibraryItem(full_path, self.view)
                self.flow_layout.addWidget(item)
                self.library_items[full_path] = item
                self.thumb_queue.append(full_path)

    def on_thumbnail_ready(self, video_path, thumb_path):
        if video_path in self.library_items:
            self.library_items[video_path].set_thumbnail(thumb_path)
