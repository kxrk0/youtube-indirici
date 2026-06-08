#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv
import io
import os
import platform

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog, QScrollBar
)

from qfluentwidgets import (
    ScrollArea, SmoothScrollArea, CardWidget, TitleLabel, SubtitleLabel, BodyLabel, StrongBodyLabel,
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
    retry_requested = pyqtSignal(dict)   # emits full row dict for smart retry

    def __init__(self, row: dict, parent=None):
        super().__init__(parent)
        self.row_id = row.get('id', 0)
        self.file_path = row.get('file_path', '') or ''
        self._thumb_worker = None
        self.setFixedHeight(88)

        h = QHBoxLayout(self)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(14)

        # Thumbnail (80×45) veya fallback ikon
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtGui import QPixmap
        from qfluentwidgets import IconWidget

        is_audio = (row.get('format_type', '') == 'audio')
        thumb_url = row.get('thumbnail_url') or ''

        self.thumb_lbl = QLabel(self)
        self.thumb_lbl.setFixedSize(80, 45)
        self.thumb_lbl.setStyleSheet(
            "background:#2a2a2a; border-radius:4px;"
        )
        self.thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if thumb_url:
            from src.ui.workers import ThumbnailUrlWorker
            self._thumb_worker = ThumbnailUrlWorker(thumb_url)
            self._thumb_worker.loaded.connect(self._on_thumb_loaded)
            self._thumb_worker.start()
        else:
            # Ikon fallback
            icon = FluentIcon.MUSIC if is_audio else FluentIcon.VIDEO
            icon_w = IconWidget(icon, self.thumb_lbl)
            icon_w.setFixedSize(24, 24)
            icon_w.move(28, 10)

        h.addWidget(self.thumb_lbl)

        # Bilgi
        info_v = QVBoxLayout()
        info_v.setSpacing(2)

        title = (row.get('title') or
                 (os.path.splitext(os.path.basename(self.file_path))[0] if self.file_path else '') or
                 row.get('url', ''))
        self.title_lbl = StrongBodyLabel(title[:80], self)
        channel = row.get('channel') or ''  # None → ''
        date = str(row.get('download_date', ''))[:16]
        size = format_size(row.get('file_size') or 0)
        dur = format_duration(row.get('duration') or 0)
        meta_parts = []
        if channel:
            meta_parts.append(channel)
        meta_parts.append(date)
        meta_parts.append(size)
        if dur and dur not in ('Bilinmiyor', '00:00'):
            meta_parts.append(dur)
        self.meta_lbl = BodyLabel('  •  '.join(meta_parts), self)
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

        # Retry button — hata ve tamamlanan satırlar için
        if row.get('url'):
            retry_btn = TransparentToolButton(FluentIcon.SYNC, self)
            retry_btn.setToolTip("Tekrar İndir")
            _row_snap = dict(row)  # closure için kopyala
            retry_btn.clicked.connect(lambda: self.retry_requested.emit(_row_snap))
            h.addWidget(retry_btn)

        del_btn = TransparentToolButton(FluentIcon.DELETE, self)
        del_btn.setToolTip("Geçmişten Sil")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.row_id))
        h.addWidget(del_btn)

    def _on_thumb_loaded(self, data: bytes):
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import Qt as _Qt
        px = QPixmap()
        px.loadFromData(data)
        if not px.isNull():
            scaled = px.scaled(80, 45, _Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               _Qt.TransformationMode.SmoothTransformation)
            self.thumb_lbl.setPixmap(scaled)

    def _open_folder(self):
        if self.file_path:
            folder = os.path.dirname(self.file_path) if os.path.isfile(self.file_path) else self.file_path
            if platform.system() == 'Windows' and os.path.exists(folder):
                os.startfile(folder)


class HistoryInterface(SmoothScrollArea):
    """İndirme geçmişi sayfası"""
    retry_requested = pyqtSignal(dict)   # propagates card signal up to MainWindow

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("historyInterface")
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.view.setObjectName("historyView")
        self.setStyleSheet("ScrollArea{background: transparent; border: none;}")
        self.view.setStyleSheet("QWidget#historyView{background: transparent;}")
        setup_smooth_scroll(self, enable_kinetic=False)
        self.setScrollAnimation(Qt.Orientation.Vertical, 500)

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

        self.export_btn = PushButton(FluentIcon.SAVE, "CSV Dışa Aktar", self.view)
        self.export_btn.clicked.connect(self.export_csv)
        header.addWidget(self.export_btn)

        self.export_json_btn = PushButton(FluentIcon.DOCUMENT, "JSON Dışa Aktar", self.view)
        self.export_json_btn.clicked.connect(self.export_json)
        header.addWidget(self.export_json_btn)

        self.integrity_btn = PushButton(FluentIcon.SEARCH, "Bütünlük Kontrolü", self.view)
        self.integrity_btn.setToolTip("İndirilen dosyaların diskten hâlâ erişilebilir olup olmadığını kontrol eder")
        self.integrity_btn.clicked.connect(self._check_file_integrity)
        header.addWidget(self.integrity_btn)

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

        # Platform dağılımı kartı
        self.platform_card = CardWidget(self.view)
        self.platform_card_layout = QVBoxLayout(self.platform_card)
        self.platform_card_layout.setContentsMargins(20, 14, 20, 14)
        self.platform_card_layout.setSpacing(6)
        plat_header = BodyLabel("Platform Dağılımı", self.platform_card)
        plat_header.setStyleSheet("color: gray; font-size: 11px;")
        self.platform_card_layout.addWidget(plat_header)
        self._platform_bars_widget = QWidget(self.platform_card)
        self._platform_bars_layout = QVBoxLayout(self._platform_bars_widget)
        self._platform_bars_layout.setSpacing(4)
        self._platform_bars_layout.setContentsMargins(0, 0, 0, 0)
        self.platform_card_layout.addWidget(self._platform_bars_widget)
        self.v_layout.addWidget(self.platform_card)

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
        self._current_rows = []
        self._rendered_count = 0
        self._BATCH = 20  # İlk yüklemede ve her scroll genişlemesinde kaç kart eklenir
        # Scroll sona yaklaşınca daha fazla yükle
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

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
        query = self.search_input.text().strip().lower()
        if not self._current_rows:
            # Hiç veri yok — DB'den yükle
            self.load_history()
            return
        if not query:
            # Filtre temizlendi — tüm satırları göster
            self._re_render_rows(self._current_rows)
            return
        # In-memory filtre — DB çağrısı yok
        filtered = [
            r for r in self._current_rows
            if query in (r.get('title') or '').lower()
            or query in (r.get('channel') or '').lower()
            or query in (r.get('url') or '').lower()
        ]
        self._re_render_rows(filtered)

    def _re_render_rows(self, rows: list):
        """Mevcut satır listesini temizleyip yeniden render et."""
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not rows:
            empty = BodyLabel("Sonuç bulunamadı.", self.list_widget)
            empty.setStyleSheet("color: gray;")
            self.list_layout.addWidget(empty)
            self._rendered_count = 0
            return
        # Lazy render için geçici olarak _current_rows override et
        _saved = self._current_rows
        self._current_rows = rows
        self._rendered_count = 0
        self._render_next_batch()
        self._current_rows = _saved

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

        # Platform dağılımı güncelle
        try:
            breakdown = get_download_history().get_platform_breakdown()
            while self._platform_bars_layout.count():
                item = self._platform_bars_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            max_count = max((p['count'] for p in breakdown), default=1)
            for p in breakdown[:8]:
                row_w = QWidget()
                row_h = QHBoxLayout(row_w)
                row_h.setContentsMargins(0, 0, 0, 0)
                row_h.setSpacing(8)
                name_lbl = BodyLabel(p['platform'])
                name_lbl.setFixedWidth(110)
                bar_bg = QWidget()
                bar_bg.setFixedHeight(12)
                bar_bg.setStyleSheet("background:#333; border-radius:4px;")
                fill_pct = int(p['count'] / max_count * 100)
                bar_fill = QWidget(bar_bg)
                bar_fill.setFixedHeight(12)
                bar_fill.setStyleSheet("background:#0078d4; border-radius:4px;")
                bar_fill.setFixedWidth(max(4, int(fill_pct * 2)))
                count_lbl = BodyLabel(str(p['count']))
                count_lbl.setStyleSheet("color:#888; font-size:11px;")
                count_lbl.setFixedWidth(36)
                row_h.addWidget(name_lbl)
                row_h.addWidget(bar_bg, 1)
                row_h.addWidget(count_lbl)
                self._platform_bars_layout.addWidget(row_w)
        except Exception:
            pass

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

        self._current_rows = rows
        self._rendered_count = 0
        self._render_next_batch()

    def _render_next_batch(self):
        """Bir sonraki batch kadar kart oluştur — lazy load."""
        start = self._rendered_count
        end = min(start + self._BATCH, len(self._current_rows))
        for row in self._current_rows[start:end]:
            card = HistoryItemCard(row, self.list_widget)
            card.delete_requested.connect(self._delete_row)
            card.open_requested.connect(self._open_file)
            card.retry_requested.connect(self.retry_requested)
            self.list_layout.addWidget(card)
        self._rendered_count = end

    def _on_scroll(self, value: int):
        """Scroll sona yaklaşınca yeni batch yükle."""
        sb = self.verticalScrollBar()
        if sb.maximum() > 0 and value >= sb.maximum() - 200:
            if self._rendered_count < len(self._current_rows):
                self._render_next_batch()

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

    def export_csv(self):
        """Mevcut geçmişi CSV dosyasına aktar"""
        if not self._current_rows:
            InfoBar.warning(title="CSV", content="Dışa aktarılacak kayıt yok.", duration=3000, parent=self)
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV Kaydet", os.path.join(os.path.expanduser('~'), 'indirme_gecmisi.csv'),
            "CSV Dosyası (*.csv)"
        )
        if not path:
            return
        try:
            fields = ['id', 'title', 'channel', 'url', 'format_type',
                      'file_path', 'file_size', 'duration', 'status', 'download_date']
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(self._current_rows)
            InfoBar.success(title="CSV", content=f"Dışa aktarıldı: {os.path.basename(path)}", duration=4000, parent=self)
        except Exception as e:
            InfoBar.error(title="CSV Hatası", content=str(e)[:120], duration=5000, parent=self)

    def export_json(self):
        """Mevcut geçmişi JSON dosyasına aktar"""
        if not self._current_rows:
            InfoBar.warning(title="JSON", content="Dışa aktarılacak kayıt yok.", duration=3000, parent=self)
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "JSON Kaydet", os.path.join(os.path.expanduser('~'), 'indirme_gecmisi.json'),
            "JSON Dosyası (*.json)"
        )
        if not path:
            return
        try:
            import json
            fields = ['id', 'title', 'channel', 'url', 'format_type',
                      'file_path', 'file_size', 'duration', 'status', 'download_date']
            rows = [{k: row.get(k) for k in fields} for row in self._current_rows]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
            InfoBar.success(title="JSON", content=f"Dışa aktarıldı: {os.path.basename(path)}", duration=4000, parent=self)
        except Exception as e:
            InfoBar.error(title="JSON Hatası", content=str(e)[:120], duration=5000, parent=self)

    def _check_file_integrity(self):
        """Tamamlanan kayıtlardaki dosya yollarını diskten kontrol et."""
        if not self._current_rows:
            InfoBar.warning(title="Bütünlük", content="Kontrol edilecek kayıt yok.", duration=3000, parent=self)
            return
        missing = []
        for row in self._current_rows:
            fp = row.get('file_path', '')
            status = row.get('status', '')
            if status == 'completed' and fp and not os.path.exists(fp):
                missing.append(os.path.basename(fp) or fp)
        if missing:
            names = '\n'.join(missing[:10])
            extra = f'\n... ve {len(missing) - 10} dosya daha' if len(missing) > 10 else ''
            InfoBar.warning(
                title=f'Eksik Dosya ({len(missing)})',
                content=f'Şu dosyalar diskten silinmiş veya taşınmış:\n{names}{extra}',
                duration=8000, parent=self
            )
        else:
            InfoBar.success(
                title='Bütünlük Kontrolü',
                content='Tüm tamamlanan dosyalar diskten erişilebilir.',
                duration=4000, parent=self
            )

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
