#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kütüphane taraması, etiket gidiş-dönüşü ve dönüştürme doğrulaması."""
import os
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


def _scan(root, extra=''):
    conf = {'download_dir': str(root), 'library_folders': extra}
    with patch('src.core.media_library.cfg.get', side_effect=lambda k, d=None: conf.get(k, d)):
        return media_library.scan()


def test_tarama_duzenlenen_alt_klasorleri_de_gorur(tmp_path):
    """Otomatik düzenleme İndirilenler/Youtube'a, kategori kuralı İndirilenler/Müzik'e taşıyordu;
    tarama alt klasöre inmediği için o dosyalar kütüphanede görünmüyordu."""
    (tmp_path / 'Youtube').mkdir()
    (tmp_path / 'Müzik' / 'Youtube').mkdir(parents=True)
    (tmp_path / 'a' / 'b' / 'c').mkdir(parents=True)
    (tmp_path / '.gizli').mkdir()
    (tmp_path / 'ust.mp3').write_bytes(b'x')
    (tmp_path / 'Youtube' / 'klip.mp4').write_bytes(b'x')
    (tmp_path / 'Müzik' / 'Youtube' / 'sarki.mp3').write_bytes(b'x')
    (tmp_path / 'a' / 'b' / 'c' / 'cok_derin.mp3').write_bytes(b'x')
    (tmp_path / '.gizli' / 'gizli.mp3').write_bytes(b'x')
    found = {f['name']: f['folder'] for f in _scan(tmp_path)}
    assert found == {'ust.mp3': '', 'klip.mp4': 'Youtube', 'sarki.mp3': os.path.join('Müzik', 'Youtube')}


def test_ek_klasor_indirme_klasorunun_icindeyse_dosya_iki_kez_gelmez(tmp_path):
    (tmp_path / 'Youtube').mkdir()
    (tmp_path / 'Youtube' / 'klip.mp4').write_bytes(b'x')
    names = [f['name'] for f in _scan(tmp_path, str(tmp_path / 'Youtube'))]
    assert names == ['klip.mp4']

