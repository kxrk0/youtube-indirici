#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arayüzden değiştirilebilen ayarlar ve doğrulamaları. Arayüz yalnızca bu anahtarları
yazabilir; tür ve aralık dışı değer açıklayıcı hatayla reddedilir.
"""
from src.utils import config as cfg
from src.utils.helpers import get_os_download_dir

AUDIO_QUALITIES = ('0', '320', '256', '192', '128')

# anahtar → (tür, varsayılan, alt sınır, üst sınır / izinli değerler)
SCHEMA: dict[str, tuple] = {
    'download_dir': (str, '', None, None),
    'speed_limit': (int, 0, 0, 50),            # MB/s, 0 = sınırsız
    'max_concurrent': (int, 3, 1, 8),
    'fragment_downloads': (int, 4, 1, 16),
    'audio_quality': (str, '0', None, AUDIO_QUALITIES),
    'auto_organize': (bool, False, None, None),
    'auto_shutdown': (bool, False, None, None),
    'filename_template': (str, '%(title)s.%(ext)s', None, None),
    'proxy': (str, '', None, None),
    'proxy_pool': (str, '', None, None),
    'custom_ffmpeg_args': (str, '', None, None),
    'webhook_url': (str, '', None, None),
    'sub_check_hours': (int, 6, 1, 24),
    'library_folders': (str, '', None, None),
}


def read_all() -> dict:
    out = {}
    for key, (kind, default, _, _) in SCHEMA.items():
        value = cfg.get(key, default)
        try:
            out[key] = kind(value) if value is not None else default
        except (TypeError, ValueError):
            out[key] = default
    if not out['download_dir']:
        out['download_dir'] = get_os_download_dir()
    return out


def validate(key: str, value):
    if key not in SCHEMA:
        raise KeyError(f"Bilinmeyen ayar: {key}")
    kind, _, low, high = SCHEMA[key]
    if kind is bool:
        if not isinstance(value, bool):
            raise TypeError(f"{key}: açık/kapalı (true/false) bekleniyordu, gelen: {value!r}")
        return value
    if kind is int:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
            raise TypeError(f"{key}: tam sayı bekleniyordu, gelen: {value!r}")
        value = int(value)
        if not low <= value <= high:
            raise ValueError(f"{key}: {low} ile {high} arasında olmalı, gelen: {value}")
        return value
    if not isinstance(value, str):
        raise TypeError(f"{key}: metin bekleniyordu, gelen: {value!r}")
    value = value.strip() if key not in ('proxy_pool', 'library_folders') else value
    if isinstance(high, tuple) and value not in high:
        raise ValueError(f"{key}: şunlardan biri olmalı: {', '.join(high)}; gelen: {value!r}")
    return value


def write(key: str, value):
    cfg.set_value(key, validate(key, value))
