#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import platform
import hashlib
import subprocess
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from src.utils.helpers import extract_video_thumbnail, get_ffmpeg_path, detect_platform


def _extract_audio_cover(audio_path: str, out_jpg: str) -> bool:
    """ID3/MP4 tag'inden kapak resmini çıkarır. Başarıda True."""
    ext = audio_path.lower().rsplit('.', 1)[-1]
    try:
        if ext in ('mp3',):
            from mutagen.id3 import ID3
            tags = ID3(audio_path)
            for key in tags:
                if key.startswith('APIC'):
                    data = tags[key].data
                    if data:
                        with open(out_jpg, 'wb') as f:
                            f.write(data)
                        return True
        elif ext in ('m4a', 'mp4', 'aac'):
            from mutagen.mp4 import MP4
            tags = MP4(audio_path)
            covr = tags.get('covr')
            if covr:
                with open(out_jpg, 'wb') as f:
                    f.write(bytes(covr[0]))
                return True
        elif ext in ('flac',):
            from mutagen.flac import FLAC
            audio = FLAC(audio_path)
            pics = audio.pictures
            if pics:
                with open(out_jpg, 'wb') as f:
                    f.write(pics[0].data)
                return True
        elif ext in ('ogg',):
            from mutagen.oggvorbis import OggVorbis
            import base64
            audio = OggVorbis(audio_path)
            metadata_block = audio.get('metadata_block_picture')
            if metadata_block:
                from mutagen.flac import Picture
                pic = Picture(base64.b64decode(metadata_block[0]))
                with open(out_jpg, 'wb') as f:
                    f.write(pic.data)
                return True
    except Exception:
        pass
    return False


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
            elif video_path.lower().endswith(('.mp3', '.m4a', '.flac', '.ogg')):
                # MP3/ses: ID3 kapak resmini çıkar, yoksa AUDIO fallback
                extracted = _extract_audio_cover(video_path, thumb_path)
                self.thumbnail_ready.emit(video_path, thumb_path if extracted else "AUDIO")
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
            # Formatları aynı info dict'ten al — ikinci API çağrısı yok
            formats = info.get('formats', []) if info else []
        self.info_ready.emit(info or {}, formats, is_playlist)


class DownloadWorker(QThread):
    progress_signal = pyqtSignal(dict)
    completed_signal = pyqtSignal(bool, str, str)
    cancelled_signal = pyqtSignal()

    def __init__(self, downloader, url, output_dir, format_id=None, is_audio=False,
                 save_metadata=False, ratelimit=None, proxy=None, write_sub=False,
                 normalize_audio=False, start_time=None, end_time=None,
                 is_live=False, custom_ffmpeg_args=None, semaphore=None,
                 filename_template=None, sponsorblock=False):
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
        self.filename_template = filename_template
        self.sponsorblock = sponsorblock
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

    def _resolve_proxy(self) -> Optional[str]:
        """Return proxy to use: explicit proxy > pool rotation > None."""
        if self.proxy:
            return self.proxy
        try:
            from src.utils import config as _cfg
            pool = [p.strip() for p in _cfg.get('proxy_pool', '').splitlines() if p.strip()]
            if pool:
                import random
                return random.choice(pool)
        except Exception:
            pass
        return None

    def _do_download(self):
        # Shorts için dikey format düzeltmesi
        if (detect_platform(self.url) == 'youtube_shorts'
                and not self.is_audio
                and (not self.format_id or self.format_id == 'best')):
            self.format_id = 'bestvideo[width<=720]+bestaudio/best'

        effective_proxy = self._resolve_proxy()
        _MAX_RETRIES = 3
        last_exc = None

        for attempt in range(_MAX_RETRIES):
            if self._cancelled:
                break
            # On retry pick a different proxy from pool
            if attempt > 0:
                try:
                    from src.utils import config as _cfg
                    pool = [p.strip() for p in _cfg.get('proxy_pool', '').splitlines() if p.strip()]
                    if pool:
                        import random
                        effective_proxy = random.choice(pool)
                except Exception:
                    pass

            try:
                if self.is_live:
                    self.download_task = self.downloader.download_livestream(
                        self.url, self.output_dir,
                        progress_callback=self.progress_callback,
                        complete_callback=self.complete_callback,
                        proxy=effective_proxy,
                    )
                elif self.is_audio:
                    self.downloader.download_audio(
                        self.url, self.output_dir,
                        progress_callback=self.progress_callback,
                        complete_callback=self.complete_callback,
                        save_info=self.save_metadata,
                        ratelimit=self.ratelimit,
                        normalize_audio=self.normalize_audio,
                        proxy=effective_proxy,
                        custom_ffmpeg_args=self.custom_ffmpeg_args,
                        filename_template=self.filename_template,
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
                        proxy=effective_proxy,
                        custom_ffmpeg_args=self.custom_ffmpeg_args,
                        filename_template=self.filename_template,
                        sponsorblock=self.sponsorblock,
                    )
                return  # success
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    self.msleep(1500 * (attempt + 1))
                    continue
                # All retries exhausted
                self.complete_callback(False, str(last_exc))
                return


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


class SpotifyInfoWorker(QThread):
    """Spotify oEmbed üzerinden şarkı meta verisi alır (auth gerekmez)"""
    info_ready = pyqtSignal(dict, list, bool)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            from src.core.spotify_downloader import get_track_info
            info = get_track_info(self.url)
            self.info_ready.emit(info or {}, [], False)
        except Exception as e:
            print(f"SpotifyInfoWorker error: {e}")
            self.info_ready.emit({}, [], False)


class SpotifyDownloadWorker(QThread):
    """spotidownloader.com API üzerinden Spotify şarkısı indirir"""
    progress_signal   = pyqtSignal(dict)
    completed_signal  = pyqtSignal(bool, str, str)
    cancelled_signal  = pyqtSignal()

    def __init__(self, url: str, output_dir: str, semaphore=None):
        super().__init__()
        self.url        = url
        self.output_dir = output_dir
        self.semaphore  = semaphore
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        self.cancelled_signal.emit()

    def _cancel_flag(self) -> bool:
        return self._cancelled

    def run(self):
        if self.semaphore:
            self.semaphore.acquire()
        try:
            self._do_download()
        finally:
            if self.semaphore:
                self.semaphore.release()

    def _do_download(self):
        from src.core.spotify_downloader import download_track

        def progress_cb(pct: int, downloaded: int, total: int):
            if self._cancelled:
                return
            self.progress_signal.emit({
                'status':           'downloading',
                'progress':         pct,
                'downloaded_bytes': downloaded,
                'total_bytes':      total,
                'speed':            0,
                'eta':              0,
                'filename':         '',
            })

        try:
            filepath = download_track(
                self.url,
                self.output_dir,
                progress_callback=progress_cb,
                cancel_flag=self._cancel_flag,
            )
            if self._cancelled:
                self.completed_signal.emit(False, "İndirme iptal edildi", "")
            elif filepath:
                self.progress_signal.emit({'status': 'processing', 'filename': filepath})
                self.completed_signal.emit(True, "", filepath)
            else:
                self.completed_signal.emit(False, "Spotify indirme başarısız — dosya oluşturulamadı", "")
        except Exception as e:
            self.completed_signal.emit(False, str(e), "")


class ThumbnailUrlWorker(QThread):
    """Uzak URL'den thumbnail bytes indirir"""
    loaded = pyqtSignal(bytes)

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self):
        try:
            import ssl
            import urllib.request
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode    = ssl.CERT_NONE
            req = urllib.request.Request(
                self._url,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                data = resp.read()
            if data:
                self.loaded.emit(data)
        except Exception:
            pass


class WhisperWorker(QThread):
    """Whisper AI ile ses/video dosyasından transkript oluşturur."""
    progress_signal  = pyqtSignal(str)    # log line
    finished_signal  = pyqtSignal(str)    # transcript text
    error_signal     = pyqtSignal(str)    # error message

    def __init__(self, file_path: str, model: str = 'base', language: str = 'tr', parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._model     = model
        self._language  = language

    def run(self):
        try:
            self.progress_signal.emit("Whisper modeli yükleniyor…")
            import whisper  # type: ignore
            model = whisper.load_model(self._model)
            self.progress_signal.emit(f"Transkript oluşturuluyor: {os.path.basename(self._file_path)}")
            result = model.transcribe(self._file_path, language=self._language, verbose=False)
            text = result.get('text', '').strip()
            # Save alongside source file
            out_path = os.path.splitext(self._file_path)[0] + '.txt'
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(text)
            self.finished_signal.emit(out_path)
        except ImportError:
            self.error_signal.emit(
                "openai-whisper kurulu değil.\n"
                "Kur: pip install openai-whisper"
            )
        except Exception as e:
            self.error_signal.emit(str(e))
