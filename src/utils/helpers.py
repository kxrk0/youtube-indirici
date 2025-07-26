#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import platform
import subprocess
from typing import Optional, Tuple

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

def check_ffmpeg() -> bool:
    """FFmpeg'in sistemde kurulu olup olmadığını kontrol eder"""
    try:
        subprocess.run(
            ['ffmpeg', '-version'], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            check=True
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def get_clipboard_text() -> Optional[str]:
    """Panodan metni alır"""
    try:
        import pyperclip
        return pyperclip.paste()
    except ImportError:
        return None 