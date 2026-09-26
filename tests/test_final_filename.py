#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Birleştirme + dönüştürme sonrası nihai dosya yolunun arayüze ulaşması.

Hata: bestvideo+bestaudio indirmesinde kuyruk kartı ve geçmiş kaydı,
birleştirmeden önce silinen ses parçasını (".f251.webm") gösteriyordu;
H.264 dönüştürme ilerlemesi de worker'da filtrelenip karta hiç varmıyordu.
"""

import os
import threading
from unittest.mock import patch

from src.core.downloader import Downloader
from src.core.download_job import DownloadJob, DownloadRequest

AUDIO_PART = os.path.join('out', 'Klip.f251.webm')
FINAL_FILE = os.path.join('out', 'Klip.mp4')
COMPLETE_TIMEOUT_S = 5


class _FakeYDL:
    """ydl.download'ı yt-dlp'nin hook sırasıyla taklit eder: parça bitti → post hook."""

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def download(self, urls):
        for hook in self.opts.get('progress_hooks', []):
            hook({'status': 'finished', 'filename': AUDIO_PART})
        for hook in self.opts.get('post_hooks', []):
            hook(FINAL_FILE)


def test_download_video_reports_final_file_not_intermediate_part():
    events = []
    done = threading.Event()

    def on_complete(success, error=None):
        events.append(('complete', success))
        done.set()

    downloader = Downloader()
    # İndirici geçmişe yazmaz (tek kaynak src.core.completion); yazmaya kalkarsa test patlar.
    with patch('src.core.downloader.yt_dlp.YoutubeDL', _FakeYDL), \
            patch('src.core.database.DownloadHistory.add_download',
                  side_effect=AssertionError('indirici geçmişe kayıt atmamalı')):
        task = downloader.download_video(
            'https://www.youtube.com/watch?v=test', 'out',
            format_id='best',
            progress_callback=events.append,
            complete_callback=on_complete,
        )
        assert done.wait(COMPLETE_TIMEOUT_S), 'complete_callback çağrılmadı'

    finished = [e for e in events if isinstance(e, dict) and e.get('status') == 'finished']
    assert finished and finished[-1]['filename'] == FINAL_FILE
    assert task.filename == FINAL_FILE
    assert events[-1] == ('complete', True)


def test_worker_forwards_conversion_progress_and_final_path():
    emitted = []
    completed = []
    job = DownloadJob(None, DownloadRequest('https://www.youtube.com/watch?v=test', 'out'),
                      emitted.append, lambda s, e, f: completed.append((s, e, f)))

    job.progress_hook({'status': 'converting', 'progress': 42, 'filename': FINAL_FILE})
    job.progress_hook({'status': 'finished', 'filename': FINAL_FILE})
    job.complete_hook(True)

    assert {'status': 'converting', 'progress': 42, 'filename': FINAL_FILE} in emitted
    assert completed == [(True, '', FINAL_FILE)]
