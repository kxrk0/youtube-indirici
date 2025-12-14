#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Otomatik Güncelleme Modülü

GitHub releases API kullanarak güncelleme kontrolü yapar.
"""

import os
import json
import threading
from typing import Dict, Optional, Callable
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Uygulama sürümü
APP_VERSION = "2.2.0"

# GitHub repo bilgileri
GITHUB_OWNER = "kxrk0"
GITHUB_REPO = "youtube-indirici"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


class UpdateInfo:
    """Güncelleme bilgisi"""
    def __init__(self, version: str = None, download_url: str = None, 
                 release_notes: str = None, published_at: str = None):
        self.version = version
        self.download_url = download_url
        self.release_notes = release_notes
        self.published_at = published_at
        self.is_newer = False
        
    def __repr__(self):
        return f"UpdateInfo(version={self.version}, is_newer={self.is_newer})"


def get_current_version() -> str:
    """Mevcut uygulama sürümünü döndür"""
    return APP_VERSION


def _compare_versions(current: str, latest: str) -> bool:
    """
    Sürümleri karşılaştır
    
    Returns:
        bool: latest > current ise True
    """
    try:
        def parse_version(v: str) -> tuple:
            # v2.1.0 -> (2, 1, 0)
            v = v.lstrip('v').lstrip('V')
            parts = v.split('.')
            return tuple(int(p) for p in parts[:3])
        
        current_parts = parse_version(current)
        latest_parts = parse_version(latest)
        
        return latest_parts > current_parts
    except (ValueError, AttributeError):
        return False


def check_for_updates() -> Optional[UpdateInfo]:
    """
    GitHub releases API'den güncelleme kontrolü yap
    
    Returns:
        UpdateInfo: Güncelleme bilgisi veya None (hata durumunda)
    """
    try:
        # API isteği oluştur
        request = Request(
            GITHUB_API_URL,
            headers={
                'User-Agent': f'YouTubeStudioDownloader/{APP_VERSION}',
                'Accept': 'application/vnd.github.v3+json'
            }
        )
        
        # API'ye bağlan
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        # Sürüm bilgisini al
        latest_version = data.get('tag_name', '').lstrip('v')
        
        # İndirme linkini bul
        download_url = None
        assets = data.get('assets', [])
        for asset in assets:
            name = asset.get('name', '').lower()
            if name.endswith('.exe') or name.endswith('.zip'):
                download_url = asset.get('browser_download_url')
                break
        
        # İndirme linki yoksa release sayfasını kullan
        if not download_url:
            download_url = data.get('html_url')
        
        # UpdateInfo oluştur
        update_info = UpdateInfo(
            version=latest_version,
            download_url=download_url,
            release_notes=data.get('body', ''),
            published_at=data.get('published_at', '')
        )
        
        # Sürüm karşılaştır
        update_info.is_newer = _compare_versions(APP_VERSION, latest_version)
        
        return update_info
        
    except HTTPError as e:
        print(f"Güncelleme kontrolü HTTP hatası: {e.code}")
        return None
    except URLError as e:
        print(f"Güncelleme kontrolü ağ hatası: {e.reason}")
        return None
    except Exception as e:
        print(f"Güncelleme kontrolü hatası: {e}")
        return None


def check_for_updates_async(callback: Callable[[Optional[UpdateInfo]], None]):
    """
    Arka planda güncelleme kontrolü yap
    
    Args:
        callback: Sonuç geldiğinde çağrılacak fonksiyon
    """
    def _check():
        result = check_for_updates()
        callback(result)
    
    thread = threading.Thread(target=_check, daemon=True)
    thread.start()


class AutoUpdater:
    """
    Otomatik güncelleme yöneticisi
    
    Kullanım:
        updater = AutoUpdater()
        updater.check_on_startup(callback=my_callback)
    """
    
    def __init__(self):
        self.last_check_result: Optional[UpdateInfo] = None
        self.is_checking = False
        
    def check_on_startup(self, callback: Callable[[Optional[UpdateInfo]], None] = None):
        """Uygulama başlangıcında güncelleme kontrolü"""
        if self.is_checking:
            return
            
        self.is_checking = True
        
        def _on_result(info: Optional[UpdateInfo]):
            self.last_check_result = info
            self.is_checking = False
            if callback:
                callback(info)
        
        check_for_updates_async(_on_result)
        
    def get_last_result(self) -> Optional[UpdateInfo]:
        """Son kontrol sonucunu döndür"""
        return self.last_check_result
        
    def is_update_available(self) -> bool:
        """Güncelleme mevcut mu?"""
        return self.last_check_result is not None and self.last_check_result.is_newer


# Global instance
_updater_instance = None

def get_auto_updater() -> AutoUpdater:
    """Global AutoUpdater instance'ını döndür"""
    global _updater_instance
    if _updater_instance is None:
        _updater_instance = AutoUpdater()
    return _updater_instance
