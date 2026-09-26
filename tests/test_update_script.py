#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Güncelleme betiği regresyon testleri.

Arka plan: betik uygulamanın kapanmasını sabit 2 sn bekliyordu. Kapanış daha uzun
sürünce .exe kilitliyken xcopy sessizce başarısız oluyor, eski sürüm yeniden
açılıyordu (v2.2.0 test derlemesinde .exe'nin değişmediği görüldü). Betik artık
süreç gerçekten kapanana kadar bekliyor, kopyalama başarısızsa bunu söylüyor.
"""
import subprocess
import sys
import time

import pytest

from src.utils import updater

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='güncelleme betiği Windows cmd için')

APP_ALIVE_S = 3
SCRIPT_TIMEOUT_S = 30


def _layout(tmp_path):
    app_dir = tmp_path / 'app'
    app_dir.mkdir()
    (app_dir / 'surum.txt').write_text('eski', encoding='utf-8')
    started = tmp_path / 'acildi.txt'
    # Betiğin "uygulamayı aç" adımı: gerçek EXE yerine işaret dosyası yazan küçük bir .bat.
    # start bir .bat'ı `cmd /K` ile açar; exit olmadan pencere (ve süreç) açık kalır.
    app_exe = app_dir / 'app.bat'
    app_exe.write_text(f'@echo acildi > "{started}"\r\nexit\r\n', encoding='ascii')
    update_tmp = tmp_path / 'ydl_update'
    source = update_tmp / 'extracted' / 'YouTubeIndirici'
    source.mkdir(parents=True)
    (source / 'surum.txt').write_text('yeni', encoding='utf-8')
    return app_dir, app_exe, source, update_tmp, started


def _run(script: str, update_tmp) -> str:
    """Betiği çalıştırır, konsol çıktısını döner. Çıktı boru yerine dosyaya: `start` ile açılan
    alt süreç boruyu devralıp açık tutarsa subprocess beklemede kalıyordu."""
    bat = update_tmp.parent / 'do_update.bat'
    log = update_tmp.parent / 'do_update.log'
    updater.write_update_script(str(bat), script)
    with open(log, 'wb') as out:
        subprocess.run(['cmd', '/c', str(bat)], stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                       timeout=SCRIPT_TIMEOUT_S, creationflags=subprocess.CREATE_NO_WINDOW)
    return log.read_bytes().decode('utf-8', 'replace')


def _wait_for(path, timeout_s=10):
    end = time.time() + timeout_s
    while time.time() < end and not path.exists():
        time.sleep(0.1)
    return path.exists()


def test_waits_for_app_to_exit_before_copying(tmp_path):
    app_dir, app_exe, source, update_tmp, started = _layout(tmp_path)
    app = subprocess.Popen([sys.executable, '-c', f'import time; time.sleep({APP_ALIVE_S})'])
    t0 = time.time()
    script = updater.build_update_script(app.pid, str(app_exe), str(app_dir), str(source), True, str(update_tmp))
    _run(script, update_tmp)
    assert app.poll() is not None, 'betik uygulama kapanmadan bitti'
    assert time.time() - t0 >= APP_ALIVE_S - 0.5
    assert (app_dir / 'surum.txt').read_text(encoding='utf-8').strip() == 'yeni'
    assert _wait_for(started), 'yeni sürüm açılmadı'
    assert not update_tmp.exists(), 'geçici klasör silinmedi'


def test_gives_up_and_reopens_old_version_when_app_never_exits(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, 'UPDATE_EXIT_WAIT_S', 1)
    monkeypatch.setattr(updater, 'UPDATE_ERROR_SHOW_S', 0)
    app_dir, app_exe, source, update_tmp, started = _layout(tmp_path)
    app = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        script = updater.build_update_script(app.pid, str(app_exe), str(app_dir), str(source), True, str(update_tmp))
        output = _run(script, update_tmp)
    finally:
        app.kill()
    assert (app_dir / 'surum.txt').read_text(encoding='utf-8').strip() == 'eski'
    assert 'kurulamadi' in output
    assert _wait_for(started), 'eski sürüm yeniden açılmadı'
    assert update_tmp.exists(), 'başarısız kurulumda indirilen dosyalar silinmemeli'
