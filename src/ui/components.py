from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QUrl
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QGraphicsOpacityEffect
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from qfluentwidgets import CardWidget, FluentIcon, StrongBodyLabel, BodyLabel

from src.utils.helpers import format_duration

class VideoInfoCard(CardWidget):
    """Video Önizleme Kartı"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        
        # Animasyon için Opaklık Efekti
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        # Ağ Yöneticisi (Resim indirmek için)
        self.nam = QNetworkAccessManager()
        self.nam.finished.connect(self.on_thumbnail_downloaded)
        
        self.h_layout = QHBoxLayout(self)
        self.h_layout.setContentsMargins(20, 10, 20, 10)
        self.h_layout.setSpacing(20)
        
        # Sol taraf: Thumbnail
        self.thumb_label = QLabel(self)
        self.thumb_label.setFixedSize(160, 90)
        self.thumb_label.setStyleSheet("background-color: #2d2d2d; border-radius: 8px;")
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setScaledContents(True) # Resmi sığdır
        
        # Varsayılan İkon
        self.default_icon = FluentIcon.VIDEO.icon().pixmap(48, 48)
        self.thumb_label.setPixmap(self.default_icon)
        
        self.h_layout.addWidget(self.thumb_label)
        
        # Sağ taraf: Bilgiler
        self.info_layout = QVBoxLayout()
        self.info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.info_layout.setSpacing(5)
        
        self.title_lbl = StrongBodyLabel("Video Başlığı Bekleniyor...", self)
        self.title_lbl.setStyleSheet("font-size: 16px;")
        
        self.channel_lbl = BodyLabel("Kanal Adı", self)
        self.duration_lbl = BodyLabel("Süre: --:--", self)
        self.duration_lbl.setStyleSheet("color: gray;")
        
        self.info_layout.addWidget(self.title_lbl)
        self.info_layout.addWidget(self.channel_lbl)
        self.info_layout.addWidget(self.duration_lbl)
        
        self.h_layout.addLayout(self.info_layout)
        self.h_layout.addStretch()

    def update_info(self, info):
        self.title_lbl.setText(info.get('title', 'Bilinmiyor'))
        self.channel_lbl.setText(info.get('uploader', 'Bilinmiyor'))
        
        duration = info.get('duration')
        if duration:
            self.duration_lbl.setText(f"Süre: {format_duration(duration)}")
            
        # Thumbnail İndir
        thumbnail_url = info.get('thumbnail')
        if thumbnail_url:
            self.nam.get(QNetworkRequest(QUrl(thumbnail_url)))
            
        # Animasyonu Başlat
        self.start_entrance_animation()

    def on_thumbnail_downloaded(self, reply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            self.thumb_label.setPixmap(pixmap)
        reply.deleteLater()
        
    def reset_info(self):
        """Kart bilgilerini sıfırlar"""
        self.title_lbl.setText("Video Başlığı Bekleniyor...")
        self.channel_lbl.setText("Kanal Adı")
        self.duration_lbl.setText("Süre: --:--")
        self.thumb_label.setPixmap(self.default_icon)
        self.hide()

    def start_entrance_animation(self):
        self.show()
        
        # Yukarıdan Aşağı Kayma Animasyonu
        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(500)
        self.pos_anim.setStartValue(QPoint(self.x(), self.y() - 20))
        self.pos_anim.setEndValue(QPoint(self.x(), self.y()))
        self.pos_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        
        # Opaklık (Fade-In) Animasyonu
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(500)
        self.fade_anim.setStartValue(0)
        self.fade_anim.setEndValue(1)
        
        self.pos_anim.start()
        self.fade_anim.start()