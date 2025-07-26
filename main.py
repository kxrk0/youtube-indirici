#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import threading
import os
from PyQt6.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from flask import Flask, request, jsonify
from flask_cors import CORS
from src.core.downloader import Downloader
from src.utils.helpers import get_os_download_dir

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
    
    # PyQt uygulamasını başlat
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("YouTube İndirici")
    qt_app.setStyle("Fusion")  # Modern görünüm için
    
    # Downloader örneğini oluştur
    downloader = Downloader()
    
    # Ana pencereyi göster
    window = MainWindow()
    window.show()
    
    # Flask API sunucusunu ayrı bir thread'de başlat
    flask_thread = threading.Thread(target=start_flask_server)
    flask_thread.daemon = True  # Ana program sonlandığında Flask thread'i de sonlandır
    flask_thread.start()
    
    print("Flask API sunucusu başlatıldı: http://127.0.0.1:5000")
    print("Tarayıcı eklentisi istekleri için hazır")
    
    # Qt event loop'unu başlat
    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main() 