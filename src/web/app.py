#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web arayüzlü uygulama: pywebview (WebView2) içinde React/TS Ortam arayüzü.

Çalıştırma:  python -m src.web.app  (ya da main.py)
Geliştirme:  ORTAM_DEV_URL=http://localhost:5179 ile Vite geliştirme sunucusuna bağlanır
             (anında yeniden yükleme). Yoksa webui/dist içindeki derleme açılır.
"""
import ctypes
import os
import sys
import threading
from ctypes import wintypes
from typing import Optional

import webview
from webview.window import FixPoint

from src.core.downloader import Downloader
from src.utils import config as cfg
from src.utils.helpers import get_data_dir, get_resource_dir, setup_ffmpeg_path
from src.web.api import OrtamApi
from src.web.single_instance import SingleInstance
from src.web.tray import TrayIcon
from src.web import window_frame

WINDOW_TITLE = 'YouTube Studio Downloader'
MINI_TITLE = 'İndirmeler'
APP_USER_MODEL_ID = 'kxrk0.YouTubeStudioDownloader'
DEFAULT_SIZE = (1100, 720)
MIN_SIZE = (960, 640)
MINI_WIDTH = 340
MINI_INITIAL_HEIGHT = 120
MINI_MAX_HEIGHT = 420
# pywebview varsayılan en küçük boyutu (200x100) boş mini pencereyi gereksiz uzun tutuyordu.
MINI_MIN_HEIGHT = 56
MINI_SCREEN_MARGIN = 16
# Son indirme bitince kendiliğinden açılmış mini pencerenin kapanmadan önce beklediği süre.
MINI_AUTO_HIDE_S = 3.0
# Ortam nötr derin tonu (hsl 220 8% 9%); sayfa yüklenene kadar beyaz parlama olmasın.
BOOT_BACKGROUND = '#151719'
# DWM öznitelikleri (Windows 11): koyu mod, köşe, başlık zemini, başlık yazısı, çerçeve.
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
TITLE_TEXT_RGB = (245, 243, 240)
# Win32 simge ve çalışma alanı sabitleri (winuser.h).
WM_SETICON = 0x0080
ICON_SMALL, ICON_BIG = 0, 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
SPI_GETWORKAREA = 0x0030
USER_DEFAULT_DPI = 96


def _dist_index() -> str:
    path = os.path.join(get_resource_dir(), 'webui', 'dist', 'index.html')
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Web arayüzü derlenmemiş: {path} yok. 'cd webui && npm install && npm run build' çalıştır."
        )
    return path


def _icon_path() -> str:
    path = os.path.join(get_resource_dir(), 'assets', 'app.ico')
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Uygulama simgesi yok: {path}")
    return path


def _colorref(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    return r | (g << 8) | (b << 16)


def _hwnd(window: webview.Window) -> Optional[int]:
    if sys.platform != 'win32' or window.native is None:
        return None
    return window.native.Handle.ToInt64()


def _set_dwm(hwnd: int, attribute: int, value: int):
    v = ctypes.c_int(value)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(v), ctypes.sizeof(v))


def paint_title_bar(window: webview.Window, rgb: tuple[int, int, int]):
    """Windows başlık çubuğunu içeriğin derin tonuna boyar; Ortam arka planıyla tek yüzey gibi durur."""
    hwnd = _hwnd(window)
    if hwnd is None:
        return
    _set_dwm(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
    _set_dwm(hwnd, DWMWA_CAPTION_COLOR, _colorref(rgb))
    _set_dwm(hwnd, DWMWA_BORDER_COLOR, _colorref(rgb))
    _set_dwm(hwnd, DWMWA_TEXT_COLOR, _colorref(TITLE_TEXT_RGB))


def set_window_icon(window: webview.Window, icon_path: str):
    """WinForms penceresi python.exe simgesiyle açılır; başlık ve görev çubuğu için uygulama simgesini koyar."""
    hwnd = _hwnd(window)
    if hwnd is None:
        return
    user32 = ctypes.windll.user32
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    for kind in (ICON_SMALL, ICON_BIG):
        handle = user32.LoadImageW(None, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if not handle:
            raise OSError(f"Simge yüklenemedi: {icon_path} (Win32 hata {ctypes.GetLastError()})")
        user32.SendMessageW(hwnd, WM_SETICON, kind, handle)


def _work_area_logical() -> tuple[int, int]:
    """Birincil ekranın görev çubuğu hariç sağ-alt köşesi, mantıksal pikselde (pywebview konumları mantıksal)."""
    rect = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    scale = ctypes.windll.user32.GetDpiForSystem() / USER_DEFAULT_DPI
    return int(rect.right / scale), int(rect.bottom / scale)


def enable_drag_regions():
    """
    CSS `app-region: drag` alanları başlık çubuğu gibi davransın: sürükleme, ekran kenarına yaslama,
    çift tıkla büyütme WebView2'den gelir. Ayar ilk gezinmeden önce açılmalı (sonradan açılınca
    sayfa yeniden yüklenene kadar etkisiz kaldığı ölçüldü); pywebview'de o ana kanca olmadığından
    WebView2 hazır işleyicisi sarılır. Pencere oluşturulmadan önce çağrılmalı.
    """
    from webview.platforms import edgechromium
    original = getattr(edgechromium.EdgeChrome, 'on_webview_ready', None)
    if original is None:
        raise RuntimeError('pywebview EdgeChrome.on_webview_ready yok; pywebview sürümü değişmiş, '
                           'başlık çubuğu sürüklenemez. src/web/app.py enable_drag_regions güncellenmeli.')
    if getattr(original, 'ortam_drag_regions', False):
        return

    def on_webview_ready(self, sender, args):
        if args.IsSuccess:
            try:
                sender.CoreWebView2.Settings.IsNonClientRegionSupportEnabled = True
            except Exception as e:
                print(f"[Pencere] WebView2 sürükleme bölgeleri açılamadı (çalışma zamanı eski olabilir): {e}")
        original(self, sender, args)

    on_webview_ready.ortam_drag_regions = True
    edgechromium.EdgeChrome.on_webview_ready = on_webview_ready


def _fix_restore_bounds(form, hwnd: int, memo: dict):
    """
    WinForms büyütülürken/küçültülürken normal boyutu istemci alanı olarak saklar (restoredWindowBounds)
    ve geri alırken başlıklı çerçeve payını ekleyerek pencereye çevirir. Başlık kaldırıldığı için bu pay
    fazladan kalıyor, her büyüt-geri al'da pencere başlık yüksekliği kadar (96 DPI'da 31 px) uzuyordu.
    Saklanan yükseklikten o pay düşülür; aynı değer iki kez düzeltilmez.
    """
    from System.Drawing import Rectangle
    from System.Reflection import BindingFlags
    form_type = form.GetType()
    while form_type is not None and form_type.FullName != 'System.Windows.Forms.Form':
        form_type = form_type.BaseType
    field = form_type.GetField('restoredWindowBounds', BindingFlags.NonPublic | BindingFlags.Instance) if form_type else None
    if field is None:
        raise RuntimeError('WinForms Form.restoredWindowBounds alanı bulunamadı (.NET sürümü farklı).')
    bounds = field.GetValue(form)
    if bounds.Height < 0 or memo.get('fixed') == (bounds.X, bounds.Y, bounds.Width, bounds.Height):
        return
    fixed = Rectangle(bounds.X, bounds.Y, bounds.Width, bounds.Height - window_frame.caption_overhang(hwnd))
    field.SetValue(form, fixed)
    memo['fixed'] = (fixed.X, fixed.Y, fixed.Width, fixed.Height)


class DesktopShell:
    """Ana pencere, mini pencere ve tepsi arasındaki yaşam döngüsü: gizle, göster, çık."""

    def __init__(self, api: OrtamApi, main: webview.Window, dev_url: Optional[str]):
        self._api = api
        self._main = main
        self._dev_url = dev_url
        self._mini: Optional[webview.Window] = None
        self._mini_visible = False
        self._mini_auto = False
        self._mini_height = MINI_INITIAL_HEIGHT
        self._main_hidden = False
        self._quitting = False
        self._hidden_notice_shown = False
        self._auto_hide: Optional[threading.Timer] = None
        self._lock = threading.RLock()
        self._frame: Optional[window_frame.CaptionlessFrame] = None
        self._restore_memo: dict = {}
        self._tray = TrayIcon(_icon_path(), WINDOW_TITLE, on_show=lambda: self.show_main(None),
                              on_downloads=lambda: self.show_main('queue'), on_mini=self.toggle_mini,
                              on_quit=self.request_quit)

    def start(self):
        self._tray.start()

    # ── Ana pencere ──
    def on_closing(self) -> bool:
        """Kapatma düğmesi: uygulama tepside sürer. Gerçek çıkış tepsiden ya da Ctrl+Q ile."""
        if self._quitting:
            return True
        self._remember_size()
        self._main_hidden = True
        threading.Thread(target=self._main.hide, name='hide-main', daemon=True).start()
        if not self._hidden_notice_shown:
            self._hidden_notice_shown = True
            self._tray.notify(WINDOW_TITLE, 'Uygulama arka planda çalışıyor. Açmak için bildirim alanındaki simgeye tıkla.')
        return False

    # ── Başlıksız çerçeve: başlık çubuğu arayüzün içinde (webui TitleBar) ──
    def install_frame(self):
        hwnd = _hwnd(self._main)
        if hwnd is not None and self._frame is None:
            self._frame = window_frame.CaptionlessFrame(
                hwnd, on_left_normal=lambda: _fix_restore_bounds(self._main.native, hwnd, self._restore_memo))

    def window_command(self, action: str):
        hwnd = _hwnd(self._main)
        if hwnd is None:
            raise RuntimeError('Ana pencere henüz oluşmadı.')
        if action == 'minimize':
            command = window_frame.SC_MINIMIZE
        elif action == 'maximize':
            command = window_frame.SC_RESTORE if window_frame.is_maximized(hwnd) else window_frame.SC_MAXIMIZE
        elif action == 'close':
            command = window_frame.SC_CLOSE
        else:
            raise ValueError(f"Bilinmeyen pencere komutu: {action!r} (minimize, maximize, close)")
        window_frame.system_command(hwnd, command)

    def window_maximized(self) -> bool:
        hwnd = _hwnd(self._main)
        return hwnd is not None and window_frame.is_maximized(hwnd)

    def show_main(self, page: Optional[str]):
        self._main_hidden = False
        self._main.show()
        self._main.restore()
        if page:
            self._api._emit({'type': 'navigate', 'page': page})

    def bring_to_front(self):
        """İkinci açılış isteği: pencereyi göster ve öne al (izni ikinci kopya verir, single_instance)."""
        self.show_main(None)
        hwnd = _hwnd(self._main)
        if hwnd:
            ctypes.windll.user32.SetForegroundWindow(hwnd)

    def _remember_size(self):
        cfg.set_value('window_width', self._main.width)
        cfg.set_value('window_height', self._main.height)

    # ── Mini pencere ──
    def _mini_url(self) -> str:
        base = self._dev_url or self._main.get_current_url() or ''
        if not base:
            raise RuntimeError('Ana pencerenin adresi alınamadı; mini pencere açılamıyor.')
        return base.split('#', 1)[0] + '#mini'

    def _mini_position(self, height: int) -> tuple[int, int]:
        right, bottom = _work_area_logical()
        return right - MINI_WIDTH - MINI_SCREEN_MARGIN, bottom - height - MINI_SCREEN_MARGIN

    def _show_mini(self, auto: bool):
        with self._lock:
            self._cancel_auto_hide()
            self._mini_auto = auto
            if self._mini_visible:
                return
            self._mini_visible = True
            x, y = self._mini_position(self._mini_height)
            if self._mini is None:
                self._mini = webview.create_window(
                    MINI_TITLE, self._mini_url(), js_api=self._api, width=MINI_WIDTH, height=self._mini_height,
                    x=x, y=y, min_size=(MINI_WIDTH, MINI_MIN_HEIGHT), frameless=True, easy_drag=False, on_top=True,
                    background_color=BOOT_BACKGROUND, text_select=False, focus=not auto,
                )
                self._mini.events.shown += self._style_mini
                self._api._add_window(self._mini)
            else:
                self._mini.move(x, y)
                self._mini.show()

    def _style_mini(self):
        hwnd = _hwnd(self._mini)
        if hwnd is not None:
            _set_dwm(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
            _set_dwm(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)

    def hide_mini(self):
        with self._lock:
            self._cancel_auto_hide()
            if self._mini is None or not self._mini_visible:
                return
            self._mini_visible = False
            self._mini.hide()

    def toggle_mini(self):
        if self._mini_visible:
            self.hide_mini()
        else:
            self._show_mini(auto=False)

    def fit_mini(self, height: int):
        """Mini sayfa içerik yüksekliğini bildirir; alt kenar yerinde kalır (kullanıcı taşıdıysa da)."""
        with self._lock:
            height = max(MINI_MIN_HEIGHT, min(MINI_MAX_HEIGHT, height))
            if self._mini is None or height == self._mini_height:
                return
            self._mini_height = height
            self._mini.resize(MINI_WIDTH, height, fix_point=FixPoint.SOUTH)

    def jobs_changed(self, active: int):
        """Ana pencere gizliyken indirme başlarsa mini pencere kendiliğinden açılır; hepsi bitince kapanır."""
        if active > 0 and self._main_hidden and not self._mini_visible:
            self._show_mini(auto=True)
        elif active == 0 and self._mini_visible and self._mini_auto:
            with self._lock:
                self._cancel_auto_hide()
                self._auto_hide = threading.Timer(MINI_AUTO_HIDE_S, self.hide_mini)
                self._auto_hide.daemon = True
                self._auto_hide.start()

    def _cancel_auto_hide(self):
        if self._auto_hide is not None:
            self._auto_hide.cancel()
            self._auto_hide = None

    # ── Çıkış ──
    def request_quit(self):
        if self._api._has_active_jobs():
            if self._main_hidden:
                self.show_main(None)
            if not self._main.create_confirmation_dialog(
                    'İndirmeler sürüyor', 'Çıkarsan süren indirmeler yarıda kalır. Yine de çıkılsın mı?'):
                return
        self.quit_now()

    def quit_now(self):
        self._quitting = True
        self._api._cancel_all()
        if not self._main_hidden:
            self._remember_size()
        self._tray.stop()
        if self._mini is not None:
            self._mini.destroy()
        self._main.destroy()


def main():
    instance = SingleInstance(get_data_dir())
    if not instance.acquire():
        # Uygulama zaten açık (çoğu zaman tepside): onun penceresini öne getir, ikinci kopya açma.
        instance.signal_existing()
        return
    setup_ffmpeg_path()
    if sys.platform == 'win32':
        # Görev çubuğunda python.exe yerine uygulamanın kendi simgesi ve grubu görünsün.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    api = OrtamApi(Downloader())
    dev_url = os.environ.get('ORTAM_DEV_URL')
    enable_drag_regions()
    width = max(int(cfg.get('window_width', DEFAULT_SIZE[0])), MIN_SIZE[0])
    height = max(int(cfg.get('window_height', DEFAULT_SIZE[1])), MIN_SIZE[1])
    window = webview.create_window(
        WINDOW_TITLE, dev_url or _dist_index(), js_api=api,
        width=width, height=height, min_size=MIN_SIZE,
        background_color=BOOT_BACKGROUND, text_select=False,
    )
    api._attach(window, paint_title_bar)
    shell = DesktopShell(api, window, dev_url)
    api._attach_shell(shell)

    def on_shown():
        api.set_title_bar(BOOT_BACKGROUND)
        set_window_icon(window, _icon_path())
        shell.install_frame()

    window.events.closing += shell.on_closing
    window.events.shown += on_shown
    window.events.loaded += api._start_services
    shell.start()
    instance.listen(shell.bring_to_front)
    webview.start(gui='edgechromium', debug=bool(dev_url), http_server=not dev_url)


if __name__ == '__main__':
    main()
