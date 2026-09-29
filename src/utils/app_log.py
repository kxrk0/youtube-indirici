#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uygulama günlüğü: stdout/stderr'e yazılan her şey zaman damgasıyla <veri klasörü>\\logs\\app.log'a da gider.

Neden: kurulu EXE konsolsuz (windowed); PyInstaller orada sys.stdout ve sys.stderr'i None yapıyor,
kodun her yerindeki print ve yakalanmamış hata izleri (iş parçacıkları dahil) kayboluyordu.
2.7.0 -> 2.7.1 güncelleme hatası bu yüzden günlükten değil süreç ve dosya zamanlarından bulundu.
Varsayılan sys.excepthook ve threading.excepthook sys.stderr'e yazdığı için yakalanmamış hatalar
ayrıca bir kanca gerekmeden günlüğe düşer. Konsol varsa (kaynak koddan çalışırken) oraya da yazılır.
"""
import datetime
import os
import sys
import threading
from typing import Optional, TextIO

LOG_DIR_NAME = 'logs'
LOG_FILE_NAME = 'app.log'
# Açılışta bu boyutu aşan günlük app.1.log olur (bir önceki silinir): 2 x 1 MB en fazla.
MAX_LOG_BYTES = 1_000_000
# Tanılama metnine giren son günlük satırı sayısı.
DIAGNOSTIC_TAIL_LINES = 200

_log_path: Optional[str] = None


class _TimestampedTee:
    """Satır başlarına zaman damgası koyarak dosyaya, varsa özgün akışa da olduğu gibi yazar."""

    def __init__(self, log_file: TextIO, original: Optional[TextIO], lock: threading.Lock):
        self._file = log_file
        self._original = original
        self._lock = lock
        self._at_line_start = True
        self.encoding = 'utf-8'

    def write(self, text: str) -> int:
        if not text:
            return 0
        with self._lock:
            out = []
            for part in text.splitlines(keepends=True):
                if self._at_line_start:
                    out.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ' ')
                out.append(part)
                self._at_line_start = part.endswith('\n')
            self._file.write(''.join(out))
            self._file.flush()
        if self._original is not None:
            try:
                self._original.write(text)
            except (OSError, ValueError):
                # Konsol kapanmış olabilir; günlük yine de yazıldı.
                pass
        return len(text)

    def flush(self):
        with self._lock:
            self._file.flush()
        if self._original is not None:
            try:
                self._original.flush()
            except (OSError, ValueError):
                pass

    def isatty(self) -> bool:
        return False


def install(data_dir: str) -> str:
    """sys.stdout ve sys.stderr'i günlüğe bağlar; günlük dosyasının yolunu döner. Bir kez çağrılır."""
    global _log_path
    if _log_path is not None:
        return _log_path
    log_dir = os.path.join(data_dir, LOG_DIR_NAME)
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, LOG_FILE_NAME)
    if os.path.exists(path) and os.path.getsize(path) > MAX_LOG_BYTES:
        os.replace(path, os.path.join(log_dir, 'app.1.log'))
    log_file = open(path, 'a', encoding='utf-8', errors='replace', buffering=1)
    lock = threading.Lock()
    sys.stdout = _TimestampedTee(log_file, sys.stdout, lock)
    sys.stderr = _TimestampedTee(log_file, sys.stderr, lock)
    _log_path = path
    return path


def log_path() -> Optional[str]:
    return _log_path


def tail(lines: int = DIAGNOSTIC_TAIL_LINES) -> str:
    """Günlüğün son satırları; günlük kurulmamışsa ya da okunamıyorsa nedenini döner."""
    if _log_path is None:
        return '(günlük kurulmadı)'
    try:
        with open(_log_path, 'r', encoding='utf-8', errors='replace') as f:
            return ''.join(f.readlines()[-lines:])
    except OSError as e:
        return f'(günlük okunamadı: {_log_path}: {e})'
