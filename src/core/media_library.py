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


def scan() -> list[dict]:
    """Kütüphane klasörlerindeki medya dosyaları (alt klasörlere inmez; eski davranış)."""
    files = []
    seen = set()
    for folder in library_dirs():
        for name in os.listdir(folder):
            ext = os.path.splitext(name)[1].lower()
            path = os.path.join(folder, name)
            if ext not in MEDIA_EXTS or path in seen or not os.path.isfile(path):
                continue
            seen.add(path)
            st = os.stat(path)
            files.append({
                'path': path, 'name': name, 'ext': ext.lstrip('.'),
                'kind': 'audio' if ext in AUDIO_EXTS else 'video',
                'size': st.st_size, 'mtime': st.st_mtime,
            })
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
