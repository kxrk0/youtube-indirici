#!/usr/bin/env python3
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
