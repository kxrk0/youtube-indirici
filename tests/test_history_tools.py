#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Geçmiş araçları: tekrar indirme kararı, eksik dosya tespiti, dışa aktarma."""
import csv
import json

from src.core.history_tools import collapse_duplicates, export_csv, export_json, missing_files, retry_request


def test_tur_ve_dosya_biliniyorsa_dogrudan_ayni_klasore_iner(tmp_path):
    f = tmp_path / 'Klip.mp4'
    f.write_bytes(b'x')
    req = retry_request({'url': 'https://youtu.be/x', 'format_type': 'video', 'file_path': str(f),
                         'format_quality': 'edit_h264', 'title': 'Klip'}, 'C:/fallback')
    assert req['mode'] == 'direct'
    assert req['outputDir'] == str(tmp_path)
    assert req['format'] == 'edit_h264'


def test_klasor_silinmisse_varsayilan_klasore_iner():
    req = retry_request({'url': 'u', 'format_type': 'audio', 'file_path': 'Z:/yok/olmayan.mp3'}, 'C:/fallback')
    assert req['outputDir'] == 'C:/fallback'
    assert req['format'] == 'bestaudio/best'


def test_bilgi_eksikse_ana_sayfaya_gider():
    assert retry_request({'url': 'u', 'format_type': None, 'file_path': None}, 'x') == {'mode': 'home', 'url': 'u'}


def test_yalnizca_tamamlanmis_ve_diskte_olmayanlar_eksik_sayilir(tmp_path):
    present = tmp_path / 'var.mp4'
    present.write_bytes(b'x')
    rows = [
        {'status': 'completed', 'file_path': str(present)},
        {'status': 'completed', 'file_path': str(tmp_path / 'yok.mp4')},
        {'status': 'error', 'file_path': str(tmp_path / 'hata.mp4')},
        {'status': 'completed', 'file_path': None},
    ]
    assert missing_files(rows) == ['yok.mp4']


def test_disa_aktarma_turkce_karakterleri_korur(tmp_path):
    rows = [{'id': 1, 'title': 'ŞAM - BANA SOR', 'url': 'u', 'status': 'completed', 'extra': 'atlanır'}]
    export_csv(rows, tmp_path / 'g.csv')
    export_json(rows, tmp_path / 'g.json')
    with open(tmp_path / 'g.csv', encoding='utf-8-sig') as f:
        assert next(csv.DictReader(f))['title'] == 'ŞAM - BANA SOR'
    data = json.loads((tmp_path / 'g.json').read_text(encoding='utf-8'))
    assert data[0]['title'] == 'ŞAM - BANA SOR' and 'extra' not in data[0]


def test_eski_cift_kayitlar_tek_satira_iner():
    rows = [
        {'id': 2, 'url': 'u', 'file_path': 'C:/d/Klip.mp4', 'status': 'completed', 'title': 'Klip.mp4', 'channel': None},
        {'id': 1, 'url': 'u', 'file_path': 'C:/d/Klip.mp4', 'status': 'completed', 'title': 'Klip', 'channel': 'Kanal'},
        {'id': 0, 'url': 'u', 'file_path': None, 'status': 'error', 'title': 'Klip', 'channel': 'Kanal'},
    ]
    out = collapse_duplicates(rows)
    assert [r['id'] for r in out] == [1, 0]
