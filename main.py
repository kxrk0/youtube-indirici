#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import threading
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QSurfaceFormat
from src.ui.main_window import MainWindow
from flask import Flask, request, jsonify
from flask_cors import CORS
from src.core.downloader import Downloader
from src.utils.helpers import get_os_download_dir, setup_ffmpeg_path
from src.utils.config import get_api_key

# Global değişkenler
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["chrome-extension://*", "moz-extension://*"]}})
downloader = None  # Downloader örneği

# Aktif indirme takibi (extension popup için)
_active_queue: list = []          # [{'title', 'url', 'progress', 'status'}]
_active_queue_lock = threading.Lock()

_API_KEY: str = ""  # Başlatma sırasında doldurulur


def _check_api_key() -> bool:
    """İstek header'ında geçerli API anahtarı var mı?"""
    if not _API_KEY:
        return True  # Anahtar henüz ayarlanmadıysa izin ver
    return request.headers.get('X-API-Key') == _API_KEY


@app.route('/ping', methods=['GET'])
def ping():
    """Eklenti bağlantı testi ve token alma endpoint'i (sadece localhost)"""
    if request.remote_addr not in ('127.0.0.1', '::1'):
        return jsonify({'status': 'error', 'message': 'Forbidden'}), 403
    return jsonify({'status': 'ok', 'token': _API_KEY})


@app.route('/health', methods=['GET'])
def health():
    """Popup health check — herhangi bir origin'den erişilebilir."""
    return jsonify({'status': 'ok', 'version': '2.1'})


@app.route('/api/queue', methods=['GET'])
def api_queue():
    """Aktif indirme kuyruğunu döndür (popup için)."""
    if request.remote_addr not in ('127.0.0.1', '::1'):
        return jsonify({'status': 'error', 'message': 'Forbidden'}), 403
    with _active_queue_lock:
        return jsonify({'status': 'ok', 'queue': list(_active_queue), 'count': len(_active_queue)})


@app.route('/api/queue/add', methods=['POST'])
def api_queue_add():
    """Kuyruğa yeni indirme ekle (popup'tan direkt indirme için)."""
    if not _check_api_key():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    data = request.json or {}
    url = data.get('url', '')
    if not url:
        return jsonify({'status': 'error', 'message': 'URL gerekli'}), 400
    fmt  = data.get('format', 'best')
    type_ = data.get('type', 'video')
    try:
        output_path = get_os_download_dir()
        entry = {'title': url[:80], 'url': url, 'progress': 0, 'status': 'queued'}
        with _active_queue_lock:
            _active_queue.append(entry)
        result = downloader.process_extension_request(
            video_url=url, format_quality=fmt,
            format_type=type_, output_path=output_path
        )
        with _active_queue_lock:
            if entry in _active_queue:
                _active_queue.remove(entry)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/download', methods=['POST'])
def download_video():
    """Tarayıcı eklentisinden gelen indirme isteklerini işler"""
    if not _check_api_key():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    data = request.json
    if not data:
        return jsonify({'status': 'error', 'message': 'İstek verisi geçersiz'}), 400

    try:
        video_url = data.get('videoUrl')
        format_quality = data.get('format')
        format_type = data.get('formatType')

        if not video_url:
            return jsonify({'status': 'error', 'message': 'Video URL\'si belirtilmemiş'}), 400
        if not format_quality or not format_type:
            return jsonify({'status': 'error', 'message': 'Format belirtilmemiş'}), 400

        output_path = get_os_download_dir()
        print(f"Eklentiden indirme isteği: {video_url} - {format_quality} ({format_type})")

        write_subs  = bool(data.get('writeSubs', False))
        start_time  = data.get('startTime')   # int seconds or None
        end_time    = data.get('endTime')     # int seconds or None
        result = downloader.process_extension_request(
            video_url=video_url,
            format_quality=format_quality,
            format_type=format_type,
            output_path=output_path,
            write_sub=write_subs,
            start_time=int(start_time) if start_time is not None else None,
            end_time=int(end_time) if end_time is not None else None,
        )
        return jsonify(result)

    except Exception as e:
        print(f"API hatası: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/info', methods=['GET'])
def api_info():
    """Video/playlist metadata. ?url=..."""
    if not _check_api_key():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    url = request.args.get('url', '')
    if not url:
        return jsonify({'status': 'error', 'message': 'url parametresi gerekli'}), 400
    try:
        info = downloader.get_video_info(url)
        return jsonify({'status': 'ok', 'info': info})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/formats', methods=['GET'])
def api_formats():
    """Mevcut formatları listele. ?url=..."""
    if not _check_api_key():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    url = request.args.get('url', '')
    if not url:
        return jsonify({'status': 'error', 'message': 'url parametresi gerekli'}), 400
    try:
        info = downloader.get_video_info(url)
        fmts = info.get('formats', []) if info else []
        return jsonify({'status': 'ok', 'formats': fmts, 'count': len(fmts)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/history', methods=['GET'])
def api_history():
    """İndirme geçmişi. ?limit=50&offset=0"""
    if request.remote_addr not in ('127.0.0.1', '::1'):
        return jsonify({'status': 'error', 'message': 'Forbidden'}), 403
    from src.core.database import get_download_history
    limit  = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    rows   = get_download_history().get_all_downloads(limit=limit, offset=offset)
    return jsonify({'status': 'ok', 'items': rows, 'count': len(rows)})


@app.route('/api/subscriptions', methods=['GET', 'POST', 'DELETE'])
def api_subscriptions():
    """Abonelikler CRUD."""
    if request.remote_addr not in ('127.0.0.1', '::1'):
        return jsonify({'status': 'error', 'message': 'Forbidden'}), 403
    from src.core.database import get_download_history
    db = get_download_history()
    if request.method == 'GET':
        return jsonify({'status': 'ok', 'subscriptions': db.get_subscriptions()})
    elif request.method == 'POST':
        data = request.json or {}
        url = data.get('url', '')
        if not url:
            return jsonify({'status': 'error', 'message': 'url gerekli'}), 400
        sid = db.add_subscription(url, name=data.get('name'), format_type=data.get('format_type', 'video'))
        return jsonify({'status': 'ok', 'id': sid})
    elif request.method == 'DELETE':
        sid = int(request.args.get('id', 0))
        db.delete_subscription(sid)
        return jsonify({'status': 'ok'})


@app.route('/api/docs', methods=['GET'])
def api_docs():
    """Basit Swagger benzeri API dokümantasyonu."""
    html = """<!DOCTYPE html><html><head><title>YDL API</title>
    <style>body{font-family:monospace;background:#1a1a2e;color:#e0e0e0;padding:24px}
    h1{color:#0078d4}h2{color:#aac8ff;margin-top:24px}
    .ep{background:#0f3460;padding:8px 16px;border-radius:6px;margin:8px 0}
    .method{color:#81c784;font-weight:bold;margin-right:8px}
    .path{color:#fff} .desc{color:#aaa;font-size:13px;margin:4px 0 0 0}
    </style></head><body>
    <h1>🎬 YDL İndirici — REST API</h1>
    <p>Tüm endpoint'ler <code>http://127.0.0.1:5000</code> altındadır.</p>
    <h2>Genel</h2>
    <div class="ep"><span class="method">GET</span><span class="path">/ping</span>
    <p class="desc">Bağlantı testi + API token al</p></div>
    <div class="ep"><span class="method">GET</span><span class="path">/health</span>
    <p class="desc">Sağlık kontrolü</p></div>
    <h2>İndirme</h2>
    <div class="ep"><span class="method">POST</span><span class="path">/download</span>
    <p class="desc">Body: {videoUrl, format, formatType, writeSubs?, startTime?, endTime?}</p></div>
    <h2>API</h2>
    <div class="ep"><span class="method">GET</span><span class="path">/api/info?url=...</span>
    <p class="desc">Video metadata al</p></div>
    <div class="ep"><span class="method">GET</span><span class="path">/api/formats?url=...</span>
    <p class="desc">Mevcut formatları listele</p></div>
    <div class="ep"><span class="method">GET</span><span class="path">/api/queue</span>
    <p class="desc">Aktif indirme kuyruğu (localhost only)</p></div>
    <div class="ep"><span class="method">POST</span><span class="path">/api/queue/add</span>
    <p class="desc">Kuyruğa indirme ekle</p></div>
    <div class="ep"><span class="method">GET</span><span class="path">/api/history?limit=50&offset=0</span>
    <p class="desc">İndirme geçmişi (localhost only)</p></div>
    <div class="ep"><span class="method">GET/POST/DELETE</span><span class="path">/api/subscriptions</span>
    <p class="desc">Kanal abonelikleri CRUD (localhost only)</p></div>
    </body></html>"""
    return html


def start_flask_server():
    """Flask API sunucusunu başlatır"""
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


def _run_cli(args):
    """--no-gui CLI modu — indirmeyi doğrudan çalıştır."""
    global downloader, _API_KEY
    _API_KEY = get_api_key()
    from src.utils.helpers import setup_ffmpeg_path, get_os_download_dir
    setup_ffmpeg_path()

    dl = Downloader()
    output = args.output or get_os_download_dir()
    fmt_type = args.type or 'video'

    print(f"[CLI] İndirme başlatılıyor: {args.url}")
    print(f"[CLI] Çıktı: {output}  Format: {args.format or 'best'}  Tür: {fmt_type}")

    result = dl.process_extension_request(
        video_url=args.url,
        format_quality=args.format or 'best',
        format_type=fmt_type,
        output_path=output,
    )
    if result.get('status') == 'error':
        print(f"[CLI] HATA: {result.get('message', 'Bilinmeyen hata')}")
        return 1
    print(f"[CLI] Tamamlandı!")
    return 0


def main():
    global downloader, _API_KEY

    # ── CLI mod kontrolü ──────────────────────────────────────────────────────
    import argparse
    parser = argparse.ArgumentParser(
        prog='ydl',
        description='YDL İndirici — GUI veya CLI modunda çalışır'
    )
    parser.add_argument('--url',          help='İndirilecek URL', default=None)
    parser.add_argument('--format',       help='Format (best/audio/1080p/720p/...)', default='best')
    parser.add_argument('--type',         help='Tür (video/audio)', default='video')
    parser.add_argument('--output',       help='Çıktı klasörü', default=None)
    parser.add_argument('--no-gui',       action='store_true', help='GUI olmadan çalıştır')
    parser.add_argument('--native-host',  action='store_true',
                        help='Chrome Native Messaging host modunda çalıştır (GUI yok)')
    args, _ = parser.parse_known_args()

    # Native Messaging host modu — Chrome eklentisi tarafından başlatılır
    if args.native_host:
        try:
            from native_host.native_host import run_native_host
        except ImportError:
            # Fallback: run the .py file directly if package import fails
            import importlib.util, os as _os
            _nm_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                     'native_host', 'native_host.py')
            _spec = importlib.util.spec_from_file_location('native_host.native_host', _nm_path)
            _mod  = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            run_native_host = _mod.run_native_host
        run_native_host()
        return

    if args.url or args.no_gui:
        sys.exit(_run_cli(args))

    # API anahtarını config'den yükle (yoksa üret ve kaydet)
    _API_KEY = get_api_key()
    print(f"Flask API anahtarı hazır (ilk 8 karakter): {_API_KEY[:8]}...")

    # FFmpeg'i PATH'e ekle
    setup_ffmpeg_path()
    
    # --- PERFORMANS OPTİMİZASYONU (180+ FPS) ---
    # GPU Hızlandırma: ANGLE/D3D11 (Windows'ta en stabil seçenek)
    os.environ["QT_OPENGL"] = "angle"
    os.environ["QT_ANGLE_PLATFORM"] = "d3d11"
    
    # Threaded Render Loop - GPU render ayrı thread'de
    os.environ["QSG_RENDER_LOOP"] = "threaded"
    
    # GPU batch rendering - daha az draw call
    os.environ["QSG_RENDERER_BATCH_SIZE"] = "256"
    
    # Qt Quick optimizasyonları
    os.environ["QML_DISABLE_DISTANCEFIELD"] = "1"  # Metin render optimizasyonu
    
    # Yüksek DPI yönetimi
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
    
    # GPU Surface Ayarları - Yüksek Hz monitörler için
    format = QSurfaceFormat()
    format.setRenderableType(QSurfaceFormat.RenderableType.OpenGLES)
    format.setVersion(3, 0)  # OpenGL ES 3.0
    format.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    
    # VSync: 0 = kapalı (unlocked FPS), 1 = açık (tearing önleme)
    # 180Hz monitör için VSync kapalı daha iyi çünkü GPU yeterince güçlü
    format.setSwapInterval(0)  # VSync KAPALI - maksimum FPS
    
    format.setSamples(4)  # 4x MSAA
    format.setDepthBufferSize(24)
    format.setStencilBufferSize(8)
    format.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(format)
    
    # PyQt uygulamasını başlat
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseOpenGLES)  # ANGLE için
    
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("YouTube İndirici")
    qt_app.setStyle("Fusion")  # Modern görünüm için

    # Splash ekranı göster
    from src.ui.splash import SplashScreen
    splash = SplashScreen()
    splash.center_on_screen()
    splash.show()
    qt_app.processEvents()

    splash.set_message("FFmpeg hazırlanıyor...")

    # Downloader örneğini oluştur (Flask API ve UI aynı instance'ı kullanır)
    splash.set_message("İndirici başlatılıyor...")
    downloader = Downloader()

    splash.set_message("Arayüz yükleniyor...")
    # Ana pencereyi oluştur
    window = MainWindow(downloader=downloader)

    splash.set_message("Hazır!")
    splash.finish(window)
    window.show()

    # show() sonrası gerçek frame boyutuyla ortala
    screen_geometry = window.screen().availableGeometry()
    window_geometry = window.frameGeometry()
    window_geometry.moveCenter(screen_geometry.center())
    window.move(window_geometry.topLeft())

    # İlk açılış sihirbazı (Onboarding)
    from src.ui.onboarding import run_onboarding_if_needed
    run_onboarding_if_needed(parent=window)
    
    # Flask API sunucusunu ayrı bir thread'de başlat
    flask_thread = threading.Thread(target=start_flask_server)
    flask_thread.daemon = True  # Ana program sonlandığında Flask thread'i de sonlandır
    flask_thread.start()
    
    print("Flask API sunucusu başlatıldı: http://127.0.0.1:5000")
    print("Tarayıcı eklentisi istekleri için hazır")
    
    # Monitör bilgisi
    screen = qt_app.primaryScreen()
    if screen:
        refresh_rate = screen.refreshRate()
        print(f"🖥️  Monitör: {screen.name()} @ {refresh_rate:.0f}Hz")
        print(f"⚡ Animasyon interval: {max(1, int(1000 / refresh_rate))}ms ({refresh_rate:.0f} FPS hedef)")
    
    # Qt event loop'unu başlat
    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main() 