#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Downloader - İndirme motoru
Özellikler:
- İptal desteği (thread-safe)
- Retry mekanizması (ağ hataları için)
- Gelişmiş ilerleme takibi
- Fragment-based indirmelerde doğru yüzde
"""

import os
import threading
import time
from typing import Dict, List, Optional, Callable

import yt_dlp
from src.utils.helpers import get_os_download_dir, get_ffmpeg_path, embed_metadata
from src.core.database import get_download_history

# İndirme durumları
DOWNLOAD_STATUS_IDLE = "idle"
DOWNLOAD_STATUS_DOWNLOADING = "downloading"
DOWNLOAD_STATUS_PROCESSING = "processing"
DOWNLOAD_STATUS_COMPLETED = "completed"
DOWNLOAD_STATUS_CANCELLED = "cancelled"
DOWNLOAD_STATUS_ERROR = "error"

class DownloadTask:
    """Tek bir indirme görevini temsil eder"""
    def __init__(self, url: str, output_path: str, task_id: str = None):
        self.url = url
        self.output_path = output_path
        self.task_id = task_id or str(time.time())
        self.status = DOWNLOAD_STATUS_IDLE
        self.progress = 0
        self.speed = 0
        self.eta = 0
        self.filename = ""
        self.error = None
        self.cancel_flag = threading.Event()
        self.retry_count = 0
        self.max_retries = 3
        
    def cancel(self):
        """İndirmeyi iptal et"""
        self.cancel_flag.set()
        self.status = DOWNLOAD_STATUS_CANCELLED
        
    def is_cancelled(self) -> bool:
        return self.cancel_flag.is_set()


class Downloader:
    """
    YouTube video indirmek için kullanılan sınıf
    
    Özellikler:
    - Thread-safe iptal desteği
    - Otomatik retry (3 deneme)
    - Fragment-based ilerleme takibi
    - Ağ hatası yönetimi
    """
    
    def __init__(self):
        self.ydl_opts: Dict = {}
        self.current_task: Optional[DownloadTask] = None
        self.active_tasks: Dict[str, DownloadTask] = {}
        self.is_downloading = False
        
    def get_video_info(self, url: str) -> Optional[Dict]:
        """Video hakkında bilgi alır"""
        try:
            print(f"Video bilgisi alınıyor: {url}")
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': False}) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    print(f"Video başlığı: {info.get('title')}")
                    # Playlist kontrolü
                    if 'entries' in info:
                        print(f"Playlist tespit edildi: {len(info['entries'])} video")
                    else:
                        print(f"Video formatları: {len(info.get('formats', []))}")
                else:
                    print("Video bilgisi alınamadı: Veri boş")
                return info
        except Exception as e:
            print(f"Video bilgisi alınamadı: {str(e)}")
            return None

    def get_playlist_info(self, url: str) -> Optional[Dict]:
        """Playlist videolarını hızlıca listeler (flat)"""
        try:
            opts = {
                'extract_flat': True, # Video detaylarına girme, sadece listeyi al
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"Playlist hatası: {str(e)}")
            return None
    
    def get_available_formats(self, url: str) -> List[Dict]:
        """Kullanılabilir formatları listeler"""
        info = self.get_video_info(url)
        if not info:
            return []
        
        formats = []
        for f in info.get('formats', []):
            # Ses ve video formatlarını ayıklama
            format_data = {
                'format_id': f.get('format_id'),
                'ext': f.get('ext'),
                'resolution': f.get('resolution'),
                'fps': f.get('fps'),
                'vcodec': f.get('vcodec'),
                'acodec': f.get('acodec'),
                'filesize': f.get('filesize'),
                'format_note': f.get('format_note'),
                'format': f.get('format')
            }
            formats.append(format_data)
            
        return formats
    
    def download_video(self, 
                      url: str, 
                      output_path: str, 
                      format_id: str = 'best',
                      progress_callback: Optional[Callable] = None,
                      complete_callback: Optional[Callable] = None,
                      cancel_callback: Optional[Callable] = None,
                      save_info: bool = False,
                      ratelimit: Optional[str] = None,
                      write_sub: bool = False,
                      sub_langs: str = 'tr,en') -> DownloadTask:
        """
        Video indirir
        
        Args:
            url: Video URL'si
            output_path: İndirme klasörü
            format_id: Format seçimi
            progress_callback: İlerleme callback'i
            complete_callback: Tamamlanma callback'i
            cancel_callback: İptal kontrolü callback'i (True dönerse iptal)
            save_info: JSON meta veri kaydet
            ratelimit: Hız limiti
            write_sub: Altyazı indir
            sub_langs: Altyazı dilleri
            
        Returns:
            DownloadTask: İndirme görevi nesnesi (iptal için kullanılabilir)
        """
        task = DownloadTask(url, output_path)
        self.active_tasks[task.task_id] = task
        
        def _progress_hook(d):
            # İptal kontrolü
            if task.is_cancelled() or (cancel_callback and cancel_callback()):
                raise Exception("İndirme iptal edildi")
            
            if d['status'] == 'downloading':
                # Fragment-based indirmelerde doğru yüzde hesaplama
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                
                # Fragment sayısı varsa kullan
                fragment_index = d.get('fragment_index')
                fragment_count = d.get('fragment_count')
                
                if fragment_count and fragment_index:
                    # Fragment-based ilerleme
                    task.progress = int((fragment_index / fragment_count) * 100)
                elif total > 0:
                    task.progress = int((downloaded / total) * 100)
                
                task.speed = d.get('speed', 0) or 0
                task.eta = d.get('eta', 0) or 0
                task.filename = d.get('filename', '')
                task.status = DOWNLOAD_STATUS_DOWNLOADING
                
                if progress_callback:
                    progress_callback({
                        'downloaded_bytes': downloaded,
                        'total_bytes': total,
                        'speed': task.speed,
                        'eta': task.eta,
                        'filename': task.filename,
                        'status': 'downloading',
                        'progress': task.progress,
                        'fragment_index': fragment_index,
                        'fragment_count': fragment_count
                    })
                    
            elif d['status'] == 'finished':
                task.filename = d.get('filename', '')
                task.status = DOWNLOAD_STATUS_PROCESSING
                if progress_callback:
                    progress_callback({'status': 'processing', 'filename': task.filename})
        
        def _download_with_retry():
            self.is_downloading = True
            task.status = DOWNLOAD_STATUS_DOWNLOADING
            
            format_spec = format_id
            if format_id == 'best':
                format_spec = 'bestvideo+bestaudio/best'
            
            ydl_opts = {
                'format': format_spec,
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'writethumbnail': True,
                'concurrent_fragment_downloads': 8,
                'http_chunk_size': 10485760,
                'writeinfojson': save_info,
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }, {
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                }, {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                }],
                'postprocessor_args': {
                    'merger': ['-c:a', 'aac', '-b:a', '192k'],
                },
                'keepvideo': False,
                'verbose': False,
                'quiet': True,
                'no_warnings': False,
                'ignoreerrors': False,
                'socket_timeout': 30,  # Ağ timeout
                'retries': 3,  # yt-dlp internal retry
                'fragment_retries': 5,  # Fragment retry
                'progress_hooks': [_progress_hook],
            }
            
            if write_sub:
                ydl_opts['writesubtitles'] = True
                ydl_opts['subtitleslangs'] = sub_langs.split(',')
                ydl_opts['embedsubtitles'] = True
            
            if ratelimit:
                ydl_opts['ratelimit'] = ratelimit
            
            ffmpeg_path = get_ffmpeg_path()
            if ffmpeg_path:
                ydl_opts['ffmpeg_location'] = ffmpeg_path
            
            last_error = None
            
            # Retry mekanizması
            while task.retry_count < task.max_retries:
                if task.is_cancelled():
                    task.status = DOWNLOAD_STATUS_CANCELLED
                    # İptal'i geçmişe kaydet
                    self._save_to_history(url, task, 'cancelled', format_id, 'video')
                    if complete_callback:
                        complete_callback(False, "İndirme iptal edildi")
                    break
                    
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    
                    task.status = DOWNLOAD_STATUS_COMPLETED
                    # Başarılı indirmeyi geçmişe kaydet
                    self._save_to_history(url, task, 'completed', format_id, 'video')
                    if complete_callback:
                        complete_callback(True)
                    break
                    
                except Exception as e:
                    last_error = str(e)
                    
                    # İptal durumunda retry yapma
                    if "iptal" in last_error.lower() or task.is_cancelled():
                        task.status = DOWNLOAD_STATUS_CANCELLED
                        self._save_to_history(url, task, 'cancelled', format_id, 'video')
                        if complete_callback:
                            complete_callback(False, "İndirme iptal edildi")
                        break
                    
                    task.retry_count += 1
                    print(f"İndirme hatası (deneme {task.retry_count}/{task.max_retries}): {last_error}")
                    
                    if task.retry_count < task.max_retries:
                        time.sleep(2)  # Retry öncesi bekle
                    else:
                        task.status = DOWNLOAD_STATUS_ERROR
                        task.error = last_error
                        # Başarısız indirmeyi geçmişe kaydet
                        self._save_to_history(url, task, 'error', format_id, 'video', last_error)
                        if complete_callback:
                            complete_callback(False, last_error)
            
            self.is_downloading = False
            if task.task_id in self.active_tasks:
                del self.active_tasks[task.task_id]
    
    def _save_to_history(self, url: str, task, status: str, format_quality: str, 
                        format_type: str, error_message: str = None):
        """İndirmeyi geçmişe kaydet"""
        try:
            history = get_download_history()
            
            # Dosya boyutunu al
            file_size = None
            if task.filename and os.path.exists(task.filename):
                file_size = os.path.getsize(task.filename)
                
            history.add_download(
                url=url,
                title=os.path.basename(task.filename) if task.filename else None,
                format_type=format_type,
                format_quality=format_quality,
                file_path=task.filename,
                file_size=file_size,
                status=status,
                error_message=error_message
            )
        except Exception as e:
            print(f"Geçmişe kaydetme hatası: {e}")
        
        # Thread'de başlat
        thread = threading.Thread(target=_download_with_retry)
        thread.daemon = True
        thread.start()
        
        self.current_task = task
        return task
    
    def download_audio(self, 
                      url: str, 
                      output_path: str, 
                      audio_quality: str = '0',  # En yüksek kalite
                      progress_callback: Optional[Callable] = None,
                      complete_callback: Optional[Callable] = None,
                      save_info: bool = False,
                      ratelimit: Optional[str] = None) -> None:
        """Sadece ses indirir (MP3 formatında)"""
        def _download_audio():
            self.is_downloading = True
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'writethumbnail': True,
                'concurrent_fragment_downloads': 8,
                'http_chunk_size': 10485760,
                'writeinfojson': save_info,  # Meta verileri kaydetme seçeneği
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': audio_quality,
                }, {
                    'key': 'EmbedThumbnail',  # Küçük resmi MP3'e göm
                }, {
                    'key': 'FFmpegMetadata',  # Meta verileri aktar
                }],
                'keepvideo': False,  # Kaynak dosyalarını sil
                'quiet': True,
                'no_warnings': False,
                'ignoreerrors': False,
            }
            
            if ratelimit:
                ydl_opts['ratelimit'] = ratelimit
            
            # FFmpeg konumunu ekle (varsa)
            ffmpeg_path = get_ffmpeg_path()
            if ffmpeg_path:
                ydl_opts['ffmpeg_location'] = ffmpeg_path
            
            # İlerleme izleme için callback ekle
            if progress_callback:
                ydl_opts['progress_hooks'] = [progress_callback]
                
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # info çekerek dosya adını al
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    final_filename = os.path.splitext(filename)[0] + ".mp3"
                    
                    # Metadata Göm
                    embed_metadata(final_filename, info)
                    
                if complete_callback:
                    complete_callback(True)
            except Exception as e:
                print(f"Ses indirme hatası: {str(e)}")
                if complete_callback:
                    complete_callback(False, str(e))
            finally:
                self.is_downloading = False
                
        # İndirmeyi ayrı bir thread'de başlat
        self.current_task = threading.Thread(target=_download_audio)
        self.current_task.daemon = True
        self.current_task.start()
        
    def cancel_download(self, task_id: str = None) -> bool:
        """
        İndirmeyi iptal eder
        
        Args:
            task_id: Belirli bir görevi iptal et (None = mevcut görevi iptal et)
            
        Returns:
            bool: İptal başarılı mı?
        """
        if task_id:
            # Belirli bir görevi iptal et
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                task.cancel()
                print(f"İndirme iptal edildi: {task_id}")
                return True
            return False
        else:
            # Mevcut görevi iptal et
            if self.current_task and isinstance(self.current_task, DownloadTask):
                self.current_task.cancel()
                print(f"Mevcut indirme iptal edildi")
                return True
            return False
    
    def cancel_all_downloads(self):
        """Tüm aktif indirmeleri iptal eder"""
        for task_id, task in list(self.active_tasks.items()):
            task.cancel()
            print(f"İndirme iptal edildi: {task_id}")
        self.active_tasks.clear()
        
    def get_active_downloads(self) -> List[DownloadTask]:
        """Aktif indirme görevlerini döndürür"""
        return list(self.active_tasks.values())
            
    def process_extension_request(self, video_url: str, format_quality: str, format_type: str, 
                                 output_path: str = None, save_metadata: bool = False) -> Dict:
        """
        Tarayıcı eklentisinden gelen indirme isteklerini işler
        
        Args:
            video_url: İndirilecek video URL'si
            format_quality: İstenilen video kalitesi (1080p, 720p, vb.) veya 'Audio Only'
            format_type: İndirme tipi ('video' veya 'audio')
            output_path: Çıktı dosyasının kaydedileceği yol
            save_metadata: Meta verileri kaydet (JSON)
            
        Returns:
            Dict: İşlem sonucu bilgisi
        """
        if not output_path:
            output_path = get_os_download_dir()
            
        try:
            # Ses formatı ise
            if format_type == 'audio' or format_quality == 'Audio Only':
                print(f"Eklentiden ses indirme isteği: {video_url}")
                self.download_audio(
                    url=video_url,
                    output_path=output_path,
                    save_info=save_metadata
                )
                return {
                    "status": "success", 
                    "message": f"MP3 indirme başlatıldı", 
                    "type": "audio"
                }
            
            # Video formatı ise
            else:
                # Format ID'yi belirleyelim
                format_id = 'best'  # Varsayılan en iyi kalite
                
                # Eğer belirli bir çözünürlük seçildiyse
                if format_quality in ['1080p', '720p', '480p', '360p']:
                    # Basit bir dönüşüm, gerçek format_id'ler için video bilgisi alınmalı
                    resolution_map = {
                        '1080p': 'best[height<=1080]',
                        '720p': 'best[height<=720]',
                        '480p': 'best[height<=480]',
                        '360p': 'best[height<=360]'
                    }
                    format_id = resolution_map.get(format_quality, 'best')
                
                print(f"Eklentiden video indirme isteği: {video_url} ({format_quality})")
                self.download_video(
                    url=video_url,
                    output_path=output_path,
                    format_id=format_id,
                    save_info=save_metadata
                )
                return {
                    "status": "success", 
                    "message": f"{format_quality} video indirme başlatıldı", 
                    "type": "video"
                }
        
        except Exception as e:
            print(f"Eklenti indirme hatası: {str(e)}")
            return {"status": "error", "message": str(e)} 