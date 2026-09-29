#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Günlük ve tanılama. Arka plan: kurulu EXE konsolsuz; print ve yakalanmamış hata izleri
kayboluyordu, 2.7.0 -> 2.7.1 güncelleme hatası günlükten değil süreçlerden bulundu.

Günlük sys.stdout/sys.stderr'i değiştirdiği için ayrı süreçte denenir.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_TIMEOUT_S = 60

# Konsolsuz EXE gibi: akışlar None iken günlük kurulur, sonra print, iş parçacığında ve ana
# iş parçacığında yakalanmamış hata.
WINDOWED_APP = '''
import sys, threading
sys.path.insert(0, {root!r})
sys.stdout = None
sys.stderr = None
from src.utils import app_log
path = app_log.install({data!r})
print('merhaba günlük')
t = threading.Thread(target=lambda: 1 / 0)
t.start(); t.join()
raise RuntimeError('ana iş parçacığı çöktü')
'''


def _run(code):
    # Uygulama akışları main.py'de UTF-8'e sabitliyor; alt süreçte aynısı ortamla.
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    return subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, encoding='utf-8',
                          timeout=RUN_TIMEOUT_S, env=env)


def test_windowed_app_output_and_crashes_reach_the_log(tmp_path):
    _run(WINDOWED_APP.format(root=ROOT, data=str(tmp_path)))
    log = (tmp_path / 'logs' / 'app.log').read_text(encoding='utf-8')
    assert 'merhaba günlük' in log
    assert 'ZeroDivisionError' in log, 'iş parçacığındaki hata günlüğe düşmeli'
    assert 'RuntimeError: ana iş parçacığı çöktü' in log
    first = log.splitlines()[0]
    assert first[:4].isdigit() and first[4] == '-', f'satır zaman damgasıyla başlamalı: {first!r}'


def test_console_still_gets_output(tmp_path):
    code = f'''
import sys
sys.path.insert(0, {ROOT!r})
from src.utils import app_log
app_log.install({str(tmp_path)!r})
print('konsolda da')
'''
    result = _run(code)
    assert result.stdout.strip() == 'konsolda da', 'konsol çıktısı damgasız ve aynen kalmalı'
    assert 'konsolda da' in (tmp_path / 'logs' / 'app.log').read_text(encoding='utf-8')


def test_large_log_rolls_over_on_start(tmp_path):
    logs = tmp_path / 'logs'
    logs.mkdir()
    (logs / 'app.log').write_bytes(b'x' * 1_000_001)
    code = f'''
import sys
sys.path.insert(0, {ROOT!r})
from src.utils import app_log
app_log.install({str(tmp_path)!r})
print('yeni')
'''
    _run(code)
    assert (logs / 'app.1.log').stat().st_size == 1_000_001
    assert 'yeni' in (logs / 'app.log').read_text(encoding='utf-8')
    assert (logs / 'app.log').stat().st_size < 1000


def test_tail_before_install_says_so():
    code = f'''
import sys
sys.path.insert(0, {ROOT!r})
from src.utils import app_log
print(app_log.tail())
'''
    assert _run(code).stdout.strip() == '(günlük kurulmadı)'


def test_diagnostics_names_versions_paths_and_log_tail(tmp_path, monkeypatch):
    from src.core import media_library
    from src.utils import app_log
    from src.utils.updater import APP_VERSION
    from src.web.api import OrtamApi
    log = tmp_path / 'app.log'
    log.write_text('önceki satır\nson satır\n', encoding='utf-8')
    monkeypatch.setattr(app_log, '_log_path', str(log))
    monkeypatch.setattr(media_library, 'library_dirs', lambda: [str(tmp_path)])
    text = OrtamApi(None).diagnostics()
    assert f'YouTube Studio Downloader {APP_VERSION}' in text
    assert 'FFmpeg:' in text and 'yt-dlp:' in text and str(tmp_path) in text
    assert text.rstrip().endswith('son satır')
