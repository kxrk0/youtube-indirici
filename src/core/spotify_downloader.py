#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spotify indirme motoru.
Akış:
  1. Spotify oEmbed API → şarkı adı + sanatçı + kapak (auth gerekmez)
  2. YouTube'da "Sanatçı - Şarkı audio" araması yap (yt-dlp ytsearch)
  3. En iyi ses formatını MP3 olarak indir (FFmpeg ile dönüştür)
"""

import os
import re
import json
import ssl
import urllib.request
import urllib.parse
from typing import Optional, Dict, Callable

# ─── SSL (Windows sertifika sorunu bypass) ───────────────────────────────────
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode    = ssl.CERT_NONE

# ─── Endpoints ────────────────────────────────────────────────────────────────
_OEMBED_URL = 'https://open.spotify.com/oembed'

_HEADERS = {
    'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept':          'application/json, */*',
    'Accept-Language': 'en-US,en;q=0.9',
}


def _http_get_json(url: str, params: dict = None, timeout: int = 15) -> Optional[dict]:
    if params:
        url = url + '?' + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            return json.loads(resp.read().decode('utf-8', errors='replace'))
    except Exception as e:
        print(f"[SpotiDown] HTTP error: {e}")
        return None


def get_track_info(spotify_url: str) -> Optional[Dict]:
    """
    Spotify oEmbed ile şarkı başlığı, sanatçı ve kapak resmi alır.
    Auth gerektirmez. Döndürdüğü dict VideoInfoCard.update_info() ile uyumludur.
    """
    data = _http_get_json(_OEMBED_URL, {'url': spotify_url})
    if not data:
        return None

    raw_title = data.get('title', '')
    # Format genellikle "Şarkı Adı · Sanatçı" veya sadece "Şarkı Adı"
    if ' · ' in raw_title:
        parts    = raw_title.split(' · ', 1)
        title    = parts[0].strip()
        uploader = parts[1].strip()
    else:
        title    = raw_title
        uploader = data.get('provider_name', 'Spotify')

    return {
        'title':      title,
        'uploader':   uploader,
        'channel':    uploader,
        'thumbnail':  data.get('thumbnail_url', ''),
        'duration':   0,
        'is_live':    False,
        'formats':    [],
        'is_spotify': True,
    }


def _embed_metadata(mp3_path: str, title: str, artist: str, thumbnail_url: str = '') -> None:
    """Mutagen ile MP3'e ID3 tag + kapak resmi gömü. Hata sessizce yutulur."""
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3, TIT2, TPE1, APIC, error as ID3Error
        audio = MP3(mp3_path, ID3=ID3)
        try:
            audio.add_tags()
        except ID3Error:
            pass  # tags already exist
        audio.tags['TIT2'] = TIT2(encoding=3, text=title)
        audio.tags['TPE1'] = TPE1(encoding=3, text=artist)
        if thumbnail_url:
            try:
                req = urllib.request.Request(thumbnail_url, headers=_HEADERS)
                with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as resp:
                    img_data = resp.read()
                audio.tags['APIC'] = APIC(
                    encoding=3, mime='image/jpeg',
                    type=3, desc='Cover', data=img_data
                )
            except Exception:
                pass
        audio.save()
        print(f"[SpotiDown] ID3 tag yazıldı: {os.path.basename(mp3_path)}")
    except ImportError:
        print("[SpotiDown] mutagen yüklü değil — metadata embed atlandı")
    except Exception as e:
        print(f"[SpotiDown] Metadata embed hatası: {e}")


def download_track(spotify_url: str,
                   output_path: str,
                   progress_callback: Optional[Callable[[int, int, int], None]] = None,
                   cancel_flag: Optional[Callable[[], bool]] = None) -> Optional[str]:
    """
    Spotify şarkısını indirir:
      1. oEmbed → başlık + sanatçı
      2. YouTube araması: "ytsearch1:{sanatçı} - {başlık} audio"
      3. yt-dlp ile en iyi ses → MP3 (FFmpeg)

    progress_callback(pct: int, downloaded: int, total: int)
    cancel_flag() → True ise iptal et.
    Döndürür: MP3 dosya yolu veya None.
    """
    import yt_dlp

    # 1. Metadata al
    track_info = get_track_info(spotify_url)
    if not track_info:
        raise RuntimeError(
            "Spotify bilgisi alınamadı. İnternet bağlantısını kontrol edin."
        )

    title    = track_info.get('title', '')
    artist   = track_info.get('uploader', '')
    # Spotify'ın kendi adını sanatçı olarak göstermesini engelle
    if artist.lower() in ('spotify', ''):
        artist = ''

    # 2. YouTube arama sorgusu
    if artist:
        search_query = f"ytsearch1:{artist} - {title} official audio"
        safe_name    = f"{artist} - {title}"
    else:
        search_query = f"ytsearch1:{title} audio"
        safe_name    = title

    safe_name = re.sub(r'[\\/:*?"<>|]', '_', safe_name).strip()[:120] or 'spotify_track'

    # Çakışma önleme
    out_base = os.path.join(output_path, safe_name)
    counter  = 1
    final_mp3 = f"{out_base}.mp3"
    while os.path.exists(final_mp3):
        final_mp3 = f"{out_base} ({counter}).mp3"
        counter  += 1

    # yt-dlp outtmpl: uzantısız base, FFmpeg .mp3 ekler
    out_template = f"{os.path.splitext(final_mp3)[0]}.%(ext)s"

    # 3. yt-dlp progress hook
    _resolved_file = [None]

    def _progress_hook(d):
        if cancel_flag and cancel_flag():
            raise yt_dlp.utils.DownloadError("İptal edildi")

        status = d.get('status')
        if status == 'downloading' and progress_callback:
            downloaded = d.get('downloaded_bytes', 0)
            total      = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            pct        = int(downloaded / total * 100) if total else 0
            progress_callback(pct, downloaded, total)
        elif status == 'finished':
            _resolved_file[0] = d.get('filename', '')

    # FFmpeg konumu
    try:
        from src.utils.helpers import get_ffmpeg_path
        ffmpeg_dir = get_ffmpeg_path()
    except Exception:
        ffmpeg_dir = None

    ydl_opts: dict = {
        'format':         'bestaudio/best',
        'outtmpl':        out_template,
        'quiet':          True,
        'no_warnings':    True,
        'progress_hooks': [_progress_hook],
        'postprocessors': [{
            'key':               'FFmpegExtractAudio',
            'preferredcodec':    'mp3',
            'preferredquality':  '320',
        }],
        'noplaylist': True,
    }
    if ffmpeg_dir:
        ydl_opts['ffmpeg_location'] = ffmpeg_dir

    print(f"[SpotiDown] Aranıyor: {search_query}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([search_query])

    # Oluşturulan dosyayı bul (.mp3)
    if os.path.exists(final_mp3):
        _embed_metadata(final_mp3, title, artist, track_info.get('thumbnail', ''))
        print(f"[SpotiDown] İndirme tamamlandı: {final_mp3}")
        return final_mp3

    # Fallback: _resolved_file üzerinden tahmin et
    if _resolved_file[0]:
        candidate = os.path.splitext(_resolved_file[0])[0] + '.mp3'
        if os.path.exists(candidate):
            _embed_metadata(candidate, title, artist, track_info.get('thumbnail', ''))
            print(f"[SpotiDown] Dosya bulundu: {candidate}")
            return candidate

    # Son çare: output_path'taki son .mp3
    try:
        mp3s = sorted(
            [f for f in os.listdir(output_path) if f.endswith('.mp3')],
            key=lambda f: os.path.getmtime(os.path.join(output_path, f)),
            reverse=True,
        )
        if mp3s:
            found = os.path.join(output_path, mp3s[0])
            print(f"[SpotiDown] Son MP3 bulundu: {found}")
            return found
    except Exception:
        pass

    raise RuntimeError(
        f"MP3 oluşturuldu ama dosya bulunamadı. Klasörü kontrol et: {output_path}"
    )
