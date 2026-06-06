#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import secrets
from typing import Any, Dict

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'cache'
)
_CONFIG_PATH = os.path.join(_CONFIG_DIR, 'config.json')

_DEFAULTS: Dict[str, Any] = {
    'theme': 'dark',
    'accent_color': '#0078D4',
    'language': 'tr',
    'download_dir': '',
    'speed_limit': 0,
    'proxy': '',
    'custom_ffmpeg_args': '',
    'api_key': '',
}

_cache: Dict[str, Any] = {}
_loaded = False


def _ensure_loaded():
    global _cache, _loaded
    if _loaded:
        return
    _loaded = True
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    for k, v in _DEFAULTS.items():
        if k not in _cache:
            _cache[k] = v


def _save():
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(_cache, f, ensure_ascii=False, indent=2)


def get(key: str, default: Any = None) -> Any:
    _ensure_loaded()
    return _cache.get(key, _DEFAULTS.get(key, default))


def set_value(key: str, value: Any):
    _ensure_loaded()
    _cache[key] = value
    _save()


def get_api_key() -> str:
    _ensure_loaded()
    key = _cache.get('api_key', '')
    if not key:
        key = secrets.token_hex(32)
        set_value('api_key', key)
    return key
