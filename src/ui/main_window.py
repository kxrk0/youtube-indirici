#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import platform
import subprocess
import hashlib
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QSize, QThread, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QIcon, QDesktopServices, QAction, QPixmap, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFileDialog, QFrame, QSpacerItem, QSizePolicy, QListWidget, QListWidgetItem,
    QScroller
)

# PyQt-Fluent-Widgets Imports
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon as FIF,
    SubtitleLabel, LineEdit, PrimaryPushButton, PushButton,
    ComboBox, CheckBox, SwitchButton, ProgressBar, IndeterminateProgressBar,
    InfoBar, InfoBarPosition, CardWidget, IconWidget, BodyLabel,
    ScrollArea, FlowLayout, TitleLabel, PipsPager, TableWidget,
    setTheme, Theme, setThemeColor, StrongBodyLabel, ToolButton,
    TransparentToolButton, FolderListSettingCard, OptionsSettingCard,
    PushSettingCard, HyperlinkCard, SettingCardGroup, SettingCard
)
from qfluentwidgets import FluentIcon

from src.core.downloader import Downloader
from src.utils.helpers import (
    is_valid_url, format_size, format_duration, 
    get_os_download_dir, check_ffmpeg, get_clipboard_text,
    extract_video_thumbnail
)
from src.ui.components import VideoInfoCard

# --- Yardımcı Sınıflar ---

class ThumbnailWorker(QThread):
    """Arka planda thumbnail oluşturan işçi"""
    thumbnail_ready = pyqtSignal(str, str) # path, thumb_path
    
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        self.is_running = True
        
    def run(self):
        cache_dir = os.path.join(os.getcwd(), 'cache', 'thumbnails')
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
        while self.is_running:
            if not self.queue:
                self.msleep(100)
                continue
                
            video_path = self.queue.pop(0)
            
            # Cache dosya adı oluştur (path hash'i)
            file_hash = hashlib.md5(video_path.encode('utf-8')).hexdigest()
            thumb_path = os.path.join(cache_dir, f"{file_hash}.jpg")
            
            if os.path.exists(thumb_path):
                self.thumbnail_ready.emit(video_path, thumb_path)
            else:
                # Ses dosyaları için thumbnail oluşturma
                if video_path.lower().endswith('.mp3'):
                    self.thumbnail_ready.emit(video_path, "AUDIO")
                    continue
                    
                success = extract_video_thumbnail(video_path, thumb_path)
                if success:
                    self.thumbnail_ready.emit(video_path, thumb_path)
                else:
                    self.thumbnail_ready.emit(video_path, "ERROR")

    def stop(self):
        self.is_running = False

# --- Arayüz Sayfaları ---

class SmoothScrollArea(ScrollArea):
    """Yumuşak kaydırma ve şeffaf arka plan özelliğine sahip ScrollArea"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        
        # Arka planı şeffaf yap (Tema geçişlerinde renk sorunu olmaması için kritik)
        self.setStyleSheet("QScrollArea {background: transparent; border: none;} QWidget#scroll_view {background: transparent;}")
        self.view.setObjectName("scroll_view")
        self.viewport().setStyleSheet("background: transparent;")
        
        # Kinetik Kaydırma (Touch hissi)
        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.TouchGesture)

class HomeInterface(SmoothScrollArea):
    """Ana Sayfa: URL Girişi ve Hızlı İndirme"""
    
    download_requested = pyqtSignal(str, str, str, str, bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homeInterface")
        self.init_ui()
        
    def init_ui(self):
        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setSpacing(20)
        self.v_layout.setContentsMargins(30, 30, 30, 30)
        
        self.title_label = TitleLabel("YouTube İndirici", self.view)
        self.v_layout.addWidget(self.title_label)
        
        # URL Giriş Kartı
        self.input_card = CardWidget(self.view)
        self.input_layout = QVBoxLayout(self.input_card)
        
        input_row = QHBoxLayout()
        self.url_input = LineEdit(self.view)
        self.url_input.setPlaceholderText("YouTube video bağlantısını yapıştırın...")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.textChanged.connect(self.on_url_changed)
        
        self.paste_btn = PushButton(FluentIcon.PASTE, "Yapıştır", self.view)
        self.paste_btn.clicked.connect(self.paste_from_clipboard)
        
        input_row.addWidget(self.url_input)
        input_row.addWidget(self.paste_btn)
        self.input_layout.addLayout(input_row)
        self.v_layout.addWidget(self.input_card)
        
        # Video Bilgi Kartı
        self.video_info_card = VideoInfoCard(self.view)
        self.video_info_card.hide()
        self.v_layout.addWidget(self.video_info_card)
        
        # Seçenekler Kartı
        self.options_card = CardWidget(self.view)
        self.options_layout = QVBoxLayout(self.options_card)
        self.options_layout.setSpacing(15)
        
        self.subtitle_opts = SubtitleLabel("İndirme Ayarları", self.view)
        self.options_layout.addWidget(self.subtitle_opts)
        
        # Tür ve Format
        opts_row1 = QHBoxLayout()
        self.type_combo = ComboBox(self.view)
        self.type_combo.addItems(["Video (MP4/WebM)", "Ses (MP3)"])
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        
        self.quality_combo = ComboBox(self.view)
        self.quality_combo.addItems(["En İyi (Otomatik)", "4K / 2160p", "1080p", "720p", "480p"])
        
        opts_row1.addWidget(StrongBodyLabel("Tür:", self.view))
        opts_row1.addWidget(self.type_combo)
        opts_row1.addSpacing(20)
        opts_row1.addWidget(StrongBodyLabel("Kalite:", self.view))
        opts_row1.addWidget(self.quality_combo)
        opts_row1.addStretch()
        self.options_layout.addLayout(opts_row1)
        
        # Konum
        path_row = QHBoxLayout()
        self.path_input = LineEdit(self.view)
        self.path_input.setText(get_os_download_dir())
        self.path_input.setReadOnly(True)
        
        self.browse_btn = PushButton(FluentIcon.FOLDER, "Gözat", self.view)
        self.browse_btn.clicked.connect(self.browse_directory)
        
        path_row.addWidget(StrongBodyLabel("Konum:", self.view))
        path_row.addWidget(self.path_input)
        path_row.addWidget(self.browse_btn)
        self.options_layout.addLayout(path_row)
        
        # Checkboxlar
        self.meta_check = CheckBox("Meta verileri kaydet (JSON)", self.view)
        self.thumb_check = CheckBox("Küçük resmi göm", self.view)
        self.thumb_check.setChecked(True)
        self.options_layout.addWidget(self.meta_check)
        self.options_layout.addWidget(self.thumb_check)
        
        self.v_layout.addWidget(self.options_card)
        
        # Buton
        self.download_btn = PrimaryPushButton(FluentIcon.DOWNLOAD, "İndirmeyi Başlat", self.view)
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setEnabled(False)
        
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.download_btn)
        self.v_layout.addLayout(btn_row)
        self.v_layout.addStretch()
        
        # Timer
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(800)
        self.search_timer.timeout.connect(self.fetch_video_info)

    def on_url_changed(self, text):
        if is_valid_url(text):
            self.video_info_card.title_lbl.setText("Bilgiler alınıyor...")
            self.video_info_card.show()
            self.search_timer.start()
        else:
            self.search_timer.stop()
            self.video_info_card.reset_info()
            self.download_btn.setEnabled(False)
            
    def fetch_video_info(self):
        url = self.url_input.text()
        if not is_valid_url(url): return
        
        main_window = self.window()
        if hasattr(main_window, 'downloader'):
            self.worker = InfoFetchWorker(main_window.downloader, url)
            self.worker.info_ready.connect(self.on_info_ready)
            self.worker.start()
            
    def on_info_ready(self, info, formats):
        if info:
            self.video_info_card.update_info(info)
            self.download_btn.setEnabled(True)
        else:
            self.video_info_card.title_lbl.setText("Video bilgisi alınamadı!")
            self.download_btn.setEnabled(False)

    def paste_from_clipboard(self):
        text = get_clipboard_text()
        if text: self.url_input.setText(text)
            
    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Klasör Seç", self.path_input.text())
        if dir_path: self.path_input.setText(dir_path)
            
    def on_type_changed(self, index):
        is_video = (index == 0)
        self.quality_combo.setEnabled(is_video)
        
    def start_download(self):
        url = self.url_input.text()
        path = self.path_input.text()
        type_idx = self.type_combo.currentIndex()
        quality = self.quality_combo.currentText()
        save_meta = self.meta_check.isChecked()
        
        type_str = 'video' if type_idx == 0 else 'audio'
        format_id = 'best'
        if type_str == 'video':
            if "4K" in quality: format_id = "bestvideo[height>=2160]+bestaudio/best"
            elif "1080p" in quality: format_id = "bestvideo[height<=1080]+bestaudio/best"
            elif "720p" in quality: format_id = "bestvideo[height<=720]+bestaudio/best"
            elif "480p" in quality: format_id = "bestvideo[height<=480]+bestaudio/best"
        
        self.download_requested.emit(url, path, format_id, type_str, save_meta)
        
        InfoBar.success(title='Sıraya Alındı', content="İndirme başladı.", duration=3000, parent=self)
        self.url_input.clear()
        self.video_info_card.reset_info()

class DownloadItemCard(CardWidget):
    """Gelişmiş İndirme Kartı"""
    def __init__(self, title, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.setFixedHeight(100)
        
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(24, 16, 24, 16)
        h_layout.setSpacing(24)
        
        # İkon
        self.icon_widget = IconWidget(FluentIcon.VIDEO, self)
        self.icon_widget.setFixedSize(40, 40)
        h_layout.addWidget(self.icon_widget)
        
        # Bilgi
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
        
        # İlerleme
        self.progress = ProgressBar(self)
        self.progress.setFixedWidth(220)
        h_layout.addWidget(self.progress)
        
        h_layout.addSpacing(16)
        
        # Butonlar (Başlangıçta gizli olabilirler veya disable)
        self.action_layout = QHBoxLayout()
        self.action_layout.setSpacing(8)
        
        self.open_folder_btn = TransparentToolButton(FluentIcon.FOLDER, self)
        self.open_folder_btn.setToolTip("Klasörü Aç")
        self.open_folder_btn.clicked.connect(self.open_folder)
        self.open_folder_btn.setEnabled(False)
        
        self.play_btn = TransparentToolButton(FluentIcon.PLAY, self)
        self.play_btn.setToolTip("Oynat")
        self.play_btn.clicked.connect(self.open_file)
        self.play_btn.setEnabled(False)
        
        self.cancel_btn = TransparentToolButton(FluentIcon.CANCEL, self)
        self.cancel_btn.setToolTip("İptal Et")
        
        self.action_layout.addWidget(self.open_folder_btn)
        self.action_layout.addWidget(self.play_btn)
        self.action_layout.addWidget(self.cancel_btn)
        
        h_layout.addLayout(self.action_layout)
        
        self.file_path = None # İndirme bitince set edilecek

    def update_progress(self, percent, speed, eta):
        self.progress.setValue(percent)
        self.status_lbl.setText(f"{speed} • {eta} kaldı")
        
    def set_finished(self, filepath=None):
        self.progress.setValue(100)
        self.progress.hide() # İlerleme çubuğunu gizle
        self.status_lbl.setText("İndirme Tamamlandı")
        self.status_lbl.setStyleSheet("color: #00cc6a;") # Yeşil renk
        
        self.icon_widget.setIcon(FluentIcon.COMPLETED)
        
        self.cancel_btn.hide()
        self.open_folder_btn.setEnabled(True)
        self.play_btn.setEnabled(True)
        
        if filepath:
            self.file_path = filepath
            
    def open_folder(self):
        path = self.file_path or get_os_download_dir()
        if os.path.isfile(path):
            path = os.path.dirname(path)
        os.startfile(path) if platform.system() == 'Windows' else None
        
    def open_file(self):
        if self.file_path and os.path.exists(self.file_path):
            os.startfile(self.file_path) if platform.system() == 'Windows' else None

class QueueInterface(SmoothScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("queueInterface")
        
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
        
    def add_download_item(self, title, url):
        item = DownloadItemCard(title, url, self.view)
        self.list_layout.insertWidget(0, item)
        return item

class LibraryItem(CardWidget):
    """Kütüphanedeki dosya kartı (Thumbnail destekli)"""
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.setFixedSize(200, 180)
        
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.v_layout.setSpacing(0)
        
        # Thumbnail Alanı
        self.thumb_label = QLabel(self)
        self.thumb_label.setFixedSize(200, 112) # 16:9 oranına yakın
        self.thumb_label.setStyleSheet("background-color: #202020; border-top-left-radius: 8px; border-top-right-radius: 8px;")
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setScaledContents(True)
        
        # Varsayılan ikon
        self.default_icon = FluentIcon.VIDEO.icon().pixmap(48, 48)
        self.thumb_label.setPixmap(self.default_icon)
        
        self.v_layout.addWidget(self.thumb_label)
        
        # Bilgi Alanı
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(10, 5, 10, 10)
        
        filename = os.path.basename(path)
        self.name_label = BodyLabel(filename, self)
        self.name_label.setWordWrap(False) # Tek satır
        
        # Butonlar
        btn_layout = QHBoxLayout()
        self.open_btn = TransparentToolButton(FluentIcon.PLAY, self)
        self.open_btn.setToolTip("Oynat")
        self.open_btn.clicked.connect(self.open_file)
        
        self.folder_btn = TransparentToolButton(FluentIcon.FOLDER, self)
        self.folder_btn.setToolTip("Klasörü Aç")
        self.folder_btn.clicked.connect(self.open_folder)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.folder_btn)
        btn_layout.addStretch()
        
        info_layout.addWidget(self.name_label)
        info_layout.addLayout(btn_layout)
        
        self.v_layout.addWidget(info_widget)

    def set_thumbnail(self, image_path):
        if image_path == "AUDIO":
            self.thumb_label.setPixmap(FluentIcon.MUSIC.icon().pixmap(48, 48))
        elif image_path == "ERROR":
            pass
        elif os.path.exists(image_path):
            self.thumb_label.setPixmap(QPixmap(image_path))

    def open_file(self):
        if platform.system() == 'Windows': os.startfile(self.path)
        elif platform.system() == 'Darwin': subprocess.call(['open', self.path])
        else: subprocess.call(['xdg-open', self.path])
            
    def open_folder(self):
        folder = os.path.dirname(self.path)
        if platform.system() == 'Windows': os.startfile(folder)
        elif platform.system() == 'Darwin': subprocess.call(['open', folder])
        else: subprocess.call(['xdg-open', folder])

class LibraryInterface(SmoothScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("libraryInterface")
        
        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setContentsMargins(30, 30, 30, 30)
        self.v_layout.setSpacing(20)
        
        # Header
        header = QHBoxLayout()
        self.title = TitleLabel("Kütüphane", self.view)
        self.refresh_btn = PushButton(FluentIcon.SYNC, "Yenile", self.view)
        self.refresh_btn.setFixedWidth(100)
        self.refresh_btn.clicked.connect(self.load_files)
        
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.refresh_btn)
        self.v_layout.addLayout(header)
        
        # Grid
        self.flow_layout = FlowLayout()
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.setSpacing(20)
        self.v_layout.addLayout(self.flow_layout)
        self.v_layout.addStretch()
        
        # Thumbnail Worker Queue
        self.thumb_queue = []
        self.thumb_worker = ThumbnailWorker(self.thumb_queue)
        self.thumb_worker.thumbnail_ready.connect(self.on_thumbnail_ready)
        self.thumb_worker.start()
        
        self.library_items = {} # path -> widget
        self.load_files()
        
    def load_files(self):
        # Temizle
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            
            # Nesne tipine göre silme işlemi
            if hasattr(item, 'widget'):
                w = item.widget()
                if w: w.deleteLater()
            elif isinstance(item, QWidget):
                item.deleteLater()
            else:
                # Eğer item direkt widget ise (QLayoutItem değilse)
                # PySide/PyQt farklılıklarında bazen direkt nesne gelebilir
                try:
                    item.deleteLater()
                except:
                    pass
        
        self.library_items.clear()
        self.thumb_queue.clear()
        
        download_dir = get_os_download_dir()
        exts = ('.mp4', '.mp3', '.webm', '.mkv')
        
        if os.path.exists(download_dir):
            files = sorted([f for f in os.listdir(download_dir) if f.lower().endswith(exts)], 
                         key=lambda x: os.path.getmtime(os.path.join(download_dir, x)), 
                         reverse=True)
            
            for f in files:
                full_path = os.path.join(download_dir, f)
                item = LibraryItem(full_path, self.view)
                self.flow_layout.addWidget(item)
                
                self.library_items[full_path] = item
                self.thumb_queue.append(full_path)
    
    def on_thumbnail_ready(self, video_path, thumb_path):
        if video_path in self.library_items:
            self.library_items[video_path].set_thumbnail(thumb_path)

class SettingsInterface(SmoothScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsInterface")
        
        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setContentsMargins(36, 36, 36, 36)
        self.v_layout.setSpacing(20)
        
        self.title = TitleLabel("Ayarlar", self.view)
        self.v_layout.addWidget(self.title)
        
        # --- Kişiselleştirme ---
        self.group1 = SettingCardGroup("Kişiselleştirme", self.view)
        
        # Tema
        self.theme_card = SwitchSettingCard(
            FluentIcon.BRIGHTNESS,
            "Uygulama Teması",
            "Karanlık veya aydınlık mod arasında geçiş yapın",
            parent=self.view
        )
        self.theme_card.switchButton.setChecked(True)
        self.theme_card.switchButton.checkedChanged.connect(lambda c: setTheme(Theme.DARK if c else Theme.LIGHT))
        self.theme_card.switchButton.setOnText("Karanlık")
        self.theme_card.switchButton.setOffText("Aydınlık")
        self.group1.addSettingCard(self.theme_card)
        
        self.v_layout.addWidget(self.group1)
        
        # --- İndirme ---
        self.group2 = SettingCardGroup("İndirme", self.view)
        
        # Klasör
        self.folder_card = PushSettingCard(
            "Klasörü Seç",
            FluentIcon.FOLDER,
            "İndirme Konumu",
            get_os_download_dir(),
            self.view
        )
        self.folder_card.clicked.connect(self.select_folder)
        self.group2.addSettingCard(self.folder_card)
        
        self.v_layout.addWidget(self.group2)
        
        # --- Hakkında ---
        self.group3 = SettingCardGroup("Hakkında", self.view)
        self.link_card = HyperlinkCard(
            "https://github.com/kxrk0/youtube-indirici",
            "GitHub Sayfası",
            FluentIcon.GITHUB,
            "Kaynak kodlarını görüntüle",
            "GitHub",
            self.view
        )
        self.group3.addSettingCard(self.link_card)
        
        self.v_layout.addWidget(self.group3)
        self.v_layout.addStretch()
        
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "İndirme Klasörünü Seç", get_os_download_dir())
        if folder:
            self.folder_card.setContent(folder)
            # Burada ayarı kalıcı olarak kaydetmek gerekir (config.ini veya QSettings)

class SwitchSettingCard(SettingCard):
    """Manuel Switch Kartı"""
    def __init__(self, icon, title, content, parent=None):
        super().__init__(icon, title, content, parent)
        self.switchButton = SwitchButton(self)
        # Switch butonunu sağa yasla
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

# --- Worker Classes (Eskisi gibi) ---
class InfoFetchWorker(QThread):
    info_ready = pyqtSignal(dict, list)
    def __init__(self, downloader, url):
        super().__init__()
        self.downloader = downloader
        self.url = url
    def run(self):
        info = self.downloader.get_video_info(self.url)
        formats = self.downloader.get_available_formats(self.url) if info else []
        self.info_ready.emit(info, formats)

class DownloadWorker(QThread):
    progress_signal = pyqtSignal(dict)
    completed_signal = pyqtSignal(bool, str)
    def __init__(self, downloader, url, output_dir, format_id=None, is_audio=False, save_metadata=False):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.output_dir = output_dir
        self.format_id = format_id
        self.is_audio = is_audio
        self.save_metadata = save_metadata
    def progress_callback(self, d):
        if d['status'] == 'downloading':
            self.progress_signal.emit({
                'downloaded_bytes': d.get('downloaded_bytes', 0),
                'total_bytes': d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0),
                'speed': d.get('speed', 0),
                'filename': d.get('filename', ''),
                'status': 'downloading',
                'eta': d.get('eta', 0)
            })
        elif d['status'] == 'finished':
            self.progress_signal.emit({'status': 'processing', 'filename': d.get('filename', '')})
    def complete_callback(self, success, error=None):
        self.completed_signal.emit(success, error if error else "")
    def run(self):
        if self.is_audio:
            self.downloader.download_audio(self.url, self.output_dir, progress_callback=self.progress_callback, complete_callback=self.complete_callback, save_info=self.save_metadata)
        else:
            self.downloader.download_video(self.url, self.output_dir, format_id=self.format_id, progress_callback=self.progress_callback, complete_callback=self.complete_callback, save_info=self.save_metadata)

class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        setTheme(Theme.DARK)
        setThemeColor('#0078D4')
        
        self.setWindowTitle("YouTube Studio Downloader")
        self.resize(1100, 750)
        if os.path.exists("extension/icons/download.svg"):
            self.setWindowIcon(QIcon("extension/icons/download.svg"))
            
        self.downloader = Downloader()
        
        self.home_interface = HomeInterface(self)
        self.queue_interface = QueueInterface(self)
        self.library_interface = LibraryInterface(self)
        self.settings_interface = SettingsInterface(self)
        
        self.init_navigation()
        self.connect_signals()
        
    def init_navigation(self):
        self.addSubInterface(self.home_interface, FluentIcon.HOME, "Ana Sayfa")
        self.addSubInterface(self.queue_interface, FluentIcon.DOWNLOAD, "İndirilenler")
        self.addSubInterface(self.library_interface, FluentIcon.LIBRARY, "Kütüphane")
        self.navigationInterface.addSeparator()
        self.addSubInterface(self.settings_interface, FluentIcon.SETTING, "Ayarlar", NavigationItemPosition.BOTTOM)
        
    def connect_signals(self):
        self.home_interface.download_requested.connect(self.start_download_process)
        
    def start_download_process(self, url, path, format_id, type_str, save_meta):
        # add_download_item artık (title, url) bekliyor, ama biz henüz title'ı bilmiyoruz (worker içinde).
        # Şimdilik URL'yi başlık olarak kullanalım, worker güncelleyebilir.
        card = self.queue_interface.add_download_item("İndirme Başlatılıyor...", url)
        
        is_audio = (type_str == 'audio')
        worker = DownloadWorker(self.downloader, url, path, format_id, is_audio, save_meta)
        worker.progress_signal.connect(lambda d: self.update_download_card(card, d))
        worker.completed_signal.connect(lambda s, e: self.finish_download_card(card, s, e, path))
        card.worker = worker
        worker.start()
        self.switchTo(self.queue_interface)
        
    def update_download_card(self, card, data):
        status = data.get('status')
        filename = data.get('filename', '')
        
        # Dosya adını güncelle (eğer varsa)
        if filename and not card.file_path:
            display_name = os.path.basename(filename)
            card.title_lbl.setText(display_name)
            
        if status == 'downloading':
            downloaded = data.get('downloaded_bytes', 0)
            total = data.get('total_bytes', 0)
            if total > 0:
                percent = int((downloaded / total) * 100)
                speed = format_size(data.get('speed', 0)) + "/s"
                eta = format_duration(data.get('eta', 0))
                card.update_progress(percent, speed, eta)
        elif status == 'processing':
            card.status_lbl.setText("Dönüştürülüyor...")
            card.progress.setMaximum(0) # Belirsiz
            
    def finish_download_card(self, card, success, error, output_dir):
        if success:
            # Dosya yolunu tahmin et (tam path worker'dan gelmediği için dizin + dosya adı yapabiliriz ama en doğrusu worker'ın path dönmesidir)
            # Şimdilik output_dir veriyoruz, kullanıcı klasörü açabilir.
            card.set_finished(output_dir)
            InfoBar.success(title='Başarılı', content="İndirme tamamlandı.", duration=3000, parent=self)
        else:
            card.status_lbl.setText("Hata!")
            card.progress.hide()
            InfoBar.error(title='Hata', content=f"{error}", duration=5000, parent=self)

if __name__ == '__main__':
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    os.environ["QT_SCALE_FACTOR"] = "1.25"
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    
    # Ortala
    geometry = w.frameGeometry()
    geometry.moveCenter(w.screen().availableGeometry().center())
    w.move(geometry.topLeft())
    
    sys.exit(app.exec())