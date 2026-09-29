#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tek kopya: ikinci açılış yeni süreç başlatmaz, çalışan kopyanın penceresini öne getirir.

Neden: pencere kapatılınca uygulama tepside sürüyor; masaüstünden yeniden açılınca ikinci bir
kopya başlıyordu. Güncellemeyi bir kopya başlatınca öteki EXE'yi kilitli tutuyor, sessiz kurulum
iptal oluyordu (2.7.0 -> 2.7.1'de görüldü). İki kopya aynı geçmiş veritabanına da yazıyordu.

Windows adlandırılmış nesneleri: mutex kimin ilk olduğunu, olay (event) "öne gel" isteğini taşır.
Adlar Local\\ altında (yalnız bu oturum) ve veri klasöründen türetilir: kaynak koddan çalışan
geliştirme kopyası kurulu uygulamayı engellemez.
"""
import ctypes
import hashlib
import threading
import time
from ctypes import wintypes
from typing import Callable

ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0
# İlk kopya mutex'i alıp olayı oluşturana kadar geçen kısa aralıkta ikinci kopya olayı bulamayabilir.
SIGNAL_RETRIES = 20
SIGNAL_RETRY_S = 0.1
# Windows arka plandaki süreci öne geçirmez; kullanıcının az önce açtığı ikinci kopya bu izni verir.
ASFW_ANY = 0xFFFFFFFF

_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_k32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
_k32.CreateMutexW.restype = wintypes.HANDLE
_k32.CreateEventW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
_k32.CreateEventW.restype = wintypes.HANDLE
_k32.OpenEventW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
_k32.OpenEventW.restype = wintypes.HANDLE
_k32.SetEvent.argtypes = (wintypes.HANDLE,)
_k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
_k32.WaitForSingleObject.restype = wintypes.DWORD
_k32.CloseHandle.argtypes = (wintypes.HANDLE,)


class SingleInstance:
    def __init__(self, key: str):
        digest = hashlib.sha256(key.lower().encode('utf-8')).hexdigest()[:16]
        self._mutex_name = f'Local\\YouTubeIndirici-{digest}'
        self._event_name = f'Local\\YouTubeIndirici-{digest}-show'
        self._mutex = None
        self._event = None

    def acquire(self) -> bool:
        """İlk kopyaysa True. Tutamaklar süreç bitene kadar açık kalır; Windows kendisi kapatır."""
        mutex = _k32.CreateMutexW(None, False, self._mutex_name)
        if not mutex:
            raise OSError(ctypes.get_last_error(), f'Tek kopya kilidi oluşturulamadı: {self._mutex_name}')
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            _k32.CloseHandle(mutex)
            return False
        self._mutex = mutex
        # Otomatik sıfırlanan olay: her SetEvent tek bir "öne gel" isteği.
        self._event = _k32.CreateEventW(None, False, False, self._event_name)
        if not self._event:
            raise OSError(ctypes.get_last_error(), f'Öne getirme olayı oluşturulamadı: {self._event_name}')
        return True

    def signal_existing(self):
        """Çalışan kopyadan penceresini göstermesini ister."""
        for _ in range(SIGNAL_RETRIES):
            event = _k32.OpenEventW(EVENT_MODIFY_STATE, False, self._event_name)
            if event:
                ctypes.windll.user32.AllowSetForegroundWindow(wintypes.DWORD(ASFW_ANY))
                _k32.SetEvent(event)
                _k32.CloseHandle(event)
                return
            time.sleep(SIGNAL_RETRY_S)
        raise OSError(ctypes.get_last_error(), f'Çalışan kopyaya ulaşılamadı: {self._event_name}')

    def listen(self, on_show: Callable[[], None]):
        """Her "öne gel" isteğinde on_show'u arka plan iş parçacığında çağırır."""
        if self._event is None:
            raise RuntimeError('listen() yalnız acquire() True döndükten sonra çağrılabilir.')

        def loop():
            while _k32.WaitForSingleObject(self._event, INFINITE) == WAIT_OBJECT_0:
                on_show()

        threading.Thread(target=loop, name='single-instance', daemon=True).start()
