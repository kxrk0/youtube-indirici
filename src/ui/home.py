#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

from PyQt6.QtCore import Qt, QTimer, QTime, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QBrush
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QFileDialog

from qfluentwidgets import (
    ScrollArea, SmoothScrollArea, CardWidget, TitleLabel, SubtitleLabel, BodyLabel, StrongBodyLabel,
    LineEdit, PrimaryPushButton, PushButton, ComboBox, CheckBox,
    FluentIcon, InfoBar, TimePicker, MessageBoxBase, TextEdit
)

from src.ui.gpu_widgets import setup_smooth_scroll
from src.ui.workers import InfoFetchWorker, SpotifyInfoWorker
from src.utils.helpers import (
    is_valid_url, get_os_download_dir, get_clipboard_text,
)
from src.ui.components import VideoInfoCard
from src.ui.dialogs import PlaylistSelectionDialog


class SkeletonWidget(QWidget):
    """Yükleniyor efekti - monitör Hz'e göre dinamik FPS"""
    def __init__(self, width=None, height=None, radius=4, parent=None):
        super().__init__(parent)
        if width:
            self.setFixedWidth(width)
        if height:
            self.setFixedHeight(height)
        self.radius = radius
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_opacity)
        self.timer.start(16)  # ~60fps — animasyon için yeterli, daha sık repaint gereksiz
        self.opacity = 1.0
        self.direction = -0.015  # 60fps baz alınmış sabit adım
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("İndirmeyi Zamanla", self)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(20)
        h_layout = QHBoxLayout()
        h_layout.addWidget(BodyLabel("Başlangıç Saati:", self))
        h_layout.addStretch()
        self.time_picker = TimePicker(self)
        self.time_picker.setTime(QTime.currentTime().addSecs(60))
        h_layout.addWidget(self.time_picker)
        self.viewLayout.addLayout(h_layout)
        self.yesButton.setText("Zamanla")
        self.cancelButton.setText("İptal")
        self.widget.setMinimumWidth(350)

    def get_time(self):
        return self.time_picker.time()


class HomeInterface(SmoothScrollArea):
    """Ana sayfa - URL girişi ve hızlı indirme"""

    _info_cache: dict = {}        # url → {'info': dict, 'formats': list, 'ts': float}
    _CACHE_TTL:  int  = 300       # 5 dakika

    # Cross-thread signals
    _disk_signal = pyqtSignal(str)   # disk estimate message from background thread

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homeInterface")
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.view.setObjectName("homeView")
        self.setStyleSheet("ScrollArea{background: transparent; border: none;}")
        self.view.setStyleSheet("QWidget#homeView{background: transparent;}")
        setup_smooth_scroll(self, enable_kinetic=False)
        self.setScrollAnimation(Qt.Orientation.Vertical, 500)
        self._current_info = None
        self._is_live = False
        self.worker = None
        # Connect cross-thread signal → GUI slot (queued automatically for different threads)
        self._disk_signal.connect(self._show_disk_estimate)
        self.init_ui()

    def init_ui(self):
        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setSpacing(20)
        self.v_layout.setContentsMargins(30, 30, 30, 30)

        self.title_label = TitleLabel("YDL İndirici", self.view)
        self.v_layout.addWidget(self.title_label)

        # URL giriş kartı
        self.input_card = CardWidget(self.view)
        input_layout = QVBoxLayout(self.input_card)
        input_row = QHBoxLayout()

        self.url_input = LineEdit(self.view)
        self.url_input.setPlaceholderText("YouTube, SoundCloud, TikTok, Instagram, Twitter/X, Vimeo, Spotify, Twitch... (Birden fazla URL yapıştırın → otomatik toplu mod)")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.textChanged.connect(self.on_url_changed)
        self.url_input.textChanged.connect(self._detect_multi_url_paste)

        self.paste_btn = PushButton(FluentIcon.PASTE, "Yapıştır", self.view)
        self.paste_btn.clicked.connect(self.paste_from_clipboard)

        self.batch_btn = PushButton(FluentIcon.ADD, "Toplu", self.view)
        self.batch_btn.setToolTip("URL Listesi Yapıştır (Batch İndirme)")
        self.batch_btn.clicked.connect(self.show_batch_dialog)

        input_row.addWidget(self.url_input)
        input_row.addWidget(self.paste_btn)
        input_row.addWidget(self.batch_btn)
        input_layout.addLayout(input_row)
        self.v_layout.addWidget(self.input_card)

        # Skeleton ve video bilgi kartı
        self.skeleton_card = VideoInfoSkeleton(self.view)
        self.skeleton_card.hide()
        self.v_layout.addWidget(self.skeleton_card)

        self.video_info_card = VideoInfoCard(self.view)
        self.video_info_card.hide()
        self.v_layout.addWidget(self.video_info_card)

        # Seçenekler kartı
        self.options_card = CardWidget(self.view)
        self.options_layout = QVBoxLayout(self.options_card)
        self.options_layout.setSpacing(15)
        self.options_layout.addWidget(SubtitleLabel("İndirme Ayarları", self.view))

        opts_row1 = QHBoxLayout()
        self.type_combo = ComboBox(self.view)
        self.type_combo.addItems(["Video (MP4/WebM)", "Ses (MP3)"])
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)

        self.quality_combo = ComboBox(self.view)
        self.quality_combo.addItems(["En İyi Kalite (Otomatik)", "best"])

        self.auto_quality_label = BodyLabel("", self.view)
        self.auto_quality_label.setStyleSheet("color: #00cc6a; font-weight: bold;")
        self.auto_quality_label.hide()

        opts_row1.addWidget(StrongBodyLabel("Tür:", self.view))
        opts_row1.addWidget(self.type_combo)
        opts_row1.addSpacing(20)
        opts_row1.addWidget(StrongBodyLabel("Kalite:", self.view))
        opts_row1.addWidget(self.quality_combo)
        opts_row1.addWidget(self.auto_quality_label)
        opts_row1.addStretch()
        self.options_layout.addLayout(opts_row1)

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

        self.meta_check = CheckBox("Meta verileri kaydet (JSON)", self.view)
        self.thumb_check = CheckBox("Küçük resmi göm", self.view)
        self.thumb_check.setChecked(True)
        self.subs_check = CheckBox("Altyazıları indir (TR/EN)", self.view)
        self.options_layout.addWidget(self.meta_check)
        self.options_layout.addWidget(self.thumb_check)
        self.options_layout.addWidget(self.subs_check)

        self.options_layout.addWidget(SubtitleLabel("Gelişmiş Seçenekler", self.view))

        self.normalize_check = CheckBox("Ses normalizasyonu (loudnorm -16 LUFS)", self.view)
        self.normalize_check.setToolTip("Ses seviyesini normalize eder - özellikle podcast/müzik için önerilir")
        self.options_layout.addWidget(self.normalize_check)

        self.sponsorblock_check = CheckBox("SponsorBlock — reklam/tanıtım segmentlerini sil", self.view)
        self.sponsorblock_check.setToolTip("Sponsor, intro, outro, selfpromo bölümlerini FFmpeg ile keser (yalnızca YouTube)")
        self.options_layout.addWidget(self.sponsorblock_check)

        self.delta_sync_check = CheckBox("Delta Sync — sadece yeni videoları indir (playlist/kanal)", self.view)
        self.delta_sync_check.setToolTip("Daha önce indirilen URL'leri atla. Büyük kanallar için kullanışlı.")
        self.options_layout.addWidget(self.delta_sync_check)

        # Disk boyutu tahmini gösterge
        self.disk_estimate_lbl = BodyLabel("", self.view)
        self.disk_estimate_lbl.setStyleSheet("color:#f0ad4e; font-size:11px;")
        self.disk_estimate_lbl.hide()
        self.options_layout.addWidget(self.disk_estimate_lbl)

        trim_row = QHBoxLayout()
        self.trim_check = CheckBox("Video kes:", self.view)
        self.trim_check.toggled.connect(self.on_trim_toggled)

        self.start_time_input = LineEdit(self.view)
        self.start_time_input.setPlaceholderText("Başlangıç (0:30)")
        self.start_time_input.setFixedWidth(100)
        self.start_time_input.setEnabled(False)

        self.end_time_input = LineEdit(self.view)
        self.end_time_input.setPlaceholderText("Bitiş (2:30)")
        self.end_time_input.setFixedWidth(100)
        self.end_time_input.setEnabled(False)

        trim_row.addWidget(self.trim_check)
        trim_row.addWidget(self.start_time_input)
        trim_row.addWidget(BodyLabel("-", self.view))
        trim_row.addWidget(self.end_time_input)
        trim_row.addStretch()
        self.options_layout.addLayout(trim_row)

        self.live_badge = BodyLabel("🔴 CANLI YAYIN", self.view)
        self.live_badge.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 13px;")
        self.live_badge.hide()
        self.options_layout.addWidget(self.live_badge)
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

    # Platforms that truly cannot be downloaded (non-Spotify DRM)
    _DRM_HOSTS = ('music.apple.com', 'tidal.com', 'deezer.com')

    @staticmethod
    def _is_drm_url(url: str) -> bool:
        return any(h in url for h in HomeInterface._DRM_HOSTS)

    @staticmethod
    def _is_spotify_url(url: str) -> bool:
        return 'open.spotify.com' in url

    @staticmethod
    def _is_channel_url(url: str) -> bool:
        import re
        return bool(re.search(
            r'youtube\.com/(@[\w.-]+|channel/[\w-]+|c/[\w-]+|user/[\w-]+)\s*/?(\?.*)?$', url
        ))

    def _detect_multi_url_paste(self, text: str):
        """Çoklu URL yapıştırılırsa otomatik toplu mod aç."""
        if '\n' not in text:
            return
        from src.utils.helpers import is_valid_url as _iv
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        valid = [l for l in lines if _iv(l)]
        if len(valid) >= 2:
            # Input temizle, batch dialog aç
            self.url_input.blockSignals(True)
            self.url_input.clear()
            self.url_input.blockSignals(False)
            # Pre-fill the dialog's text area
            self._pending_batch_urls = '\n'.join(valid)
            self.show_batch_dialog()

    def on_url_changed(self, text):
        # Non-Spotify DRM platformları: hemen hata göster
        if is_valid_url(text) and self._is_drm_url(text):
            self.search_timer.stop()
            self.skeleton_card.hide()
            self.auto_quality_label.hide()
            self.live_badge.hide()
            self.video_info_card.reset_info()
            self.video_info_card.title_lbl.setText("⛔ DRM Korumalı — İndirilemez")
            self.video_info_card.channel_lbl.setText(
                "Apple Music / Tidal / Deezer şifreli DRM kullanır — desteklenmiyor."
            )
            self.video_info_card.show()
            self.download_btn.setEnabled(False)
            self.schedule_btn.setEnabled(False)
            self._current_info = None
            self._is_live = False
            return

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
            self.live_badge.hide()
            self.download_btn.setText("İndirmeyi Başlat")
            self.download_btn.setIcon(FluentIcon.DOWNLOAD)
            self.download_btn.setEnabled(False)
            self.schedule_btn.setEnabled(False)
            self._current_info = None
            self._is_live = False

    def fetch_video_info(self):
        import time as _time
        url = self.url_input.text()
        if not is_valid_url(url):
            return

        # Spotify: özel oEmbed worker — yt-dlp çağırma
        if self._is_spotify_url(url):
            self.worker = SpotifyInfoWorker(url)
            self.worker.info_ready.connect(self.on_info_ready)
            self.worker.start()
            return

        # YouTube Kanal URL'si: kanal video listesi dialog
        if self._is_channel_url(url):
            self.skeleton_card.hide()
            self._show_channel_download_dialog(url)
            return

        # URL cache — aynı URL'yi tekrar fetch etme
        cached = HomeInterface._info_cache.get(url)
        if cached and (_time.time() - cached['ts']) < self._CACHE_TTL:
            self.skeleton_card.hide()
            self.on_info_ready(cached['info'], cached['formats'], False)
            return

        main_window = self.window()
        if hasattr(main_window, 'downloader'):
            self.worker = InfoFetchWorker(main_window.downloader, url)
            self.worker.info_ready.connect(self.on_info_ready)
            self.worker.info_ready.connect(lambda info, fmts, pl, u=url: self._cache_info(u, info, fmts))
            self.worker.start()

    def _cache_info(self, url: str, info: dict, formats: list):
        import time as _time
        if info:
            HomeInterface._info_cache[url] = {'info': info, 'formats': formats, 'ts': _time.time()}

    def on_info_ready(self, info, formats, is_playlist):
        self.skeleton_card.hide()
        # Disk boyutu tahmini arka planda başlat
        url = self.url_input.text()
        if info and url and not info.get('is_spotify'):
            self._estimate_disk_size(url)
        if not info:
            url = self.url_input.text()
            if self._is_drm_url(url):
                self.video_info_card.title_lbl.setText("⛔ DRM Korumalı — İndirilemez")
            else:
                self.video_info_card.title_lbl.setText("Bilgi alınamadı! URL geçerli mi?")
            self.video_info_card.show()
            self.download_btn.setEnabled(False)
            self.auto_quality_label.hide()
            return

        # Spotify: yalnızca MP3 indirme, format combo'yu sınırla
        if info.get('is_spotify'):
            self._current_info = info          # ← thumbnail_url buradan aktarılır
            self._is_live = False
            self.video_info_card.update_info(info)
            self.video_info_card.show()
            self.quality_combo.clear()
            self.quality_combo.addItem("🎵 MP3 (En İyi Kalite)", "spotify_audio")
            self.quality_combo.setEnabled(False)
            self.type_combo.setCurrentIndex(1)   # Ses (MP3)
            self.type_combo.setEnabled(False)
            self.download_btn.setEnabled(True)
            self.schedule_btn.setEnabled(False)
            self.auto_quality_label.hide()
            return

        self._current_info = info
        self._is_live = info.get('is_live', False) or info.get('was_live', False)

        if is_playlist:
            self.video_info_card.hide()
            dialog = PlaylistSelectionDialog(info, self.window())
            if dialog.exec():
                selected = dialog.get_selected_videos()
                if selected:
                    self.start_playlist_download(selected)
            else:
                self.url_input.clear()
        else:
            self.video_info_card.update_info(info)
            self.video_info_card.show()
            self.download_btn.setEnabled(True)
            self.schedule_btn.setEnabled(not self._is_live)

            if self._is_live:
                self.live_badge.show()
                self.download_btn.setText("Kaydı Başlat")
                self.download_btn.setIcon(FluentIcon.PLAY)
                self.quality_combo.setEnabled(False)
                self.trim_check.setEnabled(False)
            else:
                self.live_badge.hide()
                self.download_btn.setText("İndirmeyi Başlat")
                self.download_btn.setIcon(FluentIcon.DOWNLOAD)
                self.quality_combo.setEnabled(True)

            if not formats and 'formats' in info:
                formats = info['formats']
            self.populate_formats(formats)
            self.auto_quality_label.hide()

    def populate_formats(self, formats):
        self.quality_combo.clear()
        self.quality_combo.addItem("En İyi Kalite (Otomatik)", "best")
        available = []
        for fmt in formats:
            try:
                format_id = fmt.get('format_id')
                height = fmt.get('height')
                resolution = fmt.get('resolution')
                ext = fmt.get('ext')
                vcodec = fmt.get('vcodec', '')
                filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                fps = fmt.get('fps')
                dynamic_range = fmt.get('dynamic_range')

                if vcodec == 'none' or not vcodec:
                    continue

                if height is None and resolution and 'x' in resolution:
                    try:
                        height = int(resolution.split('x')[1])
                    except Exception:
                        pass

                height_val = int(height) if height else 0
                res_str = f"{height_val}p" if height_val > 0 else "Bilinmeyen"
                codec_str = self._format_codec(vcodec)
                fps_str = f"{int(fps)}fps" if fps and fps > 30 else ""
                hdr_str = "HDR" if dynamic_range and dynamic_range != 'SDR' else ""
                size_str = self._format_size(filesize) if filesize else "?"
                display_ext = f"{ext}→MP4" if ext in ['webm', 'mkv'] else ext.upper()

                parts = [res_str]
                if codec_str:
                    parts.append(codec_str)
                if fps_str:
                    parts.append(fps_str)
                if hdr_str:
                    parts.append(hdr_str)
                parts.append(f"[{display_ext}]")
                parts.append(f"({size_str})")

                available.append((format_id, " ".join(parts), height_val, fps or 0))
            except Exception:
                continue

        seen = set()
        for fmt_id, label, h, f in sorted(available, key=lambda x: (x[2], x[3]), reverse=True):
            if label not in seen:
                self.quality_combo.addItem(label, f"{fmt_id}+bestaudio/best")
                seen.add(label)

    @staticmethod
    def _format_size(bytes_size) -> str:
        if not bytes_size or bytes_size < 0:
            return "?"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f}{unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f}GB"

    @staticmethod
    def _format_codec(vcodec: str) -> str:
        if not vcodec or vcodec == 'none':
            return ""
        v = vcodec.lower()
        if 'av01' in v or 'av1' in v:
            return "AV1"
        if 'vp9' in v or 'vp09' in v:
            return "VP9"
        if 'hvc1' in v or 'hev1' in v or 'hevc' in v or 'h265' in v:
            return "H.265"
        if 'avc1' in v or 'avc' in v or 'h264' in v:
            return "H.264"
        if 'vp8' in v:
            return "VP8"
        return vcodec[:8] if len(vcodec) > 8 else vcodec

    # ─── Disk Boyutu Tahmini ──────────────────────────────────────────────────

    def _estimate_disk_size(self, url: str):
        """Arka planda yt-dlp --simulate ile boyut tahmini yap."""
        import threading
        def _do():
            try:
                import yt_dlp, shutil
                ydl_opts = {'quiet': True, 'no_warnings': True, 'simulate': True, 'format': 'bestvideo+bestaudio/best'}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                if not info:
                    return
                size = info.get('filesize') or info.get('filesize_approx') or 0
                if size <= 0:
                    return
                from src.utils.helpers import format_size
                disk_free = shutil.disk_usage(self.path_input.text()).free
                msg = f"Tahmini boyut: ~{format_size(size)}"
                if disk_free < size * 1.2:
                    msg += f"  ⚠ Yetersiz disk (boş: {format_size(disk_free)})"
                self._disk_signal.emit(msg)
            except Exception:
                pass
        threading.Thread(target=_do, daemon=True).start()

    def _show_disk_estimate(self, msg: str):
        self.disk_estimate_lbl.setText(msg)
        self.disk_estimate_lbl.show()

    def paste_from_clipboard(self):
        text = get_clipboard_text()
        if text:
            self.url_input.setText(text)

    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Klasör Seç", self.path_input.text())
        if dir_path:
            self.path_input.setText(dir_path)

    def show_batch_dialog(self):
        class BatchDownloadDialog(MessageBoxBase):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.titleLabel.setText("Toplu İndirme")
                self.viewLayout.addWidget(BodyLabel("Her satıra bir URL yazın, yapıştırın veya .txt dosyası içe aktarın:", self))
                self.url_text = TextEdit(self)
                self.url_text.setPlaceholderText(
                    "https://youtube.com/watch?v=...\nhttps://youtube.com/watch?v=..."
                )
                self.url_text.setMinimumSize(420, 200)
                self.viewLayout.addWidget(self.url_text)
                import_btn = PushButton(FluentIcon.FOLDER, ".txt Dosyası İçe Aktar", self)
                import_btn.clicked.connect(self._import_txt)
                self.viewLayout.addWidget(import_btn)
                self.yesButton.setText("İndir")
                self.cancelButton.setText("İptal")

            def _import_txt(self):
                path, _ = QFileDialog.getOpenFileName(
                    self, "URL Listesi Aç", "", "Metin Dosyaları (*.txt);;Tüm Dosyalar (*)"
                )
                if path:
                    try:
                        with open(path, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                        self.url_text.setPlainText(content)
                    except Exception as e:
                        pass

            def get_urls(self):
                urls = []
                for line in self.url_text.toPlainText().strip().split('\n'):
                    line = line.strip()
                    if line and is_valid_url(line):
                        urls.append(line)
                return urls

        dialog = BatchDownloadDialog(self.window())
        # Önceden doldurulmuş URL varsa yerleştir
        if hasattr(self, '_pending_batch_urls') and self._pending_batch_urls:
            dialog.url_text.setPlainText(self._pending_batch_urls)
            self._pending_batch_urls = ''
        if dialog.exec():
            urls = dialog.get_urls()
            if urls:
                self.process_batch_urls(urls)
            else:
                InfoBar.warning(title="Uyarı", content="Geçerli URL bulunamadı!", duration=3000, parent=self)

    def process_batch_urls(self, urls: list):
        path = self.path_input.text()
        type_str = 'video' if self.type_combo.currentIndex() == 0 else 'audio'
        save_meta = self.meta_check.isChecked()
        write_sub = self.subs_check.isChecked()
        delta = hasattr(self, 'delta_sync_check') and self.delta_sync_check.isChecked()
        main_window = self.window()
        if hasattr(main_window, 'start_download_process'):
            added = 0
            skipped = 0
            for url in urls:
                if delta:
                    try:
                        from src.core.database import get_download_history
                        if get_download_history().is_url_downloaded(url):
                            skipped += 1
                            continue
                    except Exception:
                        pass
                main_window.start_download_process(url, path, 'best', type_str, save_meta, write_sub)
                added += 1
            msg = f"{added} video sıraya eklendi."
            if skipped:
                msg += f" {skipped} Delta Sync ile atlandı."
            InfoBar.success(
                title='Toplu İndirme Başlatıldı',
                content=msg,
                duration=4000, parent=self
            )

    # ─── Kanal İndirme ───────────────────────────────────────────────────────

    def _show_channel_download_dialog(self, channel_url: str):
        """Kanal videolarını listeler, seçilenleri indirir."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
            QListWidgetItem, QDialogButtonBox, QProgressDialog
        )
        from PyQt6.QtCore import Qt, QThread
        from qfluentwidgets import SubtitleLabel, BodyLabel, PushButton as PB, CheckBox as CB

        # Önce video listesini al
        fetch_dlg = QProgressDialog("Kanal videoları alınıyor…", "İptal", 0, 0, self.window())
        fetch_dlg.setWindowTitle("Kanal")
        fetch_dlg.setMinimumDuration(0)
        fetch_dlg.setValue(0)
        fetch_dlg.show()

        videos = []
        error_msg = ['']

        class _FetchWorker(QThread):
            def __init__(self, url):
                super().__init__()
                self.url = url
            def run(self):
                try:
                    import yt_dlp
                    opts = {
                        'extract_flat': 'in_playlist',
                        'quiet': True,
                        'no_warnings': True,
                        'playlist_end': 100,
                    }
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(self.url, download=False)
                        if info:
                            entries = info.get('entries') or []
                            for e in entries:
                                if e and e.get('url') or e.get('id'):
                                    vid_url = e.get('url') or f"https://youtube.com/watch?v={e['id']}"
                                    videos.append({'url': vid_url, 'title': e.get('title', vid_url)})
                except Exception as ex:
                    error_msg[0] = str(ex)

        worker = _FetchWorker(channel_url)
        worker.finished.connect(fetch_dlg.close)

        def _on_done():
            fetch_dlg.close()
            if error_msg[0]:
                InfoBar.error(title='Kanal Hatası', content=error_msg[0][:120], duration=5000, parent=self)
                return
            if not videos:
                InfoBar.warning(title='Kanal', content='Video bulunamadı.', duration=4000, parent=self)
                return
            # Seçim dialogu
            dlg = QDialog(self.window())
            dlg.setWindowTitle(f"Kanal İndirme — {len(videos)} video")
            dlg.resize(520, 520)
            lay = QVBoxLayout(dlg)

            lay.addWidget(SubtitleLabel(f"{len(videos)} video bulundu"))
            lay.addWidget(BodyLabel("İndirmek istediklerini seç:"))

            # Tümünü seç
            sel_row = QHBoxLayout()
            sel_all = PB(FluentIcon.COMPLETED, "Tümünü Seç", dlg)
            sel_none = PB(FluentIcon.CLOSE, "Seçimi Kaldır", dlg)
            sel_row.addWidget(sel_all)
            sel_row.addWidget(sel_none)
            sel_row.addStretch()
            lay.addLayout(sel_row)

            lst = QListWidget(dlg)
            lst.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            for v in videos:
                item = QListWidgetItem(v['title'])
                item.setData(Qt.ItemDataRole.UserRole, v['url'])
                lst.addItem(item)
            lay.addWidget(lst)

            sel_all.clicked.connect(lst.selectAll)
            sel_none.clicked.connect(lst.clearSelection)

            # Tür seçimi
            type_row = QHBoxLayout()
            type_row.addWidget(BodyLabel("Tür:"))
            audio_cb = CB("Ses (MP3)", dlg)
            type_row.addWidget(audio_cb)
            type_row.addStretch()
            lay.addLayout(type_row)

            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dlg
            )
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            lay.addWidget(btns)

            if dlg.exec():
                selected = [lst.item(i).data(Qt.ItemDataRole.UserRole)
                            for i in range(lst.count())
                            if lst.item(i).isSelected()]
                if selected:
                    type_str = 'audio' if audio_cb.isChecked() else 'video'
                    path = self.path_input.text()
                    main_window = self.window()
                    for u in selected:
                        main_window.start_download_process(u, path, 'best', type_str, False)
                    InfoBar.success(
                        title='Kanal İndirme',
                        content=f"{len(selected)} video sıraya eklendi.",
                        duration=4000, parent=self
                    )
                    self.url_input.clear()

        worker.finished.connect(_on_done)
        worker.start()
        self._channel_worker = worker  # GC'den koru

    def on_type_changed(self, index):
        is_video = (index == 0)
        self.quality_combo.setEnabled(is_video)
        self.trim_check.setEnabled(is_video)
        if not is_video:
            self.trim_check.setChecked(False)

    def on_trim_toggled(self, checked):
        self.start_time_input.setEnabled(checked)
        self.end_time_input.setEnabled(checked)

    def start_download(self):
        url = self.url_input.text()

        # Delta Sync — daha önce indirilmiş mi?
        if hasattr(self, 'delta_sync_check') and self.delta_sync_check.isChecked():
            try:
                from src.core.database import get_download_history
                if get_download_history().is_url_downloaded(url):
                    InfoBar.info(
                        title='Delta Sync',
                        content='Bu URL zaten indirildi — atlandı.',
                        duration=4000, parent=self
                    )
                    return
            except Exception:
                pass

        path = self.path_input.text()
        format_id = self.quality_combo.currentData() or 'best'
        save_meta = self.meta_check.isChecked()
        write_sub = self.subs_check.isChecked()
        type_str = 'video' if self.type_combo.currentIndex() == 0 else 'audio'
        normalize_audio = self.normalize_check.isChecked()
        start_time = self.start_time_input.text().strip() if self.trim_check.isChecked() else None
        end_time = self.end_time_input.text().strip() if self.trim_check.isChecked() else None

        # Duplicate URL detection — warn if URL already successfully downloaded
        try:
            from src.core.database import get_download_history
            matches = get_download_history().search_downloads(url, limit=5)
            already = any(r.get('url') == url and r.get('status') == 'completed' for r in matches)
            if already:
                InfoBar.warning(
                    title='Tekrar İndirme',
                    content='Bu URL daha önce indirildi. Yine de devam edilecek.',
                    duration=4000, parent=self
                )
        except Exception:
            pass

        sponsorblock = self.sponsorblock_check.isChecked()

        # Auto-categorize rules
        try:
            from src.core.auto_categorize import apply_rules
            info_pre = self._current_info or {}
            cat = apply_rules(
                url=url,
                title=info_pre.get('title', ''),
                channel=info_pre.get('uploader') or info_pre.get('channel', ''),
                base_output_dir=path,
            )
            if cat.get('output_dir'):
                path = cat['output_dir']
                os.makedirs(path, exist_ok=True)
            if cat.get('type_override') and not self._is_live:
                type_str = cat['type_override']
        except Exception:
            pass

        main_window = self.window()
        if hasattr(main_window, 'start_download_process'):
            info = self._current_info or {}
            main_window.start_download_process(
                url, path, format_id, type_str, save_meta, write_sub,
                normalize_audio=normalize_audio,
                start_time=start_time,
                end_time=end_time,
                is_live=self._is_live,
                thumbnail_url=info.get('thumbnail', ''),
                video_title=info.get('title', ''),
                channel=info.get('uploader') or info.get('channel', ''),
                duration=info.get('duration') or 0,
                sponsorblock=sponsorblock,
            )
            label = "Kayıt başladı." if self._is_live else "İndirme başladı."
            InfoBar.success(title='Sıraya Alındı', content=label, duration=3000, parent=self)
            self._reset_ui()

    def schedule_download(self):
        dialog = ScheduleDialog(self.window())
        if dialog.exec():
            time = dialog.get_time()
            url = self.url_input.text()
            path = self.path_input.text()
            format_id = self.quality_combo.currentData() or 'best'
            save_meta = self.meta_check.isChecked()
            write_sub = self.subs_check.isChecked()
            type_str = 'video' if self.type_combo.currentIndex() == 0 else 'audio'
            main_window = self.window()
            if hasattr(main_window, 'add_scheduled_task'):
                main_window.add_scheduled_task(time, url, path, format_id, type_str, save_meta, write_sub)
                InfoBar.success(
                    title='Zamanlandı',
                    content=f"İndirme {time.toString('HH:mm')} için planlandı.",
                    duration=3000, parent=self
                )
                self.url_input.clear()
                self.video_info_card.reset_info()
                self.video_info_card.hide()

    def start_playlist_download(self, videos):
        path = self.path_input.text()
        type_str = 'video' if self.type_combo.currentIndex() == 0 else 'audio'
        save_meta = self.meta_check.isChecked()
        write_sub = self.subs_check.isChecked()
        main_window = self.window()
        if hasattr(main_window, 'start_download_process'):
            for vid in videos:
                main_window.start_download_process(vid['url'], path, 'best', type_str, save_meta, write_sub)
            InfoBar.success(
                title='Playlist Başlatıldı',
                content=f"{len(videos)} video eklendi.",
                duration=3000, parent=self
            )
            self.url_input.clear()

    def _reset_ui(self):
        self.url_input.clear()
        self.video_info_card.reset_info()
        self.live_badge.hide()
        self._current_info = None
        self._is_live = False
        self.download_btn.setText("İndirmeyi Başlat")
        self.download_btn.setIcon(FluentIcon.DOWNLOAD)
        self.quality_combo.clear()
        self.quality_combo.addItem("En İyi (Otomatik)", "best")
        self.quality_combo.setEnabled(True)
        self.type_combo.setEnabled(True)
