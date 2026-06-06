#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import platform

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox
)

from qfluentwidgets import (
    ScrollArea, CardWidget, TitleLabel, SubtitleLabel, BodyLabel, StrongBodyLabel,
    PushButton, LineEdit, FluentIcon, InfoBar, TransparentToolButton,
    SettingCardGroup, SettingCard
)

from src.ui.gpu_widgets import setup_smooth_scroll
from src.core.database import get_download_history
from src.utils.helpers import format_size, format_duration


class _HistoryLoader(QThread):
    loaded = pyqtSignal(list, dict)

    def __init__(self, query: str = ""):
        super().__init__()
        self.query = query

    def run(self):
        db = get_download_history()
        if self.query:
            rows = db.search_downloads(self.query, limit=100)
        else:
            rows = db.get_all_downloads(limit=200)
        stats = db.get_statistics()
        self.loaded.emit(rows, stats)


class HistoryItemCard(CardWidget):
    delete_requested = pyqtSignal(int)
    open_requested = pyqtSignal(str)

    def __init__(self, row: dict, parent=None):
        super().__init__(parent)
        self.row_id = row.get('id', 0)
        self.file_path = row.get('file_path', '')
        self.setFixedHeight(80)

        h = QHBoxLayout(self)
        h.setContentsMargins(20, 12, 20, 12)
        h.setSpacing(16)

        # Tür ikonu
        is_audio = (row.get('format_type', '') == 'audio')
        icon = FluentIcon.MUSIC if is_audio else FluentIcon.VIDEO
        from qfluentwidgets import IconWidget
        icon_w = IconWidget(icon, self)
        icon_w.setFixedSize(32, 32)
        h.addWidget(icon_w)

        # Bilgi
        info_v = QVBoxLayout()
        info_v.setSpacing(2)

        title = row.get('title') or os.path.basename(row.get('file_path', '')) or row.get('url', '')
        self.title_lbl = StrongBodyLabel(title[:80], self)
        channel = row.get('channel', '')
        date = str(row.get('download_date', ''))[:16]
        size = format_size(row.get('file_size') or 0)
        dur = format_duration(row.get('duration') or 0)
        meta = f"{channel}  •  {date}  •  {size}"
        if dur and dur != "Bilinmiyor" and dur != "00:00":
            meta += f"  •  {dur}"
        self.meta_lbl = BodyLabel(meta, self)
        self.meta_lbl.setStyleSheet("color: gray; font-size: 11px;")

        info_v.addWidget(self.title_lbl)
        info_v.addWidget(self.meta_lbl)
        h.addLayout(info_v)
        h.addStretch()

        # Durum rozeti
        status = row.get('status', 'completed')
        status_color = "#00cc6a" if status == 'completed' else "#ff6b6b"
        status_lbl = BodyLabel(status, self)
        status_lbl.setStyleSheet(f"color: {status_color}; font-size: 11px;")
        h.addWidget(status_lbl)

        # Eylem butonları
        if self.file_path and os.path.exists(self.file_path):
            open_btn = TransparentToolButton(FluentIcon.PLAY, self)
            open_btn.setToolTip("Dosyayı Aç")
            open_btn.clicked.connect(lambda: self.open_requested.emit(self.file_path))
            h.addWidget(open_btn)

            folder_btn = TransparentToolButton(FluentIcon.FOLDER, self)
            folder_btn.setToolTip("Klasörü Aç")
            folder_btn.clicked.connect(self._open_folder)
            h.addWidget(folder_btn)

        del_btn = TransparentToolButton(FluentIcon.DELETE, self)
        del_btn.setToolTip("Geçmişten Sil")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.row_id))
        h.addWidget(del_btn)

    def _open_folder(self):
        if self.file_path:
            folder = os.path.dirname(self.file_path) if os.path.isfile(self.file_path) else self.file_path
            if platform.system() == 'Windows' and os.path.exists(folder):
                os.startfile(folder)


class HistoryInterface(ScrollArea):
    """İndirme geçmişi sayfası"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("historyInterface")
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.view.setObjectName("historyView")
        self.setStyleSheet("ScrollArea{background: transparent; border: none;}")
        self.view.setStyleSheet("QWidget#historyView{background: transparent;}")
        setup_smooth_scroll(self, enable_kinetic=True)

        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setContentsMargins(36, 36, 36, 36)
        self.v_layout.setSpacing(20)

        # Başlık + butonlar
        header = QHBoxLayout()
        self.title = TitleLabel("İndirme Geçmişi", self.view)
        header.addWidget(self.title)
        header.addStretch()

        self.refresh_btn = PushButton(FluentIcon.SYNC, "Yenile", self.view)
        self.refresh_btn.clicked.connect(self.load_history)
        header.addWidget(self.refresh_btn)

        self.clear_btn = PushButton(FluentIcon.DELETE, "Tümünü Temizle", self.view)
        self.clear_btn.clicked.connect(self.clear_all)
        header.addWidget(self.clear_btn)
        self.v_layout.addLayout(header)

        # Arama kutusu
        search_row = QHBoxLayout()
        self.search_input = LineEdit(self.view)
        self.search_input.setPlaceholderText("Başlık veya kanal ara...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.search_input)
        self.v_layout.addLayout(search_row)

        # İstatistik kartı
        self.stats_card = CardWidget(self.view)
        self.stats_layout = QHBoxLayout(self.stats_card)
        self.stats_layout.setContentsMargins(20, 16, 20, 16)
        self.stat_total = self._stat_widget("Toplam", "0")
        self.stat_today = self._stat_widget("Bugün", "0")
        self.stat_month = self._stat_widget("Bu Ay", "0")
        self.stat_size = self._stat_widget("Toplam Boyut", "0 B")
        for w in [self.stat_total, self.stat_today, self.stat_month, self.stat_size]:
            self.stats_layout.addWidget(w)
            self.stats_layout.addStretch()
        self.v_layout.addWidget(self.stats_card)

        # Liste alanı
        self.list_widget = QWidget(self.view)
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setSpacing(8)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.v_layout.addWidget(self.list_widget)
        self.v_layout.addStretch()

        self._loader = None
        self._search_timer = None
        from PyQt6.QtCore import QTimer
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(400)
        self._search_timer.timeout.connect(self._do_search)

        self.is_loaded = False

    def _stat_widget(self, label: str, value: str) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(4)
        v.setContentsMargins(0, 0, 0, 0)
        lbl = BodyLabel(label)
        lbl.setStyleSheet("color: gray; font-size: 11px;")
        val = StrongBodyLabel(value)
        val.setObjectName(f"stat_{label}")
        v.addWidget(lbl)
        v.addWidget(val)
        return w

    def _update_stat(self, label: str, value: str):
        w = self.stats_card.findChild(StrongBodyLabel, f"stat_{label}")
        if w:
            w.setText(value)

    def showEvent(self, event):
        if not self.is_loaded:
            self.load_history()
            self.is_loaded = True
        super().showEvent(event)

    def _on_search_changed(self, text):
        self._search_timer.start()

    def _do_search(self):
        self.load_history(query=self.search_input.text().strip())

    def load_history(self, query: str = ""):
        self._loader = _HistoryLoader(query)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()

    def _on_loaded(self, rows: list, stats: dict):
        # İstatistikleri güncelle
        self._update_stat("Toplam", str(stats.get('total_downloads', 0)))
        self._update_stat("Bugün", str(stats.get('today', 0)))
        self._update_stat("Bu Ay", str(stats.get('this_month', 0)))
        self._update_stat("Toplam Boyut", format_size(stats.get('total_size_bytes', 0)))

        # Listeyi temizle
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not rows:
            empty = BodyLabel("Henüz indirme geçmişi yok.", self.list_widget)
            empty.setStyleSheet("color: gray;")
            self.list_layout.addWidget(empty)
            return

        for row in rows:
            card = HistoryItemCard(row, self.list_widget)
            card.delete_requested.connect(self._delete_row)
            card.open_requested.connect(self._open_file)
            self.list_layout.addWidget(card)

    def _delete_row(self, row_id: int):
        reply = QMessageBox.question(
            self, "Sil", "Bu kaydı geçmişten silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            get_download_history().delete_download(row_id)
            self.load_history(self.search_input.text().strip())

    def _open_file(self, path: str):
        if platform.system() == 'Windows' and os.path.exists(path):
            os.startfile(path)

    def clear_all(self):
        reply = QMessageBox.question(
            self, "Tüm Geçmişi Temizle",
            "Tüm indirme geçmişini silmek istediğinize emin misiniz?\nBu işlem geri alınamaz.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            get_download_history().clear_history()
            self.load_history()
            InfoBar.success(title="Temizlendi", content="Geçmiş temizlendi.", duration=3000, parent=self)
