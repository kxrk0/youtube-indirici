#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import threading

from PyQt6.QtCore import Qt, QTimer, QTime
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
from src.utils.helpers import (
    format_size, format_duration, get_clipboard_text
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

    def __init__(self, downloader=None):
        super().__init__()

        # Tema ve renk ayarlarını config'den yükle
        saved_theme = cfg.get('theme', 'dark')
        setTheme(Theme.DARK if saved_theme == 'dark' else Theme.LIGHT)
        setThemeColor(cfg.get('accent_color', '#0078D4'))

        self.setWindowTitle("YouTube Studio Downloader")
        self.resize(900, 650)

        self.app_icon = (
            QIcon("extension/icons/download.svg")
            if os.path.exists("extension/icons/download.svg")
            else QIcon()
        )
        self.setWindowIcon(self.app_icon)

        # Shared Downloader örneği
        self.downloader = downloader or Downloader()

        # Paralel indirme semafor (en fazla 3 eş zamanlı)
        self.download_semaphore = threading.Semaphore(self.MAX_CONCURRENT_DOWNLOADS)

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
        self.init_system_tray()
        self.init_keyboard_shortcuts()
        self.check_for_updates_on_startup()

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

    def paste_from_clipboard(self):
        text = get_clipboard_text()
        if text and hasattr(self.home_interface, 'url_input'):
            self.home_interface.url_input.setText(text)
            self.switchTo(self.home_interface)

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

    # ─── Güncelleme ───────────────────────────────────────────────────────────

    def check_for_updates_on_startup(self):
        updater = get_auto_updater()
        updater.check_on_startup(callback=self.on_update_check_result)

    def on_update_check_result(self, update_info):
        if update_info and update_info.is_newer:
            QTimer.singleShot(2000, lambda: self.show_update_notification(update_info))

    def show_update_notification(self, update_info):
        current = get_current_version()
        InfoBar.info(
            title=tr("update.available") if tr("update.available") != "update.available" else "Güncelleme Mevcut",
            content=f"v{current} → v{update_info.version}",
            orient=Qt.Orientation.Vertical,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=10000,
            parent=self
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
                                start_time=None, end_time=None, is_live=False):
        card = self.queue_interface.add_download_item("İndirme Başlatılıyor...", url)
        is_audio = (type_str == 'audio')
        ratelimit = self.settings_interface.get_speed_limit()
        proxy = self.settings_interface.get_proxy()
        custom_ffmpeg_args = self.settings_interface.get_custom_ffmpeg_args()

        worker = DownloadWorker(
            self.downloader, url, path, format_id, is_audio, save_meta, ratelimit,
            proxy=proxy, write_sub=write_sub, normalize_audio=normalize_audio,
            start_time=start_time, end_time=end_time,
            is_live=is_live, custom_ffmpeg_args=custom_ffmpeg_args,
            semaphore=self.download_semaphore,
        )

        worker.progress_signal.connect(lambda d: self.update_download_card(card, d))
        worker.completed_signal.connect(
            lambda s, e, f: self.finish_download_card(card, s, e, f, url, type_str)
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
                eta = format_duration(data.get('eta', 0))
                card.update_progress(progress, speed, eta)

        elif status == 'processing':
            card.status_lbl.setText("Dönüştürülüyor...")
            card.progress.setMaximum(0)

    def finish_download_card(self, card, success, error, filepath, url="", type_str="video"):
        if success:
            card.set_finished(filepath)
            title = os.path.basename(filepath) if filepath else "İndirme"
            _send_native_notification(
                "İndirme Tamamlandı",
                title,
                tray_icon=self.tray_icon
            )
            InfoBar.success(title='Başarılı', content="İndirme tamamlandı.", duration=3000, parent=self)
            # Geçmişe kaydet
            try:
                file_size = os.path.getsize(filepath) if filepath and os.path.exists(filepath) else None
                get_download_history().add_download(
                    url=url,
                    title=os.path.splitext(os.path.basename(filepath))[0] if filepath else None,
                    format_type=type_str,
                    file_path=filepath,
                    file_size=file_size,
                    status='completed'
                )
            except Exception:
                pass
            # Kütüphaneyi yenile (zaten lazy yükler)
            self.history_interface.is_loaded = False
        else:
            card.status_lbl.setText("Hata!")
            card.progress.hide()
            InfoBar.error(title='Hata', content=str(error), duration=5000, parent=self)
            try:
                get_download_history().add_download(
                    url=url, format_type=type_str,
                    status='error', error_message=str(error)[:500]
                )
            except Exception:
                pass
