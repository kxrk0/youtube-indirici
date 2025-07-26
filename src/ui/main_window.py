#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import platform
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon, QDragEnterEvent, QDropEvent, QClipboard, QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QProgressBar,
    QComboBox, QFileDialog, QMessageBox, QTabWidget,
    QRadioButton, QButtonGroup, QGroupBox, QCheckBox,
    QStatusBar, QSpacerItem, QSizePolicy
)

from src.core.downloader import Downloader
from src.utils.helpers import (
    is_valid_url, format_size, format_duration, 
    get_os_download_dir, check_ffmpeg, get_clipboard_text
)

class InfoFetchWorker(QThread):
    """Video bilgilerini ayrı bir thread'de çeken sınıf"""
    info_ready = pyqtSignal(dict, list)
    
    def __init__(self, downloader, url):
        super().__init__()
        self.downloader = downloader
        self.url = url
        
    def run(self):
        info = self.downloader.get_video_info(self.url)
        formats = self.downloader.get_available_formats(self.url) if info else []
        self.info_ready.emit(info, formats)

class DownloadWorker(QThread):
    """İndirme işlemlerini ayrı bir thread'de yürüten sınıf"""
    progress_signal = pyqtSignal(dict)
    completed_signal = pyqtSignal(bool, str)
    
    def __init__(self, downloader, url, output_dir, format_id=None, is_audio=False, save_metadata=False):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.output_dir = output_dir
        self.format_id = format_id
        self.is_audio = is_audio
        self.save_metadata = save_metadata
    
    def progress_callback(self, d):
        if d['status'] == 'downloading':
            progress_data = {
                'downloaded_bytes': d.get('downloaded_bytes', 0),
                'total_bytes': d.get('total_bytes', 0),
                'total_bytes_estimate': d.get('total_bytes_estimate', 0),
                'speed': d.get('speed', 0),
                'filename': d.get('filename', ''),
                'status': 'downloading',
                'eta': d.get('eta', 0)
            }
            self.progress_signal.emit(progress_data)
        elif d['status'] == 'finished':
            progress_data = {
                'status': 'processing',
                'filename': d.get('filename', '')
            }
            self.progress_signal.emit(progress_data)
    
    def complete_callback(self, success, error=None):
        self.completed_signal.emit(success, error if error else "")
    
    def run(self):
        if self.is_audio:
            self.downloader.download_audio(
                self.url, 
                self.output_dir, 
                progress_callback=self.progress_callback,
                complete_callback=self.complete_callback,
                save_info=self.save_metadata
            )
        else:
            self.downloader.download_video(
                self.url, 
                self.output_dir, 
                format_id=self.format_id,
                progress_callback=self.progress_callback,
                complete_callback=self.complete_callback,
                save_info=self.save_metadata
            )

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.downloader = Downloader()
        self.current_formats = []
        self.selected_format_id = 'best'
        
        self.init_ui()
        self.setup_signals()
        self.setup_clipboard_monitor()
        
        # Drag-drop desteği
        self.setAcceptDrops(True)
    
    def init_ui(self):
        """Kullanıcı arayüzünü oluşturur"""
        self.setWindowTitle("YouTube İndirici")
        self.setMinimumSize(800, 500)
        
        # Ana widget ve layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # URL giriş alanı
        url_layout = QHBoxLayout()
        url_label = QLabel("Video URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("YouTube video URL'sini yapıştırın")
        self.fetch_info_btn = QPushButton("Bilgi Al")
        
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.fetch_info_btn)
        
        # Video bilgileri bölümü
        info_group = QGroupBox("Video Bilgileri")
        info_layout = QVBoxLayout(info_group)
        
        self.video_title_label = QLabel("Başlık: ")
        self.video_duration_label = QLabel("Süre: ")
        self.video_channel_label = QLabel("Kanal: ")
        
        info_layout.addWidget(self.video_title_label)
        info_layout.addWidget(self.video_duration_label)
        info_layout.addWidget(self.video_channel_label)
        
        # İndirme seçenekleri bölümü
        options_group = QGroupBox("İndirme Seçenekleri")
        options_layout = QVBoxLayout(options_group)
        
        # İndirme türü seçimi
        type_layout = QHBoxLayout()
        self.type_group = QButtonGroup(self)
        self.video_radio = QRadioButton("Video")
        self.audio_radio = QRadioButton("Ses (MP3)")
        
        self.type_group.addButton(self.video_radio, 1)
        self.type_group.addButton(self.audio_radio, 2)
        self.video_radio.setChecked(True)
        
        type_layout.addWidget(self.video_radio)
        type_layout.addWidget(self.audio_radio)
        type_layout.addStretch()
        
        options_layout.addLayout(type_layout)
        
        # Format seçimi
        format_layout = QHBoxLayout()
        format_label = QLabel("Format:")
        self.format_combo = QComboBox()
        
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)
        
        options_layout.addLayout(format_layout)
        
        # Çıktı dizini seçimi
        output_layout = QHBoxLayout()
        output_label = QLabel("İndirme Konumu:")
        self.output_path = QLineEdit()
        self.output_path.setText(get_os_download_dir())
        self.browse_btn = QPushButton("Gözat...")
        
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(self.browse_btn)
        
        options_layout.addLayout(output_layout)
        
        # Meta veri seçenekleri
        self.save_thumbnail_check = QCheckBox("Küçük Resmi Kaydet")
        self.save_thumbnail_check.setChecked(True)
        options_layout.addWidget(self.save_thumbnail_check)
        
        self.save_metadata_check = QCheckBox("Meta Verileri JSON Olarak Kaydet")
        self.save_metadata_check.setChecked(False)  # Varsayılan olarak kapalı
        options_layout.addWidget(self.save_metadata_check)
        
        # İndirme butonları
        buttons_layout = QHBoxLayout()
        self.download_btn = QPushButton("İndir")
        self.download_btn.setEnabled(False)
        self.cancel_btn = QPushButton("İptal")
        self.cancel_btn.setEnabled(False)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.download_btn)
        buttons_layout.addWidget(self.cancel_btn)
        
        # İlerleme çubuğu
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        
        self.status_label = QLabel("Hazır")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        
        # Ana layout'a tüm bileşenleri ekle
        main_layout.addLayout(url_layout)
        main_layout.addWidget(info_group)
        main_layout.addWidget(options_group)
        main_layout.addLayout(buttons_layout)
        main_layout.addLayout(progress_layout)
        
        # Durum çubuğu
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Hazır")
        
        # FFmpeg kontrolü
        if not check_ffmpeg():
            self.statusBar.showMessage("Uyarı: FFmpeg bulunamadı. MP3 dönüşümleri çalışmayabilir.")
        
        # Ana widget'ı ayarla
        self.setCentralWidget(main_widget)
        
    def setup_signals(self):
        """Sinyal bağlantılarını kurar"""
        self.fetch_info_btn.clicked.connect(self.on_fetch_info)
        self.browse_btn.clicked.connect(self.on_browse_directory)
        self.download_btn.clicked.connect(self.on_download)
        self.cancel_btn.clicked.connect(self.on_cancel_download)
        
        self.url_input.textChanged.connect(self.on_url_changed)
        self.type_group.buttonClicked.connect(self.on_type_changed)
        
    def setup_clipboard_monitor(self):
        """Pano değişikliklerini izler"""
        from PyQt6.QtWidgets import QApplication
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)
        
    def on_clipboard_changed(self):
        """Pano değiştiğinde çağrılır"""
        text = self.clipboard.text()
        if is_valid_url(text) and self.url_input.text() == "":
            self.url_input.setText(text)
            self.statusBar.showMessage("YouTube URL'si panodan algılandı")
        
    def on_url_changed(self):
        """URL değiştiğinde çağrılır"""
        url = self.url_input.text().strip()
        if is_valid_url(url):
            self.fetch_info_btn.setEnabled(True)
        else:
            self.fetch_info_btn.setEnabled(False)
            self.download_btn.setEnabled(False)
            
    def on_type_changed(self):
        """İndirme türü değiştiğinde çağrılır"""
        if self.audio_radio.isChecked():
            self.format_combo.setEnabled(False)
        else:
            self.format_combo.setEnabled(True)
            self.populate_formats()
    
    def on_browse_directory(self):
        """Dizin seçme dialogunu gösterir"""
        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "İndirme Konumu Seç", 
            self.output_path.text(),
            QFileDialog.Option.ShowDirsOnly
        )
        
        if dir_path:
            self.output_path.setText(dir_path)
    
    def on_fetch_info(self):
        """Video bilgilerini çeker"""
        url = self.url_input.text().strip()
        
        if not is_valid_url(url):
            QMessageBox.warning(self, "Hata", "Geçerli bir YouTube URL'si girin.")
            return
        
        self.statusBar.showMessage("Video bilgileri alınıyor...")
        self.fetch_info_btn.setEnabled(False)
        
        # Bilgileri ayrı bir thread'de al
        self.fetch_info_worker = InfoFetchWorker(self.downloader, url)
        self.fetch_info_worker.info_ready.connect(self.on_info_received)
        self.fetch_info_worker.start()
        
    def on_info_received(self, info, formats):
        """Video bilgileri alındığında çağrılır"""
        if info:
            self.update_video_info(info)
            self.current_formats = formats
            self.populate_formats()
            self.download_btn.setEnabled(True)
            self.statusBar.showMessage("Video bilgileri alındı")
        else:
            self.statusBar.showMessage("Video bilgileri alınamadı")
            
        self.fetch_info_btn.setEnabled(True)
        
    def update_video_info(self, info):
        """Video bilgilerini arayüzde günceller"""
        self.video_title_label.setText(f"Başlık: {info.get('title', 'Bilinmiyor')}")
        
        duration = info.get('duration')
        if duration:
            duration_str = format_duration(duration)
            self.video_duration_label.setText(f"Süre: {duration_str}")
        else:
            self.video_duration_label.setText("Süre: Bilinmiyor")
        
        self.video_channel_label.setText(f"Kanal: {info.get('uploader', 'Bilinmiyor')}")
        
        self.statusBar.showMessage("Video bilgileri alındı")
    
    def populate_formats(self):
        """Format seçicisini doldurur"""
        if not self.current_formats:
            return
        
        self.format_combo.clear()
        
        # Her zaman gösterilen sabit seçenekler
        self.format_combo.addItem("En İyi Kalite (Otomatik)", "best")
        self.format_combo.addItem("En İyi Kalite Video+En İyi Kalite Ses", "bestvideo+bestaudio")
        
        # Format listesini analiz et ve düzgün formatları ekle
        try:
            # Debug için format sayısını göster
            print(f"Toplam format sayısı: {len(self.current_formats)}")
            
            # En iyi ses formatını bul
            best_audio_format = None
            for fmt in self.current_formats:
                if fmt.get('vcodec') == 'none' and fmt.get('acodec') != 'none':
                    best_audio_format = fmt
                    print(f"En iyi ses formatı bulundu: {fmt.get('format_id')}")
                    break
            
            # Kullanılabilir formatları listele
            available_formats = []
            for fmt in self.current_formats:
                try:
                    format_id = fmt.get('format_id', '')
                    vcodec = fmt.get('vcodec', 'none')
                    acodec = fmt.get('acodec', 'none')
                    ext = fmt.get('ext', '?')
                    height = fmt.get('height')
                    width = fmt.get('width')
                    format_note = fmt.get('format_note', '')
                    
                    # Eğer video içermiyorsa, atla
                    if vcodec == 'none':
                        continue
                    
                    # Format bilgisini oluştur
                    if height is not None and width is not None:
                        resolution = f"{width}x{height}"
                    else:
                        resolution = fmt.get('resolution', 'Bilinmiyor')
                    
                    # FPS bilgisi
                    fps = fmt.get('fps')
                    fps_str = f" {fps}fps" if fps else ""
                    
                    # Dosya boyutu
                    filesize = fmt.get('filesize')
                    size_str = f" ({format_size(filesize)})" if filesize else ""
                    
                    # Format bilgisi ve ID oluştur
                    if acodec != 'none':
                        # Hem video hem ses içeriyorsa
                        format_type = "[Video+Ses]"
                        final_format_id = format_id
                    elif best_audio_format:
                        # Sadece video içeriyorsa ve en iyi ses formatı varsa
                        format_type = "[Video+Ses]"
                        final_format_id = f"{format_id}+{best_audio_format.get('format_id')}"
                    else:
                        # Sadece video içeriyorsa ve ses formatı yoksa
                        format_type = "[Sadece Video]"
                        final_format_id = format_id
                    
                    # Etiket oluştur
                    label = f"{resolution}{fps_str} - {ext}{size_str} {format_note} {format_type}"
                    
                    # Yükseklik değerine göre sıralamak için sayısal değere dönüştür
                    if height is None:
                        height_value = 0
                    else:
                        height_value = int(height)
                    
                    # Sadece 480p ve üstü formatları ekle
                    if height_value >= 480 or height_value == 0:  # 0 ise bilinmeyen çözünürlük
                        available_formats.append((final_format_id, label, height_value))
                        print(f"Format eklendi: {label}")
                except Exception as e:
                    print(f"Format işlenirken hata: {str(e)}")
                    continue
            
            # Sonuçları ekle
            if available_formats:
                print(f"Filtrelenmiş format sayısı: {len(available_formats)}")
                # Çözünürlüğe göre sırala (en yüksekten düşüğe)
                for format_id, label, _ in sorted(available_formats, key=lambda x: x[2], reverse=True):
                    self.format_combo.addItem(label, format_id)
            else:
                print("Uygun format bulunamadı, tüm formatları ekliyorum...")
                # Hiç format bulunamazsa, tüm video formatlarını ekle
                for fmt in self.current_formats:
                    if fmt.get('vcodec') != 'none':
                        format_id = fmt.get('format_id', '')
                        label = fmt.get('format', f"Format {format_id}")
                        self.format_combo.addItem(label, format_id)
        
        except Exception as e:
            # Herhangi bir hata olursa, güvenli mod - sadece "best" seçeneği kalır
            print(f"Format listesi oluşturulurken hata: {str(e)}")
            # self.format_combo zaten temizlenmiş ve "En İyi Kalite" seçenekleri eklenmiş durumda
            
    def on_download(self):
        """İndirme işlemini başlatır"""
        url = self.url_input.text().strip()
        output_dir = self.output_path.text()
        
        if not url or not is_valid_url(url):
            QMessageBox.warning(self, "Hata", "Geçerli bir YouTube URL'si girin.")
            return
            
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"İndirme dizini oluşturulamadı: {str(e)}")
                return
        
        # Format seçimi
        is_audio = self.audio_radio.isChecked()
        format_id = None
        
        if not is_audio:
            format_id = self.format_combo.currentData()
        
        # UI bileşenlerini güncelle
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("İndirme hazırlanıyor...")
        
                 # Meta veri kaydetme seçeneğini al
        save_metadata = self.save_metadata_check.isChecked()
        
        # İndirme işçisini başlat
        self.download_worker = DownloadWorker(
            self.downloader, url, output_dir, format_id, is_audio, save_metadata
        )
        self.download_worker.progress_signal.connect(self.update_progress)
        self.download_worker.completed_signal.connect(self.on_download_complete)
        self.download_worker.start()
    
    def update_progress(self, progress_data):
        """İndirme ilerlemesini günceller"""
        status = progress_data.get('status')
        
        if status == 'downloading':
            downloaded = progress_data.get('downloaded_bytes', 0)
            total = progress_data.get('total_bytes', 0) or progress_data.get('total_bytes_estimate', 0)
            
            if total > 0:
                percent = int((downloaded / total) * 100)
                self.progress_bar.setValue(percent)
                
                # İndirme hızı
                speed = progress_data.get('speed', 0)
                if speed:
                    speed_str = format_size(speed) + "/s"
                else:
                    speed_str = "Bilinmiyor"
                    
                # Kalan süre
                eta = progress_data.get('eta', 0)
                if eta:
                    eta_str = format_duration(eta)
                else:
                    eta_str = "Bilinmiyor"
                    
                self.status_label.setText(
                    f"İndiriliyor: {percent}% - {speed_str} - Kalan: {eta_str}"
                )
            else:
                self.progress_bar.setMaximum(0)  # Belirsiz ilerleme göster
                self.status_label.setText("İndiriliyor...")
                
        elif status == 'processing':
            self.progress_bar.setMaximum(0)  # Belirsiz ilerleme göster
            self.status_label.setText("İşleniyor...")
            
    def on_download_complete(self, success, error):
        """İndirme tamamlandığında çağrılır"""
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setMaximum(100)
        
        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("İndirme tamamlandı!")
            self.statusBar.showMessage("İndirme başarıyla tamamlandı")
            
            # Dizini göster
            if os.path.exists(self.output_path.text()):
                if platform.system() == 'Windows':
                    os.startfile(self.output_path.text())
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.call(['open', self.output_path.text()])
                else:  # Linux
                    subprocess.call(['xdg-open', self.output_path.text()])
        else:
            self.progress_bar.setValue(0)
            self.status_label.setText("İndirme başarısız!")
            self.statusBar.showMessage(f"İndirme hatası: {error}")
            
            QMessageBox.critical(self, "İndirme Hatası", 
                                f"Video indirilemedi: {error}")
    
    def on_cancel_download(self):
        """İndirmeyi iptal eder"""
        if hasattr(self, 'download_worker') and self.download_worker.isRunning():
            self.download_worker.terminate()
            self.download_worker.wait()
            
            self.progress_bar.setValue(0)
            self.status_label.setText("İndirme iptal edildi")
            self.statusBar.showMessage("İndirme iptal edildi")
            
            self.download_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Sürüklenen öğeleri kabul eder"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """Bırakılan URL'yi alır"""
        urls = event.mimeData().urls()
        if urls and urls[0].isValid():
            url_text = urls[0].toString()
            if is_valid_url(url_text):
                self.url_input.setText(url_text)
                self.on_fetch_info()
                
    def closeEvent(self, event):
        """Uygulama kapatılırken çağrılır"""
        # Açık bir indirme işlemi varsa sor
        if hasattr(self, 'download_worker') and self.download_worker.isRunning():
            reply = QMessageBox.question(
                self, 
                "Çıkış Onayı", 
                "İndirme devam ediyor. Çıkmak istediğinizden emin misiniz?", 
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.download_worker.terminate()
                self.download_worker.wait()
                event.accept()
            else:
                event.ignore() 