#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import shutil
import threading

from PyQt6.QtCore import Qt, QTimer, QTime, pyqtSignal
from PyQt6.QtGui import QIcon, QAction, QShortcut, QKeySequence
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon as FIF,
    InfoBar, InfoBarPosition, setTheme, Theme, setThemeColor
)

from src.core.downloader import Downloader
from src.core.database import get_download_history
from src.ui.home import HomeInterface
from src.ui.queue import QueueInterface
from src.ui.library import LibraryInterface
from src.ui.settings import SettingsInterface
from src.ui.history import HistoryInterface
from src.ui.workers import DownloadWorker
from src.ui.mini_window import MiniWindow
from src.ui.notification_center import NotificationPanel
from src.utils.helpers import (
    format_size, format_duration, get_clipboard_text, is_valid_url
)
from src.utils.updater import get_auto_updater, get_current_version
from src.utils.i18n import tr
from src.utils import config as cfg


def _send_native_notification(title: str, body: str, tray_icon=None):
    """Windows native bildirimi gönderir, başarısız olursa tray mesajına düşer."""
    try:
        from win11toast import notify
        notify(title, body)
        return
    except Exception:
        pass
    if tray_icon:
        tray_icon.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 3000)


class MainWindow(FluentWindow):
    """Ana pencere - navigation shell"""

    MAX_CONCURRENT_DOWNLOADS = 3

    # Cross-thread signals (emitted from background threads → processed on GUI thread)
    _sub_new_video_signal = pyqtSignal(str, str, str, str)  # url, output_path, format_type, title

    def __init__(self, downloader=None):
        super().__init__()

        # Cross-thread signal connections (must be done on GUI thread)
        self._sub_new_video_signal.connect(self._on_sub_new_video)

        # Tema ve renk ayarlarını config'den yükle
        saved_theme = cfg.get('theme', 'dark')
        setTheme(Theme.DARK if saved_theme == 'dark' else Theme.LIGHT)
        setThemeColor(cfg.get('accent_color', '#0078D4'))

        self.setWindowTitle("YouTube Studio Downloader")
        self.setMinimumSize(960, 640)
        saved_w = max(int(cfg.get('window_width', 1100)), 1100)
        saved_h = max(int(cfg.get('window_height', 720)), 720)
        self.resize(saved_w, saved_h)

        self.app_icon = (
            QIcon("extension/icons/download.svg")
            if os.path.exists("extension/icons/download.svg")
            else QIcon()
        )
        self.setWindowIcon(self.app_icon)

        # Shared Downloader örneği
        self.downloader = downloader or Downloader()

        # Paralel indirme semafor — config'den limit al, default 3
        try:
            _limit = int(cfg.get('max_concurrent', self.MAX_CONCURRENT_DOWNLOADS))
        except Exception:
            _limit = self.MAX_CONCURRENT_DOWNLOADS
        self.download_semaphore = threading.Semaphore(_limit)

        self.scheduled_tasks = []

        # Zamanlayıcı
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.check_scheduled_tasks)
        self.scheduler_timer.start(1000)

        # Sayfalar
        self.home_interface = HomeInterface(self)
        self.queue_interface = QueueInterface(self)
        self.library_interface = LibraryInterface(self)
        self.history_interface = HistoryInterface(self)
        self.settings_interface = SettingsInterface(self)

        self.init_navigation()

        # Mini pencere + Bildirim merkezi — init_system_tray'den ÖNCE olmalı
        self._mini_window = MiniWindow()
        self._notif_panel = NotificationPanel(self)

        self.init_system_tray()
        self.init_keyboard_shortcuts()
        self.check_for_updates_on_startup()
        self._active_downloads = 0
        self.setAcceptDrops(True)

        # Connect history retry signal
        self.history_interface.retry_requested.connect(self._handle_retry)

        # Kısayollar
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._mini_window.toggle)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(
            lambda: self._notif_panel.toggle(self.geometry().topRight()))

        # Plugin sistemini başlat
        try:
            from src.core.plugin_manager import load_plugins, create_example_plugin
            create_example_plugin()
            load_plugins()
        except Exception as e:
            print(f"[Plugins] {e}")

        # Pano monitörü — 2 sn'de bir kontrol et, geçerli URL gelince ana sayfaya yansıt
        self._clipboard_prev = ''
        self._clipboard_timer = QTimer(self)
        self._clipboard_timer.timeout.connect(self._check_clipboard)
        self._clipboard_timer.start(2000)

        # Abonelik kontrolü zamanlayıcısı
        self._sub_timer = QTimer(self)
        self._sub_timer.timeout.connect(self._check_subscriptions)
        self._sub_timer.start(6 * 3600 * 1000)  # default 6 saat; settings değişince yenile

        # Zamanlanmış görev kontrolü (her dakika)
        self._scheduler_timer = QTimer(self)
        self._scheduler_timer.timeout.connect(self._check_scheduled_tasks)
        self._scheduler_timer.start(60 * 1000)

        # Bekleyen kuyruğu geri yükle (önceki oturumdan kalan indirmeler)
        QTimer.singleShot(1500, self._restore_queue)

    # ─── Navigasyon ───────────────────────────────────────────────────────────

    def init_navigation(self):
        self.home_interface.setObjectName("homeInterface")
        self.queue_interface.setObjectName("queueInterface")
        self.library_interface.setObjectName("libraryInterface")
        self.history_interface.setObjectName("historyInterface")
        self.settings_interface.setObjectName("settingsInterface")

        self.addSubInterface(self.home_interface, FIF.HOME, "Ana Sayfa")
        self.addSubInterface(self.queue_interface, FIF.DOWNLOAD, "İndirilenler")
        self.addSubInterface(self.library_interface, FIF.LIBRARY, "Kütüphane")
        self.addSubInterface(self.history_interface, FIF.HISTORY, "Geçmiş")
        self.navigationInterface.addSeparator()
        self.addSubInterface(self.settings_interface, FIF.SETTING, "Ayarlar", NavigationItemPosition.BOTTOM)

    # ─── System Tray ──────────────────────────────────────────────────────────

    def init_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        self.tray_icon.setToolTip("YouTube Studio Downloader")

        tray_menu = QMenu()
        show_action = QAction("Göster", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        downloads_action = QAction("İndirilenler", self)
        downloads_action.triggered.connect(lambda: (self.show_window(), self.switchTo(self.queue_interface)))
        tray_menu.addAction(downloads_action)

        mini_action = QAction("Mini Pencere (Ctrl+M)", self)
        mini_action.triggered.connect(self._mini_window.toggle)
        tray_menu.addAction(mini_action)

        notif_action = QAction("Bildirim Merkezi (Ctrl+N)", self)
        notif_action.triggered.connect(lambda: self._notif_panel.toggle(self.geometry().topRight()))
        tray_menu.addAction(notif_action)

        tray_menu.addSeparator()
        quit_action = QAction("Çıkış", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    # ─── Klavye kısayolları ───────────────────────────────────────────────────

    def init_keyboard_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+V"), self).activated.connect(self.paste_from_clipboard)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.start_current_download)
        QShortcut(QKeySequence("Escape"), self).activated.connect(lambda: self.switchTo(self.home_interface))
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.quit_app)

    def _handle_retry(self, url: str):
        """Geçmişten gelen retry isteğini ana sayfaya yönlendir"""
        if url and hasattr(self.home_interface, 'url_input'):
            self.home_interface.url_input.setText(url)
            self.switchTo(self.home_interface)
            InfoBar.info(title='Tekrar İndir', content='URL ana sayfaya yüklendi.', duration=3000, parent=self)

    def _auto_organize_file(self, filepath: str, url: str) -> str:
        """Dosyayı platforma göre alt klasöre taşır. Yeni yolu döndürür."""
        try:
            from src.utils.helpers import detect_platform
            platform_name = detect_platform(url)
            if not platform_name or platform_name == 'unknown':
                return filepath
            folder = os.path.dirname(filepath)
            platform_folder = os.path.join(folder, platform_name.capitalize())
            os.makedirs(platform_folder, exist_ok=True)
            new_path = os.path.join(platform_folder, os.path.basename(filepath))
            if not os.path.exists(new_path):
                shutil.move(filepath, new_path)
                return new_path
        except Exception:
            pass
        return filepath

    def paste_from_clipboard(self):
        text = get_clipboard_text()
        if text and hasattr(self.home_interface, 'url_input'):
            self.home_interface.url_input.setText(text)
            self.switchTo(self.home_interface)

    def _check_clipboard(self):
        """Panoda yeni geçerli URL belirdiyse home'a yansıt (kullanıcıya bildir)."""
        try:
            text = get_clipboard_text()
            if not text or text == self._clipboard_prev:
                return
            self._clipboard_prev = text
            if is_valid_url(text):
                home = self.home_interface
                if hasattr(home, 'url_input') and home.url_input.text() != text:
                    home.url_input.setText(text)
                    InfoBar.info(
                        title='Pano', content='URL panoya kopyalandı — ana sayfaya yapıştırıldı.',
                        duration=3000, parent=self
                    )
        except Exception:
            pass

    def _update_window_title(self):
        """Aktif indirme sayısını pencere başlığına yansıt."""
        n = self._active_downloads
        base = "YDL İndirici"
        if n > 0:
            self.setWindowTitle(f"[{n} İndiriliyor] {base}")
        else:
            self.setWindowTitle(base)

    def start_current_download(self):
        if self.home_interface.download_btn.isEnabled():
            self.home_interface.start_download()

    # ─── Tray olayları ────────────────────────────────────────────────────────

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick,
                      QSystemTrayIcon.ActivationReason.Trigger):
            self.show_window()

    def show_window(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.activateWindow()
        self.raise_()

    def closeEvent(self, event):
        cfg.set_value('window_width', self.width())
        cfg.set_value('window_height', self.height())
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
        self.downloader.cancel_all_downloads()
        self.tray_icon.hide()
        QApplication.quit()

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasUrls() or md.hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        md = event.mimeData()
        urls = []
        if md.hasUrls():
            urls = [u.toString() for u in md.urls()]
        elif md.hasText():
            urls = [line.strip() for line in md.text().split('\n') if line.strip()]
        valid = [u for u in urls if is_valid_url(u)]
        if not valid:
            return
        self.home_interface.url_input.setText(valid[0])
        self.switchTo(self.home_interface)
        if len(valid) > 1:
            self.home_interface.process_batch_urls(valid[1:])

    # ─── Güncelleme ───────────────────────────────────────────────────────────

    def check_for_updates_on_startup(self):
        updater = get_auto_updater()
        updater.check_on_startup(callback=self.on_update_check_result)

    def on_update_check_result(self, update_info):
        if update_info and update_info.is_newer:
            QTimer.singleShot(2000, lambda: self.show_update_notification(update_info))

    def show_update_notification(self, update_info):
        from PyQt6.QtWidgets import QWidget, QHBoxLayout
        from qfluentwidgets import InfoBarPosition, PushButton as PB

        current = get_current_version()

        # Custom InfoBar with "Şimdi Güncelle" button
        bar = InfoBar.new(
            icon=FIF.UPDATE,
            title='Güncelleme Mevcut',
            content=f"v{current} → v{update_info.version}  |  {update_info.release_notes[:80].splitlines()[0] if update_info.release_notes else ''}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=-1,   # kapanmasın — kullanıcı kapatır
            parent=self
        )
        btn = PB('Şimdi Güncelle', bar)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda: self._start_update(update_info, bar))
        bar.addWidget(btn)
        bar.show()

    def _start_update(self, update_info, bar=None):
        from src.utils.updater import download_and_install_update
        from PyQt6.QtWidgets import QProgressDialog

        if bar:
            bar.close()

        dlg = QProgressDialog("Güncelleme indiriliyor…", "İptal", 0, 100, self)
        dlg.setWindowTitle("Güncelleme")
        dlg.setMinimumDuration(0)
        dlg.setValue(0)
        dlg.show()

        # Shared state (GIL protects simple attr writes from background thread)
        self._upd_pct  = 0
        self._upd_done = None   # None=running, True=ok, False=failed

        def _progress(pct: int):
            self._upd_pct = max(0, min(100, int(pct)))

        def _do_update():
            ok = download_and_install_update(update_info, progress_callback=_progress)
            self._upd_done = bool(ok)

        import threading
        threading.Thread(target=_do_update, daemon=True).start()

        # Poll from main thread — safe, no cross-thread Qt calls
        poll = QTimer(self)
        def _tick():
            dlg.setValue(self._upd_pct)
            if self._upd_done is not None:
                poll.stop()
                dlg.close()
                if self._upd_done:
                    self._on_update_ready()
                else:
                    self._on_update_failed()
        poll.timeout.connect(_tick)
        poll.start(250)

    def _on_update_ready(self):
        """Update bat başlatıldı — uygulamayı kapat."""
        from PyQt6.QtWidgets import QApplication
        InfoBar.success(
            title='Güncelleme Hazır',
            content='Uygulama yeniden başlatılıyor…',
            duration=2000, parent=self
        )
        QTimer.singleShot(2200, QApplication.quit)

    def _on_update_failed(self):
        InfoBar.error(
            title='Güncelleme Hatası',
            content='İndirme başarısız. Lütfen GitHub\'dan manuel indirin.',
            duration=6000, parent=self
        )

    # ─── Zamanlayıcı ──────────────────────────────────────────────────────────

    def add_scheduled_task(self, time, url, path, format_id, type_str, save_meta, write_sub=False):
        self.scheduled_tasks.append({
            'time': time,
            'args': (url, path, format_id, type_str, save_meta, write_sub),
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
                    InfoBar.info(
                        title='Zamanlayıcı',
                        content=f"İndirme başladı: {task['args'][0][:60]}",
                        position=InfoBarPosition.TOP_RIGHT,
                        parent=self
                    )

    # ─── İndirme yönetimi ─────────────────────────────────────────────────────

    def start_download_process(self, url, path, format_id, type_str, save_meta,
                                write_sub=False, normalize_audio=False,
                                start_time=None, end_time=None, is_live=False,
                                thumbnail_url='', video_title='', channel='', duration=0,
                                sponsorblock=False, filename_template=None):

        # ── Spotify: özel indirici kullan ──────────────────────────────────────
        if 'open.spotify.com' in url:
            self._start_spotify_download(url, path, video_title, channel, thumbnail_url)
            return

        card = self.queue_interface.add_download_item(
            video_title or "İndirme Başlatılıyor...", url
        )
        if thumbnail_url:
            card.set_thumbnail_url(thumbnail_url)
        self._active_downloads += 1
        self._update_window_title()
        is_audio = (type_str == 'audio')
        ratelimit = self.settings_interface.get_speed_limit()
        proxy = self.settings_interface.get_proxy()
        custom_ffmpeg_args = self.settings_interface.get_custom_ffmpeg_args()
        if filename_template is None:
            try:
                filename_template = self.settings_interface.get_filename_template()
            except Exception:
                filename_template = None

        worker = DownloadWorker(
            self.downloader, url, path, format_id, is_audio, save_meta, ratelimit,
            proxy=proxy, write_sub=write_sub, normalize_audio=normalize_audio,
            start_time=start_time, end_time=end_time,
            is_live=is_live, custom_ffmpeg_args=custom_ffmpeg_args,
            semaphore=self.download_semaphore,
            filename_template=filename_template,
            sponsorblock=sponsorblock,
        )

        _mini_key = id(card)
        worker.progress_signal.connect(lambda d, mk=_mini_key, t=video_title: self._update_mini(mk, t, d))
        worker.progress_signal.connect(lambda d: self.update_download_card(card, d))
        worker.completed_signal.connect(
            lambda s, e, f, mk=_mini_key: self._mini_window.remove(mk))
        worker.completed_signal.connect(
            lambda s, e, f: self.finish_download_card(
                card, s, e, f, url, type_str,
                meta_title=video_title, meta_channel=channel,
                meta_thumbnail=thumbnail_url, meta_duration=duration,
            )
        )
        worker.cancelled_signal.connect(lambda: card.set_cancelled())
        worker.cancelled_signal.connect(lambda mk=_mini_key: self._mini_window.remove(mk))
        card.cancel_requested.connect(worker.cancel)
        card.worker = worker

        worker.start()
        self.switchTo(self.queue_interface)

    def _start_spotify_download(self, url: str, path: str,
                                  video_title: str = '', channel: str = '',
                                  thumbnail_url: str = ''):
        from src.ui.workers import SpotifyDownloadWorker

        display = video_title or 'Spotify Şarkısı'
        card = self.queue_interface.add_download_item(display, url)
        if thumbnail_url:
            card.set_thumbnail_url(thumbnail_url)
        self._active_downloads += 1
        self._update_window_title()

        worker = SpotifyDownloadWorker(url, path, semaphore=self.download_semaphore)
        worker.progress_signal.connect(lambda d: self.update_download_card(card, d))
        worker.completed_signal.connect(
            lambda s, e, f: self.finish_download_card(
                card, s, e, f, url, 'audio',
                meta_title=video_title, meta_channel=channel,
                meta_thumbnail=thumbnail_url, meta_duration=0,
            )
        )
        worker.cancelled_signal.connect(lambda: card.set_cancelled())
        card.cancel_requested.connect(worker.cancel)
        card.worker = worker

        worker.start()
        self.switchTo(self.queue_interface)

    def update_download_card(self, card, data):
        if card.is_cancelled:
            return

        status = data.get('status')
        filename = data.get('filename', '')

        if filename and not card.file_path:
            card.title_lbl.setText(os.path.basename(filename))

        if status in ('downloading', 'recording'):
            downloaded = data.get('downloaded_bytes', 0)
            total = data.get('total_bytes', 0)
            speed_val = data.get('speed') or 0
            progress = data.get('progress', 0)
            if progress <= 0 and total and total > 0:
                progress = int((downloaded / total) * 100)
            speed = format_size(speed_val) + "/s"

            if status == 'recording':
                card.status_lbl.setText(f"🔴 Kaydediliyor... {format_size(downloaded)} • {speed}")
                card.progress.setMaximum(0)
            else:
                eta = format_duration(data.get('eta') or 0)
                card.update_progress(progress, speed, eta, speed_bps=speed_val)

        elif status == 'processing':
            card.status_lbl.setText("Dönüştürülüyor...")
            card.progress.setMaximum(0)

    def finish_download_card(self, card, success, error, filepath, url="", type_str="video",
                              meta_title='', meta_channel='', meta_thumbnail='', meta_duration=0):
        self._active_downloads = max(0, self._active_downloads - 1)
        self._update_window_title()
        if self._active_downloads == 0 and hasattr(self, 'settings_interface'):
            try:
                if self.settings_interface.get_auto_shutdown():
                    import subprocess
                    InfoBar.warning(title='Otomatik Kapanma', content='Tüm indirmeler bitti. 30 saniye içinde kapanıyor...', duration=8000, parent=self)
                    QTimer.singleShot(30000, lambda: subprocess.run(['shutdown', '/s', '/t', '0']))
            except Exception:
                pass
        if success:
            # Auto-organize by platform if enabled
            if filepath and hasattr(self, 'settings_interface'):
                try:
                    if self.settings_interface.get_auto_organize():
                        filepath = self._auto_organize_file(filepath, url)
                        card.file_path = filepath
                except Exception:
                    pass
            card.set_finished(filepath)
            display_title = os.path.basename(filepath) if filepath else meta_title or "İndirme"
            _send_native_notification("İndirme Tamamlandı", display_title, tray_icon=self.tray_icon)
            # Bildirim merkezi
            try:
                self._notif_panel.push('success', 'İndirme Tamamlandı', display_title)
            except Exception:
                pass
            # Tamamlandı sesi (Windows)
            try:
                import winsound
                winsound.Beep(1000, 200)
            except Exception:
                pass
            # Plugin hook
            try:
                from src.core.plugin_manager import hook_download_complete
                hook_download_complete(filepath or '', url, {'title': meta_title, 'channel': meta_channel})
            except Exception:
                pass
            InfoBar.success(title='Başarılı', content="İndirme tamamlandı.", duration=3000, parent=self)
            # Geçmişe kaydet — title/channel/thumbnail/duration tamamen kaydedilir
            try:
                file_size = os.path.getsize(filepath) if filepath and os.path.exists(filepath) else None
                db_title = (
                    meta_title
                    or (os.path.splitext(os.path.basename(filepath))[0] if filepath else None)
                )
                get_download_history().add_download(
                    url=url,
                    title=db_title,
                    channel=meta_channel or None,
                    duration=int(meta_duration) if meta_duration else None,
                    format_type=type_str,
                    file_path=filepath,
                    file_size=file_size,
                    thumbnail_url=meta_thumbnail or None,
                    status='completed'
                )
            except Exception:
                pass
            self.history_interface.is_loaded = False
            # Şarkı sözleri — ses indirmelerinde otomatik .lrc kaydet
            if filepath and type_str == 'audio' and (meta_title or meta_channel):
                def _fetch_lrc(fp=filepath, t=meta_title or display_title,
                               a=meta_channel or '', d=int(meta_duration or 0)):
                    try:
                        from src.core.lyrics import save_lrc
                        lrc = save_lrc(fp, t, a, d)
                        if lrc:
                            QTimer.singleShot(0, lambda: InfoBar.info(
                                title='Sözler Kaydedildi',
                                content=f'{os.path.basename(lrc)}',
                                duration=3000, parent=self
                            ))
                    except Exception as _le:
                        print(f"[Lyrics] {_le}")
                threading.Thread(target=_fetch_lrc, daemon=True).start()
            # Webhook gönder
            self._send_webhook(url=url, title=meta_title or display_title,
                               filepath=filepath, success=True)
        else:
            card.status_lbl.setText("Hata!")
            card.progress.hide()
            InfoBar.error(title='Hata', content=str(error), duration=5000, parent=self)
            try:
                get_download_history().add_download(
                    url=url, title=meta_title or None,
                    channel=meta_channel or None,
                    format_type=type_str,
                    status='error', error_message=str(error)[:500]
                )
            except Exception:
                pass
            self._send_webhook(url=url, title=meta_title or '', filepath='', success=False, error=str(error))
            try:
                self._notif_panel.push('error', 'İndirme Hatası', str(error)[:80])
            except Exception:
                pass
            try:
                from src.core.plugin_manager import hook_download_error
                hook_download_error(url, str(error))
            except Exception:
                pass

    # ─── Mini Pencere Güncelleme ──────────────────────────────────────────────

    def _update_mini(self, key: int, title: str, d: dict):
        pct    = 0
        status = ''
        if d.get('status') == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total      = d.get('total_bytes', 0) or 1
            pct        = int(downloaded / total * 100)
            speed      = d.get('speed', 0) or 0
            status     = f"{format_size(speed)}/s" if speed else 'İndiriliyor...'
        elif d.get('status') == 'processing':
            pct, status = 99, 'Dönüştürülüyor...'
        try:
            self._mini_window.add_or_update(key, title, pct, status)
        except Exception:
            pass

    # ─── Webhook ──────────────────────────────────────────────────────────────

    def _send_webhook(self, url: str, title: str = '', filepath: str = '',
                      success: bool = True, error: str = ''):
        """Ayarlarda webhook URL varsa POST gönder (arka planda)."""
        try:
            webhook_url = self.settings_interface.get_webhook_url()
        except Exception:
            return
        if not webhook_url:
            return
        import threading, json, urllib.request
        payload = json.dumps({
            'event':    'download_complete' if success else 'download_error',
            'url':      url,
            'title':    title,
            'file':     filepath,
            'success':  success,
            'error':    error,
        }).encode('utf-8')
        def _post():
            try:
                req = urllib.request.Request(
                    webhook_url,
                    data=payload,
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                print(f"[Webhook] Gönderim hatası: {e}")
        threading.Thread(target=_post, daemon=True).start()

    # ─── Kuyruk Kalıcılığı ────────────────────────────────────────────────────

    def _restore_queue(self):
        """Önceki oturumdan kalan kuyruğu geri yükle."""
        try:
            db = get_download_history()
            pending = db.get_saved_queue()
            if not pending:
                return
            db.clear_queue_state()
            for item in pending:
                self.start_download_process(
                    url=item.get('url', ''),
                    path=item.get('output_path') or self.settings_interface.get_download_dir(),
                    format_id=item.get('format_id', 'best'),
                    type_str=item.get('type_str', 'video'),
                    save_meta=False,
                    thumbnail_url=item.get('thumbnail_url', ''),
                    video_title=item.get('title', ''),
                )
            if pending:
                InfoBar.info(
                    title='Kuyruk Geri Yüklendi',
                    content=f"{len(pending)} bekleyen indirme devam ettiriliyor.",
                    duration=5000, parent=self
                )
        except Exception as e:
            print(f"[Queue restore] {e}")

    def save_queue_item(self, url: str, title: str = '', output_path: str = '',
                        format_id: str = 'best', type_str: str = 'video',
                        thumbnail_url: str = ''):
        """İndirme başladığında kuyruğa kalıcı kayıt ekle."""
        try:
            get_download_history().save_queue_item(
                url=url, title=title, output_path=output_path,
                format_id=format_id, type_str=type_str, thumbnail_url=thumbnail_url
            )
        except Exception:
            pass

    # ─── Abonelik Kontrolü ────────────────────────────────────────────────────

    def _check_subscriptions(self):
        """Aktif abonelikleri arka planda kontrol et, yeni içerik varsa indir."""
        try:
            interval_ms = self.settings_interface.get_sub_check_interval_ms()
            self._sub_timer.setInterval(interval_ms)
        except Exception:
            pass

        import threading
        threading.Thread(target=self._do_subscription_check, daemon=True).start()

    def _do_subscription_check(self):
        try:
            from src.core.database import get_download_history
            from src.core.subscription_manager import check_channel_new_videos
            db = get_download_history()
            subs = db.get_subscriptions(active_only=True)
            if not subs:
                return
            # Tüm indirilen URL'leri al (hızlı lookup için set)
            all_downloaded = {r['url'] for r in db.get_all_downloads(limit=2000)}
            for sub in subs:
                new_vids = check_channel_new_videos(sub['url'], known_urls=all_downloaded)
                db.update_subscription_checked(sub['id'], len(new_vids))
                for vid in new_vids:
                    out = sub.get('output_path') or self.settings_interface.get_download_dir()
                    # GUI thread'e geçir — queued signal (thread-safe)
                    self._sub_new_video_signal.emit(
                        vid['url'], out,
                        sub.get('format_type', 'video'),
                        vid.get('title', '')
                    )
        except Exception as e:
            print(f"[SubCheck] {e}")

    def _on_sub_new_video(self, url: str, output_path: str,
                          format_type: str = 'video', title: str = ''):
        """GUI thread'den çağrılır — yeni abonelik videosu indir."""
        self.start_download_process(
            url=url, path=output_path, format_id='best',
            type_str=format_type, save_meta=False, video_title=title
        )
        InfoBar.info(
            title='Yeni Abonelik İçeriği',
            content=f"Otomatik indirme başlatıldı: {title[:60]}",
            duration=6000, parent=self
        )

    # ─── Zamanlanmış Görevler ─────────────────────────────────────────────────

    def _check_scheduled_tasks(self):
        """Her dakika çağrılır. schedule_time'ı geçmiş aktif görevleri çalıştırır."""
        import datetime
        try:
            db = get_download_history()
            tasks = db.get_scheduled_tasks()
            now = datetime.datetime.now()
            now_hhmm = now.strftime('%H:%M')
            for task in tasks:
                sched = task.get('schedule_time', '')  # format "HH:MM" or "YYYY-MM-DD HH:MM"
                # Support both HH:MM (daily) and YYYY-MM-DD HH:MM (one-shot)
                if len(sched) == 5:  # "HH:MM"
                    due = sched == now_hhmm
                else:
                    try:
                        sched_dt = datetime.datetime.strptime(sched, '%Y-%m-%d %H:%M')
                        due = sched_dt <= now
                    except ValueError:
                        due = False
                if not due:
                    continue
                # Skip if already ran today/recently (within last 2 min)
                last_run = task.get('last_run')
                if last_run:
                    try:
                        lr = datetime.datetime.fromisoformat(str(last_run))
                        if (now - lr).total_seconds() < 90:
                            continue
                    except Exception:
                        pass
                # Fire
                db.update_scheduled_task_run(task['id'])
                if not task.get('repeat_daily'):
                    db.set_scheduled_task_active(task['id'], False)
                out = task.get('output_path') or self.settings_interface.get_download_dir()
                self.start_download_process(
                    url=task['url'], path=out,
                    format_id=task.get('format_id', 'best'),
                    type_str=task.get('type_str', 'video'),
                    save_meta=False,
                    video_title=task.get('name', '')
                )
                InfoBar.info(
                    title='Zamanlanmış Görev',
                    content=f"Başlatıldı: {task.get('name', task['url'])[:60]}",
                    duration=5000, parent=self
                )
        except Exception as e:
            print(f"[Scheduler] {e}")
