#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import platform
import subprocess
import hashlib
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QSize, QThread, QTimer, QPropertyAnimation, QEasingCurve, QTime, QDate, QDateTime
from PyQt6.QtGui import QIcon, QDesktopServices, QAction, QPixmap, QColor, QPainter, QBrush, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFileDialog, QFrame, QSpacerItem, QSizePolicy, QListWidget, QListWidgetItem,
    QScroller, QScrollerProperties, QMessageBox, QApplication, QSystemTrayIcon, QMenu
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
    PushSettingCard, HyperlinkCard, SettingCardGroup, SettingCard, Slider,
    TimePicker, MessageBoxBase
)
from qfluentwidgets import FluentIcon

from src.core.downloader import Downloader
from src.utils.helpers import (
    is_valid_url, format_size, format_duration, 
    get_os_download_dir, check_ffmpeg, get_clipboard_text,
    extract_video_thumbnail, get_optimal_timer_interval, get_animation_speed_factor,
    get_monitor_refresh_rate
)
from src.utils.i18n import tr, set_language, get_current_language, get_supported_languages
from src.utils.updater import get_auto_updater, get_current_version
from src.ui.components import VideoInfoCard
from src.ui.dialogs import PlaylistSelectionDialog

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
            
            file_hash = hashlib.md5(video_path.encode('utf-8')).hexdigest()
            thumb_path = os.path.join(cache_dir, f"{file_hash}.jpg")
            
            if os.path.exists(thumb_path):
                self.thumbnail_ready.emit(video_path, thumb_path)
            else:
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

# --- Scroll Optimizasyonu ---

def setup_smooth_scroll(scroll_area, enable_kinetic=True):
    """
    ScrollArea'ya GPU-optimized smooth scrolling ekler.
    
    Args:
        scroll_area: QScrollArea veya türevi
        enable_kinetic: Kinetic (momentum) scrolling aktif mi?
    """
    refresh_rate = get_monitor_refresh_rate()
    
    # Widget optimizasyonları
    scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    
    # Viewport widget optimizasyonları  
    viewport = scroll_area.viewport()
    if viewport:
        viewport.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
    
    # Scroll step boyutunu refresh rate'e göre ayarla
    vbar = scroll_area.verticalScrollBar()
    if vbar:
        # Yüksek Hz = daha küçük adımlar = daha akıcı
        step = max(15, int(100 / (refresh_rate / 60)))
        vbar.setSingleStep(step)
    
    # Kinetic scrolling (momentum efekti)
    if enable_kinetic:
        try:
            scroller = QScroller.scroller(scroll_area.viewport())
            props = scroller.scrollerProperties()
            
            # Deceleration - yüksek Hz'de daha smooth
            decel = 0.988 if refresh_rate >= 144 else 0.982 if refresh_rate >= 120 else 0.975
            props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, decel)
            
            # Minimum hız - daha responsive başlangıç
            props.setScrollMetric(QScrollerProperties.ScrollMetric.MinimumVelocity, 0.1)
            
            # Maximum hız
            props.setScrollMetric(QScrollerProperties.ScrollMetric.MaximumVelocity, 0.8)
            
            # Overshoot (kenar bounce efekti)
            props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragResistanceFactor, 0.35)
            props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.15)
            
            # Uygula
            scroller.setScrollerProperties(props)
            
            # Mouse gesture aktifleştir
            QScroller.grabGesture(
                scroll_area.viewport(),
                QScroller.ScrollerGestureType.LeftMouseButtonGesture
            )
        except Exception as e:
            print(f"Kinetic scroll error: {e}")
    
    return scroll_area

# --- UI Components (Skeleton & Dialogs) ---

class SkeletonWidget(QWidget):
    """Yükleniyor efekti için yanıp sönen gri kutu - Monitör Hz'e göre dinamik FPS"""
    def __init__(self, width=None, height=None, radius=4, parent=None):
        super().__init__(parent)
        if width: self.setFixedWidth(width)
        if height: self.setFixedHeight(height)
        self.radius = radius
        
        # Monitör refresh rate'ine göre optimal timer interval
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_opacity)
        self.timer.start(get_optimal_timer_interval())  # 180Hz=5ms, 60Hz=16ms
        
        self.opacity = 1.0
        # Animasyon hızını refresh rate'e göre normalize et
        self.direction = -0.015 * get_animation_speed_factor()
        self.min_opacity = 0.3
        self.max_opacity = 0.9
        
    def update_opacity(self):
        self.opacity += self.direction
        if self.opacity <= self.min_opacity or self.opacity >= self.max_opacity:
            self.direction *= -1
            self.opacity = max(self.min_opacity, min(self.max_opacity, self.opacity))
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        
        color = QColor(60, 60, 60, int(255 * self.opacity))
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(self.rect(), self.radius, self.radius)

class VideoInfoSkeleton(CardWidget):
    """Video bilgisi yüklenirken gösterilecek iskelet yapı"""
    def __init__(self, parent=None):
        super().__init__(parent)
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(16, 16, 16, 16)
        h_layout.setSpacing(16)
        
        self.thumb_skel = SkeletonWidget(160, 90, 8, self)
        h_layout.addWidget(self.thumb_skel)
        
        v_layout = QVBoxLayout()
        v_layout.setSpacing(8)
        v_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        self.title_skel = SkeletonWidget(300, 24, 4, self)
        self.meta_skel = SkeletonWidget(200, 16, 4, self)
        
        v_layout.addWidget(self.title_skel)
        v_layout.addWidget(self.meta_skel)
        h_layout.addLayout(v_layout)
        h_layout.addStretch()

class ScheduleDialog(MessageBoxBase):
    """İndirme Zamanlama Diyaloğu"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("İndirmeyi Zamanla", self)
        
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(20)
        
        h_layout = QHBoxLayout()
        h_layout.addWidget(BodyLabel("Başlangıç Saati:", self))
        h_layout.addStretch()
        
        self.time_picker = TimePicker(self)
        now = QTime.currentTime().addSecs(60)
        self.time_picker.setTime(now)
        h_layout.addWidget(self.time_picker)
        
        self.viewLayout.addLayout(h_layout)
        
        self.yesButton.setText("Zamanla")
        self.cancelButton.setText("İptal")
        self.widget.setMinimumWidth(350)
        
    def get_time(self):
        return self.time_picker.time()

# --- Arayüz Sayfaları ---

class HomeInterface(ScrollArea):
    """Ana Sayfa: URL Girişi ve Hızlı İndirme - GPU optimized scroll"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homeInterface")
        
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.view.setObjectName("homeView")
        
        self.setStyleSheet("ScrollArea{background: transparent; border: none;}")
        self.view.setStyleSheet("QWidget#homeView{background: transparent;}")
        
        # GPU-optimized smooth scrolling
        setup_smooth_scroll(self, enable_kinetic=True)
        
        self.init_ui()
        
    def init_ui(self):
        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setSpacing(20)
        self.v_layout.setContentsMargins(30, 30, 30, 30)
        
        self.title_label = TitleLabel("YouTube İndirici", self.view)
        self.v_layout.addWidget(self.title_label)
        
        # URL Giriş
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
        
        # Skeleton & Video Info
        self.skeleton_card = VideoInfoSkeleton(self.view)
        self.skeleton_card.hide()
        self.v_layout.addWidget(self.skeleton_card)
        
        self.video_info_card = VideoInfoCard(self.view)
        self.video_info_card.hide()
        self.v_layout.addWidget(self.video_info_card)
        
        # Seçenekler
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
        self.quality_combo.addItems(["En İyi Kalite (Otomatik)", "best"])
        
        opts_row1.addWidget(StrongBodyLabel("Tür:", self.view))
        opts_row1.addWidget(self.type_combo)
        opts_row1.addSpacing(20)
        opts_row1.addWidget(StrongBodyLabel("Kalite:", self.view))
        opts_row1.addWidget(self.quality_combo)
        opts_row1.addStretch()
        self.options_layout.addLayout(opts_row1)
        
        self.auto_quality_label = BodyLabel("", self.view)
        self.auto_quality_label.setStyleSheet("color: #00cc6a; font-weight: bold;")
        self.auto_quality_label.hide()
        opts_row1.addWidget(self.auto_quality_label)
        
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
        self.subs_check = CheckBox("Altyazıları indir (TR/EN)", self.view)
        
        self.options_layout.addWidget(self.meta_check)
        self.options_layout.addWidget(self.thumb_check)
        self.options_layout.addWidget(self.subs_check)
        
        self.v_layout.addWidget(self.options_card)
        
        # Butonlar
        btn_row = QHBoxLayout()
        
        self.schedule_btn = PushButton(FluentIcon.HISTORY, "Zamanla", self.view)
        self.schedule_btn.clicked.connect(self.schedule_download)
        self.schedule_btn.setEnabled(False)
        
        self.download_btn = PrimaryPushButton(FluentIcon.DOWNLOAD, "İndirmeyi Başlat", self.view)
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setEnabled(False)
        
        btn_row.addStretch()
        btn_row.addWidget(self.schedule_btn)
        btn_row.addWidget(self.download_btn)
        self.v_layout.addLayout(btn_row)
        self.v_layout.addStretch()
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(800)
        self.search_timer.timeout.connect(self.fetch_video_info)

    def on_url_changed(self, text):
        if is_valid_url(text):
            self.video_info_card.hide()
            self.skeleton_card.show()
            self.auto_quality_label.hide()
            self.search_timer.start()
        else:
            self.search_timer.stop()
            self.video_info_card.reset_info()
            self.video_info_card.hide()
            self.skeleton_card.hide()
            self.auto_quality_label.hide()
            self.download_btn.setEnabled(False)
            self.schedule_btn.setEnabled(False)
            
    def fetch_video_info(self):
        url = self.url_input.text()
        if not is_valid_url(url): return
        
        main_window = self.window()
        if hasattr(main_window, 'downloader'):
            self.worker = InfoFetchWorker(main_window.downloader, url)
            self.worker.info_ready.connect(self.on_info_ready)
            self.worker.start()
            
    def on_info_ready(self, info, formats, is_playlist):
        self.skeleton_card.hide()
        if not info:
            self.video_info_card.title_lbl.setText("Video bilgisi alınamadı!")
            self.download_btn.setEnabled(False)
            self.auto_quality_label.hide()
            return

        if is_playlist:
            self.video_info_card.hide()
            dialog = PlaylistSelectionDialog(info, self.window())
            if dialog.exec():
                selected_videos = dialog.get_selected_videos()
                if selected_videos:
                    self.start_playlist_download(selected_videos)
            else:
                self.url_input.clear()
        else:
            self.video_info_card.update_info(info)
            self.video_info_card.show()
            self.download_btn.setEnabled(True)
            self.schedule_btn.setEnabled(True)
            
            if not formats and 'formats' in info:
                formats = info['formats']
                
            self.populate_formats(formats)
            self.auto_quality_label.hide()

    def populate_formats(self, formats):
        self.quality_combo.clear()
        self.quality_combo.addItem("En İyi Kalite (Otomatik)", "best")
        
        available_formats = []
        for fmt in formats:
            try:
                format_id = fmt.get('format_id')
                height = fmt.get('height')
                resolution = fmt.get('resolution')
                ext = fmt.get('ext')
                vcodec = fmt.get('vcodec')
                filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                
                if vcodec == 'none': continue
                
                if height is None and resolution:
                    try:
                        if 'x' in resolution:
                            parts = resolution.split('x')
                            if len(parts) == 2: height = int(parts[1])
                    except: pass
                
                height_val = int(height) if height else 0
                res_str = f"{height_val}p" if height_val > 0 else "Bilinmeyen"
                
                size_str = format_size(filesize) if filesize else "?"
                display_ext = f"{ext} -> MP4" if ext in ['webm', 'mkv'] else ext
                label = f"{res_str} - {display_ext} ({size_str})"
                
                available_formats.append((format_id, label, height_val))
            except: continue
        
        seen = set()
        for fmt_id, label, h in sorted(available_formats, key=lambda x: x[2], reverse=True):
            if label not in seen:
                self.quality_combo.addItem(label, f"{fmt_id}+bestaudio/best")
                seen.add(label)

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
        format_id = self.quality_combo.currentData() or 'best'
        save_meta = self.meta_check.isChecked()
        write_sub = self.subs_check.isChecked()
        type_str = 'video' if type_idx == 0 else 'audio'
        
        main_window = self.window()
        if hasattr(main_window, 'start_download_process'):
            main_window.start_download_process(url, path, format_id, type_str, save_meta, write_sub)
            InfoBar.success(title='Sıraya Alındı', content="İndirme başladı.", duration=3000, parent=self)
            self.url_input.clear()
            self.video_info_card.reset_info()
            self.quality_combo.clear()
            self.quality_combo.addItem("En İyi (Otomatik)", "best")
            
    def schedule_download(self):
        dialog = ScheduleDialog(self.window())
        if dialog.exec():
            time = dialog.get_time()
            url = self.url_input.text()
            path = self.path_input.text()
            type_idx = self.type_combo.currentIndex()
            format_id = self.quality_combo.currentData() or 'best'
            save_meta = self.meta_check.isChecked()
            write_sub = self.subs_check.isChecked()
            type_str = 'video' if type_idx == 0 else 'audio'
            
            main_window = self.window()
            if hasattr(main_window, 'add_scheduled_task'):
                main_window.add_scheduled_task(time, url, path, format_id, type_str, save_meta, write_sub)
                InfoBar.success(title='Zamanlandı', content=f"İndirme {time.toString('HH:mm')} için planlandı.", duration=3000, parent=self)
                self.url_input.clear()
                self.video_info_card.reset_info()
                self.video_info_card.hide()

    def start_playlist_download(self, videos):
        path = self.path_input.text()
        type_idx = self.type_combo.currentIndex()
        format_id = 'best'
        type_str = 'video' if type_idx == 0 else 'audio'
        save_meta = self.meta_check.isChecked()
        write_sub = self.subs_check.isChecked()
        
        main_window = self.window()
        if hasattr(main_window, 'start_download_process'):
            count = 0
            for vid in videos:
                main_window.start_download_process(vid['url'], path, format_id, type_str, save_meta, write_sub)
                count += 1
            InfoBar.success(title='Playlist Başlatıldı', content=f"{count} video eklendi.", duration=3000, parent=self)
            self.url_input.clear()

class DownloadItemCard(CardWidget):
    """Gelişmiş İndirme Kartı - İptal desteği ile"""
    
    # Signals
    cancel_requested = pyqtSignal()
    
    def __init__(self, title, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.download_task = None  # DownloadTask referansı
        self.is_cancelled = False
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
        
        self.action_layout = QHBoxLayout()
        self.action_layout.setSpacing(8)
        
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
        
        self.action_layout.addWidget(self.open_folder_btn)
        self.action_layout.addWidget(self.play_btn)
        self.action_layout.addWidget(self.delete_btn)
        self.action_layout.addWidget(self.cancel_btn)
        
        h_layout.addLayout(self.action_layout)
        self.file_path = None 

    def set_download_task(self, task):
        """DownloadTask referansını ayarla"""
        self.download_task = task
        
    def cancel_download(self):
        """İndirmeyi iptal et"""
        if self.download_task:
            self.download_task.cancel()
            self.is_cancelled = True
            self.set_cancelled()
        self.cancel_requested.emit()
        
    def set_cancelled(self):
        """İptal durumunu göster"""
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
        if filepath: self.file_path = filepath
        
    def set_error(self, error_msg: str):
        """Hata durumunu göster"""
        self.progress.hide()
        self.status_lbl.setText(f"Hata: {error_msg[:50]}...")
        self.status_lbl.setStyleSheet("color: #ff6b6b;")
        self.icon_widget.setIcon(FluentIcon.INFO)
        self.cancel_btn.hide()
        self.delete_btn.show()
            
    def delete_item(self):
        reply = QMessageBox.question(self, "Sil", "Silmek istediğinize emin misiniz?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.file_path and os.path.isfile(self.file_path):
                try: os.remove(self.file_path)
                except: pass
            self.deleteLater()
            
    def open_folder(self):
        path = self.file_path or get_os_download_dir()
        if os.path.isfile(path): path = os.path.dirname(path)
        os.startfile(path) if platform.system() == 'Windows' else None
        
    def open_file(self):
        if self.file_path and os.path.exists(self.file_path):
            os.startfile(self.file_path) if platform.system() == 'Windows' else None

class QueueInterface(ScrollArea):
    """İndirme Kuyruğu - GPU optimized scroll"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("queueInterface")
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.view.setObjectName("queueView")
        self.setStyleSheet("ScrollArea{background: transparent; border: none;}")
        self.view.setStyleSheet("QWidget#queueView{background: transparent;}")
        
        # GPU-optimized smooth scrolling
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
        
    def add_download_item(self, title, url):
        item = DownloadItemCard(title, url, self.view)
        self.list_layout.insertWidget(0, item)
        return item

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
        self.thumb_label.setStyleSheet("background-color: #202020; border-top-left-radius: 8px; border-top-right-radius: 8px;")
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setScaledContents(True)
        self.default_icon = FluentIcon.VIDEO.icon().pixmap(48, 48)
        self.thumb_label.setPixmap(self.default_icon)
        self.v_layout.addWidget(self.thumb_label)
        
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(10, 5, 10, 10)
        
        filename = os.path.basename(path)
        self.name_label = BodyLabel(filename, self)
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

    def set_thumbnail(self, image_path):
        if image_path == "AUDIO": self.thumb_label.setPixmap(FluentIcon.MUSIC.icon().pixmap(48, 48))
        elif os.path.exists(image_path): self.thumb_label.setPixmap(QPixmap(image_path))

    def delete_file(self):
        reply = QMessageBox.question(self, "Sil", "Silmek istediğinize emin misiniz?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.exists(self.path): os.remove(self.path)
                self.deleteLater()
            except: pass

    def open_file(self):
        if platform.system() == 'Windows': os.startfile(self.path)
        
    def open_folder(self):
        folder = os.path.dirname(self.path)
        if platform.system() == 'Windows': os.startfile(folder)

class LibraryInterface(ScrollArea):
    """Kütüphane - GPU optimized scroll (FlowLayout için kritik)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("libraryInterface")
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.view.setObjectName("libraryView")
        self.setStyleSheet("ScrollArea{background: transparent; border: none;}")
        self.view.setStyleSheet("QWidget#libraryView{background: transparent;}")
        
        # GPU-optimized smooth scrolling (kritik - çok widget var)
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
        
        if self.flow_layout:
            while self.flow_layout.count():
                item = self.flow_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            self.flow_layout.deleteLater()
            
        self.flow_layout = FlowLayout()
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.setSpacing(20)
        self.v_layout.insertLayout(1, self.flow_layout)
        
        download_dir = get_os_download_dir()
        exts = ('.mp4', '.mp3', '.webm', '.mkv')
        if os.path.exists(download_dir):
            files = sorted([f for f in os.listdir(download_dir) if f.lower().endswith(exts)], 
                         key=lambda x: os.path.getmtime(os.path.join(download_dir, x)), reverse=True)
            for f in files:
                full_path = os.path.join(download_dir, f)
                item = LibraryItem(full_path, self.view)
                self.flow_layout.addWidget(item)
                self.library_items[full_path] = item
                self.thumb_queue.append(full_path)
    
    def on_thumbnail_ready(self, video_path, thumb_path):
        if video_path in self.library_items:
            self.library_items[video_path].set_thumbnail(thumb_path)

class SettingsInterface(ScrollArea):
    """Ayarlar - GPU optimized scroll"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsInterface")
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.view.setObjectName("settingsView")
        self.setStyleSheet("ScrollArea{background: transparent; border: none;}")
        self.view.setStyleSheet("QWidget#settingsView{background: transparent;}")
        
        # GPU-optimized smooth scrolling
        setup_smooth_scroll(self, enable_kinetic=True)
        
        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setContentsMargins(36, 36, 36, 36)
        self.v_layout.setSpacing(20)
        
        self.title = TitleLabel("Ayarlar", self.view)
        self.v_layout.addWidget(self.title)
        
        self.group_lang = SettingCardGroup("Dil / Language", self.view)
        self.lang_card = LanguageSettingCard(FluentIcon.LANGUAGE, "Uygulama Dili", "Arayüz dilini seçin", parent=self.view)
        self.group_lang.addSettingCard(self.lang_card)
        self.v_layout.addWidget(self.group_lang)

        self.group1 = SettingCardGroup("Kişiselleştirme", self.view)
        
        # Tema toggle
        self.theme_card = SwitchSettingCard(FluentIcon.BRIGHTNESS, "Uygulama Teması", "Karanlık/Aydınlık", parent=self.view)
        self.theme_card.switchButton.setChecked(True)
        self.theme_card.switchButton.checkedChanged.connect(lambda c: setTheme(Theme.DARK if c else Theme.LIGHT))
        self.group1.addSettingCard(self.theme_card)
        
        # Accent Color Picker
        self.color_card = AccentColorCard(FluentIcon.PALETTE, "Vurgu Rengi", "Arayüz vurgu rengini seçin", parent=self.view)
        self.group1.addSettingCard(self.color_card)
        
        self.v_layout.addWidget(self.group1)
        
        self.group2 = SettingCardGroup("İndirme", self.view)
        self.folder_card = PushSettingCard("Klasörü Seç", FluentIcon.FOLDER, "İndirme Konumu", get_os_download_dir(), self.view)
        self.folder_card.clicked.connect(self.select_folder)
        self.group2.addSettingCard(self.folder_card)
        
        self.speed_card = SliderSettingCard(FluentIcon.SPEED_HIGH, "İndirme Hızı Limiti", "Sınırsız", parent=self.view)
        self.speed_card.slider.setRange(0, 50)
        self.speed_card.slider.valueChanged.connect(self.on_speed_changed)
        self.group2.addSettingCard(self.speed_card)
        
        # Proxy
        self.proxy_card = LineEditSettingCard(
            FluentIcon.GLOBE,
            "Proxy Sunucusu",
            "Örn: http://user:pass@host:port",
            parent=self.view
        )
        self.group2.addSettingCard(self.proxy_card)
        
        self.v_layout.addWidget(self.group2)
        
        self.group3 = SettingCardGroup("Geliştiriciler", self.view)
        self.dev1_card = HyperlinkCard("https://github.com/kxrk0", "Proje Sahibi", FluentIcon.GITHUB, "kxrk0", "Open", self.view)
        self.group3.addSettingCard(self.dev1_card)
        self.dev2_card = HyperlinkCard("https://github.com/swaffX", "Geliştirici", FluentIcon.GITHUB, "swaffX", "Open", self.view)
        self.group3.addSettingCard(self.dev2_card)
        self.v_layout.addWidget(self.group3)
        self.v_layout.addStretch()
        
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "İndirme Klasörünü Seç", get_os_download_dir())
        if folder: self.folder_card.setContent(folder)
            
    def on_speed_changed(self, value):
        self.speed_card.setContent("Sınırsız" if value == 0 else f"{value} MB/s")
    
    def get_speed_limit(self):
        val = self.speed_card.slider.value()
        return f"{val}M" if val > 0 else None
        
    def get_proxy(self):
        return self.proxy_card.line_edit.text().strip() or None

class SwitchSettingCard(SettingCard):
    def __init__(self, icon, title, content, parent=None):
        super().__init__(icon, title, content, parent)
        self.switchButton = SwitchButton(self)
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

class LineEditSettingCard(SettingCard):
    def __init__(self, icon, title, content, parent=None):
        super().__init__(icon, title, content, parent)
        self.line_edit = LineEdit(self)
        self.line_edit.setPlaceholderText(content)
        self.line_edit.setFixedWidth(200)
        self.hBoxLayout.addWidget(self.line_edit, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

class LanguageSettingCard(SettingCard):
    """Dil seçici kart - i18n entegrasyonu"""
    
    # Dil kodu -> Görünen isim
    LANGUAGES = [
        ("tr", "Türkçe"),
        ("en", "English"),
        ("de", "Deutsch"),
    ]
    
    def __init__(self, icon, title, content, parent=None):
        super().__init__(icon, title, content, parent)
        self.comboBox = ComboBox(self)
        
        # Dil isimlerini ekle
        for lang_code, lang_name in self.LANGUAGES:
            self.comboBox.addItem(lang_name, userData=lang_code)
        
        # Mevcut dili seç
        current_lang = get_current_language()
        for i, (lang_code, _) in enumerate(self.LANGUAGES):
            if lang_code == current_lang:
                self.comboBox.setCurrentIndex(i)
                break
        
        # Dil değişikliği olayını bağla
        self.comboBox.currentIndexChanged.connect(self.on_language_changed)
        
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        
    def on_language_changed(self, index: int):
        """Dil değişikliği olayı"""
        if 0 <= index < len(self.LANGUAGES):
            lang_code = self.LANGUAGES[index][0]
            set_language(lang_code)
            
            # Kullanıcıya bilgi ver (yeniden başlatma gerekiyor)
            InfoBar.info(
                title="Dil Değiştirildi",
                content="Değişiklikler uygulamayı yeniden başlattığınızda geçerli olacak.",
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self.window()
            )

class SliderSettingCard(SettingCard):
    def __init__(self, icon, title, content, parent=None):
        super().__init__(icon, title, content, parent)
        self.slider = Slider(Qt.Orientation.Horizontal, self)
        self.slider.setFixedWidth(150)
        self.hBoxLayout.addWidget(self.slider, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

class AccentColorCard(SettingCard):
    """Vurgu rengi seçici kart"""
    
    # Fluent Design önerilen renkler
    ACCENT_COLORS = [
        ("#0078D4", "Mavi"),      # Windows Blue
        ("#0099BC", "Turkuaz"),
        ("#00B294", "Yeşil"),
        ("#00CC6A", "Açık Yeşil"),
        ("#FFB900", "Altın"),
        ("#FF8C00", "Turuncu"),
        ("#E81123", "Kırmızı"),
        ("#C30052", "Magenta"),
        ("#9A0089", "Mor"),
        ("#881798", "Koyu Mor"),
    ]
    
    def __init__(self, icon, title, content, parent=None):
        super().__init__(icon, title, content, parent)
        
        self.color_buttons = []
        self.color_layout = QHBoxLayout()
        self.color_layout.setSpacing(8)
        
        for color_hex, color_name in self.ACCENT_COLORS:
            btn = PushButton(self)
            btn.setFixedSize(28, 28)
            btn.setToolTip(color_name)
            btn.setStyleSheet(f"""
                PushButton {{
                    background-color: {color_hex};
                    border: 2px solid transparent;
                    border-radius: 14px;
                }}
                PushButton:hover {{
                    border: 2px solid white;
                }}
            """)
            btn.clicked.connect(lambda checked, c=color_hex: self.set_accent_color(c))
            self.color_buttons.append(btn)
            self.color_layout.addWidget(btn)
            
        self.hBoxLayout.addLayout(self.color_layout)
        self.hBoxLayout.addSpacing(16)
        
    def set_accent_color(self, color_hex: str):
        """Vurgu rengini değiştir"""
        setThemeColor(color_hex)
        
        # Seçili rengi vurgula
        for btn in self.color_buttons:
            if color_hex in btn.styleSheet():
                btn.setStyleSheet(btn.styleSheet().replace(
                    "border: 2px solid transparent",
                    "border: 2px solid white"
                ))
            else:
                # Reset border
                current = btn.styleSheet()
                if "border: 2px solid white" in current:
                    btn.setStyleSheet(current.replace(
                        "border: 2px solid white",
                        "border: 2px solid transparent"
                    ))

class InfoFetchWorker(QThread):
    info_ready = pyqtSignal(dict, list, bool)
    def __init__(self, downloader, url):
        super().__init__()
        self.downloader = downloader
        self.url = url
    def run(self):
        if "list=" in self.url and "watch?v=" not in self.url:
             is_playlist = True
             info = self.downloader.get_playlist_info(self.url)
             formats = []
        else:
            is_playlist = False
            info = self.downloader.get_video_info(self.url)
            formats = self.downloader.get_available_formats(self.url) if info else []
        self.info_ready.emit(info, formats, is_playlist)

class DownloadWorker(QThread):
    """İndirme işlemini yöneten worker thread"""
    progress_signal = pyqtSignal(dict)
    completed_signal = pyqtSignal(bool, str, str)
    cancelled_signal = pyqtSignal()
    
    def __init__(self, downloader, url, output_dir, format_id=None, is_audio=False, 
                 save_metadata=False, ratelimit=None, proxy=None, write_sub=False):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.output_dir = output_dir
        self.format_id = format_id
        self.is_audio = is_audio
        self.save_metadata = save_metadata
        self.ratelimit = ratelimit
        self.proxy = proxy
        self.write_sub = write_sub
        self.final_filename = None
        self.download_task = None
        self._cancelled = False
        
    def cancel(self):
        """İndirmeyi iptal et"""
        self._cancelled = True
        if self.download_task:
            self.download_task.cancel()
        self.cancelled_signal.emit()
        
    def is_cancelled(self) -> bool:
        return self._cancelled
        
    def progress_callback(self, d):
        if self._cancelled:
            return
            
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)
            progress = d.get('progress', 0)  # Yeni: fragment-based progress
            
            self.progress_signal.emit({
                'downloaded_bytes': downloaded,
                'total_bytes': total,
                'speed': speed,
                'filename': d.get('filename', ''),
                'status': 'downloading',
                'eta': eta,
                'progress': progress
            })
        elif d['status'] == 'finished':
            self.final_filename = d.get('filename', '')
            self.progress_signal.emit({'status': 'processing', 'filename': self.final_filename})
            
    def complete_callback(self, success, error=None):
        if self._cancelled:
            self.completed_signal.emit(False, "İndirme iptal edildi", "")
        else:
            self.completed_signal.emit(success, error if error else "", self.final_filename if success else "")
            
    def run(self):
        if self.is_audio:
            self.downloader.download_audio(
                self.url, 
                self.output_dir, 
                progress_callback=self.progress_callback, 
                complete_callback=self.complete_callback, 
                save_info=self.save_metadata, 
                ratelimit=self.ratelimit
            )
        else:
            # Yeni API kullan - DownloadTask döner
            self.download_task = self.downloader.download_video(
                self.url, 
                self.output_dir, 
                format_id=self.format_id, 
                progress_callback=self.progress_callback, 
                complete_callback=self.complete_callback, 
                cancel_callback=self.is_cancelled,  # İptal kontrolü
                save_info=self.save_metadata, 
                ratelimit=self.ratelimit, 
                write_sub=self.write_sub
            )

class MainWindow(FluentWindow):
    """
    Ana Pencere
    
    Özellikler:
    - System Tray entegrasyonu (minimize to tray)
    - Klavye kısayolları
    - Zamanlanmış görevler
    """
    def __init__(self):
        super().__init__()
        setTheme(Theme.DARK)
        setThemeColor('#0078D4')
        self.setWindowTitle("YouTube Studio Downloader")
        self.resize(900, 650)
        
        # İkon
        self.app_icon = QIcon("extension/icons/download.svg") if os.path.exists("extension/icons/download.svg") else QIcon()
        self.setWindowIcon(self.app_icon)
        
        # Downloader
        self.downloader = Downloader()
        self.scheduled_tasks = []
        
        # Zamanlayıcı
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.check_scheduled_tasks)
        self.scheduler_timer.start(1000)
        
        # Interface'ler
        self.home_interface = HomeInterface(self)
        self.queue_interface = QueueInterface(self)
        self.library_interface = LibraryInterface(self)
        self.settings_interface = SettingsInterface(self)
        
        # Kurulum
        self.init_navigation()
        self.init_system_tray()
        self.init_keyboard_shortcuts()
        
        # Başlangıçta güncelleme kontrolü
        self.check_for_updates_on_startup()
        
    def init_system_tray(self):
        """Sistem tepsisi entegrasyonu"""
        # Tray ikonu oluştur
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        self.tray_icon.setToolTip("YouTube Studio Downloader")
        
        # Tray menüsü oluştur
        tray_menu = QMenu()
        
        # Göster/Gizle
        show_action = QAction("Göster", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)
        
        # İndirilenler
        downloads_action = QAction("İndirilenler", self)
        downloads_action.triggered.connect(lambda: (self.show_window(), self.switchTo(self.queue_interface)))
        tray_menu.addAction(downloads_action)
        
        tray_menu.addSeparator()
        
        # Çıkış
        quit_action = QAction("Çıkış", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # Tray ikonuna tıklama
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        # Tray ikonunu göster
        self.tray_icon.show()
        
    def init_keyboard_shortcuts(self):
        """Klavye kısayolları"""
        # Ctrl+V: Panodan yapıştır
        shortcut_paste = QShortcut(QKeySequence("Ctrl+V"), self)
        shortcut_paste.activated.connect(self.paste_from_clipboard)
        
        # Ctrl+D: İndirmeyi başlat
        shortcut_download = QShortcut(QKeySequence("Ctrl+D"), self)
        shortcut_download.activated.connect(self.start_current_download)
        
        # Escape: İptal / Geri
        shortcut_escape = QShortcut(QKeySequence("Escape"), self)
        shortcut_escape.activated.connect(self.on_escape_pressed)
        
        # Ctrl+Q: Çıkış
        shortcut_quit = QShortcut(QKeySequence("Ctrl+Q"), self)
        shortcut_quit.activated.connect(self.quit_app)
        
    def paste_from_clipboard(self):
        """Panodan URL yapıştır"""
        text = get_clipboard_text()
        if text and self.home_interface.url_input:
            self.home_interface.url_input.setText(text)
            self.switchTo(self.home_interface)
            
    def start_current_download(self):
        """Mevcut URL'yi indir"""
        if self.home_interface.download_btn.isEnabled():
            self.home_interface.start_download()
            
    def on_escape_pressed(self):
        """Escape tuşuna basıldığında"""
        # Ana sayfaya dön
        self.switchTo(self.home_interface)
        
    def on_tray_activated(self, reason):
        """Tray ikonuna tıklandığında"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()
            
    def show_window(self):
        """Pencereyi göster ve ön plana getir"""
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.activateWindow()
        self.raise_()
        
    def closeEvent(self, event):
        """Pencere kapatıldığında tray'e minimize et"""
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "YouTube Studio Downloader",
                "Uygulama arka planda çalışmaya devam ediyor.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            event.ignore()
        else:
            event.accept()
            
    def quit_app(self):
        """Uygulamadan tamamen çık"""
        # Tüm indirmeleri iptal et
        self.downloader.cancel_all_downloads()
        
        # Tray ikonunu gizle
        self.tray_icon.hide()
        
        # Uygulamayı kapat
        QApplication.quit()
        
    def check_for_updates_on_startup(self):
        """Başlangıçta güncelleme kontrolü"""
        updater = get_auto_updater()
        updater.check_on_startup(callback=self.on_update_check_result)
        
    def on_update_check_result(self, update_info):
        """Güncelleme kontrolü sonucu"""
        if update_info and update_info.is_newer:
            # Yeni sürüm mevcut - bildirim göster
            QTimer.singleShot(2000, lambda: self.show_update_notification(update_info))
            
    def show_update_notification(self, update_info):
        """Güncelleme bildirimi göster"""
        from qfluentwidgets import InfoBar, InfoBarPosition
        
        current = get_current_version()
        new_version = update_info.version
        
        InfoBar.info(
            title=tr("update.available"),
            content=f"{tr('update.current_version')}: v{current} → {tr('update.new_version')}: v{new_version}",
            orient=Qt.Orientation.Vertical,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=10000,
            parent=self
        )
        
    def init_navigation(self):
        self.home_interface.setObjectName("homeInterface")
        self.queue_interface.setObjectName("queueInterface")
        self.library_interface.setObjectName("libraryInterface")
        self.settings_interface.setObjectName("settingsInterface")
        
        self.addSubInterface(self.home_interface, FluentIcon.HOME, "Ana Sayfa")
        self.addSubInterface(self.queue_interface, FluentIcon.DOWNLOAD, "İndirilenler")
        self.addSubInterface(self.library_interface, FluentIcon.LIBRARY, "Kütüphane")
        self.navigationInterface.addSeparator()
        self.addSubInterface(self.settings_interface, FluentIcon.SETTING, "Ayarlar", NavigationItemPosition.BOTTOM)
        
    def add_scheduled_task(self, time, url, path, format_id, type_str, save_meta):
        self.scheduled_tasks.append({
            'time': time,
            'args': (url, path, format_id, type_str, save_meta),
            'processed': False
        })
        
    def check_scheduled_tasks(self):
        now = QTime.currentTime()
        for task in self.scheduled_tasks:
            if not task['processed']:
                t = task['time']
                if t.hour() == now.hour() and t.minute() == now.minute():
                    self.start_download_process(*task['args'])
                    task['processed'] = True
                    InfoBar.info(title='Zamanlayıcı', content=f"İndirme başladı: {task['args'][0]}", position=InfoBarPosition.TOP_RIGHT, parent=self)

    def start_download_process(self, url, path, format_id, type_str, save_meta):
        """İndirme işlemini başlat"""
        card = self.queue_interface.add_download_item("İndirme Başlatılıyor...", url)
        is_audio = (type_str == 'audio')
        ratelimit = self.settings_interface.get_speed_limit()
        
        # Worker oluştur
        worker = DownloadWorker(self.downloader, url, path, format_id, is_audio, save_meta, ratelimit)
        
        # Sinyalleri bağla
        worker.progress_signal.connect(lambda d: self.update_download_card(card, d))
        worker.completed_signal.connect(lambda s, e, f: self.finish_download_card(card, s, e, f))
        worker.cancelled_signal.connect(lambda: card.set_cancelled())
        
        # Kart iptal butonunu worker'a bağla
        card.cancel_requested.connect(worker.cancel)
        card.worker = worker
        
        worker.start()
        self.switchTo(self.queue_interface)
        
    def update_download_card(self, card, data):
        """İndirme kartını güncelle"""
        if card.is_cancelled:
            return
            
        status = data.get('status')
        filename = data.get('filename', '')
        
        if filename and not card.file_path:
            card.title_lbl.setText(os.path.basename(filename))
            
        if status == 'downloading':
            downloaded = data.get('downloaded_bytes', 0)
            total = data.get('total_bytes', 0)
            speed_val = data.get('speed')
            if speed_val is None: speed_val = 0
            
            # Fragment-based progress varsa kullan, yoksa byte-based hesapla
            progress = data.get('progress', 0)
            if progress <= 0 and total and total > 0:
                progress = int((downloaded / total) * 100)
            
            speed = format_size(speed_val) + "/s"
            eta = format_duration(data.get('eta', 0))
            card.update_progress(progress, speed, eta)
            
        elif status == 'processing':
            card.status_lbl.setText("Dönüştürülüyor...")
            card.progress.setMaximum(0)
            
    def finish_download_card(self, card, success, error, filepath):
        if success:
            card.set_finished(filepath)
            InfoBar.success(title='Başarılı', content="İndirme tamamlandı.", duration=3000, parent=self)
        else:
            card.status_lbl.setText("Hata!")
            card.progress.hide()
            InfoBar.error(title='Hata', content=f"{error}", duration=5000, parent=self)

if __name__ == '__main__':
    if 'QT_SCALE_FACTOR' in os.environ: del os.environ['QT_SCALE_FACTOR']
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())