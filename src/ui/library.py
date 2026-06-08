#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import platform

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox, QMenu, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit, QSizePolicy
)

from qfluentwidgets import (
    ScrollArea, SmoothScrollArea, CardWidget, TitleLabel, SubtitleLabel, BodyLabel, PushButton,
    FluentIcon, TransparentToolButton, FlowLayout, InfoBar,
    SearchLineEdit, ComboBox
)

from src.ui.gpu_widgets import setup_smooth_scroll
from src.ui.workers import ThumbnailWorker, FormatConverterWorker, WhisperWorker
from src.utils.helpers import get_os_download_dir


class LibraryItem(CardWidget):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.setFixedSize(220, 190)
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.v_layout.setSpacing(0)

        self.thumb_label = QLabel(self)
        self.thumb_label.setFixedSize(220, 124)
        self.thumb_label.setStyleSheet(
            "background-color: #1a1a1a; border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setScaledContents(False)  # Manuel scale — aspect ratio koru

        # Varsayılan ikon — uzantıya göre seç
        ext = os.path.splitext(path)[1].lower()
        default_icon = FluentIcon.MUSIC if ext in ('.mp3', '.m4a', '.flac') else FluentIcon.VIDEO
        self.thumb_label.setPixmap(default_icon.icon().pixmap(64, 64))
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
            self.thumb_label.setPixmap(FluentIcon.MUSIC.icon().pixmap(64, 64))
        elif image_path and image_path != "ERROR" and os.path.exists(image_path):
            w, h = self.thumb_label.width(), self.thumb_label.height()
            scaled = QPixmap(image_path).scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.thumb_label.setPixmap(scaled)

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
        act_preview = menu.addAction("▶ Önizle")
        act_preview.triggered.connect(self.show_preview)
        act_meta = menu.addAction("✏ Metadata Düzenle")
        act_meta.triggered.connect(self.show_metadata_editor)
        act_transcript = menu.addAction("🎙 Transkript Oluştur (Whisper)")
        act_transcript.triggered.connect(self.show_transcript_dialog)
        menu.addSeparator()
        act_open = menu.addAction("Dosyayı Aç")
        act_open.triggered.connect(self.open_file)
        act_folder = menu.addAction("Klasörü Aç")
        act_folder.triggered.connect(self.open_folder)
        act_del = menu.addAction("Sil")
        act_del.triggered.connect(self.delete_file)

        menu.exec(event.globalPos())

    def show_preview(self):
        """Yerleşik medya önizleme penceresi."""
        dialog = _MediaPreviewDialog(self.path, self.window())
        dialog.exec()

    def show_metadata_editor(self):
        """ID3/MP4 metadata editörü."""
        dialog = _MetadataEditorDialog(self.path, self.window())
        if dialog.exec():
            self.name_label.setText(os.path.basename(self.path))

    def show_transcript_dialog(self):
        """Whisper AI transkript dialogu."""
        dialog = _WhisperDialog(self.path, self.window())
        dialog.exec()

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


class _MediaPreviewDialog(QDialog):
    """Basit yerleşik medya önizleme (dosya adı + bilgi + aç butonu)."""

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.setWindowTitle("Medya Önizleme")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        # Thumbnail / ikon
        thumb = QLabel(self)
        thumb.setFixedSize(360, 202)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet("background:#1a1a1a; border-radius:6px;")
        ext = os.path.splitext(filepath)[1].lower()
        # Önce video thumbnail dene
        from src.utils.helpers import get_app_dir as _get_app_dir
        cache_dir = os.path.join(_get_app_dir(), 'cache', 'thumbnails')
        os.makedirs(cache_dir, exist_ok=True)
        import hashlib
        fhash = hashlib.md5(filepath.encode()).hexdigest()
        thumb_path = os.path.join(cache_dir, f"{fhash}.jpg")
        if os.path.exists(thumb_path):
            px = QPixmap(thumb_path).scaled(360, 202,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            thumb.setPixmap(px)
        elif ext in ('.mp3', '.m4a', '.ogg', '.opus'):
            from qfluentwidgets import FluentIcon
            thumb.setPixmap(FluentIcon.MUSIC.icon().pixmap(64, 64))
        else:
            from qfluentwidgets import FluentIcon
            thumb.setPixmap(FluentIcon.VIDEO.icon().pixmap(64, 64))
        layout.addWidget(thumb, alignment=Qt.AlignmentFlag.AlignCenter)

        # Dosya bilgisi
        name = BodyLabel(os.path.basename(filepath), self)
        name.setWordWrap(True)
        layout.addWidget(name)
        try:
            size = os.path.getsize(filepath)
            from src.utils.helpers import format_size
            info = BodyLabel(f"Boyut: {format_size(size)}  •  {ext.upper().lstrip('.')}", self)
        except Exception:
            info = BodyLabel(ext.upper().lstrip('.'), self)
        layout.addWidget(info)

        # Butonlar
        btn_box = QDialogButtonBox(self)
        open_btn = btn_box.addButton("Oynat / Aç", QDialogButtonBox.ButtonRole.ActionRole)
        open_btn.clicked.connect(self._open)
        close_btn = btn_box.addButton("Kapat", QDialogButtonBox.ButtonRole.RejectRole)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(btn_box)

    def _open(self):
        if os.path.exists(self.filepath) and platform.system() == 'Windows':
            os.startfile(self.filepath)


class _MetadataEditorDialog(QDialog):
    """ID3 (MP3) veya MP4 tag editörü — mutagen tabanlı."""

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.setWindowTitle("Metadata Düzenle")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._fields: dict[str, QLineEdit] = {}
        ext = os.path.splitext(filepath)[1].lower()
        current = self._read_tags(filepath, ext)

        for key, label in [('title', 'Başlık'), ('artist', 'Sanatçı'),
                            ('album', 'Albüm'), ('year', 'Yıl'), ('comment', 'Yorum')]:
            le = QLineEdit(current.get(key, ''), self)
            self._fields[key] = le
            form.addRow(label + ':', le)
        layout.addLayout(form)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self
        )
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    @staticmethod
    def _read_tags(path: str, ext: str) -> dict:
        tags = {}
        try:
            if ext == '.mp3':
                from mutagen.mp3 import MP3
                from mutagen.id3 import ID3
                audio = MP3(path, ID3=ID3)
                t = audio.tags or {}
                tags['title']   = str(t.get('TIT2', ''))
                tags['artist']  = str(t.get('TPE1', ''))
                tags['album']   = str(t.get('TALB', ''))
                tags['year']    = str(t.get('TDRC', ''))
                tags['comment'] = str(t.get('COMM::eng', ''))
            elif ext in ('.mp4', '.m4a'):
                from mutagen.mp4 import MP4
                audio = MP4(path)
                t = audio.tags or {}
                tags['title']   = (t.get('\xa9nam', [''])[0])
                tags['artist']  = (t.get('\xa9ART', [''])[0])
                tags['album']   = (t.get('\xa9alb', [''])[0])
                tags['year']    = (t.get('\xa9day', [''])[0])
                tags['comment'] = (t.get('\xa9cmt', [''])[0])
        except Exception:
            pass
        return tags

    def _save(self):
        ext = os.path.splitext(self.filepath)[1].lower()
        try:
            if ext == '.mp3':
                from mutagen.mp3 import MP3
                from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, COMM, error as ID3Error
                audio = MP3(self.filepath, ID3=ID3)
                try:
                    audio.add_tags()
                except ID3Error:
                    pass
                audio.tags['TIT2'] = TIT2(encoding=3, text=self._fields['title'].text())
                audio.tags['TPE1'] = TPE1(encoding=3, text=self._fields['artist'].text())
                audio.tags['TALB'] = TALB(encoding=3, text=self._fields['album'].text())
                audio.tags['TDRC'] = TDRC(encoding=3, text=self._fields['year'].text())
                if self._fields['comment'].text():
                    audio.tags['COMM::eng'] = COMM(encoding=3, lang='eng',
                        desc='', text=self._fields['comment'].text())
                audio.save()
            elif ext in ('.mp4', '.m4a'):
                from mutagen.mp4 import MP4
                audio = MP4(self.filepath)
                if audio.tags is None:
                    audio.add_tags()
                audio.tags['\xa9nam'] = [self._fields['title'].text()]
                audio.tags['\xa9ART'] = [self._fields['artist'].text()]
                audio.tags['\xa9alb'] = [self._fields['album'].text()]
                audio.tags['\xa9day'] = [self._fields['year'].text()]
                audio.tags['\xa9cmt'] = [self._fields['comment'].text()]
                audio.save()
            from qfluentwidgets import InfoBar
            InfoBar.success(title='Kaydedildi', content='Metadata güncellendi.',
                            duration=3000, parent=self.window())
            self.accept()
        except ImportError:
            from qfluentwidgets import InfoBar
            InfoBar.error(title='Hata', content='mutagen kütüphanesi bulunamadı.',
                          duration=4000, parent=self.window())
        except Exception as e:
            from qfluentwidgets import InfoBar
            InfoBar.error(title='Kayıt Hatası', content=str(e)[:120],
                          duration=4000, parent=self.window())


class _FormatConverterCard(CardWidget):
    """Dosya sürükle-bırak + format seçimi ile dönüştürme paneli."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._worker = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(14)

        # İkon
        icon_lbl = QLabel(self)
        icon_lbl.setPixmap(FluentIcon.DEVELOPER_TOOLS.icon().pixmap(32, 32))
        lay.addWidget(icon_lbl)

        # Başlık + açıklama
        txt_col = QVBoxLayout()
        txt_col.setSpacing(2)
        self._title_lbl = SubtitleLabel("Format Dönüştür", self)
        self._desc_lbl = BodyLabel("Dosyayı buraya sürükleyin veya seçin → MP3 / MP4 / MKV / WebM", self)
        self._desc_lbl.setStyleSheet("color: #888;")
        txt_col.addWidget(self._title_lbl)
        txt_col.addWidget(self._desc_lbl)
        lay.addLayout(txt_col, stretch=1)

        # Format seçici
        self._fmt_combo = ComboBox(self)
        self._fmt_combo.addItems(["MP3", "MP4", "MKV", "WebM", "WAV", "AAC"])
        self._fmt_combo.setFixedWidth(90)
        lay.addWidget(self._fmt_combo)

        # Dosya seç butonu
        self._browse_btn = PushButton(FluentIcon.FOLDER, "Dosya Seç", self)
        self._browse_btn.setFixedWidth(110)
        self._browse_btn.clicked.connect(self._browse)
        lay.addWidget(self._browse_btn)

        # Dönüştür butonu
        self._convert_btn = PushButton(FluentIcon.PLAY, "Dönüştür", self)
        self._convert_btn.setFixedWidth(100)
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(self._start_convert)
        lay.addWidget(self._convert_btn)

        self._selected_file = ''

    def _browse(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Dosya Seç", "",
            "Medya Dosyaları (*.mp4 *.mp3 *.mkv *.webm *.avi *.mov *.wav *.m4a *.ogg *.flac *.opus)"
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._selected_file = path
        name = os.path.basename(path)
        self._desc_lbl.setText(f"Seçili: {name}")
        self._desc_lbl.setStyleSheet("color: #0078D4; font-weight: bold;")
        self._convert_btn.setEnabled(True)

    def _start_convert(self):
        if not self._selected_file or not os.path.exists(self._selected_file):
            return
        if self._worker and self._worker.isRunning():
            return
        fmt = self._fmt_combo.currentText().lower()
        self._convert_btn.setEnabled(False)
        self._desc_lbl.setText("Dönüştürülüyor…")
        self._desc_lbl.setStyleSheet("color: #f0a020; font-weight: bold;")

        self._worker = FormatConverterWorker(self._selected_file, fmt)
        self._worker.completed_signal.connect(self._on_done)
        self._worker.start()

    def _on_done(self, success: bool, result: str):
        self._convert_btn.setEnabled(True)
        if success:
            self._desc_lbl.setText(f"✓ Tamamlandı: {os.path.basename(result)}")
            self._desc_lbl.setStyleSheet("color: #00cc6a; font-weight: bold;")
            InfoBar.success(title="Dönüştürme Tamamlandı",
                            content=os.path.basename(result), duration=4000, parent=self.window())
        else:
            self._desc_lbl.setText("✗ Hata! Dosyayı tekrar seçin.")
            self._desc_lbl.setStyleSheet("color: #e81123; font-weight: bold;")
            InfoBar.error(title="Dönüştürme Hatası", content=result[:120],
                          duration=5000, parent=self.window())

    # ─── Drag & Drop ──────────────────────────────────────────────────────────
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isfile(path):
                self._set_file(path)
                event.acceptProposedAction()


class LibraryInterface(SmoothScrollArea):
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
        setup_smooth_scroll(self, enable_kinetic=False)
        self.setScrollAnimation(Qt.Orientation.Vertical, 500)

        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setContentsMargins(30, 30, 30, 30)
        self.v_layout.setSpacing(20)

        header = QHBoxLayout()
        self.title = TitleLabel("Kütüphane", self.view)
        self.refresh_btn = PushButton(FluentIcon.SYNC, "Yenile", self.view)
        self.refresh_btn.setFixedWidth(90)
        self.refresh_btn.clicked.connect(self.load_files)
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.refresh_btn)
        self.v_layout.addLayout(header)

        # ─── Format Dönüştürücü Paneli ────────────────────────────────────────
        self.converter_card = _FormatConverterCard(self.view)
        self.v_layout.addWidget(self.converter_card)

        # Arama ve filtre satırı
        filter_row = QHBoxLayout()
        self.search_input = SearchLineEdit(self.view)
        self.search_input.setPlaceholderText("Dosya adı ara...")
        self.search_input.setFixedWidth(240)
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(300)
        self._filter_timer.timeout.connect(self._apply_filter)
        self.search_input.textChanged.connect(lambda _: self._filter_timer.start())

        self.type_filter = ComboBox(self.view)
        self.type_filter.addItems(["Tümü", "Video", "Ses"])
        self.type_filter.setFixedWidth(100)
        self.type_filter.currentIndexChanged.connect(self._apply_filter)

        self.sort_combo = ComboBox(self.view)
        self.sort_combo.addItems(["Tarih (Yeni→Eski)", "Tarih (Eski→Yeni)", "Ad (A→Z)", "Ad (Z→A)", "Boyut (Büyük→Küçük)"])
        self.sort_combo.setFixedWidth(200)
        self.sort_combo.currentIndexChanged.connect(self._apply_filter)

        filter_row.addWidget(self.search_input)
        filter_row.addSpacing(12)
        filter_row.addWidget(self.type_filter)
        filter_row.addSpacing(12)
        filter_row.addWidget(self.sort_combo)
        filter_row.addStretch()
        self.v_layout.addLayout(filter_row)

        self.flow_layout = FlowLayout()
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.setSpacing(20)
        self.v_layout.insertLayout(1, self.flow_layout)
        self.v_layout.addStretch()

        self._all_files = []
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

        from src.utils import config as _cfg
        MEDIA_EXTS = ('.mp4', '.mp3', '.webm', '.mkv', '.m4a', '.flac',
                      '.ogg', '.opus', '.avi', '.mov', '.wav', '.aac')
        # Tüm kütüphane klasörlerini topla
        scan_dirs = []
        default_dir = _cfg.get('download_dir', '') or get_os_download_dir()
        scan_dirs.append(default_dir)
        # Ek kütüphane klasörleri (ayarlardan)
        extra_raw = _cfg.get('library_folders', '')
        for line in extra_raw.splitlines():
            line = line.strip()
            if line and os.path.isdir(line) and line not in scan_dirs:
                scan_dirs.append(line)

        self._all_files = []
        seen = set()
        for scan_dir in scan_dirs:
            if not os.path.exists(scan_dir):
                continue
            for f in os.listdir(scan_dir):
                if f.lower().endswith(MEDIA_EXTS):
                    fp = os.path.join(scan_dir, f)
                    if fp not in seen:
                        seen.add(fp)
                        self._all_files.append(fp)
        self._apply_filter()

    def _apply_filter(self):
        query = self.search_input.text().lower() if hasattr(self, 'search_input') else ''
        type_idx = self.type_filter.currentIndex() if hasattr(self, 'type_filter') else 0
        sort_idx = self.sort_combo.currentIndex() if hasattr(self, 'sort_combo') else 0

        VIDEO_EXTS = {'.mp4', '.webm', '.mkv', '.avi', '.mov'}
        AUDIO_EXTS = {'.mp3', '.m4a', '.flac', '.ogg', '.opus', '.wav', '.aac'}

        filtered = []
        for fp in self._all_files:
            ext = os.path.splitext(fp)[1].lower()
            if type_idx == 1 and ext not in VIDEO_EXTS:
                continue
            if type_idx == 2 and ext not in AUDIO_EXTS:
                continue
            if query and query not in os.path.basename(fp).lower():
                continue
            filtered.append(fp)

        if sort_idx == 0:
            filtered.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
        elif sort_idx == 1:
            filtered.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0)
        elif sort_idx == 2:
            filtered.sort(key=lambda x: os.path.basename(x).lower())
        elif sort_idx == 3:
            filtered.sort(key=lambda x: os.path.basename(x).lower(), reverse=True)
        elif sort_idx == 4:
            filtered.sort(key=lambda x: os.path.getsize(x) if os.path.exists(x) else 0, reverse=True)

        # Mevcut kartları temizle
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self.library_items.clear()
        self.thumb_queue.clear()

        for fp in filtered:
            card = LibraryItem(fp, self.view)
            self.flow_layout.addWidget(card)
            self.library_items[fp] = card
            self.thumb_queue.append(fp)

    def on_thumbnail_ready(self, video_path, thumb_path):
        if video_path in self.library_items:
            self.library_items[video_path].set_thumbnail(thumb_path)


class _WhisperDialog(QDialog):
    """Whisper AI transkript oluşturma dialogu."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._worker: WhisperWorker | None = None
        self.setWindowTitle("Transkript Oluştur — Whisper AI")
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # File label
        file_lbl = BodyLabel(f"📄 {os.path.basename(file_path)}", self)
        file_lbl.setWordWrap(True)
        layout.addWidget(file_lbl)

        # Options row
        opts_row = QHBoxLayout()
        opts_row.addWidget(BodyLabel("Model:", self))
        from qfluentwidgets import ComboBox as CB
        self._model_combo = CB(self)
        for m in ['tiny', 'base', 'small', 'medium', 'large']:
            self._model_combo.addItem(m)
        self._model_combo.setCurrentText('base')
        opts_row.addWidget(self._model_combo)
        opts_row.addSpacing(20)
        opts_row.addWidget(BodyLabel("Dil:", self))
        self._lang_combo = CB(self)
        for lang, code in [('Türkçe', 'tr'), ('English', 'en'), ('Otomatik', 'auto')]:
            self._lang_combo.addItem(lang, userData=code)
        opts_row.addWidget(self._lang_combo)
        opts_row.addStretch()
        layout.addLayout(opts_row)

        # Log / progress area
        from PyQt6.QtWidgets import QTextEdit
        self._log = QTextEdit(self)
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(180)
        self._log.setStyleSheet("background:#111; color:#ccc; font-family:Consolas; font-size:11px;")
        layout.addWidget(self._log)

        # Transcript output
        self._transcript = QTextEdit(self)
        self._transcript.setReadOnly(False)
        self._transcript.setPlaceholderText("Transkript burada görünecek…")
        self._transcript.setMinimumHeight(100)
        layout.addWidget(self._transcript)

        # Buttons
        btn_row = QHBoxLayout()
        self._start_btn = PushButton("▶ Başlat", self)
        self._start_btn.clicked.connect(self._start)
        btn_row.addWidget(self._start_btn)
        self._save_btn = PushButton("💾 TXT Kaydet", self)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_txt)
        btn_row.addWidget(self._save_btn)
        btn_row.addStretch()
        close_btn = PushButton("Kapat", self)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _start(self):
        if self._worker and self._worker.isRunning():
            return
        self._log.clear()
        self._transcript.clear()
        self._start_btn.setEnabled(False)
        self._save_btn.setEnabled(False)
        model = self._model_combo.currentText()
        lang_data = self._lang_combo.currentData()
        lang = 'tr' if lang_data is None else lang_data
        if lang == 'auto':
            lang = None
        self._worker = WhisperWorker(self._file_path, model=model, language=lang or 'tr')
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.error_signal.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, msg: str):
        self._log.append(msg)

    def _on_finished(self, out_path: str):
        self._start_btn.setEnabled(True)
        self._save_btn.setEnabled(True)
        try:
            with open(out_path, 'r', encoding='utf-8') as f:
                self._transcript.setPlainText(f.read())
        except Exception:
            pass
        self._log.append(f"✅ Kaydedildi: {out_path}")

    def _on_error(self, msg: str):
        self._start_btn.setEnabled(True)
        self._log.append(f"❌ Hata: {msg}")

    def _save_txt(self):
        from PyQt6.QtWidgets import QFileDialog
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Transkript Kaydet", os.path.splitext(self._file_path)[0] + '.txt', "Metin (*.txt)"
        )
        if out_path:
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(self._transcript.toPlainText())
            self._log.append(f"💾 Kaydedildi: {out_path}")
