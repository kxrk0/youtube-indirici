#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
İndirme sonrası geçmiş kaydı.

Hata: indirici de (downloader._save_to_history) arayüz de kayıt atıyordu; her indirme
geçmişte iki kez görünüyordu (biri başlıkla, biri ".mp4" dosya adıyla). Tek kaynak artık
src.core.completion; format da orada tutuluyor ki "tekrar indir" aynı kaliteyi seçsin.
"""
from unittest.mock import patch

from src.core import completion
from src.core.database import DownloadHistory


def _meta(**kw):
    base = dict(url='https://www.youtube.com/watch?v=x', type_str='video', title='UZI - CINDY',
                channel='MuzikPlay', thumbnail_url='https://i.ytimg.com/x.jpg', duration=119,
                format_quality='edit_h264')
    base.update(kw)
    return completion.DownloadMeta(**base)


def test_basari_tek_kayit_ve_tum_bilgilerle_yazilir(tmp_path):
    db = DownloadHistory(str(tmp_path / 'h.db'))
    media = tmp_path / 'Klip.mp4'
    media.write_bytes(b'x' * 10)
    with patch('src.core.completion.get_download_history', return_value=db), \
            patch('src.core.completion.send_webhook'), patch('src.core.completion._plugin_hook'):
        final = completion.on_success(str(media), _meta())
    rows = db.get_all_downloads()
    assert final == str(media)
    assert len(rows) == 1
    row = rows[0]
    assert row['title'] == 'UZI - CINDY' and row['channel'] == 'MuzikPlay'
    assert row['format_quality'] == 'edit_h264' and row['file_size'] == 10 and row['status'] == 'completed'


def test_hata_tek_kayit_ve_mesajla_yazilir(tmp_path):
    db = DownloadHistory(str(tmp_path / 'h.db'))
    with patch('src.core.completion.get_download_history', return_value=db), \
            patch('src.core.completion.send_webhook'), patch('src.core.completion._plugin_hook'):
        completion.on_failure('HTTP 403', _meta())
    rows = db.get_all_downloads()
    assert len(rows) == 1 and rows[0]['status'] == 'error' and rows[0]['error_message'] == 'HTTP 403'
