#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H.264 dönüştürücü testleri.

Arka plan: dönüştürme yt-dlp'nin run_ffmpeg'i ile çalışıyordu; çıktı sonuna
kadar biriktiği için 4K bir videoda dakikalarca ilerleme bildirimi çıkmıyor,
iptal düğmesi işlemiyordu. Uygulama o sırada kapatıldığında yarım .h264.mp4
diskte kalıyordu. Testler üçünü de kilitliyor.
"""

import os
import shutil
import subprocess
import threading

import pytest

from src.core.ytdlp_base import (
    ForceH264PP, ProcessCancelled, is_edit_safe, pick_h264_encoder,
)

pytestmark = pytest.mark.skipif(
    shutil.which('ffmpeg') is None, reason='ffmpeg yok'
)


@pytest.fixture
def av1_kaynak(tmp_path):
    """Kısa, H.264 olmayan bir test klibi üretir."""
    path = tmp_path / 'kaynak.mp4'
    subprocess.run(
        ['ffmpeg', '-hide_banner', '-v', 'error',
         '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=25', '-t', '3',
         '-f', 'lavfi', '-i', 'sine=frequency=440', '-t', '3',
         '-c:v', 'libvpx-vp9', '-b:v', '200k', '-c:a', 'aac', '-shortest',
         '-y', str(path)],
        check=True, capture_output=True,
    )
    return str(path)


def _vcodec(path):
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', path],
        capture_output=True, text=True,
    )
    return out.stdout.strip()


def test_encoder_secimi_calisan_bir_encoder_donduruyor():
    name, args = pick_h264_encoder()
    assert name
    assert isinstance(args, list)


def test_edit_safe_ayrimi():
    assert is_edit_safe('avc1.640028')
    assert is_edit_safe('h264')
    assert not is_edit_safe('av01.0.12M.08')
    assert not is_edit_safe('vp09.00.50.08')
    assert not is_edit_safe('')


def test_donusturme_h264_uretiyor_ve_ilerleme_bildiriyor(av1_kaynak):
    yuzdeler = []
    pp = ForceH264PP(on_progress=yuzdeler.append)
    pp.run({'filepath': av1_kaynak, 'vcodec': 'vp09.00.50.08', 'duration': 3})

    assert _vcodec(av1_kaynak) == 'h264'
    assert yuzdeler, 'ilerleme bildirimi hiç gelmedi'
    assert yuzdeler[-1] == 100
    assert all(0 <= p <= 100 for p in yuzdeler)


def test_zaten_h264_ise_dokunmuyor(tmp_path):
    path = str(tmp_path / 'zaten.mp4')
    subprocess.run(
        ['ffmpeg', '-hide_banner', '-v', 'error',
         '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=25', '-t', '1',
         '-c:v', 'libx264', '-y', path],
        check=True, capture_output=True,
    )
    onceki = os.path.getsize(path)

    yuzdeler = []
    pp = ForceH264PP(on_progress=yuzdeler.append)
    pp.run({'filepath': path, 'vcodec': 'avc1.640015'})

    assert os.path.getsize(path) == onceki
    assert yuzdeler == []


def test_iptal_yarim_dosya_birakmiyor(av1_kaynak):
    """En kritik davranış: iptal edilen dönüştürme çöp bırakmamalı."""
    iptal = threading.Event()
    pp = ForceH264PP(on_progress=lambda p: iptal.set(), should_cancel=iptal.is_set)

    with pytest.raises(ProcessCancelled):
        pp.run({'filepath': av1_kaynak, 'vcodec': 'vp09.00.50.08', 'duration': 3})

    klasor = os.path.dirname(av1_kaynak)
    assert not [f for f in os.listdir(klasor) if f.endswith('.h264.mp4')]
    # Kaynak dosya bozulmamış olmalı.
    assert _vcodec(av1_kaynak) == 'vp9'


def test_eksik_dosyada_sessizce_geciyor(tmp_path):
    pp = ForceH264PP()
    files, info = pp.run({'filepath': str(tmp_path / 'yok.mp4'), 'vcodec': 'av01'})
    assert files == []


# --------------------------------------------------------------------------
# Donanım encoder çözünürlük tavanı
#
# Arka plan: 8K (7680x3150) bir kaynakta h264_nvenc "No capable devices
# found" ile açılamadı; ffmpeg "Nothing was written into output file" dedi ve
# indirme "Hata!" ile bitti. NVENC/QSV/AMF H.264 encoder'ları 4096x4096
# üstünü kabul etmiyor; probe 320x240 ile yapıldığı için seçim bunu görmüyordu.
# --------------------------------------------------------------------------

def test_8k_kaynakta_donanim_encoder_atlaniyor():
    from src.core.ytdlp_base import encoder_chain
    zincir = encoder_chain(7680, 3150)
    assert [ad for ad, _ in zincir] == ['libx264']


def test_4k_ve_altinda_zincir_libx264_ile_bitiyor():
    from src.core.ytdlp_base import encoder_chain
    zincir = encoder_chain(3840, 2160)
    assert zincir[-1][0] == 'libx264'
    assert len({ad for ad, _ in zincir}) == len(zincir)


def test_encoder_acilamayinca_sonrakine_geciliyor(av1_kaynak, monkeypatch):
    """Probe'u geçen encoder gerçek kaynakta patlarsa dönüştürme yine bitmeli."""
    import src.core.ytdlp_base as m
    monkeypatch.setattr(
        m, 'encoder_chain',
        lambda w, h: [('h264_yok_boyle_encoder', []), ('libx264', ['-preset', 'ultrafast', '-crf', '18'])],
    )
    yuzdeler = []
    pp = ForceH264PP(on_progress=yuzdeler.append)
    pp.run({'filepath': av1_kaynak, 'vcodec': 'vp09.00.50.08', 'duration': 3,
            'width': 320, 'height': 240})

    assert _vcodec(av1_kaynak) == 'h264'
    assert yuzdeler[-1] == 100
    klasor = os.path.dirname(av1_kaynak)
    assert not [f for f in os.listdir(klasor) if f.endswith('.h264.mp4')]
