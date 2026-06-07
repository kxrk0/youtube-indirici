#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import secrets
from typing import Any, Dict

def _get_config_dir() -> str:
    from src.utils.helpers import get_app_dir
    return os.path.join(get_app_dir(), 'cache')

_CONFIG_DIR = None  # lazily resolved
_CONFIG_PATH = None  # lazily resolved

_DEFAULTS: Dict[str, Any] = {
    'theme': 'dark',
    'accent_color': '#0078D4',
    'language': 'tr',
    'download_dir': '',
    'speed_limit': 0,
    'proxy': '',
    'custom_ffmpeg_args': '',
    'api_key': '',
    'window_width': 1100,
    'window_height': 720,
}

_cache: Dict[str, Any] = {}
_loaded = False


def _ensure_loaded():
    global _cache, _loaded, _CONFIG_DIR, _CONFIG_PATH
    if _loaded:
        return
    _loaded = True
    if _CONFIG_DIR is None:
        _CONFIG_DIR = _get_config_dir()
        _CONFIG_PATH = os.path.join(_CONFIG_DIR, 'config.json')
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
