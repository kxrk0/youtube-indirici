#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
İndirme bittikten sonra yapılan her şey, arayüzden bağımsız:
platforma göre klasörleme, geçmiş kaydı, kuyruk kaydını silme, şarkı sözleri,
webhook, eklenti kancaları, Windows bildirimi ve ses.

Arayüz yalnızca sonucu gösterir; yan etkilerin tek kaynağı burası.
"""
import json
import os
import shutil
import threading
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from src.core.database import get_download_history
from src.utils import config as cfg

WEBHOOK_TIMEOUT_S = 5
# Tamamlandı sesi: 1 kHz, 200 ms (eski arayüzdeki ses).
BEEP_HZ = 1000
BEEP_MS = 200
DB_ERROR_MAX = 500


@dataclass
class DownloadMeta:
    url: str
    type_str: str = 'video'
    title: str = ''
    channel: str = ''
    thumbnail_url: str = ''
    duration: float = 0
    # yt-dlp format değeri; geçmişten "tekrar indir" aynı kaliteyi bunla seçer.
    format_quality: str = ''


def auto_organize(filepath: str, url: str) -> str:
    """Ayar açıksa dosyayı platform adlı alt klasöre taşır; yeni yolu döndürür."""
    if not filepath or not cfg.get('auto_organize', False):
        return filepath
    from src.utils.helpers import detect_platform
    platform_name = detect_platform(url)
    if not platform_name or platform_name == 'unknown':
        return filepath
    folder = os.path.join(os.path.dirname(filepath), platform_name.capitalize())
    target = os.path.join(folder, os.path.basename(filepath))
    if os.path.exists(target):
        return filepath
    try:
        os.makedirs(folder, exist_ok=True)
        shutil.move(filepath, target)
    except OSError as e:
        print(f"[Tamamlama] Dosya platform klasörüne taşınamadı ({filepath} → {folder}): {e}")
        return filepath
    return target


def _in_background(fn: Callable, *args):
    threading.Thread(target=fn, args=args, daemon=True).start()


def send_webhook(url: str, title: str, filepath: str, success: bool, error: str = ''):
    webhook_url = (cfg.get('webhook_url', '') or '').strip()
    if not webhook_url:
        return
    payload = json.dumps({
        'event': 'download_complete' if success else 'download_error',
        'url': url, 'title': title, 'file': filepath, 'success': success, 'error': error,
    }).encode('utf-8')

    def post():
        req = urllib.request.Request(webhook_url, data=payload, headers={'Content-Type': 'application/json'},
                                     method='POST')
        try:
            urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT_S)
        except Exception as e:
            print(f"[Webhook] {webhook_url} adresine gönderilemedi: {e}")
    _in_background(post)


def beep():
    def play():
        try:
            import winsound
            winsound.Beep(BEEP_HZ, BEEP_MS)
        except Exception as e:
            print(f"[Bildirim] Ses çalınamadı: {e}")
    _in_background(play)


def notify_native(title: str, body: str, on_failure: Optional[Callable[[str, str], None]] = None):
    """Windows bildirimi arka planda; win11toast WinRT çağrısı boyunca bekliyor."""
    def run():
        try:
            from win11toast import notify
            notify(title, body)
        except Exception as e:
            print(f"[Bildirim] Windows bildirimi gönderilemedi: {e}")
            if on_failure:
                on_failure(title, body)
    _in_background(run)


def fetch_lyrics(filepath: str, meta: DownloadMeta, on_saved: Optional[Callable[[str], None]] = None):
    """Ses indirmelerinde .lrc kaydeder (arka planda)."""
    if not filepath or meta.type_str != 'audio' or not (meta.title or meta.channel):
        return

    def run():
        try:
            from src.core.lyrics import save_lrc
            lrc = save_lrc(filepath, meta.title, meta.channel, int(meta.duration or 0))
        except Exception as e:
            print(f"[Sözler] {os.path.basename(filepath)} için sözler alınamadı: {e}")
            return
        if lrc and on_saved:
            on_saved(lrc)
    _in_background(run)


def _plugin_hook(name: str, *args):
    try:
        from src.core import plugin_manager
        getattr(plugin_manager, name)(*args)
    except Exception as e:
        print(f"[Eklenti] {name} kancası hata verdi: {e}")


def _forget_queue_item(url: str):
    try:
        get_download_history().remove_queue_item_by_url(url)
    except Exception as e:
        print(f"[Kuyruk] Kalıcı kuyruk kaydı silinemedi ({url}): {e}")


def on_success(filepath: str, meta: DownloadMeta) -> str:
    """Başarılı indirmenin yan etkileri. Son dosya yolunu döndürür (klasörleme taşımış olabilir)."""
    _forget_queue_item(meta.url)
    filepath = auto_organize(filepath, meta.url)
    title = meta.title or (os.path.splitext(os.path.basename(filepath))[0] if filepath else '')
    size = os.path.getsize(filepath) if filepath and os.path.exists(filepath) else None
    try:
        get_download_history().add_download(
            url=meta.url, title=title or None, channel=meta.channel or None,
            duration=int(meta.duration) if meta.duration else None, format_type=meta.type_str,
            format_quality=meta.format_quality or None, file_path=filepath, file_size=size, thumbnail_url=meta.thumbnail_url or None, status='completed',
        )
    except Exception as e:
        print(f"[Geçmiş] Başarılı indirme kaydedilemedi ({meta.url}): {e}")
    _plugin_hook('hook_download_complete', filepath or '', meta.url, {'title': meta.title, 'channel': meta.channel})
    send_webhook(meta.url, title, filepath, True)
    return filepath


def on_failure(error: str, meta: DownloadMeta):
    _forget_queue_item(meta.url)
    try:
        get_download_history().add_download(
            url=meta.url, title=meta.title or None, channel=meta.channel or None,
            format_type=meta.type_str, format_quality=meta.format_quality or None, status='error', error_message=str(error)[:DB_ERROR_MAX],
        )
    except Exception as e:
        print(f"[Geçmiş] Hatalı indirme kaydedilemedi ({meta.url}): {e}")
    _plugin_hook('hook_download_error', meta.url, str(error))
    send_webhook(meta.url, meta.title, '', False, str(error))
