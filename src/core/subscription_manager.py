#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Abonelik yöneticisi — kanal/playlist'i periyodik olarak kontrol eder,
yeni içerik varsa otomatik indirme başlatır.
"""

from __future__ import annotations
import re
from typing import Optional, List, Dict, Callable


def check_channel_new_videos(channel_url: str, known_urls: set = None) -> List[Dict]:
    """
    yt-dlp ile kanal/playlist sayfasını tarar, yeni video URL'lerini döndürür.
    known_urls — daha önce indirilen URL'ler kümesi (bunlar çıkarılır).
    """
    try:
        import yt_dlp
        ydl_opts = {
            'quiet':        True,
            'no_warnings':  True,
            'extract_flat': 'in_playlist',
            'playlistend':  20,       # sadece son 20 videoyu al
            'noplaylist':   False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
        if not info:
            return []
        entries = info.get('entries', []) or []
        result = []
        for e in entries:
            if not e:
                continue
            url = e.get('url') or e.get('webpage_url') or ''
            if not url:
                # build from id
                vid_id = e.get('id', '')
                if vid_id:
                    url = f'https://www.youtube.com/watch?v={vid_id}'
            if not url:
                continue
            if known_urls and url in known_urls:
                continue
            result.append({
                'url':      url,
                'title':    e.get('title', 'Başlıksız'),
                'duration': e.get('duration', 0),
            })
        return result
    except Exception as e:
        print(f"[SubMgr] Kanal kontrolü hatası: {e}")
        return []


def get_channel_name(channel_url: str) -> Optional[str]:
    """Kanal/playlist adını döndürür."""
    try:
        import yt_dlp
        ydl_opts = {
            'quiet': True, 'no_warnings': True,
            'extract_flat': True, 'playlistend': 1,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
        if info:
            return info.get('channel') or info.get('uploader') or info.get('title') or None
    except Exception:
        pass
    return None
