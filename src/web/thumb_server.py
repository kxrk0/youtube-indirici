#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kütüphane kart kapaklarını 127.0.0.1'de HTTP ile sunar.

Neden köprü değil: kapaklar pywebview köprüsünden base64 metin olarak geliyordu (kapak başına
~110 KB). Yanıtlar arayüzün ana iş parçacığında ayrıştırıldığı için kaydırırken kare atlıyordu
(ölçüm, 318 dosyalık kütüphane: kapaklar gelirken 21 uzun görev, toplam 1,4 sn; bellekteyken 2,
0,66 sn). <img> ile yüklenen dosyayı tarayıcı ağ ve çözme iş parçacıklarında işler, önbelleğinde
de tutar.

Yalnızca register() ile kaydedilen dosyalar sunulur; adres rastgele tuzlu bir özetten oluşur,
yol içermez. Başka bir yerel süreç ya da web sayfası buradan rastgele dosya isteyemez.
"""
import hashlib
import secrets
import threading
from socketserver import ThreadingMixIn
from typing import Optional
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from src.core import media_library

THUMB_PREFIX = '/t/'
# Aynı anda en çok bu kadar kapak üretilir: video karesi için her biri bir ffmpeg süreci.
MAX_PARALLEL_RENDERS = 2
# Adres dosyanın yolu, boyutu ve değişme zamanından türüyor; içerik değişince adres de değişir,
# bu yüzden yanıt (kapak yok yanıtı dahil) süresiz önbelleğe alınabilir.
IMMUTABLE_CACHE = 'public, max-age=31536000, immutable'


class _ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):  # noqa: A002  (üst sınıfın imzası)
        pass


class ThumbServer:
    def __init__(self):
        self._salt = secrets.token_hex(16)
        self._paths: dict[str, str] = {}
        self._lock = threading.Lock()
        self._renders = threading.Semaphore(MAX_PARALLEL_RENDERS)
        self._httpd = make_server('127.0.0.1', 0, self._app, server_class=_ThreadingWSGIServer,
                                  handler_class=_QuietHandler)
        self.base_url = f'http://127.0.0.1:{self._httpd.server_port}'
        threading.Thread(target=self._httpd.serve_forever, name='thumb-server', daemon=True).start()

    def register(self, path: str, size: int, mtime: float) -> str:
        """Dosyanın kart kapağı adresi."""
        key = hashlib.sha256(f'{self._salt}|{path}|{size}|{mtime}'.encode('utf-8')).hexdigest()[:32]
        with self._lock:
            self._paths[key] = path
        return f'{self.base_url}{THUMB_PREFIX}{key}.jpg'

    def _lookup(self, url_path: str) -> Optional[str]:
        if not (url_path.startswith(THUMB_PREFIX) and url_path.endswith('.jpg')):
            return None
        with self._lock:
            return self._paths.get(url_path[len(THUMB_PREFIX):-len('.jpg')])

    def _app(self, environ, start_response):
        media = self._lookup(environ.get('PATH_INFO', ''))
        if environ.get('REQUEST_METHOD') != 'GET' or media is None:
            start_response('404 Not Found', [('Content-Length', '0')])
            return [b'']
        # Hazır kapaklar üretim sırası beklemesin; yalnız üretim sınırlı.
        thumb = media_library.card_thumbnail(media, render=False)
        if thumb is media_library.NOT_RENDERED:
            with self._renders:
                thumb = media_library.card_thumbnail(media)
        if thumb is None:
            start_response('404 Not Found', [('Content-Length', '0'), ('Cache-Control', IMMUTABLE_CACHE)])
            return [b'']
        with open(thumb, 'rb') as f:
            body = f.read()
        start_response('200 OK', [('Content-Type', 'image/jpeg'), ('Content-Length', str(len(body))),
                                  ('Cache-Control', IMMUTABLE_CACHE)])
        return [body]

    def close(self):
        self._httpd.shutdown()
        self._httpd.server_close()
