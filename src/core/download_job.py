#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arayüzden bağımsız indirme işi.

run() çağıran iş parçacığında çalışır ve biter; ilerleme ve sonuç geri çağrılarla
bildirilir. Web arayüzü (src/web/api.py) bunu düz threading.Thread içinde çalıştırır.
"""
import random
import time
from dataclasses import dataclass
from typing import Callable, Optional

from src.utils import config as cfg
from src.utils.helpers import detect_platform

# İlerleme en fazla bu aralıkla bildirilir. yt-dlp her veri bloğunda çağırıyor; hızlı
# bağlantıda saniyede yüzlerce bildirim arayüz kuyruğunu doldurup animasyonları takıltıyordu.
PROGRESS_EMIT_INTERVAL_S = 0.05
MAX_ATTEMPTS = 3
# Yeniden denemeler arası bekleme: 1.5 sn, 3 sn (deneme numarasıyla artar).
RETRY_BACKOFF_S = 1.5
CANCELLED_MESSAGE = "İndirme iptal edildi"
# YouTube Shorts dikey; "best" bazen yatay 1080p'ye kırpılmış kopyayı seçiyor.
SHORTS_FORMAT = 'bestvideo[width<=720]+bestaudio/best'

ProgressCallback = Callable[[dict], None]
CompleteCallback = Callable[[bool, str, str], None]


@dataclass
class DownloadRequest:
    url: str
    output_dir: str
    format_id: Optional[str] = None
    is_audio: bool = False
    save_metadata: bool = False
    ratelimit: Optional[str] = None
    proxy: Optional[str] = None
    write_sub: bool = False
    normalize_audio: bool = False
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_live: bool = False
    custom_ffmpeg_args: Optional[str] = None
    filename_template: Optional[str] = None
    sponsorblock: bool = False


def _proxy_pool() -> list[str]:
    return [p.strip() for p in cfg.get('proxy_pool', '').splitlines() if p.strip()]


class DownloadJob:
    def __init__(self, downloader, request: DownloadRequest,
                 on_progress: ProgressCallback, on_complete: CompleteCallback, semaphore=None):
        self.downloader = downloader
        self.request = request
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._semaphore = semaphore
        self._cancelled = False
        self._task = None
        self._last_emit = 0.0
        self.final_filename = ''

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self):
        self._cancelled = True
        if self._task:
            self._task.cancel()

    def run(self):
        if self._semaphore:
            self._semaphore.acquire()
        try:
            self._download()
        finally:
            if self._semaphore:
                self._semaphore.release()

    # yt-dlp geri çağrıları
    def progress_hook(self, d: dict):
        if self._cancelled:
            return
        status = d.get('status')
        if status == 'downloading':
            done = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            now = time.monotonic()
            if now - self._last_emit < PROGRESS_EMIT_INTERVAL_S and not (total and done >= total):
                return
            self._last_emit = now
            self._on_progress({
                'status': 'downloading', 'downloaded_bytes': done, 'total_bytes': total,
                'speed': d.get('speed', 0), 'eta': d.get('eta', 0),
                'progress': d.get('progress', 0), 'filename': d.get('filename', ''),
            })
        elif status == 'finished':
            self.final_filename = d.get('filename', '')
            self._on_progress({'status': 'processing', 'filename': self.final_filename})
        else:
            # 'processing', 'converting', 'recording' ayrı gösterilir; düşürülünce 4K H.264
            # dönüştürmesi boyunca ilerleme son indirme satırında donmuş görünüyordu.
            self._on_progress(d)

    def complete_hook(self, success: bool, error=None):
        if self._cancelled:
            self._on_complete(False, CANCELLED_MESSAGE, '')
        else:
            self._on_complete(success, error or '', self.final_filename if success else '')

    def _download(self):
        req = self.request
        format_id = req.format_id
        if detect_platform(req.url) == 'youtube_shorts' and not req.is_audio and format_id in (None, '', 'best'):
            format_id = SHORTS_FORMAT

        pool = _proxy_pool()
        proxy = req.proxy or (random.choice(pool) if pool else None)
        last_error = None
        for attempt in range(MAX_ATTEMPTS):
            if self._cancelled:
                self.complete_hook(False)
                return
            if attempt > 0 and pool and not req.proxy:
                proxy = random.choice(pool)
            try:
                if req.is_live:
                    self._task = self.downloader.download_livestream(
                        req.url, req.output_dir,
                        progress_callback=self.progress_hook, complete_callback=self.complete_hook, proxy=proxy,
                    )
                elif req.is_audio:
                    self.downloader.download_audio(
                        req.url, req.output_dir,
                        progress_callback=self.progress_hook, complete_callback=self.complete_hook,
                        save_info=req.save_metadata, ratelimit=req.ratelimit,
                        normalize_audio=req.normalize_audio, proxy=proxy,
                        custom_ffmpeg_args=req.custom_ffmpeg_args, filename_template=req.filename_template,
                    )
                else:
                    self._task = self.downloader.download_video(
                        req.url, req.output_dir, format_id=format_id,
                        progress_callback=self.progress_hook, complete_callback=self.complete_hook,
                        cancel_callback=lambda: self._cancelled,
                        save_info=req.save_metadata, ratelimit=req.ratelimit, write_sub=req.write_sub,
                        start_time=req.start_time, end_time=req.end_time, proxy=proxy,
                        custom_ffmpeg_args=req.custom_ffmpeg_args, filename_template=req.filename_template,
                        sponsorblock=req.sponsorblock,
                    )
                return
            except Exception as e:
                last_error = e
                print(f"[İndirme] Deneme {attempt + 1}/{MAX_ATTEMPTS} başarısız ({req.url}): {e}")
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(RETRY_BACKOFF_S * (attempt + 1))
        self.complete_hook(False, str(last_error))


class SpotifyJob:
    """spotidownloader üzerinden Spotify şarkısı; DownloadJob ile aynı arayüz."""

    def __init__(self, url: str, output_dir: str,
                 on_progress: ProgressCallback, on_complete: CompleteCallback, semaphore=None):
        self.url = url
        self.output_dir = output_dir
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._semaphore = semaphore
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self):
        self._cancelled = True

    def run(self):
        if self._semaphore:
            self._semaphore.acquire()
        try:
            self._download()
        finally:
            if self._semaphore:
                self._semaphore.release()

    def _download(self):
        from src.core.spotify_downloader import download_track

        def progress(pct: int, downloaded: int, total: int):
            if not self._cancelled:
                self._on_progress({'status': 'downloading', 'progress': pct, 'downloaded_bytes': downloaded,
                                   'total_bytes': total, 'speed': 0, 'eta': 0, 'filename': ''})
        try:
            filepath = download_track(self.url, self.output_dir, progress_callback=progress,
                                      cancel_flag=lambda: self._cancelled)
        except Exception as e:
            self._on_complete(False, f"Spotify indirmesi başarısız: {e}", '')
            return
        if self._cancelled:
            self._on_complete(False, CANCELLED_MESSAGE, '')
        elif filepath:
            self._on_progress({'status': 'processing', 'filename': filepath})
            self._on_complete(True, '', filepath)
        else:
            self._on_complete(False, "Spotify şarkısı indirilemedi; bağlantıyı kontrol et.", '')


class ConcurrencyLimiter:
    """
    Aynı anda en fazla N indirme. threading.Semaphore'dan farkı: sınır çalışırken değişebilir
    (Ayarlar'daki "eş zamanlı indirme" yeniden başlatma istemesin). acquire/release arayüzü aynı.
    """

    def __init__(self, limit: int):
        import threading
        self._cond = threading.Condition()
        self._limit = max(1, int(limit))
        self._active = 0

    def set_limit(self, limit: int):
        with self._cond:
            self._limit = max(1, int(limit))
            self._cond.notify_all()

    def acquire(self):
        with self._cond:
            while self._active >= self._limit:
                self._cond.wait()
            self._active += 1

    def release(self):
        with self._cond:
            self._active -= 1
            self._cond.notify_all()
