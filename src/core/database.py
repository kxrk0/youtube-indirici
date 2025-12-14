#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
İndirme Geçmişi Veritabanı
SQLite ile indirme kaydı tutma
"""

import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager


class DownloadHistory:
    """
    İndirme geçmişi yönetimi
    
    Özellikler:
    - İndirme kaydı tutma
    - Arama ve filtreleme
    - İstatistik hesaplama
    """
    
    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: Veritabanı dosya yolu (varsayılan: cache/history.db)
        """
        if db_path is None:
            # Varsayılan konum
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cache_dir = os.path.join(root_dir, 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            db_path = os.path.join(cache_dir, 'history.db')
            
        self.db_path = db_path
        self._init_db()
        
    @contextmanager
    def _get_connection(self):
        """Thread-safe veritabanı bağlantısı"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
            
    def _init_db(self):
        """Veritabanı tablolarını oluştur"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # İndirme geçmişi tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    channel TEXT,
                    duration INTEGER,
                    format_type TEXT,
                    format_quality TEXT,
                    file_path TEXT,
                    file_size INTEGER,
                    thumbnail_url TEXT,
                    status TEXT DEFAULT 'completed',
                    error_message TEXT,
                    download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # İndeks oluştur
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_download_date ON downloads(download_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON downloads(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON downloads(url)')
            
    def add_download(self, 
                     url: str, 
                     title: str = None,
                     channel: str = None,
                     duration: int = None,
                     format_type: str = None,
                     format_quality: str = None,
                     file_path: str = None,
                     file_size: int = None,
                     thumbnail_url: str = None,
                     status: str = 'completed',
                     error_message: str = None) -> int:
        """
        Yeni indirme kaydı ekle
        
        Returns:
            int: Eklenen kaydın ID'si
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO downloads (
                    url, title, channel, duration, format_type, format_quality,
                    file_path, file_size, thumbnail_url, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (url, title, channel, duration, format_type, format_quality,
                  file_path, file_size, thumbnail_url, status, error_message))
            return cursor.lastrowid
            
    def get_all_downloads(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Tüm indirmeleri getir (en yeniden en eskiye)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM downloads 
                ORDER BY download_date DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
            
    def search_downloads(self, query: str, limit: int = 50) -> List[Dict]:
        """Başlık veya kanal adında arama yap"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            search_term = f'%{query}%'
            cursor.execute('''
                SELECT * FROM downloads 
                WHERE title LIKE ? OR channel LIKE ? OR url LIKE ?
                ORDER BY download_date DESC 
                LIMIT ?
            ''', (search_term, search_term, search_term, limit))
            return [dict(row) for row in cursor.fetchall()]
            
    def get_download_by_id(self, download_id: int) -> Optional[Dict]:
        """ID ile indirme kaydı getir"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM downloads WHERE id = ?', (download_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
            
    def get_downloads_by_status(self, status: str, limit: int = 50) -> List[Dict]:
        """Duruma göre indirmeleri getir"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM downloads 
                WHERE status = ?
                ORDER BY download_date DESC 
                LIMIT ?
            ''', (status, limit))
            return [dict(row) for row in cursor.fetchall()]
            
    def update_download_status(self, download_id: int, status: str, error_message: str = None):
        """İndirme durumunu güncelle"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE downloads 
                SET status = ?, error_message = ?
                WHERE id = ?
            ''', (status, error_message, download_id))
            
    def delete_download(self, download_id: int):
        """İndirme kaydını sil"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM downloads WHERE id = ?', (download_id,))
            
    def clear_history(self):
        """Tüm geçmişi temizle"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM downloads')
            
    def get_statistics(self) -> Dict:
        """İndirme istatistiklerini getir"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Toplam indirme sayısı
            cursor.execute('SELECT COUNT(*) FROM downloads')
            total_downloads = cursor.fetchone()[0]
            
            # Başarılı indirmeler
            cursor.execute("SELECT COUNT(*) FROM downloads WHERE status = 'completed'")
            successful = cursor.fetchone()[0]
            
            # Başarısız indirmeler
            cursor.execute("SELECT COUNT(*) FROM downloads WHERE status = 'error'")
            failed = cursor.fetchone()[0]
            
            # Toplam dosya boyutu
            cursor.execute('SELECT SUM(file_size) FROM downloads WHERE file_size IS NOT NULL')
            total_size = cursor.fetchone()[0] or 0
            
            # Toplam süre
            cursor.execute('SELECT SUM(duration) FROM downloads WHERE duration IS NOT NULL')
            total_duration = cursor.fetchone()[0] or 0
            
            # Bu ay indirilenler
            cursor.execute('''
                SELECT COUNT(*) FROM downloads 
                WHERE download_date >= date('now', 'start of month')
            ''')
            this_month = cursor.fetchone()[0]
            
            # Bugün indirilenler
            cursor.execute('''
                SELECT COUNT(*) FROM downloads 
                WHERE date(download_date) = date('now')
            ''')
            today = cursor.fetchone()[0]
            
            return {
                'total_downloads': total_downloads,
                'successful': successful,
                'failed': failed,
                'total_size_bytes': total_size,
                'total_duration_seconds': total_duration,
                'this_month': this_month,
                'today': today
            }
            
    def is_url_downloaded(self, url: str) -> bool:
        """URL daha önce indirilmiş mi?"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM downloads 
                WHERE url = ? AND status = 'completed'
            ''', (url,))
            return cursor.fetchone()[0] > 0
            
    def get_recent_channels(self, limit: int = 10) -> List[str]:
        """En son indirilen kanalları getir"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT channel FROM downloads 
                WHERE channel IS NOT NULL AND channel != ''
                ORDER BY download_date DESC 
                LIMIT ?
            ''', (limit,))
            return [row[0] for row in cursor.fetchall()]


# Global instance
_history_instance = None

def get_download_history() -> DownloadHistory:
    """Global DownloadHistory instance'ını döndür"""
    global _history_instance
    if _history_instance is None:
        _history_instance = DownloadHistory()
    return _history_instance
