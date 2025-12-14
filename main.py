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

# Global değişkenler
app = Flask(__name__)
CORS(app)  # CORS desteği ekle (tarayıcı eklentisi için gerekli)
downloader = None  # Downloader örneği

@app.route('/download', methods=['POST'])
def download_video():
    """Tarayıcı eklentisinden gelen indirme isteklerini işler"""
    data = request.json
    
    if not data:
        return jsonify({'status': 'error', 'message': 'İstek verisi geçersiz'}), 400
    
    try:
        video_url = data.get('videoUrl')
        format_quality = data.get('format')  # Çözünürlük (1080p, 720p, vb.) veya "Audio Only"
        format_type = data.get('formatType')  # 'video' veya 'audio'
        video_title = data.get('videoTitle')  # Video başlığı (opsiyonel)
        
        if not video_url:
            return jsonify({'status': 'error', 'message': 'Video URL\'si belirtilmemiş'}), 400
            
        if not format_quality or not format_type:
            return jsonify({'status': 'error', 'message': 'Format belirtilmemiş'}), 400
            
        # Varsayılan indirme konumunu belirle
        output_path = get_os_download_dir()
        
        print(f"Eklentiden indirme isteği: {video_url} - {format_quality} ({format_type})")
        
        # Global downloader örneğini kullan
        result = downloader.process_extension_request(
            video_url=video_url,
            format_quality=format_quality, 
            format_type=format_type,
            output_path=output_path
        )
        
        return jsonify(result)
        
    except Exception as e:
        print(f"API hatası: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def start_flask_server():
    """Flask API sunucusunu başlatır"""
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

def main():
    global downloader
    
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
    
    # Downloader örneğini oluştur
    downloader = Downloader()
    
    # Ana pencereyi göster
    window = MainWindow()
    window.show()
    
    # Ekranın tam ortasına konumlandır
    screen_geometry = window.screen().availableGeometry()
    window_geometry = window.frameGeometry()
    window_geometry.moveCenter(screen_geometry.center())
    window.move(window_geometry.topLeft())
    
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