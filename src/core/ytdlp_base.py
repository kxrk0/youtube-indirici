#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yt-dlp ortak katmanı.

Projede yt-dlp 8 ayrı yerde elle kuruluyordu; hiçbirinde JS runtime
tanımlı değildi ve 403 gibi kurtarılabilir hatalar için strateji yoktu.
Tüm çağrılar artık buradaki taban seçeneklerle kurulur.

Sağladıkları:
- JS runtime tespiti — YouTube nsig/challenge çözümü için gerekli.
  Runtime yokken çıkarma "deprecated" sayılıyor ve bazı formatlar düşüyor
  (ölçüm: aynı video, runtime'sız 44 format, node ile 48).
- 403 gibi hatalarda deneme başına kurtarma stratejisi (cache temizliği,
  ardından InnerTube istemci rotasyonu).
- Türkçe, aksiyon içeren hata mesajları.
- yt-dlp sürüm denetimi — bayat sürüm YouTube tarafında 403'ün ana sebebi.
"""

import os
import sys
import json
import shutil
import threading
import time
from typing import Dict, List, Optional, Tuple

# yt_dlp paketini import etmek supported_js_runtimes kaydını dolduruyor;
# yt_dlp.YoutubeDL alt modülünü tek başına import etmek yeterli değil.
import yt_dlp
from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor, FFmpegPostProcessorError
from yt_dlp.utils import prepend_extension


class ProcessCancelled(Exception):
    """Kullanıcı dönüştürmeyi iptal etti — hata değil, akış kesintisi."""


def _remove_quietly(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

# Tercih sırası: deno yt-dlp'nin varsayılanı ve en iyi test edileni.
_RUNTIME_CANDIDATES = ('deno', 'node', 'bun', 'quickjs')

# Windows'ta PATH'e girmemiş yaygın kurulum konumları.
_EXTRA_RUNTIME_PATHS: Dict[str, Tuple[str, ...]] = {
    'node': (
        r'C:\Program Files\nodejs\node.exe',
        r'C:\Program Files (x86)\nodejs\node.exe',
    ),
    'deno': (
        os.path.join(os.path.expanduser('~'), '.deno', 'bin', 'deno.exe'),
    ),
    'bun': (
        os.path.join(os.path.expanduser('~'), '.bun', 'bin', 'bun.exe'),
    ),
}

# 403 kalıcı olduğunda denenecek InnerTube istemcileri.
# Adlar yt_dlp.extractor.youtube._base.INNERTUBE_CLIENTS ile doğrulandı.
_FALLBACK_PLAYER_CLIENTS = ['tv', 'web_safari', 'visionos']

_PYPI_URL = 'https://pypi.org/pypi/yt-dlp/json'
_VERSION_CACHE_TTL = 24 * 60 * 60  # PyPI'yi günde bir kez yokla

_runtime_cache: Optional[Dict[str, Dict[str, Optional[str]]]] = None
_runtime_lock = threading.Lock()


def _resolve_runtime(name: str) -> Optional[str]:
    """Runtime çalıştırılabilirinin yolunu döndürür; bulunamazsa None."""
    found = shutil.which(name)
    if found:
        return found
    for candidate in _EXTRA_RUNTIME_PATHS.get(name, ()):
        if os.path.isfile(candidate):
            return candidate
    return None


def detect_js_runtimes() -> Dict[str, Dict[str, Optional[str]]]:
    """
    Sistemde bulunan JS runtime'ları yt-dlp'nin beklediği biçimde döndürür:
    {'node': {'path': 'C:\\...\\node.exe'}}. Hiçbiri yoksa boş dict.

    Sonuç süreç ömrü boyunca cache'lenir — her indirmede PATH taramak gereksiz.
    """
    global _runtime_cache
    if _runtime_cache is not None:
        return _runtime_cache
    with _runtime_lock:
        if _runtime_cache is not None:
            return _runtime_cache
        found: Dict[str, Dict[str, Optional[str]]] = {}
        for name in _RUNTIME_CANDIDATES:
            path = _resolve_runtime(name)
            if path:
                found[name] = {'path': path}
        _runtime_cache = found
        return found


def has_js_runtime() -> bool:
    return bool(detect_js_runtimes())


def base_opts(**extra) -> Dict:
    """
    Her yt-dlp çağrısının başlangıç noktası.

    extra ile verilen anahtarlar tabanı ezer; çağıran taraf istediğini
    değiştirebilir ama JS runtime'ı unutamaz.
    """
    opts: Dict = {
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 30,
    }
    runtimes = detect_js_runtimes()
    if runtimes:
        opts['js_runtimes'] = runtimes
    opts.update(extra)
    return opts


def recovery_opts(attempt: int) -> Dict:
    """
    Retry denemesi başına ek seçenekler.

    attempt 0 : olduğu gibi dene.
    attempt 1 : cache purge yeterli olabilir (çağıran purge_player_cache
                çağırır), seçenek değişmez.
    attempt 2+: YouTube varsayılan istemcisi 403 veriyor — istemci rotasyonu.
    """
    if attempt < 2:
        return {}
    return {
        'extractor_args': {
            'youtube': {'player_client': list(_FALLBACK_PLAYER_CLIENTS)},
        },
    }


def purge_player_cache() -> bool:
    """
    yt-dlp'nin önbelleğe aldığı player JS / nsig fonksiyonlarını siler.
    Bayat imza fonksiyonu 403'ün sık sebeplerinden biri.
    """
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            ydl.cache.remove()
        return True
    except Exception:
        return False


def is_recoverable_error(message: str) -> bool:
    """403 / geçici ağ hataları gibi tekrar denemenin anlamlı olduğu durumlar."""
    low = (message or '').lower()
    return any(sign in low for sign in (
        '403', 'forbidden', 'timed out', 'timeout', 'connection reset',
        'unable to download video data', 'fragment', 'temporary failure',
        'remote end closed',
    ))


def explain_error(message: str) -> str:
    """Ham yt-dlp hatasını kullanıcının ne yapacağını bilebileceği metne çevirir."""
    raw = message or ''
    low = raw.lower()

    if '403' in low or 'forbidden' in low:
        detail = ('YouTube isteği reddetti (403). Genelde yt-dlp sürümü '
                  'eskidiği için olur.')
        stale = version_hint()
        if stale:
            detail += f' {stale}'
        if not has_js_runtime():
            detail += (' Ayrıca sistemde JavaScript runtime yok; Node.js veya '
                       'Deno kurmak çözüm ihtimalini artırır.')
        return detail

    if 'not a bot' in low or 'sign in to confirm' in low:
        return ('YouTube bot doğrulaması istiyor. Ayarlar\'dan tarayıcı '
                'çerezlerini kullanmayı deneyin veya farklı bir ağdan bağlanın.')

    if 'private video' in low:
        return 'Video özel (private) — indirilemez.'

    if 'age' in low and ('restrict' in low or 'confirm' in low):
        return 'Yaş sınırlı video. Giriş yapılmış tarayıcı çerezi gerekiyor.'

    if 'not available in your country' in low or 'geo' in low and 'block' in low:
        return 'Video ülkenizde engelli. Ayarlar\'dan proxy tanımlayın.'

    if 'video unavailable' in low or 'removed' in low:
        return 'Video kaldırılmış veya erişime kapalı.'

    if 'requested format is not available' in low:
        return ('Seçilen format bu videoda yok. Farklı bir kalite seçin '
                've format listesini yenileyin.')

    if 'ffmpeg' in low:
        return 'FFmpeg bulunamadı veya çalışmadı. Kurulumu kontrol edin.'

    if 'timed out' in low or 'timeout' in low:
        return 'Bağlantı zaman aşımına uğradı. İnternet bağlantınızı kontrol edin.'

    return raw


# --------------------------------------------------------------------------
# Düzenleme uyumluluğu (H.264)
# --------------------------------------------------------------------------

# After Effects / Premiere bu codec'leri sorunsuz açar. AV1 ve VP9 açılır ama
# görüntü siyah kalır — konteyner mp4 olsa bile.
EDIT_SAFE_VCODECS = ('avc1', 'avc3', 'h264')

# Sadece H.264 video + AAC ses seçen selector. Dönüştürme yok, ama YouTube
# avc1'i genelde 1080p'de kesiyor; üstü sadece VP9/AV1 olarak veriliyor.
EDIT_FORMAT_SPEC = 'bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best'

# Denenme sırası: donanım encoder'ları çok daha hızlı, kalite farkı düzenleme
# kaynağı için kabul edilebilir. libx264 her zaman son çare olarak çalışır.
_LIBX264: Tuple[str, List[str]] = ('libx264', ['-preset', 'medium', '-crf', '18'])
# 4K üstünde CPU tek seçenek; ölçüm (7680x3150, 25 fps): medium 6.2 fps,
# faster 10 fps. crf sabit kaldığı için kalite farkı düzenleme kaynağında
# görünmez, süre 10 dakikadan 6.5'e iner.
_LIBX264_BEYOND_HW: Tuple[str, List[str]] = ('libx264', ['-preset', 'faster', '-crf', '18'])
_HW_H264_ENCODERS: Tuple[Tuple[str, List[str]], ...] = (
    ('h264_nvenc', ['-preset', 'p5', '-rc', 'vbr', '-cq', '19', '-b:v', '0']),
    ('h264_qsv',   ['-preset', 'medium', '-global_quality', '20']),
    ('h264_amf',   ['-quality', 'quality', '-rc', 'cqp', '-qp_i', '20', '-qp_p', '22']),
)
_H264_ENCODERS: Tuple[Tuple[str, List[str]], ...] = (*_HW_H264_ENCODERS, _LIBX264)

# NVENC / QSV / AMF H.264 encoder'ları 4096x4096 üstünü açmıyor ("No capable
# devices found"). 8K kaynak sadece libx264 ile çevrilebilir.
HW_H264_MAX_DIM = 4096

_hw_encoder_cache: Optional[List[Tuple[str, List[str]]]] = None
_encoder_lock = threading.Lock()


def _ffmpeg_exe() -> str:
    """Paketlenmiş ffmpeg varsa onu, yoksa PATH'tekini kullan."""
    try:
        from src.utils.helpers import get_ffmpeg_path
        bin_dir = get_ffmpeg_path()
        if bin_dir:
            candidate = os.path.join(bin_dir, 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
            if os.path.isfile(candidate):
                return candidate
    except Exception:
        pass
    return shutil.which('ffmpeg') or 'ffmpeg'


def _encoder_works(name: str, extra: List[str]) -> bool:
    """
    Encoder'ı 2 karelik sentetik kaynakla gerçekten çalıştırır.

    `ffmpeg -encoders` listesi derleme desteğini gösterir, çalışma zamanını
    değil: NVENC'siz makinede h264_nvenc listede görünür ama açılışta patlar.
    """
    import subprocess
    cmd = [
        _ffmpeg_exe(), '-hide_banner', '-v', 'error',
        '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=25', '-t', '0.1',
        '-c:v', name, *extra, '-f', 'null', '-',
    ]
    try:
        kwargs = {'capture_output': True, 'timeout': 30}
        if os.name == 'nt':
            kwargs['creationflags'] = 0x08000000  # CREATE_NO_WINDOW
        return subprocess.run(cmd, **kwargs).returncode == 0
    except Exception:
        return False


def _working_hw_encoders() -> List[Tuple[str, List[str]]]:
    """Bu makinede probe'u geçen donanım encoder'ları; süreç ömrü boyunca cache."""
    global _hw_encoder_cache
    if _hw_encoder_cache is not None:
        return _hw_encoder_cache
    with _encoder_lock:
        if _hw_encoder_cache is None:
            _hw_encoder_cache = [
                (name, extra) for name, extra in _HW_H264_ENCODERS
                if _encoder_works(name, extra)
            ]
        return _hw_encoder_cache


def encoder_chain(width: int, height: int) -> List[Tuple[str, List[str]]]:
    """
    Kaynak çözünürlüğüne göre denenecek encoder sırası. Son eleman her zaman
    libx264; öncekiler bu makinede çalışan ve çözünürlüğü kaldıran donanım
    encoder'ları.
    """
    if max(width or 0, height or 0) > HW_H264_MAX_DIM:
        return [_LIBX264_BEYOND_HW]
    return [*_working_hw_encoders(), _LIBX264]


def pick_h264_encoder() -> Tuple[str, List[str]]:
    """Bu makinede gerçekten çalışan en hızlı H.264 encoder'ı (4K ve altı için)."""
    return encoder_chain(0, 0)[0]


def is_edit_safe(vcodec: str) -> bool:
    v = (vcodec or '').lower()
    return v.startswith(EDIT_SAFE_VCODECS)


class ForceH264PP(FFmpegPostProcessor):
    """
    Videoyu H.264 + AAC MP4'e çevirir; zaten H.264 ise dokunmaz.

    Neden gerekli: yt-dlp'nin FFmpegVideoConvertor'ı burada işe yaramıyor.
    Kaynak zaten .mp4 olduğu için adımı atlıyor, atlamasa bile stream copy
    yapıyor — yani AV1 mp4 konteynerine girip AV1 kalıyor. After Effects ve
    Premiere AV1 çözemediği için dosya açılıyor, ses geliyor, görüntü siyah.
    """

    def __init__(self, downloader=None, on_progress=None, should_cancel=None):
        super().__init__(downloader)
        self._on_progress = on_progress
        self._should_cancel = should_cancel

    def _duration(self, path: str, info: Dict) -> float:
        duration = info.get('duration')
        if duration:
            try:
                return float(duration)
            except (TypeError, ValueError):
                pass
        try:
            return float(self.get_metadata_object(path)['format']['duration'])
        except Exception:
            return 0.0

    def _source_vcodec(self, path: str, info: Dict) -> str:
        vcodec = (info.get('vcodec') or '').lower()
        if vcodec and vcodec != 'none':
            return vcodec
        try:
            meta = self.get_metadata_object(path)
            for stream in meta.get('streams', []):
                if stream.get('codec_type') != 'video':
                    continue
                # Gömülü kapak resmi (attached_pic) video sayılmaz.
                if stream.get('disposition', {}).get('attached_pic'):
                    continue
                return (stream.get('codec_name') or '').lower()
        except Exception:
            pass
        return ''

    def _dimensions(self, path: str, info: Dict) -> Tuple[int, int]:
        width, height = info.get('width') or 0, info.get('height') or 0
        if width and height:
            return int(width), int(height)
        try:
            meta = self.get_metadata_object(path)
            for stream in meta.get('streams', []):
                if stream.get('codec_type') != 'video':
                    continue
                if stream.get('disposition', {}).get('attached_pic'):
                    continue
                return int(stream.get('width') or 0), int(stream.get('height') or 0)
        except Exception:
            pass
        return 0, 0

    def run(self, info):
        path = info.get('filepath')
        if not path or not os.path.exists(path):
            return [], info

        vcodec = self._source_vcodec(path, info)
        if is_edit_safe(vcodec):
            self.to_screen('Video zaten H.264 — dönüştürme atlandı')
            return [], info

        width, height = self._dimensions(path, info)
        chain = encoder_chain(width, height)
        duration = self._duration(path, info)
        temp = prepend_extension(path, 'h264')

        # Probe 320x240 ile yapılıyor; gerçek kaynakta encoder yine de
        # açılmayabilir (çözünürlük tavanı, sürücü). Bir sonrakine geç,
        # libx264 son sırada olduğu için zincir boşa düşmez.
        for index, (encoder, encoder_args) in enumerate(chain):
            args = [
                # Kapak resmi akışını dışarıda bırak; yoksa bazı ffmpeg sürümleri
                # onu ikinci video akışı olarak taşıyor.
                '-map', '0:v:0', '-map', '0:a:0?',
                '-c:v', encoder, *encoder_args,
                '-profile:v', 'high', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '192k',
                '-movflags', '+faststart',
            ]
            self.to_screen(f"H.264'e dönüştürülüyor ({vcodec or 'bilinmeyen'} → avc1, {encoder})")
            try:
                self._transcode(path, temp, args, duration)
                break
            except FFmpegPostProcessorError as exc:
                _remove_quietly(temp)
                if index == len(chain) - 1:
                    raise
                self.report_warning(f'{encoder} açılamadı ({exc}); {chain[index + 1][0]} deneniyor')
            except BaseException:
                # Yarım kalan dosya diskte kalmasın; bir sonraki denemede
                # "zaten var" sanılıp bozuk çıktı teslim edilmesin.
                _remove_quietly(temp)
                raise

        os.replace(temp, path)
        return [], info

    def _transcode(self, src: str, dst: str, args: List[str], duration: float) -> None:
        """
        ffmpeg'i ilerleme bildirimiyle ve iptal edilebilir şekilde çalıştırır.

        yt-dlp'nin run_ffmpeg'i çıktıyı sonuna kadar biriktiriyor: 4K bir videoda
        bir dakikadan uzun süren dönüştürme boyunca arayüz son indirme
        satırında donmuş görünüyordu ve iptal düğmesi işlemiyordu.
        """
        import subprocess

        cmd = [
            self.executable, '-y', '-hide_banner', '-loglevel', 'error',
            '-progress', 'pipe:1', '-nostats',
            '-i', src, *args, dst,
        ]
        popen_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'stdin': subprocess.DEVNULL,
            'text': True,
        }
        if os.name == 'nt':
            popen_kwargs['creationflags'] = 0x08000000  # CREATE_NO_WINDOW

        process = subprocess.Popen(cmd, **popen_kwargs)
        try:
            for line in process.stdout:
                if self._should_cancel and self._should_cancel():
                    process.kill()
                    raise ProcessCancelled('Dönüştürme iptal edildi')

                key, _, value = line.strip().partition('=')
                if key not in ('out_time_us', 'out_time_ms') or not duration:
                    continue
                try:
                    # İki anahtar da mikrosaniye taşıyor (ffmpeg'in eski adlandırması).
                    seconds = int(value) / 1_000_000
                except ValueError:
                    continue
                percent = max(0, min(100, int(seconds / duration * 100)))
                if self._on_progress:
                    self._on_progress(percent)
        finally:
            if process.poll() is None:
                process.kill()
            stderr = process.stderr.read() if process.stderr else ''
            process.wait()

        if process.returncode != 0:
            last_line = (stderr or '').strip().splitlines()
            raise FFmpegPostProcessorError(last_line[-1] if last_line else 'ffmpeg başarısız')

        if self._on_progress:
            self._on_progress(100)


# --------------------------------------------------------------------------
# Sürüm denetimi
# --------------------------------------------------------------------------

def installed_version() -> str:
    try:
        return yt_dlp.version.__version__
    except Exception:
        return '0'


def _version_tuple(v: str) -> Tuple[int, ...]:
    parts: List[int] = []
    for chunk in (v or '').split('.'):
        digits = ''.join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts[:3])


def _cache_path() -> str:
    from src.utils.config import _get_config_dir
    return os.path.join(_get_config_dir(), 'ytdlp_version.json')


def _read_cached_latest() -> Optional[str]:
    try:
        path = _cache_path()
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if time.time() - float(data.get('checked_at', 0)) < _VERSION_CACHE_TTL:
            return data.get('latest')
    except Exception:
        pass
    return None


def _write_cached_latest(latest: str) -> None:
    try:
        path = _cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'latest': latest, 'checked_at': time.time()}, fh)
    except Exception:
        pass


def latest_version(timeout: float = 6.0, use_cache: bool = True) -> Optional[str]:
    """PyPI'deki son yt-dlp sürümü. Ağ yoksa None — çağıran taraf sessiz geçmeli."""
    if use_cache:
        cached = _read_cached_latest()
        if cached:
            return cached
    try:
        from urllib.request import urlopen, Request
        req = Request(_PYPI_URL, headers={'User-Agent': 'youtube-indirici'})
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        latest = data['info']['version']
        _write_cached_latest(latest)
        return latest
    except Exception:
        return None


def is_stale(timeout: float = 6.0) -> Optional[bool]:
    """Kurulu sürüm PyPI'dekinden eski mi? Belirlenemezse None."""
    latest = latest_version(timeout=timeout)
    if not latest:
        return None
    return _version_tuple(installed_version()) < _version_tuple(latest)


def version_hint() -> str:
    """403 mesajına eklenecek, ortama göre değişen güncelleme talimatı."""
    stale = is_stale()
    if stale is not True:
        return ''
    latest = latest_version() or '?'
    current = installed_version()
    if getattr(sys, 'frozen', False):
        return (f'Kurulu yt-dlp {current}, güncel sürüm {latest} — '
                f'uygulamanın yeni sürümünü indirin.')
    return (f'Kurulu yt-dlp {current}, güncel sürüm {latest} — '
            f'"pip install -U yt-dlp" çalıştırın.')
