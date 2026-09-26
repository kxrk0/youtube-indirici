#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bildirim alanı simgesi. pywebview'ün tepsi desteği yok; pystray kendi ileti döngüsünü
ayrı bir iş parçacığında çalıştırır, menü eylemleri o iş parçacığından çağrılır.
"""
import threading
from typing import Callable

import pystray
from PIL import Image


class TrayIcon:
    def __init__(self, icon_path: str, tooltip: str, *, on_show: Callable[[], None], on_downloads: Callable[[], None],
                 on_mini: Callable[[], None], on_quit: Callable[[], None]):
        menu = pystray.Menu(
            # default=True: simgeye sol tıklamak bu eylemi çalıştırır.
            pystray.MenuItem('Göster', lambda: on_show(), default=True),
            pystray.MenuItem('İndirilenler', lambda: on_downloads()),
            pystray.MenuItem('Mini pencere (Ctrl+M)', lambda: on_mini()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Çıkış', lambda: on_quit()),
        )
        self._icon = pystray.Icon('youtube-studio-downloader', Image.open(icon_path), tooltip, menu)
        self._thread = threading.Thread(target=self._icon.run, name='tray', daemon=True)

    def start(self):
        self._thread.start()

    def notify(self, title: str, message: str):
        self._icon.notify(message, title)

    def stop(self):
        self._icon.stop()
