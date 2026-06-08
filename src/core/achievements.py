#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Başarım (Achievement) Sistemi
Hone'dan ilham: kullanıcı milestone'larını kutla, rozet ver.
"""

import src.utils.config as cfg

# ─── Tanımlı başarımlar ───────────────────────────────────────────────────────

ACHIEVEMENTS = [
    {'id': 'first',     'icon': '🎉', 'title': 'İlk İndirme!',       'desc': 'İlk videonu indirdin.',             'threshold': 1},
    {'id': 'ten',       'icon': '🔥', 'title': '10 İndirme',          'desc': '10 video tamamlandı.',              'threshold': 10},
    {'id': 'fifty',     'icon': '⚡', 'title': 'Hız Canavarı',        'desc': '50 indirme!',                       'threshold': 50},
    {'id': 'hundred',   'icon': '💯', 'title': 'Yüzlük Kulüp',        'desc': '100 indirme tamamlandı.',           'threshold': 100},
    {'id': 'fivehund',  'icon': '🏆', 'title': 'İndirme Ustası',      'desc': '500 indirme! Efsane.',              'threshold': 500},
    {'id': 'thousand',  'icon': '👑', 'title': 'Efsane İndirici',     'desc': '1000 indirme! Taç sende.',          'threshold': 1000},
    {'id': 'spotify',   'icon': '🎵', 'title': 'Spotify Müzisyeni',   'desc': 'Spotify\'dan indirdin.',            'threshold': None, 'trigger': 'spotify'},
    {'id': 'bulk',      'icon': '📦', 'title': 'Toplu İndirici',      'desc': '10+ URL tek seferde indirildi.',    'threshold': None, 'trigger': 'bulk_10'},
    {'id': 'night_owl', 'icon': '🦉', 'title': 'Gece Kuşu',           'desc': 'Gece 00:00-05:00 arası indirdin.', 'threshold': None, 'trigger': 'night'},
    {'id': 'audio_fan', 'icon': '🎧', 'title': 'Ses Aşığı',           'desc': '25 ses dosyası indirdin.',          'threshold': None, 'trigger': 'audio_25'},
]

_TOTAL_KEY   = 'ach_total_downloads'
_UNLOCKED_KEY = 'ach_unlocked'
_AUDIO_KEY   = 'ach_audio_count'


def get_total() -> int:
    return int(cfg.get(_TOTAL_KEY, 0))


def get_unlocked() -> list:
    return cfg.get(_UNLOCKED_KEY, [])


def _unlock(ach_id: str) -> dict | None:
    """Başarımı unlock et. Yeniyse dict döner, zaten varsa None."""
    unlocked = get_unlocked()
    if ach_id in unlocked:
        return None
    unlocked.append(ach_id)
    cfg.set_value(_UNLOCKED_KEY, unlocked)
    for a in ACHIEVEMENTS:
        if a['id'] == ach_id:
            return a
    return None


def on_download_complete(format_type: str = 'video', platform: str = '') -> list[dict]:
    """
    İndirme tamamlandığında çağır.
    Unlock edilen yeni başarımların listesini döner (toast göstermek için).
    """
    import datetime

    new_unlocks = []

    # Toplam sayacı artır
    total = get_total() + 1
    cfg.set_value(_TOTAL_KEY, total)

    # Eşik başarımları
    for ach in ACHIEVEMENTS:
        thresh = ach.get('threshold')
        if thresh and total == thresh:
            r = _unlock(ach['id'])
            if r:
                new_unlocks.append(r)

    # Trigger başarımları
    trigger = ach_id = None

    # Spotify
    if 'spotify' in platform.lower():
        r = _unlock('spotify')
        if r:
            new_unlocks.append(r)

    # Gece kuşu
    hour = datetime.datetime.now().hour
    if 0 <= hour < 5:
        r = _unlock('night_owl')
        if r:
            new_unlocks.append(r)

    # Ses sayacı
    if format_type == 'audio':
        audio_cnt = int(cfg.get(_AUDIO_KEY, 0)) + 1
        cfg.set_value(_AUDIO_KEY, audio_cnt)
        if audio_cnt >= 25:
            r = _unlock('audio_fan')
            if r:
                new_unlocks.append(r)

    return new_unlocks


def on_bulk_download(count: int) -> list[dict]:
    """Toplu indirme tamamlanınca çağır."""
    new_unlocks = []
    if count >= 10:
        r = _unlock('bulk_10')
        if r:
            new_unlocks.append(r)
    return new_unlocks


def get_stats() -> dict:
    """UI için istatistik özeti."""
    total = get_total()
    unlocked = get_unlocked()
    return {
        'total_downloads': total,
        'unlocked_count': len(unlocked),
        'total_achievements': len(ACHIEVEMENTS),
        'next_milestone': _next_milestone(total),
    }


def _next_milestone(total: int) -> dict | None:
    thresholds = sorted(
        [a for a in ACHIEVEMENTS if a.get('threshold')],
        key=lambda a: a['threshold']
    )
    for a in thresholds:
        if total < a['threshold']:
            return {'threshold': a['threshold'], 'remaining': a['threshold'] - total, 'icon': a['icon'], 'title': a['title']}
    return None
