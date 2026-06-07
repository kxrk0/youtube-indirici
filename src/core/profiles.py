#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
İndirme Profilleri — önceden tanımlı ayar kümeleri.
Kullanıcı profilini seçince tüm indirme parametreleri otomatik dolar.
"""

from __future__ import annotations
import json
import os
from typing import List, Dict, Any

_PROFILES_FILE = os.path.join(os.getcwd(), 'cache', 'profiles.json')

DEFAULT_PROFILES: List[Dict[str, Any]] = [
    {
        'name': '🎬 YouTube 1080p',
        'format_id': 'bestvideo[height<=1080]+bestaudio/best',
        'type_str': 'video',
        'sponsorblock': True,
        'normalize_audio': False,
        'filename_template': '%(title)s.%(ext)s',
        'ratelimit': None,
        'builtin': True,
    },
    {
        'name': '🎵 Müzik MP3 (En İyi)',
        'format_id': 'bestaudio/best',
        'type_str': 'audio',
        'sponsorblock': False,
        'normalize_audio': True,
        'filename_template': '%(uploader)s - %(title)s.%(ext)s',
        'ratelimit': None,
        'builtin': True,
    },
    {
        'name': '📱 TikTok / Shorts',
        'format_id': 'bestvideo[width<=720]+bestaudio/best',
        'type_str': 'video',
        'sponsorblock': False,
        'normalize_audio': False,
        'filename_template': '%(title)s.%(ext)s',
        'ratelimit': None,
        'builtin': True,
    },
    {
        'name': '🎙 Podcast MP3 (Normalize)',
        'format_id': 'bestaudio/best',
        'type_str': 'audio',
        'sponsorblock': False,
        'normalize_audio': True,
        'filename_template': '%(uploader)s - %(title)s.%(ext)s',
        'ratelimit': '2M',
        'builtin': True,
    },
    {
        'name': '📺 4K Ultra HD',
        'format_id': 'bestvideo[height<=2160]+bestaudio/best',
        'type_str': 'video',
        'sponsorblock': False,
        'normalize_audio': False,
        'filename_template': '%(title)s [4K].%(ext)s',
        'ratelimit': None,
        'builtin': True,
    },
    {
        'name': '⚡ Hızlı 480p',
        'format_id': 'bestvideo[height<=480]+bestaudio/best',
        'type_str': 'video',
        'sponsorblock': True,
        'normalize_audio': False,
        'filename_template': '%(title)s.%(ext)s',
        'ratelimit': None,
        'builtin': True,
    },
]


def _load_profiles() -> List[Dict]:
    os.makedirs(os.path.dirname(_PROFILES_FILE), exist_ok=True)
    if os.path.exists(_PROFILES_FILE):
        try:
            with open(_PROFILES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_profiles(profiles: List[Dict]):
    os.makedirs(os.path.dirname(_PROFILES_FILE), exist_ok=True)
    with open(_PROFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)


def get_all_profiles() -> List[Dict]:
    """Yerleşik + kullanıcı tanımlı profilleri döndür."""
    user = [p for p in _load_profiles() if not p.get('builtin')]
    return DEFAULT_PROFILES + user


def get_profile(name: str) -> Dict | None:
    for p in get_all_profiles():
        if p['name'] == name:
            return p
    return None


def add_profile(profile: Dict):
    """Kullanıcı profili ekle/güncelle."""
    profile = dict(profile)
    profile.pop('builtin', None)
    existing = _load_profiles()
    existing = [p for p in existing if p['name'] != profile['name']]
    existing.append(profile)
    _save_profiles(existing)


def delete_profile(name: str):
    existing = [p for p in _load_profiles() if p['name'] != name]
    _save_profiles(existing)


def profile_names() -> List[str]:
    return [p['name'] for p in get_all_profiles()]
