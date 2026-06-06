#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import platform
import hashlib
import subprocess
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from src.utils.helpers import extract_video_thumbnail, get_ffmpeg_path, detect_platform


class ThumbnailWorker(QThread):
    thumbnail_ready = pyqtSignal(str, str)

    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        self.is_running = True

    def run(self):
        cache_dir = os.path.join(os.getcwd(), 'cache', 'thumbnails')
        os.makedirs(cache_dir, exist_ok=True)

        while self.is_running:
            if not self.queue:
                self.msleep(100)
                continue
            video_path = self.queue.pop(0)
            file_hash = hashlib.md5(video_path.encode('utf-8')).hexdigest()
            thumb_path = os.path.join(cache_dir, f"{file_hash}.jpg")

            if os.path.exists(thumb_path):
                self.thumbnail_ready.emit(video_path, thumb_path)
            elif video_path.lower().endswith('.mp3'):
                self.thumbnail_ready.emit(video_path, "AUDIO")
            else:
                success = extract_video_thumbnail(video_path, thumb_path)
                self.thumbnail_ready.emit(video_path, thumb_path if success else "ERROR")

    def stop(self):
        self.is_running = False


class InfoFetchWorker(QThread):
    info_ready = pyqtSignal(dict, list, bool)

    def __init__(self, downloader, url):
        super().__init__()
        self.downloader = downloader
        self.url = url

    def run(self):
        if "list=" in self.url and "watch?v=" not in self.url:
            is_playlist = True
            info = self.downloader.get_playlist_info(self.url)
            formats = []
        else:
            is_playlist = False
            info = self.downloader.get_video_info(self.url)
            formats = self.downloader.get_available_formats(self.url) if info else []
        self.info_ready.emit(info or {}, formats, is_playlist)


class DownloadWorker(QThread):
    progress_signal = pyqtSignal(dict)
    completed_signal = pyqtSignal(bool, str, str)
    cancelled_signal = pyqtSignal()

    def __init__(self, downloader, url, output_dir, format_id=None, is_audio=False,
                 save_metadata=False, ratelimit=None, proxy=None, write_sub=False,
                 normalize_audio=False, start_time=None, end_time=None,
                 is_live=False, custom_ffmpeg_args=None, semaphore=None):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.output_dir = output_dir
        self.format_id = format_id
        self.is_audio = is_audio
        self.save_metadata = save_metadata
        self.ratelimit = ratelimit
        self.proxy = proxy
        self.write_sub = write_sub
        self.normalize_audio = normalize_audio
        self.start_time = start_time
        self.end_time = end_time
        self.is_live = is_live
        self.custom_ffmpeg_args = custom_ffmpeg_args
        self.semaphore = semaphore
        self.final_filename = None
        self.download_task = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if self.download_task:
            self.download_task.cancel()
        self.cancelled_signal.emit()

    def is_cancelled_flag(self) -> bool:
        return self._cancelled

    def progress_callback(self, d):
        if self._cancelled:
            return
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            self.progress_signal.emit({
                'downloaded_bytes': downloaded,
                'total_bytes': total,
                'speed': d.get('speed', 0),
                'filename': d.get('filename', ''),
                'status': 'downloading',
                'eta': d.get('eta', 0),
                'progress': d.get('progress', 0),
            })
        elif d['status'] == 'finished':
            self.final_filename = d.get('filename', '')
            self.progress_signal.emit({'status': 'processing', 'filename': self.final_filename})

    def complete_callback(self, success, error=None):
        if self._cancelled:
            self.completed_signal.emit(False, "İndirme iptal edildi", "")
        else:
            self.completed_signal.emit(
                success,
                error if error else "",
                self.final_filename if success else ""
            )

    def run(self):
        if self.semaphore:
            self.semaphore.acquire()
        try:
            self._do_download()
        finally:
            if self.semaphore:
                self.semaphore.release()

    def _do_download(self):
        # Shorts için dikey format düzeltmesi
        if (detect_platform(self.url) == 'youtube_shorts'
                and not self.is_audio
                and (not self.format_id or self.format_id == 'best')):
            self.format_id = 'bestvideo[width<=720]+bestaudio/best'

        if self.is_live:
            self.download_task = self.downloader.download_livestream(
                self.url, self.output_dir,
                progress_callback=self.progress_callback,
                complete_callback=self.complete_callback,
                proxy=self.proxy,
            )
        elif self.is_audio:
            self.downloader.download_audio(
                self.url, self.output_dir,
                progress_callback=self.progress_callback,
                complete_callback=self.complete_callback,
                save_info=self.save_metadata,
                ratelimit=self.ratelimit,
                normalize_audio=self.normalize_audio,
                proxy=self.proxy,
                custom_ffmpeg_args=self.custom_ffmpeg_args,
            )
        else:
            self.download_task = self.downloader.download_video(
                self.url, self.output_dir,
                format_id=self.format_id,
                progress_callback=self.progress_callback,
                complete_callback=self.complete_callback,
                cancel_callback=self.is_cancelled_flag,
                save_info=self.save_metadata,
                ratelimit=self.ratelimit,
                write_sub=self.write_sub,
                start_time=self.start_time,
                end_time=self.end_time,
                proxy=self.proxy,
                custom_ffmpeg_args=self.custom_ffmpeg_args,
            )


class FormatConverterWorker(QThread):
    """FFmpeg ile format dönüştürme worker'ı"""
    progress_signal = pyqtSignal(str)
    completed_signal = pyqtSignal(bool, str)

    def __init__(self, input_path: str, output_format: str):
        super().__init__()
        self.input_path = input_path
        self.output_format = output_format.lower().strip('.')

    def run(self):
        try:
            base = os.path.splitext(self.input_path)[0]
            output_path = f"{base}_converted.{self.output_format}"

            ffmpeg_dir = get_ffmpeg_path()
            if ffmpeg_dir:
                ffmpeg_cmd = os.path.join(
                    ffmpeg_dir,
                    'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg'
                )
            else:
                ffmpeg_cmd = 'ffmpeg'

            cmd = [ffmpeg_cmd, '-y', '-i', self.input_path]

            if self.output_format == 'mp3':
                cmd += ['-vn', '-q:a', '0', '-map', 'a']
            elif self.output_format == 'mp4':
                cmd += ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k']
            elif self.output_format == 'webm':
                cmd += ['-c:v', 'libvpx-vp9', '-crf', '30', '-b:v', '0', '-c:a', 'libopus']
            elif self.output_format == 'mkv':
                cmd += ['-c:v', 'copy', '-c:a', 'copy']

            cmd.append(output_path)

            flags = subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
            result = subprocess.run(cmd, capture_output=True, creationflags=flags)

            if result.returncode == 0:
                self.completed_signal.emit(True, output_path)
            else:
                err = result.stderr.decode('utf-8', errors='replace')[-300:]
                self.completed_signal.emit(False, err)
        except Exception as e:
            self.completed_signal.emit(False, str(e))
