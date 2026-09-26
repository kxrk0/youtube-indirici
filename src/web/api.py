#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web arayüzünün Python köprüsü.

pywebview bu sınıfın genel metodlarını JS'e `window.pywebview.api.<ad>()` olarak açar;
her çağrı ayrı bir iş parçacığında çalışır ve dönüş değeri JSON olarak Promise'e düşer.
Python'dan arayüze olaylar (indirme ilerlemesi, bitiş) `window.__ortamEvent(...)` ile itilir.

Kural: burada iş mantığı yok. Her şey src.core'dan gelir; köprü yalnızca veriyi arayüzün
ihtiyacı kadar süzer (tam format listesi yerine kalite seçenekleri gibi).
"""
import base64
import datetime
import itertools
import json
import os
import re
import shutil
import ssl
import subprocess
import threading
import urllib.request
from typing import Any, Optional

from src.core import completion, history_tools, media_library
from src.core.database import get_download_history
from src.core import automation, settings_schema
from src.core.download_job import ConcurrencyLimiter, DownloadJob, DownloadRequest, SpotifyJob
from src.core.formats import auto_codec_family, build_quality_options
from src.utils import config as cfg
from src.utils.helpers import get_clipboard_text, get_os_download_dir, is_valid_url

THUMBNAIL_TIMEOUT_S = 10
# Geçmişten okunacak satır; aynı bağlantının kopyaları elendikten sonra RECENT_LIMIT'e iner.
RECENT_SCAN_ROWS = 60
RECENT_LIMIT = 12
# Zamanlayıcı kontrol aralığı; dakikalık görevleri kaçırmamak için dakikadan kısa.
SCHEDULER_TICK_S = 20
YTDLP_UPDATE_TIMEOUT_S = 120
# Proxy testi: dış IP'yi JSON döndüren basit uç (eski arayüzle aynı).
PROXY_TEST_URL = 'http://httpbin.org/ip'
PROXY_TEST_TIMEOUT_S = 10
AUTO_SHUTDOWN_DELAY_S = 30
# Geçmiş sayfasında gösterilen satır (eski arayüzle aynı sınır).
HISTORY_ROWS = 200
CHANNEL_SCAN_LIMIT = 100
DEFAULT_CONCURRENCY = 3
DRM_HOSTS = ('music.apple.com', 'tidal.com', 'deezer.com')
CHANNEL_RE = re.compile(r'youtube\.com/(@[\w.-]+|channel/[\w-]+|c/[\w-]+|user/[\w-]+)\s*/?(\?.*)?$')


def _thumbnail_request(url: str) -> bytes:
    # YouTube görsel sunucuları bazı kurumsal ağlarda aracı sertifikayla geliyor; eski arayüzdeki
    # ThumbnailUrlWorker da doğrulamayı kapatıyordu. Yalnızca kamuya açık görseller için.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=THUMBNAIL_TIMEOUT_S, context=ctx) as resp:
        return resp.read()


def _relative_note(size, when) -> str:
    parts = []
    if size:
        parts.append(_size_text(size))
    if when:
        try:
            dt = datetime.datetime.fromisoformat(str(when))
        except ValueError:
            dt = None
        if dt is not None:
            today = datetime.date.today()
            if dt.date() == today:
                parts.append(f"bugün {dt:%H:%M}")
            elif dt.date() == today - datetime.timedelta(days=1):
                parts.append(f"dün {dt:%H:%M}")
            else:
                parts.append(f"{dt:%d.%m.%Y}")
    return ', '.join(parts)


def release_summary(notes: str) -> str:
    """Sürüm notunun ilk anlamlı satırı. Notlar Markdown; '## Yenilikler' gibi başlıklar
    güncelleme bandında bilgi taşımıyor, madde işaretleri de gereksiz."""
    for line in notes.splitlines():
        text = line.strip()
        if not text or text.startswith('#'):
            continue
        return text.lstrip('-*> ').strip()
    return ''


def _size_text(n) -> str:
    """Türkçe ondalık, 1024 tabanı (Gezgin ile aynı): 145,9 MB."""
    units = ('B', 'KB', 'MB', 'GB')
    value = float(n)
    i = 0
    while value >= 1024 and i < len(units) - 1:
        value /= 1024
        i += 1
    return f"{int(value)} B" if i == 0 else f"{value:.1f}".replace('.', ',') + f" {units[i]}"


class OrtamApi:
    def __init__(self, downloader):
        self._downloader = downloader
        self._window = None
        self._paint_title_bar = None
        self._jobs: dict[int, Any] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        limit = int(cfg.get('max_concurrent', DEFAULT_CONCURRENCY) or DEFAULT_CONCURRENCY)
        self._semaphore = ConcurrencyLimiter(limit)
        self._fired: set = set()
        self._services_started = False
        self._shutdown_timer: Optional[threading.Timer] = None
        self._windows: list = []
        self._shell = None
        # Süren işlerin son durumu: sonradan açılan mini pencere buradan başlar.
        self._job_views: dict[int, dict] = {}
        self._update_info = None

    # pywebview, altçizgiyle başlayan öznitelikleri JS'e açmaz.
    def _attach(self, window, paint_title_bar):
        self._window = window
        self._paint_title_bar = paint_title_bar
        self._windows.append(window)

    def _attach_shell(self, shell):
        """Tepsi, mini pencere ve çıkışı yöneten masaüstü kabuğu (src/web/app.py)."""
        self._shell = shell

    def _add_window(self, window):
        self._windows.append(window)

    def _has_active_jobs(self) -> bool:
        with self._lock:
            return bool(self._jobs)

    def set_title_bar(self, hex_color: str) -> bool:
        """Arayüz paleti değişince Windows başlık çubuğunu aynı derin tona boyar."""
        value = hex_color.lstrip('#')
        if len(value) != 6:
            raise ValueError(f"set_title_bar: #rrggbb bekleniyordu, gelen: {hex_color!r}")
        self._paint_title_bar(self._window, tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)))
        return True

    def _emit(self, event: dict):
        script = f"window.__ortamEvent && window.__ortamEvent({json.dumps(event, ensure_ascii=False)})"
        for window in list(self._windows):
            try:
                window.run_js(script)
            except Exception as e:
                print(f"[Web] Olay pencereye iletilemedi ({window.title}, {event.get('type')}): {e}")

    # ── Açılış ──
    def bootstrap(self) -> dict:
        return {
            'downloadDir': cfg.get('download_dir') or get_os_download_dir(),
            'recent': self.recent(),
        }

    def clipboard(self) -> str:
        return get_clipboard_text() or ''

    # ── Bilgi ──
    def fetch_info(self, url: str) -> dict:
        url = (url or '').strip()
        if not is_valid_url(url):
            return {'kind': 'error', 'message': 'Bu geçerli bir bağlantı değil.'}
        if any(h in url for h in DRM_HOSTS):
            return {'kind': 'drm'}
        if 'open.spotify.com' in url:
            from src.core.spotify_downloader import get_track_info
            info = get_track_info(url)
            if not info:
                return {'kind': 'error', 'message': 'Spotify bu şarkının bilgisini vermedi.'}
            return {'kind': 'video', 'url': url, 'spotify': True, 'title': info.get('title', ''),
                    'channel': info.get('uploader', ''), 'duration': 0, 'thumbnail': info.get('thumbnail', ''),
                    'isLive': False, 'heatmap': None, 'options': [], 'autoFamily': ''}
        if CHANNEL_RE.search(url):
            return self._channel(url)
        if 'list=' in url and 'watch?v=' not in url:
            info = self._downloader.get_playlist_info(url)
            if not info:
                return {'kind': 'error', 'message': 'Oynatma listesi okunamadı.'}
            entries = [{'title': e.get('title') or 'Video',
                        'url': e.get('url') or f"https://www.youtube.com/watch?v={e.get('id')}"}
                       for e in (info.get('entries') or []) if e]
            return {'kind': 'list', 'title': info.get('title', ''), 'entries': entries}
        info = self._downloader.get_video_info(url)
        if not info:
            return {'kind': 'error', 'message': 'Bu bağlantı açılamadı. Sorun sürerse Ayarlar’dan yt-dlp’yi güncelle.'}
        formats = info.get('formats') or []
        heatmap = info.get('heatmap')
        return {
            'kind': 'video', 'url': url, 'spotify': False,
            'title': info.get('title') or '',
            'channel': info.get('uploader') or info.get('channel') or '',
            'duration': info.get('duration') or 0,
            'thumbnail': info.get('thumbnail') or '',
            'isLive': bool(info.get('is_live') or info.get('was_live')),
            'heatmap': [{'start': h.get('start_time', 0), 'end': h.get('end_time', 0), 'value': h.get('value', 0)}
                        for h in heatmap] if heatmap else None,
            'options': build_quality_options(formats),
            'autoFamily': auto_codec_family(formats),
        }

    def _channel(self, url: str) -> dict:
        import yt_dlp
        from src.core.ytdlp_base import base_opts
        try:
            with yt_dlp.YoutubeDL(base_opts(extract_flat='in_playlist', playlist_end=CHANNEL_SCAN_LIMIT)) as ydl:
                info = ydl.extract_info(url, download=False) or {}
        except Exception as e:
            return {'kind': 'error', 'message': f'Kanal okunamadı: {str(e)[:120]}'}
        entries = [{'title': e.get('title') or 'Video',
                    'url': e.get('url') or f"https://www.youtube.com/watch?v={e['id']}"}
                   for e in (info.get('entries') or []) if e and (e.get('url') or e.get('id'))]
        return {'kind': 'list', 'title': info.get('title') or 'Kanal', 'entries': entries}

    def thumbnail(self, url: str) -> Optional[str]:
        """Kapağı data URL olarak verir: tarayıcı başka alan adından gelen görselin
        piksellerini okumaya izin vermiyor (palet çıkarımı için gerekli)."""
        if not url:
            return None
        try:
            data = _thumbnail_request(url)
        except Exception as e:
            print(f"[Web] Kapak indirilemedi ({url}): {e}")
            return None
        mime = 'image/png' if data[:8] == b'\x89PNG\r\n\x1a\n' else (
            'image/webp' if data[8:12] == b'WEBP' else 'image/jpeg')
        return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    def estimate_size(self, url: str, output_dir: str) -> dict:
        import yt_dlp
        from src.core.ytdlp_base import base_opts
        try:
            with yt_dlp.YoutubeDL(base_opts(simulate=True, format='bestvideo+bestaudio/best')) as ydl:
                info = ydl.extract_info(url, download=False) or {}
        except Exception as e:
            print(f"[Web] Boyut tahmini alınamadı ({url}): {e}")
            return {'size': None, 'free': None}
        size = info.get('filesize') or info.get('filesize_approx') or None
        free = shutil.disk_usage(output_dir).free if output_dir and os.path.isdir(output_dir) else None
        return {'size': size, 'free': free}

    def was_downloaded(self, url: str) -> bool:
        return get_download_history().is_url_downloaded(url)

    # ── İndirme ──
    def start_download(self, req: dict) -> int:
        return self._start_job(req, origin='ui')

    def _start_job(self, req: dict, origin: str) -> int:
        """origin: 'ui' | 'schedule' | 'subscription' | 'restore'. Arayüz 'added' olayıyla listeye ekler."""
        job_id = next(self._ids)
        url = req['url']
        is_audio = req.get('type') == 'audio'
        output_dir = req.get('outputDir') or cfg.get('download_dir') or get_os_download_dir()
        meta = completion.DownloadMeta(url=url, type_str='audio' if is_audio else 'video',
                                       title=req.get('title', ''), channel=req.get('channel', ''),
                                       thumbnail_url=req.get('thumbnail', ''), duration=req.get('duration') or 0,
                                       format_quality='' if is_audio else (req.get('format') or 'best'))
        try:
            from src.core.auto_categorize import apply_rules
            rule = apply_rules(url=url, title=meta.title, channel=meta.channel, base_output_dir=output_dir)
            if rule.get('output_dir'):
                output_dir = rule['output_dir']
                os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            print(f"[Web] Otomatik kategori uygulanamadı ({url}): {e}")

        def progress(d: dict):
            event = {'type': 'progress', 'job': job_id, **{k: d.get(k) for k in (
                'status', 'downloaded_bytes', 'total_bytes', 'speed', 'eta', 'progress')}}
            view = self._job_views.get(job_id)
            if view is not None:
                view['last'] = event
            self._emit(event)

        def complete(success: bool, error: str, filepath: str):
            with self._lock:
                job = self._jobs.pop(job_id, None)
                self._job_views.pop(job_id, None)
            cancelled = job is not None and job.cancelled
            self._notify_shell()
            if success:
                final = completion.on_success(filepath, meta)
                size = os.path.getsize(final) if final and os.path.exists(final) else None
                completion.notify_native("İndirme tamamlandı", os.path.basename(final) if final else meta.title)
                completion.beep()
                completion.fetch_lyrics(final, meta)
                self._emit({'type': 'done', 'job': job_id, 'ok': True, 'file': final, 'size': size,
                            'note': _relative_note(size, datetime.datetime.now().isoformat())})
            else:
                if not cancelled:
                    completion.on_failure(error, meta)
                self._emit({'type': 'done', 'job': job_id, 'ok': False, 'cancelled': cancelled, 'error': error})
            self._maybe_shutdown()

        trim = req.get('trim')
        if 'open.spotify.com' in url:
            job = SpotifyJob(url, output_dir, progress, complete, semaphore=self._semaphore)
        else:
            request = DownloadRequest(
                url=url, output_dir=output_dir, format_id=req.get('format') or 'best', is_audio=is_audio,
                save_metadata=bool(req.get('saveMeta')), write_sub=bool(req.get('subs')),
                normalize_audio=bool(req.get('normalize')), sponsorblock=bool(req.get('sponsorblock')),
                start_time=f"{trim[0]:.1f}" if trim else None, end_time=f"{trim[1]:.1f}" if trim else None,
                is_live=bool(req.get('isLive')),
                ratelimit=f"{cfg.get('speed_limit')}M" if int(cfg.get('speed_limit', 0) or 0) > 0 else None,
                proxy=(cfg.get('proxy') or '').strip() or None,
                custom_ffmpeg_args=(cfg.get('custom_ffmpeg_args') or '').strip() or None,
                filename_template=(cfg.get('filename_template') or '').strip() or '%(title)s.%(ext)s',
            )
            job = DownloadJob(self._downloader, request, progress, complete, semaphore=self._semaphore)
        added = {'type': 'added', 'job': job_id, 'origin': origin, 'url': url, 'title': meta.title or url,
                 'thumbnail': meta.thumbnail_url}
        with self._lock:
            self._jobs[job_id] = job
            self._job_views[job_id] = {'added': added, 'last': None}
        self._emit(added)
        self._notify_shell()
        try:
            get_download_history().save_queue_item(url=url, title=meta.title, output_path=output_dir,
                                                   format_id=req.get('format') or 'best',
                                                   type_str=meta.type_str, thumbnail_url=meta.thumbnail_url)
        except Exception as e:
            print(f"[Web] Kalıcı kuyruğa yazılamadı ({url}): {e}")
        threading.Thread(target=job.run, name=f'download-{job_id}', daemon=True).start()
        return job_id

    def _maybe_shutdown(self):
        """Ayar açıksa ve son indirme bittiyse bilgisayarı kapatmayı planlar (iptal için süre tanır)."""
        if self._has_active_jobs() or not cfg.get('auto_shutdown', False):
            return
        self._emit({'type': 'notice', 'tone': 'info',
                    'text': f'Tüm indirmeler bitti. Bilgisayar {AUTO_SHUTDOWN_DELAY_S} saniye içinde kapanacak.'})
        self._shutdown_timer = threading.Timer(AUTO_SHUTDOWN_DELAY_S, lambda: subprocess.run(['shutdown', '/s', '/t', '0']))
        self._shutdown_timer.daemon = True
        self._shutdown_timer.start()

    def cancel_shutdown(self) -> bool:
        if self._shutdown_timer is None:
            return False
        self._shutdown_timer.cancel()
        self._shutdown_timer = None
        return True

    # ── Arka plan servisleri ──
    def _start_services(self):
        """Pencere açıldıktan sonra bir kez: yarım kalan kuyruk, zamanlayıcı, abonelik kontrolü."""
        if self._services_started:
            return
        self._services_started = True
        threading.Thread(target=self._restore_queue, name='restore-queue', daemon=True).start()
        threading.Thread(target=self._scheduler_loop, name='scheduler', daemon=True).start()
        threading.Thread(target=self._subscription_loop, name='subscriptions', daemon=True).start()

    def _restore_queue(self):
        db = get_download_history()
        pending = db.get_saved_queue()
        if not pending:
            return
        db.clear_queue_state()
        for item in pending:
            self._start_job({'url': item.get('url', ''), 'outputDir': item.get('output_path') or '',
                             'type': item.get('type_str', 'video'), 'format': item.get('format_id', 'best'),
                             'title': item.get('title', ''), 'thumbnail': item.get('thumbnail_url', '')}, origin='restore')
        self._emit({'type': 'notice', 'tone': 'info', 'text': f'{len(pending)} yarım kalan indirme sürdürülüyor.'})

    def _scheduler_loop(self):
        import time as _time
        while True:
            try:
                now = datetime.datetime.now()
                db = get_download_history()
                for task in automation.due_tasks(db.get_scheduled_tasks(), now, self._fired):
                    self._fired.add(automation.firing_key(task, now))
                    db.update_scheduled_task_run(task['id'])
                    if automation.is_one_shot(task):
                        db.set_scheduled_task_active(task['id'], False)
                    self._start_job({'url': task['url'], 'outputDir': task.get('output_path') or '',
                                     'type': task.get('type_str', 'video'), 'format': task.get('format_id') or 'best',
                                     'title': task.get('name', '')}, origin='schedule')
                    self._emit({'type': 'notice', 'tone': 'info', 'text': f"Zamanlanmış indirme başladı: {task.get('name') or task['url']}"})
            except Exception as e:
                print(f"[Zamanlayıcı] Kontrol başarısız: {e}")
            _time.sleep(SCHEDULER_TICK_S)

    def _subscription_loop(self):
        import time as _time
        from src.core.subscription_manager import check_channel_new_videos
        while True:
            _time.sleep(max(1, int(cfg.get('sub_check_hours', 6) or 6)) * 3600)
            try:
                db = get_download_history()
                subs = db.get_subscriptions(active_only=True)
                known = db.get_all_downloaded_urls() if subs else set()
                for sub in subs:
                    new = check_channel_new_videos(sub['url'], known_urls=known)
                    db.update_subscription_checked(sub['id'], len(new))
                    for vid in new:
                        self._start_job({'url': vid['url'], 'outputDir': sub.get('output_path') or '',
                                         'type': sub.get('format_type', 'video'), 'format': 'best',
                                         'title': vid.get('title', '')}, origin='subscription')
                    if new:
                        self._emit({'type': 'notice', 'tone': 'info',
                                    'text': f"{sub.get('name') or sub['url']}: {len(new)} yeni video indiriliyor."})
            except Exception as e:
                print(f"[Abonelik] Kontrol başarısız: {e}")

    def cancel(self, job_id: int) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return False
        job.cancel()
        return True

    def _notify_shell(self):
        if self._shell is None:
            return
        with self._lock:
            active = len(self._jobs)
        self._shell.jobs_changed(active)

    def _cancel_all(self):
        with self._lock:
            jobs = list(self._jobs.values())
        for job in jobs:
            job.cancel()

    def active_jobs(self) -> list[dict]:
        """Süren işler: eklendiği andaki bilgi ve son ilerleme olayı (mini pencere açılışı için)."""
        with self._lock:
            return [dict(v) for v in self._job_views.values()]

    # ── Kabuk: ana pencere, mini pencere, çıkış ──
    def show_main(self, page: Optional[str] = None) -> bool:
        self._shell.show_main(page)
        return True

    def toggle_mini(self) -> bool:
        self._shell.toggle_mini()
        return True

    def hide_mini(self) -> bool:
        self._shell.hide_mini()
        return True

    def fit_mini(self, height: int) -> bool:
        self._shell.fit_mini(int(height))
        return True

    def quit_app(self) -> bool:
        self._shell.request_quit()
        return True

    # ── Uygulama güncellemesi ──
    def check_update(self) -> Optional[dict]:
        from src.utils.updater import check_for_updates, get_current_version
        info = check_for_updates()
        if info is None or not info.is_newer:
            return None
        self._update_info = info
        return {'current': get_current_version(), 'version': info.version,
                'notes': release_summary(info.release_notes or '')}

    def install_update(self) -> bool:
        """Yeni sürümü indirir; 'update' olaylarıyla ilerleme bildirir. Başarılıysa uygulama kapanır, yükleyici açar."""
        from src.utils.updater import download_and_install_update
        if self._update_info is None:
            raise RuntimeError('Önce güncelleme denetlenmeli (check_update).')

        def progress(pct: int):
            self._emit({'type': 'update', 'percent': max(0, min(100, int(pct)))})

        if not download_and_install_update(self._update_info, progress_callback=progress):
            raise RuntimeError('Güncelleme indirilemedi ya da kurulamadı. Sürüm sayfası tarayıcıda açıldıysa oradan indir.')
        self._shell.quit_now()
        return True

    # ── Geçmiş ──
    def recent(self) -> list[dict]:
        rows = get_download_history().get_all_downloads(limit=RECENT_SCAN_ROWS)
        items = []
        seen = set()
        for r in rows:
            url, title = r.get('url'), r.get('title')
            if not url or not title or url in seen or r.get('status') not in ('completed', 'error'):
                continue
            seen.add(url)
            failed = r.get('status') == 'error'
            items.append({
                'key': f"db-{r.get('id')}", 'url': url, 'title': title, 'failed': failed,
                'note': (r.get('error_message') or 'Hata')[:60] if failed
                else _relative_note(r.get('file_size'), r.get('download_date')),
                'file': r.get('file_path'), 'thumbnail': r.get('thumbnail_url'),
            })
            if len(items) >= RECENT_LIMIT:
                break
        return items

    def history(self) -> dict:
        db = get_download_history()
        rows = db.get_all_downloads(limit=HISTORY_ROWS)
        return {
            'rows': [self._history_row(r) for r in history_tools.collapse_duplicates(rows)],
            'stats': db.get_statistics(),
            'platforms': db.get_platform_breakdown(),
        }

    @staticmethod
    def _history_row(r: dict) -> dict:
        path = r.get('file_path') or ''
        title = r.get('title') or (os.path.splitext(os.path.basename(path))[0] if path else '') or r.get('url') or ''
        return {
            'id': r.get('id'), 'url': r.get('url') or '', 'title': title, 'channel': r.get('channel') or '',
            'date': str(r.get('download_date') or ''), 'size': r.get('file_size'), 'duration': r.get('duration'),
            'type': r.get('format_type') or '', 'status': r.get('status') or '', 'error': r.get('error_message') or '',
            'file': path, 'exists': bool(path) and os.path.exists(path), 'thumbnail': r.get('thumbnail_url') or '',
        }

    def delete_history(self, row_id: int) -> bool:
        """Satırı ve (eski sürümün attığı) aynı bağlantı + dosya + durumdaki eşini siler."""
        db = get_download_history()
        row = db.get_download_by_id(int(row_id))
        if row is None:
            return False
        twins = [r for r in db.get_all_downloads(limit=HISTORY_ROWS)
                 if r.get('url') == row.get('url') and r.get('file_path') == row.get('file_path')
                 and r.get('status') == row.get('status') and row.get('file_path')]
        for r in twins or [row]:
            db.delete_download(r['id'])
        return True

    def clear_history(self) -> bool:
        get_download_history().clear_history()
        return True

    def missing_files(self) -> list[str]:
        return history_tools.missing_files(get_download_history().get_all_downloads(limit=HISTORY_ROWS))

    def export_history(self, kind: str) -> Optional[str]:
        """Geçmişi CSV ya da JSON olarak kaydeder; kullanıcı iptal ederse None."""
        import webview
        if kind not in ('csv', 'json'):
            raise ValueError(f"export_history: 'csv' ya da 'json' bekleniyordu, gelen: {kind!r}")
        result = self._window.create_file_dialog(
            webview.FileDialog.SAVE, directory=os.path.expanduser('~'),
            save_filename=f'indirme_gecmisi.{kind}',
            file_types=(f"{kind.upper()} dosyası (*.{kind})",),
        )
        if not result:
            return None
        path = result if isinstance(result, str) else result[0]
        rows = get_download_history().get_all_downloads(limit=HISTORY_ROWS)
        (history_tools.export_csv if kind == 'csv' else history_tools.export_json)(rows, path)
        return path

    def retry_request(self, row_id: int) -> dict:
        row = get_download_history().get_download_by_id(int(row_id))
        if row is None:
            raise LookupError(f"Geçmişte {row_id} numaralı kayıt yok; liste yenilenmeli.")
        return history_tools.retry_request(row, cfg.get('download_dir') or get_os_download_dir())

    # ── Kütüphane ──
    def library(self) -> dict:
        return {'files': media_library.scan(), 'dirs': media_library.library_dirs()}

    def library_thumbnail(self, path: str) -> Optional[str]:
        thumb = media_library.thumbnail(path)
        if not thumb:
            return None
        with open(thumb, 'rb') as f:
            return f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode('ascii')}"

    def delete_file(self, path: str) -> bool:
        media_library.delete_file(path)
        return True

    def read_tags(self, path: str) -> dict:
        return media_library.read_tags(path)

    def write_tags(self, path: str, values: dict) -> bool:
        media_library.write_tags(path, values)
        return True

    def convert(self, path: str, fmt: str) -> str:
        return media_library.convert(path, fmt)

    def transcribe(self, path: str, model: str, language: Optional[str]) -> dict:
        """Uzun sürer (dakikalar); ara durumlar 'transcribe' olayıyla akar."""
        def progress(line: str):
            self._emit({'type': 'transcribe', 'path': path, 'line': line})
        text, out = media_library.transcribe(path, model, language or None, progress)
        return {'text': text, 'file': out}

    def pick_media_file(self) -> Optional[str]:
        import webview
        exts = ';'.join(f'*{e}' for e in sorted(media_library.MEDIA_EXTS))
        result = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=(f"Medya dosyaları ({exts})",))
        return result[0] if result else None

    # ── Ayarlar ──
    def settings(self) -> dict:
        import sys as _sys
        from src.core.ytdlp_base import installed_version
        from src.utils.updater import get_current_version
        return {
            'values': settings_schema.read_all(),
            'appVersion': get_current_version(),
            'ytdlpVersion': installed_version(),
            'frozen': bool(getattr(_sys, 'frozen', False)),
        }

    def set_setting(self, key: str, value) -> bool:
        settings_schema.write(key, value)
        if key == 'max_concurrent':
            self._semaphore.set_limit(value)
        return True

    def ytdlp_latest(self) -> Optional[str]:
        from src.core.ytdlp_base import latest_version
        return latest_version()

    def update_ytdlp(self) -> str:
        import sys as _sys
        if getattr(_sys, 'frozen', False):
            raise RuntimeError('EXE sürümünde yt-dlp uygulamayla birlikte gelir; uygulamayı güncelle.')
        result = subprocess.run([_sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'],
                                capture_output=True, text=True, timeout=YTDLP_UPDATE_TIMEOUT_S,
                                creationflags=subprocess.CREATE_NO_WINDOW if _sys.platform == 'win32' else 0)
        if result.returncode != 0:
            raise RuntimeError(f"pip yt-dlp'yi güncelleyemedi: {(result.stderr or result.stdout)[-300:]}")
        return 'yt-dlp güncellendi. Etkili olması için uygulamayı yeniden başlat.'

    def test_proxy(self, proxy: str) -> str:
        proxy = (proxy or '').strip()
        if not proxy:
            raise ValueError('Proxy adresi boş.')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
        with opener.open(PROXY_TEST_URL, timeout=PROXY_TEST_TIMEOUT_S) as resp:
            return f"Bağlantı çalışıyor. Görünen adres: {json.loads(resp.read().decode())['origin']}"

    def subscriptions(self) -> list[dict]:
        return [{'id': s['id'], 'url': s['url'], 'name': s.get('name') or s['url'], 'type': s.get('format_type', 'video'),
                 'lastChecked': str(s.get('last_checked') or ''), 'active': bool(s.get('active', 1))}
                for s in get_download_history().get_subscriptions(active_only=False)]

    def add_subscription(self, url: str, type_str: str) -> bool:
        url = (url or '').strip()
        if not is_valid_url(url):
            raise ValueError('Geçerli bir kanal ya da oynatma listesi bağlantısı gir.')
        if type_str not in ('video', 'audio'):
            raise ValueError(f"Tür 'video' ya da 'audio' olmalı: {type_str!r}")
        db = get_download_history()
        db.add_subscription(url, name=url[:60], format_type=type_str,
                            output_path=cfg.get('download_dir') or get_os_download_dir())

        def resolve_name():
            from src.core.subscription_manager import get_channel_name
            name = get_channel_name(url)
            if name:
                db.rename_subscription(url, name)
                self._emit({'type': 'subscriptions-changed'})
        threading.Thread(target=resolve_name, daemon=True).start()
        return True

    def delete_subscription(self, sub_id: int) -> bool:
        get_download_history().delete_subscription(int(sub_id))
        return True

    def schedules(self) -> list[dict]:
        return [{'id': t['id'], 'name': t.get('name') or t['url'], 'url': t['url'], 'when': t.get('schedule_time', ''),
                 'daily': bool(t.get('repeat_daily')), 'type': t.get('type_str', 'video'), 'lastRun': str(t.get('last_run') or '')}
                for t in get_download_history().get_scheduled_tasks()]

    def add_schedule(self, req: dict) -> bool:
        url = (req.get('url') or '').strip()
        if not is_valid_url(url):
            raise ValueError('Geçerli bir bağlantı gir.')
        automation.parse_schedule(req.get('when', ''))  # geçersizse açıklayıcı hata
        get_download_history().add_scheduled_task(
            name=(req.get('name') or '').strip() or url[:40], url=url, schedule_time=req['when'].strip(),
            output_path=req.get('outputDir') or '', format_id=req.get('format') or 'best',
            type_str=req.get('type') or 'video', repeat_daily=bool(req.get('daily')))
        return True

    def delete_schedule(self, task_id: int) -> bool:
        get_download_history().delete_scheduled_task(int(task_id))
        return True

    def rules(self) -> list[dict]:
        from src.core.auto_categorize import load_rules
        return load_rules()

    def add_rule(self, rule: dict) -> bool:
        import re as _re
        from src.core.auto_categorize import add_rule
        name, pattern = (rule.get('name') or '').strip(), (rule.get('pattern') or '').strip()
        if not name or not pattern:
            raise ValueError('Kural adı ve desen zorunlu.')
        if rule.get('match_field') not in ('title', 'url', 'channel'):
            raise ValueError("Alan 'title', 'url' ya da 'channel' olmalı.")
        try:
            _re.compile(pattern, _re.IGNORECASE)
        except _re.error as e:
            raise ValueError(f"Desen geçerli bir düzenli ifade değil: {e}") from None
        add_rule({'name': name, 'match_field': rule['match_field'], 'pattern': pattern,
                  'output_subdir': (rule.get('output_subdir') or '').strip(), 'type_override': rule.get('type_override') or ''})
        return True

    def delete_rule(self, name: str) -> bool:
        from src.core.auto_categorize import delete_rule
        delete_rule(name)
        return True

    def reset_rules(self) -> bool:
        from src.core.auto_categorize import reset_to_defaults
        reset_to_defaults()
        return True

    def open_plugins_folder(self) -> bool:
        from src.core.plugin_manager import get_plugins_dir
        os.startfile(get_plugins_dir())
        return True

    def reload_plugins(self) -> int:
        from src.core.plugin_manager import load_plugins
        return len(load_plugins())

    def open_url(self, url: str) -> bool:
        import webbrowser
        if not url.startswith(('https://', 'http://')):
            raise ValueError(f'Yalnızca web bağlantıları açılır: {url!r}')
        return webbrowser.open(url)

    # ── Sistem ──
    def reveal(self, path: str) -> bool:
        """Dosyayı Gezgin'de seçili açar; dosya yoksa klasörünü."""
        if path and os.path.isfile(path):
            subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
            return True
        folder = path if path and os.path.isdir(path) else os.path.dirname(path or '')
        if folder and os.path.isdir(folder):
            os.startfile(folder)
            return True
        return False

    def open_file(self, path: str) -> bool:
        if not path or not os.path.isfile(path):
            return False
        os.startfile(path)
        return True

    def pick_folder(self, current: str) -> Optional[str]:
        import webview
        result = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=current or '')
        return result[0] if result else None
