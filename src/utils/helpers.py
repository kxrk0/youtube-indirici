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

# Cached monitor info
_cached_refresh_rate: Optional[float] = None

def get_monitor_refresh_rate() -> float:
    """
    Monitörün refresh rate'ini algılar ve cache'ler.
    180Hz, 144Hz, 120Hz, 60Hz vb. monitörleri destekler.
    
    Returns:
        float: Refresh rate (Hz cinsinden), varsayılan 60.0
    """
    global _cached_refresh_rate
    
    if _cached_refresh_rate is not None:
        return _cached_refresh_rate
    
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                rate = screen.refreshRate()
                if rate > 0:
                    _cached_refresh_rate = rate
                    return rate
    except Exception:
        pass
    
    _cached_refresh_rate = 60.0
    return _cached_refresh_rate

def get_optimal_timer_interval() -> int:
    """
    Monitör refresh rate'ine göre optimal timer interval hesaplar.
    
    Returns:
        int: Millisaniye cinsinden interval (min 1ms)
    """
    rate = get_monitor_refresh_rate()
    return max(1, int(1000 / rate))

def get_animation_speed_factor() -> float:
    """
    Animasyon hızı için normalize edilmiş faktör.
    60Hz baz alınarak hesaplanır.
    
    Returns:
        float: 60Hz için 1.0, 180Hz için ~0.33
    """
    rate = get_monitor_refresh_rate()
    return 60.0 / rate

def is_valid_url(url: str) -> bool:
    """URL'nin YouTube url'si olup olmadığını kontrol eder"""
    youtube_regex = r'^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$'
    return bool(re.match(youtube_regex, url))

def format_size(bytes_size: int) -> str:
    """Byte cinsinden dosya boyutunu okunaklı hale getirir"""
    if bytes_size < 0:
        return "Bilinmiyor"
    
    size_units = ['B', 'KB', 'MB', 'GB', 'TB']
    index = 0
    size = float(bytes_size)
    
    while size >= 1024 and index < len(size_units) - 1:
        size /= 1024
        index += 1
        
    return f"{size:.2f} {size_units[index]}"

def format_duration(seconds: int) -> str:
    """Saniye cinsinden süreyi okunaklı hale getirir"""
    if seconds < 0:
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

def setup_ffmpeg_path():
    """Yerel FFmpeg dizinini sistem PATH değişkenine ekler"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(current_dir))
    
    ffmpeg_bin_dir = os.path.join(root_dir, 'ffmpeg-8.0.1-essentials_build', 'bin')
    
    if os.path.exists(ffmpeg_bin_dir):
        # Mevcut PATH'e ekle (en başa)
        os.environ["PATH"] = ffmpeg_bin_dir + os.pathsep + os.environ["PATH"]
        print(f"FFmpeg PATH'e eklendi: {ffmpeg_bin_dir}")
        return True
    return False

def get_ffmpeg_path() -> Optional[str]:
    """Yerel FFmpeg dizinini döndürür (varsa)"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(current_dir))
    
    # ffmpeg-8.0.1-essentials_build/bin
    local_ffmpeg_dir = os.path.join(root_dir, 'ffmpeg-8.0.1-essentials_build', 'bin')
    local_ffmpeg_exe = os.path.join(local_ffmpeg_dir, 'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg')
    
    if os.path.exists(local_ffmpeg_exe):
        return local_ffmpeg_dir # yt-dlp dizin yolu ister
        
    return None

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
    """Videodan küçük resim oluşturur"""
    ffmpeg_dir = get_ffmpeg_path()
    
    # Eğer yerel FFmpeg varsa tam yolunu oluştur, yoksa sistemdekini ('ffmpeg') kullan
    if ffmpeg_dir:
        ffmpeg_cmd = os.path.join(ffmpeg_dir, 'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg')
    else:
        ffmpeg_cmd = 'ffmpeg'
        
    try:
        # Videonun 5. saniyesinden bir kare al
        cmd = [
            ffmpeg_cmd,
            '-y', # Varsa üzerine yaz
            '-ss', '00:00:05', # 5. saniye
            '-i', video_path,
            '-vframes', '1', # Tek kare
            '-vf', 'scale=320:-1', # Genişlik 320px, yükseklik orantılı
            '-q:v', '2', # Kalite
            output_path
        ]
        
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0,
            check=True # Hata varsa exception fırlat
        )
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Thumbnail hatası ({ffmpeg_cmd}): {e}")
        return False

def get_clipboard_text() -> Optional[str]:
    """Panodan metni alır"""
    try:
        import pyperclip
        return pyperclip.paste()
    except ImportError:
        return None 