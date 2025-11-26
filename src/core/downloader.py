#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import threading
from typing import Dict, List, Optional, Tuple, Callable

import yt_dlp
from src.utils.helpers import get_os_download_dir, get_ffmpeg_path

class Downloader:
    """YouTube video indirmek için kullanılan sınıf"""
    
    def __init__(self):
        self.ydl_opts: Dict = {}
        self.current_task = None
        self.is_downloading = False
        
    def get_video_info(self, url: str) -> Optional[Dict]:
        """Video hakkında bilgi alır"""
        try:
            print(f"Video bilgisi alınıyor: {url}")
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': False}) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    print(f"Video başlığı: {info.get('title')}")
                    print(f"Video formatları: {len(info.get('formats', []))}")
                else:
                    print("Video bilgisi alınamadı: Veri boş")
                return info
        except Exception as e:
            print(f"Video bilgisi alınamadı: {str(e)}")
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
                      save_info: bool = False) -> None:
        """Video indirir"""
        def _download():
            self.is_downloading = True
            
            # En yüksek kaliteli indirme için format_id düzenle
            format_spec = format_id
            if format_id == 'best':
                format_spec = 'bestvideo+bestaudio/best'
                
            print(f"İndirme için format: {format_spec}")
            
            # Format seçimini kontrol et
            if '+' in format_spec and not format_spec.startswith('bestvideo'):
                print(f"Özel format kombinasyonu tespit edildi: {format_spec}")
            
            ydl_opts = {
                'format': format_spec,
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'ffmpeg_location': get_ffmpeg_path(),
                'writethumbnail': True,
                'concurrent_fragment_downloads': 8,
                'http_chunk_size': 10485760,
                'writeinfojson': save_info,  # Meta verileri kaydetme seçeneği
                'merge_output_format': 'mp4',  # Çıktı formatını MP4 olarak ayarla
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }, {
                    # Thumbnail'i video içine göm ve dosyayı sil
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                }, {
                    # Kaynak dosyaları temizle (WebM gibi)
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                }],
                'keepvideo': False,  # Dönüştürmeden sonra kaynak video dosyalarını silme
                'verbose': False,  # Detaylı çıktı istiyorsanız True yapın
                'quiet': True,
                'no_warnings': False,  # Uyarıları göster
                'ignoreerrors': False,  # Hataları yakala
            }
            
            # İlerleme izleme için callback ekle
            if progress_callback:
                ydl_opts['progress_hooks'] = [progress_callback]
                
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                    
                if complete_callback:
                    complete_callback(True)
            except Exception as e:
                print(f"İndirme hatası: {str(e)}")
                if complete_callback:
                    complete_callback(False, str(e))
            finally:
                self.is_downloading = False
                
        # İndirmeyi ayrı bir thread'de başlat
        self.current_task = threading.Thread(target=_download)
        self.current_task.daemon = True
        self.current_task.start()
    
    def download_audio(self, 
                      url: str, 
                      output_path: str, 
                      audio_quality: str = '0',  # En yüksek kalite
                      progress_callback: Optional[Callable] = None,
                      complete_callback: Optional[Callable] = None,
                      save_info: bool = False) -> None:
        """Sadece ses indirir (MP3 formatında)"""
        def _download_audio():
            self.is_downloading = True
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'ffmpeg_location': get_ffmpeg_path(),
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
            
            # İlerleme izleme için callback ekle
            if progress_callback:
                ydl_opts['progress_hooks'] = [progress_callback]
                
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                    
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
        
    def cancel_download(self):
        """Mevcut indirmeyi iptal eder"""
        if self.is_downloading and self.current_task:
            # yt-dlp doğrudan iptal edilemez, bu yüzden thread'i durduramıyoruz
            # Ancak gelecek sürümlerde iptal desteği ekleyebiliriz
            pass
            
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