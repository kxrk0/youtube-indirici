#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kalite menüsü regresyon testleri.

Arka plan: qfluentwidgets'ın ComboBox.addItem imzası PyQt'ninkinden farklı —
addItem(text, icon=None, userData=None). Kod uzun süre addItem(label, data)
diye çağırdığı için veri `icon` parametresine gidiyor, userData None kalıyordu.
currentData() her satırda None dönüyor, indirme tarafındaki `or 'best'`
yedeği devreye giriyor ve seçilen kalite ne olursa olsun bestvideo+bestaudio
indiriliyordu. Aşağıdaki testler o hatanın geri gelmesini engelliyor.
"""

import pytest

from src.core.formats import build_quality_options, quality_of


def _video(fid, width, height, vcodec, size=None, note=None, proto="https", ext="mp4"):
    return {
        "format_id": fid, "width": width, "height": height, "vcodec": vcodec,
        "acodec": "none", "ext": ext, "filesize": size, "format_note": note,
        "protocol": proto,
    }


_AUDIO = {
    "format_id": "140", "vcodec": "none", "acodec": "mp4a.40.2",
    "ext": "m4a", "filesize": 2_000_000, "protocol": "https",
}

# 3840x1920 sinema oranlı bir videonun formatları — YouTube bunu 2160p diyor
# ama height 1920, listede "1920p" görünüp 4K yok sanılıyordu.
_CINEMA = [
    _video("401", 3840, 1920, "av01.0.12M.08", 164_000_000, "2160p"),
    _video("313", 3840, 1920, "vp09.00.50.08", 278_000_000, "2160p"),
    _video("400", 2560, 1280, "av01.0.12M.08", 66_000_000, "1440p"),
    _video("137", 1920, 960, "avc1.640028", 40_500_000, "1080p"),
    _video("270", 1920, 960, "avc1.640028", None, "1080p", proto="m3u8_native"),
    _video("136", 1280, 640, "avc1.4d401f", 14_000_000, "720p"),
    _video("134", 640, 320, "avc1.4d4016", 4_900_000, "360p"),
    _AUDIO,
]


def _labels(formats):
    return [o['label'] for o in build_quality_options(formats)]


def _data(formats):
    return [o['data'] for o in build_quality_options(formats)]


def test_her_satir_veri_tasiyor():
    """Asıl regresyon: hiçbir seçenek format verisiz kalmamalı (yoksa hep bestvideo iniyordu)."""
    options = build_quality_options(_CINEMA)
    assert options
    for opt in options:
        assert opt['data'], f"{opt['label']!r} satırında format verisi yok"


def test_duzenleme_secenekleri_dogru_veriyi_veriyor():
    data = _data(_CINEMA)
    assert "best" in data
    assert "edit_h264" in data
    assert "edit_h264_max" in data
    assert "webm" in data


def test_sinema_orani_2160p_olarak_etiketleniyor():
    labels = _labels(_CINEMA)
    assert any("2160p" in label for label in labels)
    assert not any("1920p" in label for label in labels)


def test_720p_alti_listelenmiyor():
    labels = _labels(_CINEMA)
    assert not any(label.startswith("360p") for label in labels)
    assert any(label.startswith("720p") for label in labels)


def test_dusuk_kaliteli_videoda_filtre_kapaniyor():
    """720p+ hiç yoksa liste boş kalmamalı."""
    formats = [_video("134", 640, 360, "avc1.4d4016", 4_900_000, "360p"), _AUDIO]
    labels = _labels(formats)
    assert any(label.startswith("360p") for label in labels)


def test_avc1_yoksa_h264_secenegi_gizleniyor():
    """Dönüştürmesiz H.264 vaadi tutulamıyorsa o satır çıkmamalı."""
    formats = [_video("313", 3840, 2160, "vp09.00.50.08", 200_000_000, "2160p"), _AUDIO]
    data = _data(formats)
    assert "edit_h264" not in data
    assert "edit_h264_max" in data


def test_m3u8_kopyalari_elenmis():
    """137 (https) ve 270 (m3u8) aynı satır — biri gösterilmeli."""
    labels = _labels(_CINEMA)
    assert sum(1 for label in labels if label.startswith("1080p · H.264")) == 1


@pytest.mark.parametrize("width,height,expected", [
    (3840, 1920, 2160),   # sinema oranı, yatay
    (2880, 2160, 2160),   # 4:3, yatay
    (1920, 960, 1080),
    (1920, 1080, 1080),
    (2560, 1280, 1440),
    (1280, 640, 720),
    (1080, 1920, 1080),   # dikey — kısa kenar
    (2160, 3840, 2160),
    (720, 1280, 720),
    (1080, 1080, 1080),   # kare
])
def test_kalite_basamagi_format_note_yokken(width, height, expected):
    """YouTube dışı kaynaklarda format_note gelmiyor; geometrik hesap tutmalı."""
    assert quality_of({"width": width, "height": height}) == expected


def test_format_note_geometriyi_eziyor():
    fmt = {"width": 3840, "height": 1920, "format_note": "2160p60 HDR"}
    assert quality_of(fmt) == 2160
