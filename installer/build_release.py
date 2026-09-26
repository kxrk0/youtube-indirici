#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yayın dosyalarını üretir: arayüz derlemesi → PyInstaller → NSIS kurucu + zip.

Çalıştırma (depo kökünden):  venv\\Scripts\\python.exe installer\\build_release.py
Çıktı: release\\YouTubeIndirici-<sürüm>-Setup.exe ve release\\YouTubeIndirici-v<sürüm>.zip

Yayına önce zip, sonra kurucu yüklenmeli: 2.6.1 ve öncesinin güncelleyicisi ilk .exe/.zip'i
alıyor; kurucuyu alırsa EXE'nin üzerine kopyalayıp uygulamayı bozar.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.utils.updater import APP_VERSION  # noqa: E402  (ROOT yola eklendikten sonra)

APP_DIR_NAME = 'YouTubeIndirici'
RELEASE_DIR = os.path.join(ROOT, 'release')
DIST_DIR = os.path.join(ROOT, 'dist', APP_DIR_NAME)
NSI_SCRIPT = os.path.join(ROOT, 'installer', 'youtube_indirici.nsi')
MAKENSIS_CANDIDATES = (r'C:\Program Files (x86)\NSIS\makensis.exe', r'C:\Program Files\NSIS\makensis.exe')
# Adım süre sınırları (bu makinede ölçülen: arayüz ~1 sn, PyInstaller ~80 sn, NSIS ~40 sn).
WEBUI_TIMEOUT_S = 300
PYINSTALLER_TIMEOUT_S = 900
MAKENSIS_TIMEOUT_S = 600


def _makensis() -> str:
    found = shutil.which('makensis') or next((p for p in MAKENSIS_CANDIDATES if os.path.isfile(p)), None)
    if not found:
        raise SystemExit('makensis bulunamadı. NSIS kur: winget install NSIS.NSIS')
    return found


def _run(cmd: list, cwd: str, timeout_s: int):
    print(f"> {' '.join(cmd)}", flush=True)
    try:
        subprocess.run(cmd, cwd=cwd, check=True, timeout=timeout_s)
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"Adım başarısız (çıkış kodu {e.returncode}): {' '.join(cmd)}") from e
    except subprocess.TimeoutExpired as e:
        raise SystemExit(f"Adım {timeout_s} sn'de bitmedi: {' '.join(cmd)}") from e


def main():
    makensis = _makensis()
    npm = shutil.which('npm')
    if not npm:
        raise SystemExit('npm bulunamadı; arayüz derlenemiyor. Node.js kurulu olmalı.')
    _run([npm, 'run', 'build'], os.path.join(ROOT, 'webui'), WEBUI_TIMEOUT_S)
    _run([sys.executable, '-m', 'PyInstaller', 'youtube_indirici.spec', '--noconfirm'], ROOT, PYINSTALLER_TIMEOUT_S)
    if not os.path.isfile(os.path.join(DIST_DIR, f'{APP_DIR_NAME}.exe')):
        raise SystemExit(f'PyInstaller çıktısı yok: {DIST_DIR}')

    os.makedirs(RELEASE_DIR, exist_ok=True)
    setup = os.path.join(RELEASE_DIR, f'{APP_DIR_NAME}-{APP_VERSION}-Setup.exe')
    _run([makensis, '/V2', f'/DVERSION={APP_VERSION}', f'/DDIST={DIST_DIR}', f'/DOUTFILE={setup}', NSI_SCRIPT],
         os.path.join(ROOT, 'installer'), MAKENSIS_TIMEOUT_S)
    archive = shutil.make_archive(os.path.join(RELEASE_DIR, f'{APP_DIR_NAME}-v{APP_VERSION}'), 'zip',
                                  root_dir=os.path.dirname(DIST_DIR), base_dir=APP_DIR_NAME)
    print(f"\nSürüm {APP_VERSION} hazır:\n  {archive}\n  {setup}")


if __name__ == '__main__':
    main()
