from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QUrl
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QGraphicsOpacityEffect
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from qfluentwidgets import CardWidget, FluentIcon, StrongBodyLabel, BodyLabel

from src.utils.helpers import format_duration, get_monitor_refresh_rate

class VideoInfoCard(CardWidget):
    """Video Önizleme Kartı - Dinamik refresh rate desteği"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        
        # Monitör refresh rate'ini al
        self.refresh_rate = get_monitor_refresh_rate()
        
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

    def _calculate_animation_duration(self, base_duration_ms: int) -> int:
        """
        Refresh rate'e göre animasyon süresini optimize eder.
        Yüksek Hz monitörlerde daha fazla frame = daha akıcı animasyon.
        
        Args:
            base_duration_ms: 60Hz için baz animasyon süresi
            
        Returns:
            int: Optimize edilmiş animasyon süresi (ms)
        """
        # Yüksek refresh rate'lerde animasyonu biraz uzatmak daha akıcı görünür
        # Çünkü gözümüz daha fazla kare görür
        if self.refresh_rate >= 144:
            return int(base_duration_ms * 1.2)  # 600ms for 144Hz+
        elif self.refresh_rate >= 120:
            return int(base_duration_ms * 1.1)  # 550ms for 120Hz
        return base_duration_ms  # 500ms for 60Hz

    def start_entrance_animation(self):
        self.show()
        
        # Animasyon süresini refresh rate'e göre hesapla
        duration = self._calculate_animation_duration(500)
        
        # Yukarıdan Aşağı Kayma Animasyonu
        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(duration)
        self.pos_anim.setStartValue(QPoint(self.x(), self.y() - 20))
        self.pos_anim.setEndValue(QPoint(self.x(), self.y()))
        self.pos_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        
        # Opaklık (Fade-In) Animasyonu
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(duration)
        self.fade_anim.setStartValue(0)
        self.fade_anim.setEndValue(1)
        
        self.pos_anim.start()
        self.fade_anim.start()