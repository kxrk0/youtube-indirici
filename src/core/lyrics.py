#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Şarkı Sözleri (Lyrics) Modülü
lrclib.net üzerinden senkronize (.lrc) veya düz (.txt) sözler alır.
Auth gerekmez, ücretsiz, no-rate-limit.
"""

import json
import os
import re
import ssl
import urllib.parse
import urllib.request
from typing import Optional

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_BASE = 'https://lrclib.net/api'
_HEADERS = {
    'User-Agent': 'YDL-Indirici/2.3 (https://github.com/kxrk0/youtube-indirici)',
    'Accept': 'application/json',
}


def _get(path: str, params: dict = None) -> Optional[list | dict]:
    url = _BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f"[Lyrics] HTTP error: {e}")
        return None


def _clean(s: str) -> str:
    return re.sub(r'[^\w\s]', '', s or '').strip().lower()


def fetch_lrc(title: str, artist: str = '', duration_s: int = 0) -> Optional[str]:
    """
    .lrc formatında senkronize sözleri döndürür.
    Bulamazsa plain text sözleri döndürür.
    Hiç bulamazsa None.

    Args:
        title: Şarkı adı
        artist: Sanatçı adı (opsiyonel, kalite artırır)
        duration_s: Saniye cinsinden süre (opsiyonel, kesinliği artırır)
    """
    # 1. Direkt lookup (en kesin — title + artist + duration üçlüsü)
    if artist and duration_s:
        params = {
            'track_name': title,
            'artist_name': artist,
            'duration': duration_s,
        }
        data = _get('/get', params)
        if isinstance(data, dict) and not data.get('statusCode'):
            synced = data.get('syncedLyrics')
            if synced:
                print(f"[Lyrics] Senkronize sözler bulundu: {title}")
                return synced
            plain = data.get('plainLyrics')
            if plain:
                return plain

    # 2. Arama (daha geniş)
    search_params: dict = {'track_name': title}
    if artist:
        search_params['artist_name'] = artist
    results = _get('/search', search_params)
    if not isinstance(results, list) or not results:
        # 3. Son deneme — sadece başlıkla
        results = _get('/search', {'q': f'{artist} {title}'.strip()}) or []

    if not isinstance(results, list) or not results:
        print(f"[Lyrics] Bulunamadı: {title}")
        return None

    # En iyi eşleşmeyi seç
    clean_title = _clean(title)
    clean_artist = _clean(artist)

    scored: list[tuple[int, dict]] = []
    for r in results:
        score = 0
        if _clean(r.get('trackName', '')) == clean_title:
            score += 3
        elif clean_title in _clean(r.get('trackName', '')):
            score += 1
        if artist and _clean(r.get('artistName', '')) == clean_artist:
            score += 2
        if r.get('syncedLyrics'):
            score += 1
        scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0][1]

    synced = best.get('syncedLyrics')
    if synced:
        print(f"[Lyrics] Senkronize sözler: {best.get('trackName')}")
        return synced
    plain = best.get('plainLyrics')
    if plain:
        print(f"[Lyrics] Düz sözler: {best.get('trackName')}")
        return plain

    return None


def save_lrc(audio_path: str, title: str, artist: str = '',
             duration_s: int = 0) -> Optional[str]:
    """
    Sözleri alır ve audio_path'ın yanına .lrc dosyası olarak kaydeder.
    Kaydedilen dosya yolunu döndürür, başarısız olursa None.
    """
    lrc_content = fetch_lrc(title, artist, duration_s)
    if not lrc_content:
        return None

    base = os.path.splitext(audio_path)[0]
    lrc_path = base + '.lrc'
    try:
        with open(lrc_path, 'w', encoding='utf-8') as f:
            f.write(lrc_content)
        print(f"[Lyrics] Kaydedildi: {lrc_path}")
        return lrc_path
    except Exception as e:
        print(f"[Lyrics] Kayıt hatası: {e}")
        return None
