# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

# Arayüz derlemesi (cd webui && npm run build) EXE'ye gömülür; yoksa derleme anlamsız.
if not os.path.isfile(os.path.join('webui', 'dist', 'index.html')):
    raise SystemExit("webui/dist yok: önce 'cd webui && npm install && npm run build' çalıştır.")

datas = [
    ('locales', 'locales'),
    ('extension/icons', 'extension/icons'),
    ('native_host', 'native_host'),
    ('cache', 'cache'),
    ('webui/dist', 'webui/dist'),
    ('assets', 'assets'),
]

# FFmpeg ikili dosyalarını EXE yanına ekle
import glob as _glob
_ffmpeg_src = next(iter(_glob.glob(os.path.join('.', 'ffmpeg*', 'bin'))), None)
if _ffmpeg_src:
    for _f in ('ffmpeg.exe', 'ffprobe.exe'):
        _fp = os.path.join(_ffmpeg_src, _f)
        if os.path.exists(_fp):
            datas.append((_fp, 'ffmpeg-bin'))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'webview',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'clr',
        # pystray arka ucu çalışma anında seçiliyor, PyInstaller kendisi göremiyor.
        'pystray._win32',
        'yt_dlp',
        'mutagen',
        'mutagen.mp3',
        'mutagen.id3',
        'mutagen.mp4',
        'pyperclip',
        'win11toast',
        'src.core.auto_categorize',
        'src.core.profiles',
        'src.core.plugin_manager',
        'src.core.subscription_manager',
        'src.web.app',
        'src.web.api',
        'src.web.tray',
        'native_host.native_host',
    ],
    hookspath=[],
    runtime_hooks=[],
    # Whisper (torch + llvmlite ~480 MB) EXE'ye girmez; döküm, kurulu Python'la çalışırken kullanılabilir.
    # numpy zaten dışarıda olduğu için gömülse de çalışmazdı.
    excludes=['tkinter', 'matplotlib', 'numpy', 'whisper', 'torch', 'llvmlite', 'numba', 'tiktoken'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='YouTubeIndirici',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YouTubeIndirici',
)
