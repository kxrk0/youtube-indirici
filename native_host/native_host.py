#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chrome Native Messaging Host — YouTube İndirici
Masaüstü uygulaması açık olmasa bile eklentiden indirme yapar.

Protokol: 4-byte LE uint32 uzunluk + UTF-8 JSON (stdin/stdout)

Mesaj formatı (gelen):
  { "url": str, "formatType": "video"|"audio", "format": str, "title": str }

Mesaj formatı (giden):
  { "status": "started"|"completed"|"error", "folder": str, "message": str }
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import shutil
from pathlib import Path

# Kayıt klasörü: ~/Downloads/YDL İndirilenler
DOWNLOADS_DIR = str(Path.home() / "Downloads" / "YDL İndirilenler")


# ─── Native Messaging I/O ────────────────────────────────────────────────────

def _read_message() -> dict | None:
    """stdin'den 4-byte uzunluk + JSON oku."""
    try:
        raw_len = sys.stdin.buffer.read(4)
        if not raw_len or len(raw_len) < 4:
            return None
        length = struct.unpack('<I', raw_len)[0]
        data = sys.stdin.buffer.read(length)
        return json.loads(data.decode('utf-8'))
    except Exception:
        return None


def _write_message(msg: dict):
    """stdout'a 4-byte uzunluk + JSON yaz."""
    try:
        data = json.dumps(msg, ensure_ascii=False).encode('utf-8')
        sys.stdout.buffer.write(struct.pack('<I', len(data)))
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    except Exception:
        pass


# ─── yt-dlp Bulma ────────────────────────────────────────────────────────────

def _find_ytdlp() -> list[str]:
    """yt-dlp binary veya Python modülü yolunu döndür."""
    # 1. PATH'te yt-dlp var mı?
    for candidate in ['yt-dlp', 'yt-dlp.exe']:
        if shutil.which(candidate):
            return [candidate]

    # 2. Uygulama EXE'si yanında dist/ içinde var mı?
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    for name in ['yt-dlp.exe', 'yt-dlp']:
        p = os.path.join(exe_dir, name)
        if os.path.exists(p):
            return [p]

    # 3. Python modülü olarak çalıştır
    return [sys.executable, '-m', 'yt_dlp']


# ─── İndirme ─────────────────────────────────────────────────────────────────

def _do_download(msg: dict):
    url        = msg.get('url', '').strip()
    fmt_type   = msg.get('formatType', 'video')   # 'video' or 'audio'
    fmt        = msg.get('format', 'best')
    title      = msg.get('title', 'download')

    if not url:
        _write_message({'status': 'error', 'message': 'URL boş'})
        return

    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    output_template = os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s')
    ytdlp_cmd = _find_ytdlp()

    cmd = ytdlp_cmd + [
        '--no-playlist',
        '--no-warnings',
        '-o', output_template,
    ]

    if fmt_type == 'audio':
        cmd += [
            '-x',
            '--audio-format', 'mp3',
            '--audio-quality', '0',
        ]
    else:
        # Hedef: en iyi MP4
        if fmt and fmt not in ('best', 'auto', 'video', ''):
            cmd += ['-f', fmt]
        else:
            cmd += [
                '-f',
                'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best',
            ]
        cmd += ['--merge-output-format', 'mp4']

    cmd.append(url)

    # İndirme başladı bildirimi
    _write_message({'status': 'started', 'url': url, 'title': title})

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            encoding='utf-8',
            errors='replace',
        )
        if result.returncode == 0:
            _write_message({'status': 'completed', 'folder': DOWNLOADS_DIR})
        else:
            err = (result.stderr or result.stdout or 'yt-dlp hatası').strip()
            _write_message({'status': 'error', 'message': err[-300:]})

    except subprocess.TimeoutExpired:
        _write_message({'status': 'error', 'message': 'Zaman aşımı (10 dk)'})
    except FileNotFoundError:
        _write_message({
            'status': 'error',
            'message': 'yt-dlp bulunamadı. PATH\'e ekleyin veya masaüstü uygulamasını açın.'
        })
    except Exception as e:
        _write_message({'status': 'error', 'message': str(e)})


# ─── Entry Point ─────────────────────────────────────────────────────────────

def run_native_host():
    """Ana döngü — Chrome'dan mesaj oku, işle, yanıtla."""
    msg = _read_message()
    if msg:
        _do_download(msg)


if __name__ == '__main__':
    run_native_host()
