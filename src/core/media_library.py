#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kütüphane: indirilen dosyaları tarama, kapak önizlemesi, etiket okuma/yazma,
format dönüştürme ve Whisper transkripti. Arayüzden bağımsız.
"""
import hashlib
import os
import platform
import subprocess
import threading
from typing import Callable, Optional

from src.utils import config as cfg
from src.utils.helpers import extract_video_thumbnail, get_data_dir, get_ffmpeg_path, get_os_download_dir

VIDEO_EXTS = {'.mp4', '.webm', '.mkv', '.avi', '.mov'}
AUDIO_EXTS = {'.mp3', '.m4a', '.flac', '.ogg', '.opus', '.wav', '.aac'}
MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS
CONVERT_FORMATS = ('mp3', 'mp4', 'mkv', 'webm', 'wav', 'aac')
TAG_FIELDS = ('title', 'artist', 'album', 'year', 'comment')
WHISPER_MODELS = ('tiny', 'base', 'small', 'medium', 'large')
# ffmpeg dönüştürme hata çıktısının kullanıcıya gösterilen son kısmı.
FFMPEG_ERROR_TAIL = 300


def library_dirs() -> list[str]:
    """İndirme klasörü + Ayarlar'daki ek kütüphane klasörleri (var olanlar, sırayla, tekrarsız)."""
    dirs = [cfg.get('download_dir', '') or get_os_download_dir()]
    for line in (cfg.get('library_folders', '') or '').splitlines():
        line = line.strip()
        if line and line not in dirs:
            dirs.append(line)
    return [d for d in dirs if os.path.isdir(d)]


# Alt klasör derinliği: kategori kuralının klasörü (İndirilenler\Müzik) ve otomatik düzenlemenin
# platform klasörü (…\Müzik\Youtube) üst üste gelebilir. Eskiden hiç inilmiyordu; düzenlenen
# dosyalar kütüphanede görünmüyordu. Daha derine inmek İndirilenler'deki ilgisiz ağaçları tarar.
MAX_SCAN_DEPTH = 2


def _scan_dir(root: str, folder: str, depth: int, seen: set, files: list):
    try:
        entries = list(os.scandir(folder))
    except OSError as e:
        print(f"[Kütüphane] Klasör okunamadı, atlandı ({folder}): {e}")
        return
    for entry in entries:
        # Gizli/sistem klasörleri ($RECYCLE.BIN, .git) ve bağlantılar (döngü) atlanır.
        if entry.name.startswith(('.', '$')) or entry.is_symlink():
            continue
        if entry.is_dir(follow_symlinks=False):
            if depth < MAX_SCAN_DEPTH:
                _scan_dir(root, entry.path, depth + 1, seen, files)
            continue
        ext = os.path.splitext(entry.name)[1].lower()
        key = os.path.normcase(entry.path)
        if ext not in MEDIA_EXTS or key in seen or not entry.is_file(follow_symlinks=False):
            continue
        seen.add(key)
        st = entry.stat()
        files.append({
            'path': entry.path, 'name': entry.name, 'ext': ext.lstrip('.'),
            'kind': 'audio' if ext in AUDIO_EXTS else 'video',
            'size': st.st_size, 'mtime': st.st_mtime,
            # Kütüphane klasörüne göre alt klasör ('' = doğrudan içinde); aramada ve kartta kullanılır.
            'folder': os.path.relpath(folder, root) if folder != root else '',
        })


def scan() -> list[dict]:
    """Kütüphane klasörlerindeki medya dosyaları, MAX_SCAN_DEPTH alt klasöre kadar."""
    files: list = []
    seen: set = set()
    for folder in library_dirs():
        _scan_dir(folder, folder, 0, seen, files)
    return files


def _thumb_cache_path(media_path: str) -> str:
    # Eski arayüzün önbellek düzeni: aynı dosyanın kapağı yeniden üretilmez.
    cache_dir = os.path.join(get_data_dir(), 'thumbnails')
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, hashlib.md5(media_path.encode('utf-8')).hexdigest() + '.jpg')


def _extract_audio_cover(audio_path: str, out_jpg: str) -> bool:
    ext = os.path.splitext(audio_path)[1].lower()
    data = None
    if ext == '.mp3':
        from mutagen.id3 import ID3
        tags = ID3(audio_path)
        data = next((tags[k].data for k in tags if k.startswith('APIC')), None)
    elif ext in ('.m4a', '.mp4', '.aac'):
        from mutagen.mp4 import MP4
        covr = (MP4(audio_path).tags or {}).get('covr')
        data = bytes(covr[0]) if covr else None
    elif ext == '.flac':
        from mutagen.flac import FLAC
        pics = FLAC(audio_path).pictures
        data = pics[0].data if pics else None
    if not data:
        return False
    with open(out_jpg, 'wb') as f:
        f.write(data)
    return True


def thumbnail(media_path: str) -> Optional[str]:
    """Önbellekteki (gerekirse üretilen) kapak dosyasının yolu; üretilemezse None."""
    if not os.path.isfile(media_path):
        return None
    out = _thumb_cache_path(media_path)
    if os.path.exists(out):
        return out
    ext = os.path.splitext(media_path)[1].lower()
    try:
        ok = _extract_audio_cover(media_path, out) if ext in AUDIO_EXTS else extract_video_thumbnail(media_path, out)
    except Exception as e:
        print(f"[Kütüphane] Kapak çıkarılamadı ({os.path.basename(media_path)}): {e}")
        return None
    return out if ok and os.path.exists(out) else None


# Kütüphane kartı 16:9, en geniş ~240 CSS px; 2x ekranda keskin kalacak boyut. Tam kapak (640 px kare
# ses kapağı ya da video karesi) karta ~100 KB taşıyordu, bu boyutta ~15-25 KB.
CARD_THUMB_SIZE = (480, 270)
CARD_THUMB_QUALITY = 82
# Kapağı olmayan dosyanın işareti: yüzlerce kapaksız MP3'te her açılışta etiket okunmasın.
NO_CARD_THUMB_MARK = '.yok'


def _card_thumb_base(media_path: str) -> str:
    # Anahtara boyut ve değişme zamanı da girer: dosya değişince (kapak eklenince) eski sonuç kullanılmaz.
    st = os.stat(media_path)
    key = f'{media_path}|{st.st_size}|{st.st_mtime_ns}'
    cache_dir = os.path.join(get_data_dir(), 'thumbnails', 'card')
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, hashlib.md5(key.encode('utf-8')).hexdigest())


# card_thumbnail(render=False) dönüşü: kapak henüz üretilmedi (üretmek ffmpeg/etiket okuma ister).
NOT_RENDERED = object()


def card_thumbnail(media_path: str, render: bool = True):
    """Kart boyutunda (CARD_THUMB_SIZE, ortadan kırpılmış) JPEG kapağın yolu; kapak yoksa None.
    render=False: yalnız önbelleğe bakar, üretilmemişse NOT_RENDERED döner."""
    from PIL import Image, ImageOps
    if not os.path.isfile(media_path):
        return None
    base = _card_thumb_base(media_path)
    out, missing = base + '.jpg', base + NO_CARD_THUMB_MARK
    if os.path.exists(out):
        return out
    if os.path.exists(missing):
        return None
    if not render:
        return NOT_RENDERED
    full = thumbnail(media_path)
    if not full:
        open(missing, 'wb').close()
        return None
    try:
        with Image.open(full) as im:
            card = ImageOps.fit(im.convert('RGB'), CARD_THUMB_SIZE, Image.Resampling.LANCZOS)
    except OSError as e:
        # Bozuk gömülü kapak: kartta simge kalır, her açılışta yeniden denenmez.
        print(f"[Kütüphane] Kapak okunamadı ({os.path.basename(media_path)}): {e}")
        open(missing, 'wb').close()
        return None
    # Aynı kart iki istekte aynı anda üretilebilir; geçici adlar çakışmasın.
    tmp = f'{out}.{os.getpid()}.{threading.get_ident()}.tmp'
    card.save(tmp, 'JPEG', quality=CARD_THUMB_QUALITY, optimize=True, progressive=True)
    os.replace(tmp, out)
    return out


def delete_file(path: str):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Silinecek dosya yok: {path}")
    os.remove(path)


# ── Etiketler ──

def read_tags(path: str) -> dict:
    ext = os.path.splitext(path)[1].lower()
    tags = {k: '' for k in TAG_FIELDS}
    if ext == '.mp3':
        from mutagen.id3 import ID3, ID3NoHeaderError
        try:
            t = ID3(path)
        except ID3NoHeaderError:
            return tags
        tags.update(title=str(t.get('TIT2', '')), artist=str(t.get('TPE1', '')), album=str(t.get('TALB', '')),
                    year=str(t.get('TDRC', '')), comment=str(t.get('COMM::eng', '')))
    elif ext in ('.mp4', '.m4a'):
        from mutagen.mp4 import MP4
        t = MP4(path).tags or {}
        first = lambda k: str((t.get(k) or [''])[0])
        tags.update(title=first('\xa9nam'), artist=first('\xa9ART'), album=first('\xa9alb'),
                    year=first('\xa9day'), comment=first('\xa9cmt'))
    else:
        raise ValueError(f"Etiket düzenleme yalnızca MP3, MP4 ve M4A için: {os.path.basename(path)}")
    return tags


def write_tags(path: str, values: dict):
    ext = os.path.splitext(path)[1].lower()
    v = {k: str(values.get(k, '') or '') for k in TAG_FIELDS}
    if ext == '.mp3':
        from mutagen.id3 import COMM, ID3, ID3NoHeaderError, TALB, TDRC, TIT2, TPE1
        try:
            t = ID3(path)
        except ID3NoHeaderError:
            t = ID3()
        t['TIT2'] = TIT2(encoding=3, text=v['title'])
        t['TPE1'] = TPE1(encoding=3, text=v['artist'])
        t['TALB'] = TALB(encoding=3, text=v['album'])
        t['TDRC'] = TDRC(encoding=3, text=v['year'])
        t['COMM::eng'] = COMM(encoding=3, lang='eng', desc='', text=v['comment'])
        t.save(path)
    elif ext in ('.mp4', '.m4a'):
        from mutagen.mp4 import MP4
        audio = MP4(path)
        if audio.tags is None:
            audio.add_tags()
        for key, field in (('\xa9nam', 'title'), ('\xa9ART', 'artist'), ('\xa9alb', 'album'),
                           ('\xa9day', 'year'), ('\xa9cmt', 'comment')):
            audio.tags[key] = [v[field]]
        audio.save()
    else:
        raise ValueError(f"Etiket düzenleme yalnızca MP3, MP4 ve M4A için: {os.path.basename(path)}")


# ── Dönüştürme ──

def _ffmpeg() -> str:
    folder = get_ffmpeg_path()
    exe = 'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg'
    return os.path.join(folder, exe) if folder else exe


def convert(path: str, fmt: str) -> str:
    """Dosyayı fmt'ye çevirir; çıktı '<ad>_converted.<fmt>'. Başarısızsa ffmpeg hatasıyla RuntimeError."""
    fmt = fmt.lower().strip('.')
    if fmt not in CONVERT_FORMATS:
        raise ValueError(f"Desteklenmeyen format: {fmt}. Geçerli: {', '.join(CONVERT_FORMATS)}")
    out = f"{os.path.splitext(path)[0]}_converted.{fmt}"
    cmd = [_ffmpeg(), '-y', '-i', path]
    if fmt == 'mp3':
        cmd += ['-vn', '-q:a', '0', '-map', 'a']
    elif fmt == 'mp4':
        cmd += ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k']
    elif fmt == 'webm':
        cmd += ['-c:v', 'libvpx-vp9', '-crf', '30', '-b:v', '0', '-c:a', 'libopus']
    elif fmt == 'mkv':
        cmd += ['-c:v', 'copy', '-c:a', 'copy']
    elif fmt in ('wav', 'aac'):
        cmd += ['-vn']
    cmd.append(out)
    flags = subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
    result = subprocess.run(cmd, capture_output=True, creationflags=flags)
    if result.returncode != 0:
        tail = result.stderr.decode('utf-8', errors='replace')[-FFMPEG_ERROR_TAIL:]
        raise RuntimeError(f"ffmpeg {os.path.basename(path)} dosyasını {fmt} yapamadı: {tail}")
    return out


# ── Transkript ──

def transcribe(path: str, model: str, language: Optional[str], on_progress: Callable[[str], None]) -> tuple[str, str]:
    """Whisper ile metne çevirir, dosyanın yanına .txt yazar. (metin, txt yolu) döndürür."""
    if model not in WHISPER_MODELS:
        raise ValueError(f"Bilinmeyen Whisper modeli: {model}")
    try:
        import whisper  # type: ignore
    except ImportError as e:
        raise RuntimeError("openai-whisper kurulu değil. Kur: pip install openai-whisper") from e
    on_progress(f"'{model}' modeli yükleniyor. İlk kullanımda indirilir, biraz sürebilir.")
    loaded = whisper.load_model(model)
    on_progress(f"Metne çevriliyor: {os.path.basename(path)}")
    text = (loaded.transcribe(path, language=language, verbose=False).get('text') or '').strip()
    out = os.path.splitext(path)[0] + '.txt'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(text)
    on_progress(f"Kaydedildi: {out}")
    return text, out
