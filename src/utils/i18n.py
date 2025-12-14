#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Çoklu Dil Desteği (i18n) Modülü

Kullanım:
    from src.utils.i18n import tr, set_language, get_current_language
    
    # Çeviri al
    text = tr("home.title")
    
    # Dil değiştir
    set_language("en")
"""

import os
import json
from typing import Dict, Optional, List

# Desteklenen diller
SUPPORTED_LANGUAGES = {
    "tr": "Türkçe",
    "en": "English",
    "de": "Deutsch",
}

# Varsayılan dil
DEFAULT_LANGUAGE = "tr"

# Global değişkenler
_current_language = DEFAULT_LANGUAGE
_translations: Dict[str, dict] = {}
_locales_dir = None


def _get_locales_dir() -> str:
    """Dil dosyaları dizinini bul"""
    global _locales_dir
    if _locales_dir is None:
        # Proje kök dizinini bul
        current_file = os.path.abspath(__file__)
        utils_dir = os.path.dirname(current_file)
        src_dir = os.path.dirname(utils_dir)
        root_dir = os.path.dirname(src_dir)
        _locales_dir = os.path.join(root_dir, 'locales')
    return _locales_dir


def _load_language(lang_code: str) -> dict:
    """Dil dosyasını yükle"""
    locales_dir = _get_locales_dir()
    lang_file = os.path.join(locales_dir, f"{lang_code}.json")
    
    if os.path.exists(lang_file):
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Dil dosyası yüklenemedi ({lang_code}): {e}")
            return {}
    else:
        print(f"Dil dosyası bulunamadı: {lang_file}")
        return {}


def _ensure_loaded(lang_code: str):
    """Dil yüklenmemişse yükle"""
    global _translations
    if lang_code not in _translations:
        _translations[lang_code] = _load_language(lang_code)


def set_language(lang_code: str) -> bool:
    """
    Uygulama dilini değiştir
    
    Args:
        lang_code: Dil kodu (tr, en, de, vb.)
        
    Returns:
        bool: Başarılı mı?
    """
    global _current_language
    
    if lang_code not in SUPPORTED_LANGUAGES:
        print(f"Desteklenmeyen dil: {lang_code}")
        return False
    
    _ensure_loaded(lang_code)
    
    if _translations.get(lang_code):
        _current_language = lang_code
        print(f"Dil değiştirildi: {SUPPORTED_LANGUAGES[lang_code]}")
        return True
    
    return False


def get_current_language() -> str:
    """Mevcut dil kodunu döndür"""
    return _current_language


def get_language_name(lang_code: str = None) -> str:
    """Dil adını döndür"""
    code = lang_code or _current_language
    return SUPPORTED_LANGUAGES.get(code, code)


def get_supported_languages() -> Dict[str, str]:
    """Desteklenen dilleri döndür (kod: isim)"""
    return SUPPORTED_LANGUAGES.copy()


def tr(key: str, default: str = None, **kwargs) -> str:
    """
    Çeviri al
    
    Args:
        key: Nokta ile ayrılmış anahtar (örn: "home.title")
        default: Bulunamazsa varsayılan değer
        **kwargs: Format parametreleri
        
    Returns:
        str: Çevrilmiş metin
        
    Örnek:
        tr("home.title")  # "YouTube İndirici"
        tr("download.remaining")  # "kaldı"
        tr("info.videos_added", count=5)  # "5 videos added" (eğer format destekliyorsa)
    """
    global _current_language, _translations
    
    _ensure_loaded(_current_language)
    
    # Anahtarı parçala
    keys = key.split('.')
    
    # Mevcut dilde ara
    value = _translations.get(_current_language, {})
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
        else:
            value = None
            break
    
    # Bulunamadıysa varsayılan dilde ara
    if value is None and _current_language != DEFAULT_LANGUAGE:
        _ensure_loaded(DEFAULT_LANGUAGE)
        value = _translations.get(DEFAULT_LANGUAGE, {})
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break
    
    # Hala bulunamadıysa default veya key döndür
    if value is None:
        return default if default is not None else key
    
    # String değilse string'e çevir
    if not isinstance(value, str):
        return str(value)
    
    # Format parametreleri varsa uygula
    if kwargs:
        try:
            value = value.format(**kwargs)
        except KeyError:
            pass
    
    return value


def reload_translations():
    """Tüm çevirileri yeniden yükle"""
    global _translations
    _translations = {}
    _ensure_loaded(_current_language)


# Modül yüklendiğinde varsayılan dili yükle
_ensure_loaded(DEFAULT_LANGUAGE)
