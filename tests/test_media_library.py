#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kütüphane taraması, etiket gidiş-dönüşü ve dönüştürme doğrulaması."""
from unittest.mock import patch

import pytest

from src.core import media_library


def test_tarama_yalnizca_medya_dosyalarini_ve_ek_klasoru_alir(tmp_path):
    main, extra = tmp_path / 'indir', tmp_path / 'ek'
    main.mkdir(); extra.mkdir()
    (main / 'klip.mp4').write_bytes(b'x')
    (main / 'not.txt').write_text('x')
    (extra / 'sarki.mp3').write_bytes(b'xx')
    conf = {'download_dir': str(main), 'library_folders': f"{extra}\n{tmp_path / 'yok'}"}
    with patch('src.core.media_library.cfg.get', side_effect=lambda k, d=None: conf.get(k, d)):
        files = media_library.scan()
    assert sorted((f['name'], f['kind']) for f in files) == [('klip.mp4', 'video'), ('sarki.mp3', 'audio')]


def test_mp3_etiketleri_yazilip_okunur(tmp_path):
    path = tmp_path / 'sarki.mp3'
    path.write_bytes(b'')
    values = {'title': 'BANA SOR', 'artist': 'ERA7CAPONE X ŞAM', 'album': '', 'year': '2026', 'comment': 'test'}
    media_library.write_tags(str(path), values)
    assert media_library.read_tags(str(path)) == values


def test_desteklenmeyen_turde_etiket_hatasi_aciklayici():
    with pytest.raises(ValueError, match='MP3, MP4 ve M4A'):
        media_library.read_tags('C:/x/klip.webm')


def test_bilinmeyen_donusturme_formati_reddedilir():
    with pytest.raises(ValueError, match='Desteklenmeyen format'):
        media_library.convert('x.mp4', 'gif')
