#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Başlıksız pencere çerçevesi (yalnız Windows). Ortam'da başlık çubuğu arayüzün içine,
bulanık kapak arka planının üstüne çizilir (webui TitleBar); Windows'un düz başlık şeridi
tasarımı ikiye bölüyordu.

Pencere normal (başlıklı) açılır ki kenardan boyutlandırma, ekran kenarına yaslama ve
küçültme animasyonları çalışsın; yalnız WM_NCCALCSIZE'da başlık yüksekliği istemci alanına
katılır. Sürükleme WebView2'nin `app-region: drag` desteğiyle yapılır.
"""
import ctypes
from ctypes import wintypes
from typing import Callable, Optional

WM_NCCALCSIZE = 0x0083
WM_SIZE = 0x0005
SIZE_MINIMIZED, SIZE_MAXIMIZED = 1, 2
WM_SYSCOMMAND = 0x0112
SC_MINIMIZE = 0xF020
SC_MAXIMIZE = 0xF030
SC_RESTORE = 0xF120
SC_CLOSE = 0xF060
GWLP_WNDPROC = -4
GWL_STYLE, GWL_EXSTYLE = -16, -20
SM_CYFRAME = 33
SM_CXPADDEDBORDER = 92
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_FRAMECHANGED = 0x0001, 0x0002, 0x0004, 0x0020

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [('rgrc', wintypes.RECT * 3), ('lppos', ctypes.c_void_p)]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SetWindowLongPtrW.restype = ctypes.c_void_p
_user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
_user32.CallWindowProcW.restype = LRESULT
_user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_uint]
_user32.IsZoomed.argtypes = [wintypes.HWND]
_user32.GetDpiForWindow.argtypes = [wintypes.HWND]
_user32.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, ctypes.c_uint]
_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.AdjustWindowRectExForDpi.argtypes = [ctypes.POINTER(wintypes.RECT), wintypes.DWORD, wintypes.BOOL,
                                             wintypes.DWORD, ctypes.c_uint]


class CaptionlessFrame:
    """Pencere yordamını alt sınıflar; nesne yaşadığı sürece geri çağrı canlı kalmalı (GC'ye karşı tutulur)."""

    def __init__(self, hwnd: int, on_left_normal: Optional[Callable[[], None]] = None):
        """on_left_normal: pencere büyütülünce ya da küçültülünce, varsayılan yordamdan sonra çağrılır."""
        self._hwnd = hwnd
        self._on_left_normal = on_left_normal
        self._proc = WNDPROC(self._wndproc)
        ctypes.set_last_error(0)
        self._previous = _user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ctypes.cast(self._proc, ctypes.c_void_p))
        if not self._previous:
            raise OSError(f"Pencere yordamı değiştirilemedi (hwnd {hwnd}, Win32 hata {ctypes.get_last_error()})")
        # Çerçeveyi yeni WM_NCCALCSIZE yanıtıyla yeniden hesaplat.
        _user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_SIZE and wparam in (SIZE_MAXIMIZED, SIZE_MINIMIZED) and self._on_left_normal is not None:
            result = _user32.CallWindowProcW(self._previous, hwnd, msg, wparam, lparam)
            try:
                self._on_left_normal()
            except Exception as e:
                print(f"[Pencere] Geri yükleme boyutu düzeltilemedi, geri alınca pencere uzayabilir: {e}")
            return result
        if msg != WM_NCCALCSIZE or not wparam:
            return _user32.CallWindowProcW(self._previous, hwnd, msg, wparam, lparam)
        try:
            params = NCCALCSIZE_PARAMS.from_address(lparam)
            top = params.rgrc[0].top
            result = _user32.CallWindowProcW(self._previous, hwnd, msg, wparam, lparam)
            # Varsayılan yordam yanları ve altı ayarladı; üstü (başlık) geri alınır. Büyütülmüş
            # pencere ekranın çerçeve kalınlığı kadar dışına taşar, o pay içeride bırakılır.
            params.rgrc[0].top = top + (_frame_thickness(hwnd) if _user32.IsZoomed(hwnd) else 0)
            return result
        except Exception as e:
            # Geri çağrıdan istisna kaçarsa ctypes 0 döner ve pencere bozulur; varsayılana düş.
            print(f"[Pencere] WM_NCCALCSIZE işlenemedi, varsayılan çerçeve kullanılıyor: {e}")
            return _user32.CallWindowProcW(self._previous, hwnd, msg, wparam, lparam)


def _frame_thickness(hwnd: int) -> int:
    dpi = _user32.GetDpiForWindow(hwnd)
    return _user32.GetSystemMetricsForDpi(SM_CYFRAME, dpi) + _user32.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi)


def caption_overhang(hwnd: int) -> int:
    """Windows'un bu pencere için saydığı başlık + üst kenar yüksekliği. Başlık kaldırıldığı için
    istemci alanından pencere boyu hesaplayan kod (AdjustWindowRectEx) bu kadar fazla bulur."""
    rect = wintypes.RECT(0, 0, 0, 0)
    style = _user32.GetWindowLongW(hwnd, GWL_STYLE) & 0xFFFFFFFF
    exstyle = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
    if not _user32.AdjustWindowRectExForDpi(ctypes.byref(rect), style, False, exstyle, _user32.GetDpiForWindow(hwnd)):
        raise OSError(f"AdjustWindowRectExForDpi başarısız (hwnd {hwnd}, Win32 hata {ctypes.get_last_error()})")
    return -rect.top


def is_maximized(hwnd: int) -> bool:
    return bool(_user32.IsZoomed(hwnd))


def system_command(hwnd: int, command: int):
    """Küçült/büyüt/kapat Windows'un kendi yoluyla (animasyonlar ve kapanış olayı dahil)."""
    if not _user32.PostMessageW(hwnd, WM_SYSCOMMAND, command, 0):
        raise OSError(f"Pencere komutu gönderilemedi (hwnd {hwnd}, komut {command:#x}, Win32 hata {ctypes.get_last_error()})")
