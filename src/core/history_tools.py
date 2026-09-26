#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""İndirme geçmişi araçları: dışa aktarma, eksik dosya kontrolü, tekrar indirme isteği."""
import csv
import json
import os

EXPORT_FIELDS = ['id', 'title', 'channel', 'url', 'format_type', 'file_path', 'file_size',
                 'duration', 'status', 'download_date']
AUDIO_RETRY_FORMAT = 'bestaudio/best'
VIDEO_RETRY_FORMAT = 'bestvideo+bestaudio/best'


def collapse_duplicates(rows: list[dict]) -> list[dict]:
    """
    Eski sürümde her indirme iki kez kaydediliyordu (indirici dosya adıyla, arayüz başlıkla).
    Aynı bağlantı + aynı dosya + aynı durumdaki satırlardan bilgisi dolu olanı (kanalı olan) tutar.
    Veritabanına dokunmaz; yalnızca gösterim için.
    """
    kept: dict[tuple, dict] = {}
    order: list[tuple] = []
    for r in rows:
        key = (r.get('url'), r.get('file_path') or r.get('id'), r.get('status'))
        if key not in kept:
            kept[key] = r
            order.append(key)
        elif not kept[key].get('channel') and r.get('channel'):
            kept[key] = r
    return [kept[k] for k in order]


def export_csv(rows: list[dict], path: str):
    # utf-8-sig: Excel Türkçe karakterleri BOM olmadan bozuk açıyor.
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def export_json(rows: list[dict], path: str):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump([{k: r.get(k) for k in EXPORT_FIELDS} for r in rows], f, ensure_ascii=False, indent=2)


def missing_files(rows: list[dict]) -> list[str]:
    """Tamamlanmış ama dosyası artık diskte olmayan kayıtların dosya adları."""
    return [os.path.basename(r['file_path']) or r['file_path'] for r in rows
            if r.get('status') == 'completed' and r.get('file_path') and not os.path.exists(r['file_path'])]


def retry_request(row: dict, fallback_dir: str) -> dict:
    """
    Geçmiş satırından yeniden indirme isteği. Tür ve eski dosya klasörü biliniyorsa aynı
    ayarlarla doğrudan indirilir ('direct'); bilinmiyorsa bağlantı ana sayfaya gider ('home').
    """
    url = row.get('url') or ''
    file_path = row.get('file_path') or ''
    type_str = row.get('format_type') or ''
    if not (type_str and file_path):
        return {'mode': 'home', 'url': url}
    folder = os.path.dirname(file_path)
    return {
        'mode': 'direct', 'url': url, 'type': type_str,
        'format': row.get('format_quality') or (AUDIO_RETRY_FORMAT if type_str == 'audio' else VIDEO_RETRY_FORMAT),
        'outputDir': folder if os.path.isdir(folder) else fallback_dir,
        'title': row.get('title') or '', 'channel': row.get('channel') or '',
        'thumbnail': row.get('thumbnail_url') or '', 'duration': row.get('duration') or 0,
    }
