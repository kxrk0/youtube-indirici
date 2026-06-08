#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
İndirme Geçmişi Veritabanı
SQLite ile indirme kaydı tutma
"""

import os
import sqlite3
import threading
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager

from src.utils.helpers import get_app_dir


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
            # EXE ve kaynak modda doğru kök dizini kullan (frozen EXE'de __file__ _MEIPASS'a işaret eder)
            cache_dir = os.path.join(get_app_dir(), 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            db_path = os.path.join(cache_dir, 'history.db')
            
        self.db_path = db_path
        self._local = threading.local()   # Per-thread connection cache
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Thread-local persistent connection — her thread tek conn kullanır."""
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")   # WAL: okuma yazmayla çakışmaz
            conn.execute("PRAGMA synchronous=NORMAL")  # WAL ile güvenli, fsync sayısı azalır
            conn.execute("PRAGMA cache_size=-8000")    # 8MB cache
            self._local.conn = conn
        return conn

    @contextmanager
    def _get_connection(self):
        """Thread-local connection context manager (geriye dönük uyumluluk)."""
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
            
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

            # Abonelikler tablosu (kanal/playlist otomatik takip)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    name TEXT,
                    type TEXT DEFAULT 'channel',
                    format_type TEXT DEFAULT 'video',
                    output_path TEXT,
                    check_interval_hours INTEGER DEFAULT 6,
                    last_checked TIMESTAMP,
                    last_new_count INTEGER DEFAULT 0,
                    active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Kalıcı kuyruk tablosu (uygulama kapanınca bekleyen indirmeler)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS queue_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    output_path TEXT,
                    format_id TEXT DEFAULT 'best',
                    type_str TEXT DEFAULT 'video',
                    thumbnail_url TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Platform istatistikleri view'i
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS platform_stats (
                    platform TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0,
                    total_bytes INTEGER DEFAULT 0,
                    last_download TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    output_path TEXT,
                    format_id TEXT,
                    type_str TEXT DEFAULT 'video',
                    schedule_time TEXT NOT NULL,
                    repeat_daily INTEGER DEFAULT 0,
                    last_run TIMESTAMP,
                    active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
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


    # ── Abonelikler ─────────────────────────────────────────────────────────

    def add_subscription(self, url: str, name: str = None, type_: str = 'channel',
                         format_type: str = 'video', output_path: str = None,
                         check_interval_hours: int = 6) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO subscriptions
                (url, name, type, format_type, output_path, check_interval_hours)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (url, name, type_, format_type, output_path, check_interval_hours))
            return cursor.lastrowid

    def get_subscriptions(self, active_only: bool = True) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            q = 'SELECT * FROM subscriptions'
            if active_only:
                q += ' WHERE active = 1'
            q += ' ORDER BY created_at DESC'
            cursor.execute(q)
            return [dict(row) for row in cursor.fetchall()]

    def update_subscription_checked(self, sub_id: int, new_count: int = 0):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE subscriptions SET last_checked = CURRENT_TIMESTAMP,
                last_new_count = ? WHERE id = ?
            ''', (new_count, sub_id))

    def delete_subscription(self, sub_id: int):
        with self._get_connection() as conn:
            conn.cursor().execute('DELETE FROM subscriptions WHERE id = ?', (sub_id,))

    # ── Kuyruk Durumu ────────────────────────────────────────────────────────

    def save_queue_item(self, url: str, title: str = None, output_path: str = None,
                        format_id: str = 'best', type_str: str = 'video',
                        thumbnail_url: str = None) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO queue_state (url, title, output_path, format_id, type_str, thumbnail_url)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (url, title, output_path, format_id, type_str, thumbnail_url))
            return cursor.lastrowid

    def get_saved_queue(self) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM queue_state ORDER BY added_at ASC')
            return [dict(row) for row in cursor.fetchall()]

    def clear_queue_state(self):
        with self._get_connection() as conn:
            conn.cursor().execute('DELETE FROM queue_state')

    def remove_queue_item(self, item_id: int):
        with self._get_connection() as conn:
            conn.cursor().execute('DELETE FROM queue_state WHERE id = ?', (item_id,))

    # ── Platform İstatistikleri ──────────────────────────────────────────────

    def get_platform_breakdown(self) -> List[Dict]:
        """Her platformdan kaç indirme yapıldı."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    CASE
                        WHEN url LIKE '%youtube.com%' OR url LIKE '%youtu.be%' THEN 'YouTube'
                        WHEN url LIKE '%music.youtube.com%' THEN 'YouTube Music'
                        WHEN url LIKE '%soundcloud.com%' THEN 'SoundCloud'
                        WHEN url LIKE '%spotify.com%' THEN 'Spotify'
                        WHEN url LIKE '%tiktok.com%' THEN 'TikTok'
                        WHEN url LIKE '%instagram.com%' THEN 'Instagram'
                        WHEN url LIKE '%twitter.com%' OR url LIKE '%x.com%' THEN 'Twitter/X'
                        WHEN url LIKE '%vimeo.com%' THEN 'Vimeo'
                        WHEN url LIKE '%twitch.tv%' THEN 'Twitch'
                        WHEN url LIKE '%reddit.com%' THEN 'Reddit'
                        ELSE 'Diğer'
                    END as platform,
                    COUNT(*) as count,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as ok,
                    SUM(COALESCE(file_size, 0)) as total_bytes
                FROM downloads
                GROUP BY platform
                ORDER BY count DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def get_daily_downloads(self, days: int = 30) -> List[Dict]:
        """Son N günlük günlük indirme sayısı."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT date(download_date) as day, COUNT(*) as count
                FROM downloads
                WHERE download_date >= date('now', ?)
                GROUP BY day ORDER BY day ASC
            ''', (f'-{days} days',))
            return [dict(row) for row in cursor.fetchall()]


    # ─── Scheduled Tasks ────────────────────────────────────────────────────
    def add_scheduled_task(self, name: str, url: str, schedule_time: str,
                           output_path: str = '', format_id: str = 'best',
                           type_str: str = 'video', repeat_daily: bool = False) -> int:
        with self._get_connection() as conn:
            cur = conn.execute(
                '''INSERT INTO scheduled_tasks (name, url, output_path, format_id, type_str, schedule_time, repeat_daily)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (name, url, output_path, format_id, type_str, schedule_time, int(repeat_daily))
            )
            return cur.lastrowid

    def get_scheduled_tasks(self) -> List[Dict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                'SELECT * FROM scheduled_tasks WHERE active=1 ORDER BY schedule_time'
            ).fetchall()
            return [dict(r) for r in rows]

    def update_scheduled_task_run(self, task_id: int):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE scheduled_tasks SET last_run=CURRENT_TIMESTAMP WHERE id=?",
                (task_id,)
            )

    def delete_scheduled_task(self, task_id: int):
        with self._get_connection() as conn:
            conn.execute('DELETE FROM scheduled_tasks WHERE id=?', (task_id,))

    def set_scheduled_task_active(self, task_id: int, active: bool):
        with self._get_connection() as conn:
            conn.execute('UPDATE scheduled_tasks SET active=? WHERE id=?', (int(active), task_id))


# Global instance
_history_instance = None

def get_download_history() -> DownloadHistory:
    """Global DownloadHistory instance'ını döndür"""
    global _history_instance
    if _history_instance is None:
        _history_instance = DownloadHistory()
    return _history_instance
