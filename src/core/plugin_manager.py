#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plugin Sistemi — kullanıcı Python snippet'lerini plugins/ klasörüne koyar,
indirme pipeline'ına hook olur.

Her plugin dosyası aşağıdaki fonksiyonları opsiyonel olarak tanımlayabilir:

    def on_download_start(url: str, options: dict) -> dict:
        # options dict'ini değiştirebilir (ratelimit, format vb.)
        return options

    def on_download_complete(filepath: str, url: str, metadata: dict):
        # İndirme tamamlanınca çağrılır
        pass

    def on_download_error(url: str, error: str):
        pass

    PLUGIN_NAME = "My Plugin"
    PLUGIN_VERSION = "1.0"
    PLUGIN_DESCRIPTION = "What it does"
"""

from __future__ import annotations
import os
import importlib.util
import traceback
from typing import List, Dict, Any, Optional


_PLUGINS_DIR  = os.path.join(os.getcwd(), 'plugins')
_loaded: List[Any] = []   # loaded module objects
_enabled: Dict[str, bool] = {}


def get_plugins_dir() -> str:
    os.makedirs(_PLUGINS_DIR, exist_ok=True)
    return _PLUGINS_DIR


def load_plugins() -> List[Dict]:
    """plugins/ klasöründeki .py dosyalarını yükle."""
    global _loaded, _enabled
    _loaded.clear()
    os.makedirs(_PLUGINS_DIR, exist_ok=True)
    info_list = []

    for fname in sorted(os.listdir(_PLUGINS_DIR)):
        if not fname.endswith('.py') or fname.startswith('_'):
            continue
        path = os.path.join(_PLUGINS_DIR, fname)
        try:
            spec   = importlib.util.spec_from_file_location(fname[:-3], path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _loaded.append(module)
            name = getattr(module, 'PLUGIN_NAME', fname[:-3])
            _enabled.setdefault(name, True)
            info_list.append({
                'name':        name,
                'version':     getattr(module, 'PLUGIN_VERSION', '?'),
                'description': getattr(module, 'PLUGIN_DESCRIPTION', ''),
                'file':        fname,
                'enabled':     _enabled.get(name, True),
            })
            print(f"[PluginMgr] Yüklendi: {name}")
        except Exception as e:
            print(f"[PluginMgr] Plugin yüklenemedi ({fname}): {e}")
    return info_list


def set_enabled(plugin_name: str, enabled: bool):
    _enabled[plugin_name] = enabled


def _call_hook(hook: str, *args, **kwargs):
    """Tüm etkin plugin'lerdeki hook fonksiyonunu güvenli çağır."""
    result = None
    for module in _loaded:
        name = getattr(module, 'PLUGIN_NAME', module.__name__)
        if not _enabled.get(name, True):
            continue
        fn = getattr(module, hook, None)
        if callable(fn):
            try:
                result = fn(*args, **kwargs) or result
            except Exception:
                traceback.print_exc()
    return result


def hook_download_start(url: str, options: dict) -> dict:
    """plugins on_download_start hook'larını çalıştır; güncellenmiş options döndür."""
    for module in _loaded:
        name = getattr(module, 'PLUGIN_NAME', module.__name__)
        if not _enabled.get(name, True):
            continue
        fn = getattr(module, 'on_download_start', None)
        if callable(fn):
            try:
                new_opts = fn(url, options)
                if isinstance(new_opts, dict):
                    options = new_opts
            except Exception:
                traceback.print_exc()
    return options


def hook_download_complete(filepath: str, url: str, metadata: dict):
    _call_hook('on_download_complete', filepath, url, metadata)


def hook_download_error(url: str, error: str):
    _call_hook('on_download_error', url, error)


# Örnek plugin oluştur (ilk çalıştırmada)
def create_example_plugin():
    example = os.path.join(_PLUGINS_DIR, '_example_plugin.py')
    if os.path.exists(example):
        return
    os.makedirs(_PLUGINS_DIR, exist_ok=True)
    with open(example, 'w', encoding='utf-8') as f:
        f.write('''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Örnek YDL Plugin — bu dosyayı kopyalayıp düzenleyin.
Başına _ ile başlayan dosyalar otomatik yüklenmez.
"""

PLUGIN_NAME        = "Örnek Plugin"
PLUGIN_VERSION     = "1.0"
PLUGIN_DESCRIPTION = "İndirme tamamlanınca konsola yazdırır"


def on_download_complete(filepath: str, url: str, metadata: dict):
    print(f"[ÖrnekPlugin] Tamamlandı: {filepath}")


def on_download_error(url: str, error: str):
    print(f"[ÖrnekPlugin] Hata ({url}): {error}")
''')
