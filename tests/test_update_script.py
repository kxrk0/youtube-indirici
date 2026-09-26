#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Güncelleme betiği regresyon testleri.

Arka plan: betik uygulamanın kapanmasını sabit 2 sn bekliyordu. Kapanış daha uzun
sürünce .exe kilitliyken xcopy sessizce başarısız oluyor, eski sürüm yeniden
açılıyordu (v2.2.0 test derlemesinde .exe'nin değişmediği görüldü). Betik artık
süreç gerçekten kapanana kadar bekliyor, kopyalama başarısızsa bunu söylüyor.
"""
import os
import shutil
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
    script = updater.build_update_script(app.pid, str(app_exe), str(app_dir), str(source), 'zip', str(update_tmp))
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
        script = updater.build_update_script(app.pid, str(app_exe), str(app_dir), str(source), 'zip', str(update_tmp))
        output = _run(script, update_tmp)
    finally:
        app.kill()
    assert (app_dir / 'surum.txt').read_text(encoding='utf-8').strip() == 'eski'
    assert 'kurulamadi' in output
    assert _wait_for(started), 'eski sürüm yeniden açılmadı'
    assert update_tmp.exists(), 'başarısız kurulumda indirilen dosyalar silinmemeli'


MAKENSIS_CANDIDATES = (r'C:\Program Files (x86)\NSIS\makensis.exe', r'C:\Program Files\NSIS\makensis.exe')
MAKENSIS = shutil.which('makensis') or next((p for p in MAKENSIS_CANDIDATES if os.path.isfile(p)), None)
BUILD_TIMEOUT_S = 60

# Güncelleyicinin kurucuyu çağırdığı biçimi (/S /D=klasör) sınayan en küçük NSIS kurucusu.
FAKE_INSTALLER_NSI = '''
Unicode true
RequestExecutionLevel user
OutFile "{out}"
InstallDir "$TEMP\\yanlis_klasor"
Section
  SetOutPath "$INSTDIR"
  FileOpen $0 "$INSTDIR\\surum.txt" w
  FileWrite $0 "yeni"
  FileClose $0
SectionEnd
'''


def test_update_asset_prefers_installer_then_zip():
    zip_asset = {'name': 'YouTubeIndirici-v2.6.2.zip', 'browser_download_url': 'https://x/zip'}
    setup = {'name': 'YouTubeIndirici-2.6.2-Setup.exe', 'browser_download_url': 'https://x/setup'}
    assert updater.pick_update_asset([zip_asset, setup]) == 'https://x/setup'
    assert updater.pick_update_asset([zip_asset]) == 'https://x/zip'
    assert updater.pick_update_asset([{'name': 'notlar.txt', 'browser_download_url': 'https://x/t'}]) is None


@pytest.mark.skipif(MAKENSIS is None, reason='NSIS (makensis) kurulu değil')
def test_runs_installer_silently_into_app_folder_after_app_exits(tmp_path):
    app_dir, app_exe, _, update_tmp, started = _layout(tmp_path)
    app_dir_spaced = tmp_path / 'Kurulu Uygulama'
    app_dir.rename(app_dir_spaced)
    app_exe = app_dir_spaced / 'app.bat'
    installer = update_tmp / 'YouTubeIndirici-9.9.9-Setup.exe'
    nsi = tmp_path / 'sahte.nsi'
    nsi.write_text(FAKE_INSTALLER_NSI.format(out=installer), encoding='utf-8')
    subprocess.run([MAKENSIS, '/V1', str(nsi)], check=True, timeout=BUILD_TIMEOUT_S, capture_output=True)

    app = subprocess.Popen([sys.executable, '-c', f'import time; time.sleep({APP_ALIVE_S})'])
    script = updater.build_update_script(app.pid, str(app_exe), str(app_dir_spaced), str(installer), 'installer',
                                         str(update_tmp))
    _run(script, update_tmp)
    assert app.poll() is not None, 'betik uygulama kapanmadan bitti'
    # /D boşluklu yolda da tırnaksız verilmeli; yanlışsa kurucu varsayılan klasöre kurar.
    assert (app_dir_spaced / 'surum.txt').read_text(encoding='utf-8').strip() == 'yeni'
    assert _wait_for(started), 'yeni sürüm açılmadı'
    assert not update_tmp.exists(), 'geçici klasör silinmedi'


def test_release_names_keep_zip_before_installer_for_old_updaters():
    """GitHub varlıkları ada göre sıralıyor; 2.6.1 ve öncesi ilk .exe/.zip'i alır ve kurucuyu
    EXE'nin üzerine kopyalardı. Zip her iki harf duyarlılığında da önce gelmeli."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'installer'))
    from build_release import release_names
    zip_name, setup_name = release_names('2.6.10')
    assert sorted([setup_name, zip_name]) == [zip_name, setup_name]
    assert sorted([setup_name, zip_name], key=str.lower) == [zip_name, setup_name]
    assert setup_name.lower().endswith(updater.INSTALLER_SUFFIX)
    assert updater.pick_update_asset([{'name': n, 'browser_download_url': n} for n in (zip_name, setup_name)]) == setup_name
