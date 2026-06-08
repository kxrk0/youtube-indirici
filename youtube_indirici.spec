# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# qfluentwidgets kaynaklarını önceden topla — Analysis'e INPUT olarak ver
qfw_datas, qfw_binaries, qfw_hiddenimports = collect_all('qfluentwidgets')

datas = [
    ('locales', 'locales'),
    ('extension/icons', 'extension/icons'),
    ('native_host', 'native_host'),
    ('cache', 'cache'),
] + qfw_datas

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
    binaries=qfw_binaries,
    datas=datas,
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        'qfluentwidgets',
        'yt_dlp',
        'flask',
        'flask_cors',
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
        'src.ui.mini_window',
        'src.ui.notification_center',
        'native_host.native_host',
    ] + qfw_hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy'],
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
    icon='extension/icons/app.ico' if os.path.exists('extension/icons/app.ico') else None,
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
