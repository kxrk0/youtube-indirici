#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import platform
import subprocess
from typing import Optional, Tuple

# Mutagen
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TYER
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

def get_app_dir() -> str:
    """EXE veya script dizinini döndürür (config/db için)"""
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Kurulu EXE'nin verisi %LOCALAPPDATA%\<bu ad>: Program Files'a yazılamıyor.
DATA_DIR_NAME = 'YouTubeIndirici'
# 2.6.2–2.6.3 kurucusunun kullanıcı klasörü (%LOCALAPPDATA%\Programs\YouTubeIndirici); verisi cache\ altındaydı.
LEGACY_INSTALL_SUBDIR = os.path.join('Programs', 'YouTubeIndirici')


def _local_appdata() -> str:
    return os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), 'AppData', 'Local')


def get_data_dir() -> str:
    """Ayar, geçmiş ve kapakların yazıldığı klasör. EXE: %LOCALAPPDATA%\\YouTubeIndirici;
    kaynak koddan çalışırken proje kökündeki cache\\."""
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.join(_local_appdata(), DATA_DIR_NAME)
    return os.path.join(get_app_dir(), 'cache')


def get_plugins_dir() -> str:
    """Kullanıcı eklentileri. EXE: veri klasöründe; kaynak koddan çalışırken proje kökündeki plugins\\."""
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.join(get_data_dir(), 'plugins')
    return os.path.join(get_app_dir(), 'plugins')


def migrate_legacy_data() -> Optional[str]:
    """2.6.x ve öncesi veriyi EXE'nin yanında (cache\\, plugins\\) tutuyordu. Yeni veri klasörü
    henüz yoksa ilk bulunan eski konumdan kopyalar; eskisi yedek olarak kalır.
    Kopyalanan kaynağı, kopyalama olmadıysa None döner."""
    import shutil
    import sys
    if not getattr(sys, 'frozen', False):
        return None
    data_dir = get_data_dir()
    if os.path.isdir(data_dir):
        return None
    for root in (get_app_dir(), os.path.join(_local_appdata(), LEGACY_INSTALL_SUBDIR)):
        legacy_cache = os.path.join(root, 'cache')
        if not os.path.isdir(legacy_cache):
            continue
        # Yarım kalan kopya veri klasörü sayılıp bir daha denenmesin diye önce yanına kopyalanır.
        staging = data_dir + '.tasiniyor'
        shutil.rmtree(staging, ignore_errors=True)
        try:
            shutil.copytree(legacy_cache, staging)
            legacy_plugins = os.path.join(root, 'plugins')
            if os.path.isdir(legacy_plugins):
                shutil.copytree(legacy_plugins, os.path.join(staging, 'plugins'))
            os.rename(staging, data_dir)
        except OSError as e:
            shutil.rmtree(staging, ignore_errors=True)
            raise RuntimeError(f"Eski veriler {legacy_cache} konumundan {data_dir} konumuna taşınamadı: {e}. "
                               f"Klasörü elle kopyalayıp uygulamayı yeniden aç.") from e
        return root
    return None


def get_resource_dir() -> str:
    """Paketlenmiş kaynakların (locales, icons) dizinini döndürür"""
    import sys
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return get_app_dir()


def is_valid_url(url: str) -> bool:
    """Desteklenen tüm platformların URL'lerini kabul eder"""
    if not url or not url.strip():
        return False
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        return False
    supported = (
        r'(youtube\.com|youtu\.be|music\.youtube\.com)',
        r'soundcloud\.com',
        r'open\.spotify\.com',   # accepted for UI display, DRM-blocked at download time
        r'bandcamp\.com',
        r'tiktok\.com',
        r'instagram\.com',
        r'(twitter\.com|x\.com)',
        r'vimeo\.com',
        r'dailymotion\.com',
        r'twitch\.tv',
        r'(reddit\.com|redd\.it)',
    )
    return any(re.search(p, url) for p in supported)


def detect_platform(url: str) -> str:
    """URL'den platform adını döndür"""
    if not url:
        return 'unknown'
    if 'music.youtube.com' in url:
        return 'youtube_music'
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube_shorts' if '/shorts/' in url else 'youtube'
    if 'soundcloud.com' in url:
        return 'soundcloud'
    if 'spotify.com' in url:
        return 'spotify'
    if 'bandcamp.com' in url:
        return 'bandcamp'
    if 'tiktok.com' in url:
        return 'tiktok'
    if 'instagram.com' in url:
        return 'instagram'
    if 'twitter.com' in url or 'x.com' in url:
        return 'twitter'
    if 'vimeo.com' in url:
        return 'vimeo'
    if 'dailymotion.com' in url:
        return 'dailymotion'
    if 'twitch.tv' in url:
        return 'twitch'
    if 'reddit.com' in url or 'redd.it' in url:
        return 'reddit'
    return 'unknown'

def format_size(bytes_size) -> str:
    """Byte cinsinden dosya boyutunu okunaklı hale getirir"""
    if bytes_size is None or bytes_size < 0:
        return "Bilinmiyor"
    
    size_units = ['B', 'KB', 'MB', 'GB', 'TB']
    index = 0
    size = float(bytes_size)
    
    while size >= 1024 and index < len(size_units) - 1:
        size /= 1024
        index += 1
        
    return f"{size:.2f} {size_units[index]}"

def format_duration(seconds) -> str:
    """Saniye cinsinden süreyi okunaklı hale getirir"""
    if seconds is None or seconds < 0:
        return "Bilinmiyor"
    
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f"{int(hours)}:{int(minutes):02d}:{int(seconds):02d}"
    else:
        return f"{int(minutes):02d}:{int(seconds):02d}"

def get_os_download_dir() -> str:
    """İşletim sistemine özgü indirme klasörünü döndürür"""
    system = platform.system()
    
    if system == 'Windows':
        return os.path.join(os.path.expanduser('~'), 'Downloads')
    elif system == 'Darwin':  # macOS
        return os.path.join(os.path.expanduser('~'), 'Downloads')
    elif system == 'Linux':
        return os.path.join(os.path.expanduser('~'), 'Downloads')
    else:
        return os.getcwd()  # Varsayılan olarak mevcut dizin

def _find_ffmpeg_bin_dir() -> Optional[str]:
    """FFmpeg bin dizinini bulur. EXE ve kaynak modda çalışır."""
    import glob, sys
    exe_name = 'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg'

    root_dirs = []
    if getattr(sys, 'frozen', False):
        # EXE modu: _MEIPASS (datas → ffmpeg-bin) ve EXE'nin yanı
        if hasattr(sys, '_MEIPASS'):
            root_dirs.append(sys._MEIPASS)
        root_dirs.append(os.path.dirname(sys.executable))
    else:
        # Kaynak modu: proje kökü
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dirs.append(os.path.dirname(os.path.dirname(current_dir)))

    for root_dir in root_dirs:
        candidates = [
            os.path.join(root_dir, 'ffmpeg-bin'),
            os.path.join(root_dir, 'ffmpeg', 'bin'),
        ] + glob.glob(os.path.join(root_dir, 'ffmpeg*', 'bin'))
        for candidate in candidates:
            if os.path.exists(os.path.join(candidate, exe_name)):
                return candidate

    return None


def setup_ffmpeg_path():
    """Yerel FFmpeg dizinini sistem PATH değişkenine ekler"""
    ffmpeg_bin_dir = _find_ffmpeg_bin_dir()
    if ffmpeg_bin_dir:
        os.environ["PATH"] = ffmpeg_bin_dir + os.pathsep + os.environ["PATH"]
        print(f"FFmpeg PATH'e eklendi: {ffmpeg_bin_dir}")
        return True
    return False


def get_ffmpeg_path() -> Optional[str]:
    """Yerel FFmpeg bin dizinini döndürür (yt-dlp dizin yolu ister)"""
    return _find_ffmpeg_bin_dir()

def embed_metadata(file_path: str, info: dict):
    """MP3 dosyasına meta verileri ve kapak fotoğrafını gömer"""
    if not HAS_MUTAGEN or not file_path.lower().endswith('.mp3'):
        return
        
    try:
        audio = MP3(file_path, ID3=ID3)
        
        try:
            audio.add_tags()
        except:
            pass
            
        if info.get('title'):
            audio.tags.add(TIT2(encoding=3, text=info['title']))
            
        artist = info.get('artist') or info.get('uploader')
        if artist:
            audio.tags.add(TPE1(encoding=3, text=artist))
            
        album = info.get('album')
        if album:
            audio.tags.add(TALB(encoding=3, text=album))
            
        date = info.get('upload_date')
        if date and len(date) >= 4:
            audio.tags.add(TYER(encoding=3, text=date[:4]))
            
        base_name = os.path.splitext(file_path)[0]
        thumb_exts = ['.jpg', '.jpeg', '.png', '.webp']
        thumb_path = None
        
        for ext in thumb_exts:
            if os.path.exists(base_name + ext):
                thumb_path = base_name + ext
                break
                
        if thumb_path:
            with open(thumb_path, 'rb') as albumart:
                audio.tags.add(APIC(
                    encoding=3,
                    mime=f'image/{thumb_path.split(".")[-1].replace("jpg", "jpeg")}',
                    type=3, 
                    desc=u'Cover',
                    data=albumart.read()
                ))
                
        audio.save()
        print(f"Metadata gömüldü: {file_path}")
        
    except Exception as e:
        print(f"Metadata hatası: {e}")

def check_ffmpeg() -> bool:
    """FFmpeg'in sistemde kurulu olup olmadığını kontrol eder"""
    return get_ffmpeg_path() is not None

def extract_video_thumbnail(video_path: str, output_path: str) -> bool:
    """Videodan küçük resim oluşturur. Ses-only dosyalar için False döner."""
    ffmpeg_dir = get_ffmpeg_path()
    if ffmpeg_dir:
        ffmpeg_cmd = os.path.join(ffmpeg_dir, 'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg')
    else:
        ffmpeg_cmd = 'ffmpeg'

    flags = subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
    base_args = [ffmpeg_cmd, '-y', '-i', video_path, '-vframes', '1', '-vf', 'scale=320:-1', '-q:v', '2']

    # 5. saniyeden dene, başarısız olursa ilk kareyi al
    attempts = [
        base_args[:2] + ['-ss', '00:00:05'] + base_args[2:] + [output_path],
        base_args + [output_path],
    ]

    for cmd in attempts:
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=flags,
                timeout=20,
            )
            if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True
        except Exception:
            pass

    return False

def get_clipboard_text() -> Optional[str]:
    """Panodan metni alır"""
    try:
        import pyperclip
        return pyperclip.paste()
    except ImportError:
        return None 