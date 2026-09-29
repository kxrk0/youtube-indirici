#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yayın dosyalarını üretir: arayüz derlemesi → PyInstaller → FFmpeg → NSIS kurucu + zip.

Çalıştırma (depo kökünden):  venv\\Scripts\\python.exe installer\\build_release.py
Çıktı: release\\YouTubeIndirici_<sürüm>-Setup.exe ve release\\YouTubeIndirici-v<sürüm>.zip

2.6.1 ve öncesinin güncelleyicisi yayındaki ilk .exe/.zip'i alıyor; kurucuyu alırsa EXE'nin
üzerine kopyalayıp uygulamayı bozar. GitHub varlıkları yükleme sırasına göre değil ada göre
sıralıyor (v2.6.2'de görüldü), bu yüzden adlar zip önce gelecek biçimde seçildi ('_' > '-').
Kurucu adı '-Setup.exe' ile bitmeli (updater.INSTALLER_SUFFIX).
"""
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from urllib.request import Request, urlopen

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

# Kurucu FFmpeg'i sistemde bulamazsa bunu kurar. gyan.dev Windows için resmi FFmpeg sitesinin
# gösterdiği statik derleme; yanındaki .sha256 ile doğrulanır.
FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
FFMPEG_SHA256_URL = FFMPEG_URL + '.sha256'
# Zip içindeki '<sürüm>-essentials_build/' klasörüne göre yollar. LICENSE: GPL, ikiliyle dağıtılmalı.
FFMPEG_MEMBERS = {'bin/ffmpeg.exe': 'ffmpeg.exe', 'bin/ffprobe.exe': 'ffprobe.exe', 'LICENSE': 'LICENSE'}
# PyInstaller'ın build\ klasörü; kökteki ffmpeg* klasörlerini spec EXE'ye gömer, buraya gömmez.
FFMPEG_CACHE_DIR = os.path.join(ROOT, 'build', 'ffmpeg')
# Soket başına süre sınırı (indirme ~100 MB; toplam süreye değil, takılan bağlantıya karşı).
FFMPEG_SOCKET_TIMEOUT_S = 60
DOWNLOAD_CHUNK_BYTES = 1 << 20


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


def _download(url: str, dest: str):
    req = Request(url, headers={'User-Agent': f'YouTubeIndirici-build/{APP_VERSION}'})
    try:
        with urlopen(req, timeout=FFMPEG_SOCKET_TIMEOUT_S) as resp, open(dest, 'wb') as out:
            while chunk := resp.read(DOWNLOAD_CHUNK_BYTES):
                out.write(chunk)
    except OSError as e:
        raise SystemExit(f'{url} indirilemedi: {e}') from e


def extract_ffmpeg(archive: str, dest_dir: str):
    """Zip'ten FFMPEG_MEMBERS'ı dest_dir'e düz yazar; biri eksikse SystemExit."""
    with zipfile.ZipFile(archive) as z:
        by_suffix = {}
        for name in z.namelist():
            _, _, inner = name.partition('/')
            if inner in FFMPEG_MEMBERS:
                by_suffix[inner] = name
        missing = sorted(set(FFMPEG_MEMBERS) - set(by_suffix))
        if missing:
            raise SystemExit(f'FFmpeg zip\'inde beklenen dosyalar yok: {missing} ({archive})')
        os.makedirs(dest_dir, exist_ok=True)
        for inner, name in by_suffix.items():
            with z.open(name) as src, open(os.path.join(dest_dir, FFMPEG_MEMBERS[inner]), 'wb') as out:
                shutil.copyfileobj(src, out)


def fetch_ffmpeg() -> str:
    """Kurucuya girecek FFmpeg klasörü. build\\ffmpeg doluysa onu kullanır; yenilemek için o klasörü sil."""
    if all(os.path.isfile(os.path.join(FFMPEG_CACHE_DIR, f)) for f in FFMPEG_MEMBERS.values()):
        return FFMPEG_CACHE_DIR
    os.makedirs(os.path.dirname(FFMPEG_CACHE_DIR), exist_ok=True)
    archive = FFMPEG_CACHE_DIR + '.zip'
    sha_file = archive + '.sha256'
    print(f'> FFmpeg indiriliyor: {FFMPEG_URL}', flush=True)
    _download(FFMPEG_SHA256_URL, sha_file)
    _download(FFMPEG_URL, archive)
    with open(sha_file, encoding='ascii') as f:
        expected = f.read().split()[0].lower()
    digest = hashlib.sha256()
    with open(archive, 'rb') as f:
        while chunk := f.read(DOWNLOAD_CHUNK_BYTES):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise SystemExit(f'FFmpeg zip\'i doğrulanamadı: SHA256 {digest.hexdigest()} != {expected} ({FFMPEG_URL}). '
                         f'Yeniden dene; sürerse sürüm arada değişmiş olabilir.')
    staging = FFMPEG_CACHE_DIR + '.tmp'
    shutil.rmtree(staging, ignore_errors=True)
    extract_ffmpeg(archive, staging)
    shutil.rmtree(FFMPEG_CACHE_DIR, ignore_errors=True)
    os.rename(staging, FFMPEG_CACHE_DIR)
    os.remove(archive)
    os.remove(sha_file)
    return FFMPEG_CACHE_DIR


def release_names(version: str) -> tuple[str, str]:
    """(zip, kurucu) dosya adları; ada göre sıralamada zip önce gelir (modül açıklaması)."""
    return f'{APP_DIR_NAME}-v{version}.zip', f'{APP_DIR_NAME}_{version}-Setup.exe'


def main():
    makensis = _makensis()
    npm = shutil.which('npm')
    if not npm:
        raise SystemExit('npm bulunamadı; arayüz derlenemiyor. Node.js kurulu olmalı.')
    _run([npm, 'run', 'build'], os.path.join(ROOT, 'webui'), WEBUI_TIMEOUT_S)
    _run([sys.executable, '-m', 'PyInstaller', 'youtube_indirici.spec', '--noconfirm'], ROOT, PYINSTALLER_TIMEOUT_S)
    if not os.path.isfile(os.path.join(DIST_DIR, f'{APP_DIR_NAME}.exe')):
        raise SystemExit(f'PyInstaller çıktısı yok: {DIST_DIR}')
    # 2.6.3'e kadar spec geliştiricinin cache\ klasörünü (geçmiş, ayarlar, API anahtarı) pakete koyuyordu.
    bundled_cache = os.path.join(DIST_DIR, '_internal', 'cache')
    if os.path.exists(bundled_cache):
        raise SystemExit(f'Pakette kişisel veri var: {bundled_cache}. youtube_indirici.spec datas listesine bak.')
    ffmpeg_dir = fetch_ffmpeg()

    os.makedirs(RELEASE_DIR, exist_ok=True)
    zip_name, setup_name = release_names(APP_VERSION)
    setup = os.path.join(RELEASE_DIR, setup_name)
    _run([makensis, '/V2', f'/DVERSION={APP_VERSION}', f'/DDIST={DIST_DIR}', f'/DFFMPEG_DIR={ffmpeg_dir}',
          f'/DOUTFILE={setup}', NSI_SCRIPT],
         os.path.join(ROOT, 'installer'), MAKENSIS_TIMEOUT_S)
    archive = shutil.make_archive(os.path.join(RELEASE_DIR, zip_name.removesuffix('.zip')), 'zip',
                                  root_dir=os.path.dirname(DIST_DIR), base_dir=APP_DIR_NAME)
    print(f"\nSürüm {APP_VERSION} hazır:\n  {archive}\n  {setup}")


if __name__ == '__main__':
    main()
