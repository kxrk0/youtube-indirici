#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kütüphane kart kapakları: küçültme, önbellek ve yerel HTTP sunucusu.

Arka plan: kapaklar köprüden base64 metin olarak geliyordu (kapak başına ~110 KB); 318 dosyalık
kütüphanede kaydırırken 21 uzun görev (1,4 sn) ölçüldü. Artık kart boyutunda JPEG olarak
127.0.0.1'den <img> ile yükleniyor.
"""
import os
import urllib.error
import urllib.parse
import urllib.request

import pytest
from PIL import Image

from src.core import media_library
from src.web.thumb_server import IMMUTABLE_CACHE, ThumbServer

HTTP_TIMEOUT_S = 10


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    target = tmp_path / 'veri'
    monkeypatch.setattr(media_library, 'get_data_dir', lambda: str(target))
    return target


@pytest.fixture
def media_with_cover(tmp_path, monkeypatch):
    """Tam kapağı 640x640 olan bir medya dosyası (kare ses kapağı gibi)."""
    media = tmp_path / 'şarkı.mp3'
    media.write_bytes(b'ses')
    cover = tmp_path / 'kapak.jpg'
    Image.new('RGB', (640, 640), (200, 40, 40)).save(cover)
    calls = []
    monkeypatch.setattr(media_library, 'thumbnail', lambda p: calls.append(p) or str(cover))
    return media, calls


def test_card_thumbnail_is_card_sized_and_cached(data_dir, media_with_cover):
    media, calls = media_with_cover
    assert media_library.card_thumbnail(str(media), render=False) is media_library.NOT_RENDERED
    out = media_library.card_thumbnail(str(media))
    with Image.open(out) as im:
        assert im.size == media_library.CARD_THUMB_SIZE
        assert im.format == 'JPEG'
    assert media_library.card_thumbnail(str(media), render=False) == out
    assert media_library.card_thumbnail(str(media)) == out
    assert len(calls) == 1, 'hazır kart kapağı yeniden üretilmemeli'


def test_changed_file_gets_a_new_card(data_dir, media_with_cover):
    media, calls = media_with_cover
    first = media_library.card_thumbnail(str(media))
    media.write_bytes(b'kapak eklenmis ses')
    second = media_library.card_thumbnail(str(media))
    assert first != second and len(calls) == 2


def test_missing_cover_is_remembered(data_dir, tmp_path, monkeypatch):
    media = tmp_path / 'kapaksiz.mp3'
    media.write_bytes(b'ses')
    calls = []
    monkeypatch.setattr(media_library, 'thumbnail', lambda p: calls.append(p))
    assert media_library.card_thumbnail(str(media)) is None
    assert media_library.card_thumbnail(str(media), render=False) is None
    assert media_library.card_thumbnail(str(media)) is None
    assert len(calls) == 1, 'kapaksız dosyanın etiketleri her açılışta yeniden okunmamalı'


def test_corrupt_cover_is_remembered_as_missing(data_dir, tmp_path, monkeypatch):
    media = tmp_path / 'bozuk.mp3'
    media.write_bytes(b'ses')
    bad = tmp_path / 'bozuk.jpg'
    bad.write_bytes(b'jpeg degil')
    monkeypatch.setattr(media_library, 'thumbnail', lambda p: str(bad))
    assert media_library.card_thumbnail(str(media)) is None
    assert media_library.card_thumbnail(str(media), render=False) is None


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), b''


@pytest.fixture
def server():
    srv = ThumbServer()
    yield srv
    srv.close()


def test_server_serves_registered_card(data_dir, media_with_cover, server):
    media, _ = media_with_cover
    st = os.stat(media)
    url = server.register(str(media), st.st_size, st.st_mtime)
    assert url.startswith('http://127.0.0.1:') and str(media) not in url
    status, headers, body = _get(url)
    assert status == 200
    assert headers['Content-Type'] == 'image/jpeg'
    assert headers['Cache-Control'] == IMMUTABLE_CACHE
    assert body[:2] == b'\xff\xd8'


def test_server_404_for_missing_cover_is_cacheable(data_dir, tmp_path, monkeypatch, server):
    media = tmp_path / 'kapaksiz.mp3'
    media.write_bytes(b'ses')
    monkeypatch.setattr(media_library, 'thumbnail', lambda p: None)
    status, headers, _ = _get(server.register(str(media), 3, 1.0))
    assert status == 404
    assert headers['Cache-Control'] == IMMUTABLE_CACHE


def test_server_refuses_unregistered_and_path_urls(data_dir, media_with_cover, server):
    media, calls = media_with_cover
    for path in ('/t/0123456789abcdef0123456789abcdef.jpg', '/t/' + urllib.parse.quote(str(media)) + '.jpg',
                 '/../cache/config.json', '/'):
        status, _, _ = _get(server.base_url + path)
        assert status == 404, path
    assert calls == [], 'kayıtsız istek kapak üretmemeli'


def test_urls_differ_between_sessions(media_with_cover):
    media, _ = media_with_cover
    a, b = ThumbServer(), ThumbServer()
    try:
        assert a.register(str(media), 1, 1.0).split('/t/')[1] != b.register(str(media), 1, 1.0).split('/t/')[1]
    finally:
        a.close()
        b.close()
