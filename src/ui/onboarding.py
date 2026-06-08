#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Onboarding Sihirbazı — İlk açılışta gösterilir.
Hone'dan ilham: adım adım kurulum, büyük CTA, temiz dark UI.
"""

import os
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QColor, QFont, QPixmap, QPainter, QBrush, QRadialGradient
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QStackedWidget, QFileDialog, QButtonGroup
)

from qfluentwidgets import (
    TitleLabel, SubtitleLabel, BodyLabel, StrongBodyLabel,
    PrimaryPushButton, PushButton, CardWidget,
    FluentIcon, setThemeColor, InfoBar
)
import src.utils.config as cfg


# ─── Adım baz sınıfı ──────────────────────────────────────────────────────────

class _StepCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("stepCard")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(48, 40, 48, 40)
        self.layout_.setSpacing(20)
        self.layout_.setAlignment(Qt.AlignmentFlag.AlignTop)


# ─── Adım 1: Hoş Geldin ───────────────────────────────────────────────────────

class _WelcomeStep(_StepCard):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Logo placeholder — büyük emoji ikon
        icon_lbl = QLabel("⬇️", self)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 72px; margin-bottom: 8px;")
        self.layout_.addWidget(icon_lbl)

        title = TitleLabel("YDL İndirici'ye Hoş Geldin", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        self.layout_.addWidget(title)

        sub = BodyLabel(
            "YouTube, Spotify, TikTok ve 1000+ platformdan\n"
            "video & müzik indir. Hızlı, ücretsiz, reklamsız.", self
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #888; font-size: 15px; line-height: 1.6;")
        sub.setWordWrap(True)
        self.layout_.addWidget(sub)

        self.layout_.addSpacing(12)

        # Özellik grid'i — Hone'un numbered card stili
        feats = [
            ("001", "🎬", "Video & Ses", "MP4, MP3, WebM, MKV"),
            ("002", "🎵", "Spotify Desteği", "Şarkı sözleriyle birlikte"),
            ("003", "📦", "Toplu İndirme", "Kanal & playlist desteği"),
            ("004", "🔄", "Otomatik Güncelleme", "Her zaman güncel"),
        ]
        grid = QHBoxLayout()
        grid.setSpacing(12)
        for num, icon, feat_title, feat_sub in feats:
            card = CardWidget(self)
            card.setFixedWidth(160)
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(14, 14, 14, 14)
            card_lay.setSpacing(4)

            num_lbl = QLabel(num, card)
            num_lbl.setStyleSheet("color: #0078D4; font-size: 11px; font-weight: bold;")
            icon_l = QLabel(icon, card)
            icon_l.setStyleSheet("font-size: 28px;")
            title_l = StrongBodyLabel(feat_title, card)
            sub_l = BodyLabel(feat_sub, card)
            sub_l.setStyleSheet("color: #666; font-size: 11px;")
            sub_l.setWordWrap(True)

            card_lay.addWidget(num_lbl)
            card_lay.addWidget(icon_l)
            card_lay.addWidget(title_l)
            card_lay.addWidget(sub_l)
            grid.addWidget(card)
        self.layout_.addLayout(grid)


# ─── Adım 2: İndirme Klasörü ──────────────────────────────────────────────────

class _FolderStep(_StepCard):
    def __init__(self, parent=None):
        super().__init__(parent)

        icon_lbl = QLabel("📁", self)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 56px;")
        self.layout_.addWidget(icon_lbl)

        TitleLabel("İndirme Klasörü", self) .setParent(None)
        t = TitleLabel("İndirme Klasörü", self)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_.addWidget(t)

        sub = BodyLabel("Videolar nereye kaydedilsin?", self)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #888;")
        self.layout_.addWidget(sub)

        self.layout_.addSpacing(20)

        # Klasör kutusu
        from qfluentwidgets import LineEdit
        self._path_input = LineEdit(self)
        default = os.path.join(os.path.expanduser('~'), 'Downloads', 'YDL İndirilenler')
        saved = cfg.get('download_dir', '')
        self._path_input.setText(saved or default)
        self._path_input.setReadOnly(True)
        self._path_input.setMinimumWidth(360)
        self.layout_.addWidget(self._path_input, alignment=Qt.AlignmentFlag.AlignCenter)

        browse_btn = PushButton(FluentIcon.FOLDER, "Klasör Seç", self)
        browse_btn.clicked.connect(self._browse)
        self.layout_.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        tip = BodyLabel("💡 İstediğin zaman Ayarlar > Genel'den değiştirebilirsin.", self)
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setStyleSheet("color: #555; font-size: 12px;")
        self.layout_.addWidget(tip)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Klasör Seç", self._path_input.text())
        if d:
            self._path_input.setText(d)

    def get_folder(self) -> str:
        return self._path_input.text()


# ─── Adım 3: Varsayılan Kalite ────────────────────────────────────────────────

class _QualityStep(_StepCard):
    def __init__(self, parent=None):
        super().__init__(parent)

        icon_lbl = QLabel("⚡", self)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 56px;")
        self.layout_.addWidget(icon_lbl)

        t = TitleLabel("Varsayılan Kalite", self)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_.addWidget(t)

        sub = BodyLabel("Hız mı, kalite mi, yoksa sadece ses mi?", self)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #888;")
        self.layout_.addWidget(sub)

        self.layout_.addSpacing(20)

        options = [
            ("🏆", "En İyi Kalite", "1080p+ video, en yüksek bitrate", "best"),
            ("⚡", "Dengeli", "720p video, hızlı indir", "720p"),
            ("🎵", "Sadece Ses", "MP3 320kbps, video yok", "audio"),
        ]

        self._selected = "best"
        self._cards = {}

        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        for icon, title_, desc, key in options:
            card = CardWidget(self)
            card.setFixedWidth(180)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(18, 18, 18, 18)
            card_lay.setSpacing(6)

            QLabel(icon, card).setStyleSheet("font-size: 32px;")
            card_lay.addWidget(QLabel(icon, card))

            tl = StrongBodyLabel(title_, card)
            card_lay.addWidget(tl)

            dl = BodyLabel(desc, card)
            dl.setWordWrap(True)
            dl.setStyleSheet("color: #666; font-size: 11px;")
            card_lay.addWidget(dl)

            self._cards[key] = card
            card.mousePressEvent = lambda e, k=key: self._select(k)
            cards_row.addWidget(card)

        self.layout_.addLayout(cards_row)
        self._select("best")

    def _select(self, key: str):
        self._selected = key
        for k, card in self._cards.items():
            if k == key:
                card.setStyleSheet("CardWidget { border: 2px solid #0078D4; border-radius: 8px; }")
            else:
                card.setStyleSheet("")

    def get_quality(self) -> str:
        return self._selected


# ─── Adım 4: Chrome Eklenti ───────────────────────────────────────────────────

class _ExtensionStep(_StepCard):
    def __init__(self, parent=None):
        super().__init__(parent)

        icon_lbl = QLabel("🧩", self)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 56px;")
        self.layout_.addWidget(icon_lbl)

        t = TitleLabel("Chrome Eklentisi", self)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_.addWidget(t)

        sub = BodyLabel(
            "YouTube'da video izlerken tek tıkla indir.\n"
            "Masaüstü uygulaması kapalı olsa da çalışır.", self
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #888; font-size: 14px;")
        sub.setWordWrap(True)
        self.layout_.addWidget(sub)

        self.layout_.addSpacing(16)

        # Adım adım kurulum kartları
        steps = [
            ("1", "Chrome'u aç", "Tarayıcını başlat"),
            ("2", "Eklentiyi kur", "Chrome Web Store'dan YDL İndirici'yi ekle"),
            ("3", "Videoya git", "Herhangi bir YouTube videosunu aç"),
            ("4", "İndir butonu", "Sağ üstte beliren butona tıkla"),
        ]

        for num, step_title, step_desc in steps:
            row_card = CardWidget(self)
            row_lay = QHBoxLayout(row_card)
            row_lay.setContentsMargins(16, 12, 16, 12)
            row_lay.setSpacing(16)

            num_bubble = QLabel(num, row_card)
            num_bubble.setFixedSize(32, 32)
            num_bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num_bubble.setStyleSheet(
                "background: #0078D4; color: white; border-radius: 16px;"
                "font-weight: bold; font-size: 14px;"
            )
            row_lay.addWidget(num_bubble)

            txt_col = QVBoxLayout()
            txt_col.setSpacing(2)
            txt_col.addWidget(StrongBodyLabel(step_title, row_card))
            desc_lbl = BodyLabel(step_desc, row_card)
            desc_lbl.setStyleSheet("color: #666; font-size: 12px;")
            txt_col.addWidget(desc_lbl)
            row_lay.addLayout(txt_col, stretch=1)
            self.layout_.addWidget(row_card)

        self.layout_.addSpacing(8)
        skip_lbl = BodyLabel("Şimdi atla — istediğin zaman Ayarlar'dan kurabilirsin.", self)
        skip_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        skip_lbl.setStyleSheet("color: #444; font-size: 12px;")
        self.layout_.addWidget(skip_lbl)


# ─── Ana Onboarding Dialog ────────────────────────────────────────────────────

class OnboardingDialog(QDialog):
    """
    İlk açılış sihirbazı.
    cfg.get('onboarding_done') False iken main()'den çağrılır.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("YDL İndirici — Kurulum")
        self.setFixedSize(780, 620)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Arka plan — koyu kart
        root = QWidget(self)
        root.setGeometry(0, 0, 780, 620)
        root.setStyleSheet(
            "QWidget { background: #1a1a1a; border-radius: 16px; }"
        )

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── İlerleme çubuğu (üst) ────────────────────────────────────────────
        self._progress_bar = _StepProgressBar(4, root)
        outer.addWidget(self._progress_bar)

        # ── Adımlar ──────────────────────────────────────────────────────────
        self._stack = QStackedWidget(root)
        self._steps = [
            _WelcomeStep(),
            _FolderStep(),
            _QualityStep(),
            _ExtensionStep(),
        ]
        for s in self._steps:
            self._stack.addWidget(s)
        outer.addWidget(self._stack, stretch=1)

        # ── Alt gezinme çubuğu ───────────────────────────────────────────────
        nav = QWidget(root)
        nav.setStyleSheet("QWidget { background: #141414; border-radius: 0px; }")
        nav_lay = QHBoxLayout(nav)
        nav_lay.setContentsMargins(40, 16, 40, 16)

        self._back_btn = PushButton(FluentIcon.LEFT_ARROW, "Geri", nav)
        self._back_btn.setFixedWidth(100)
        self._back_btn.clicked.connect(self._go_back)
        self._back_btn.hide()

        self._step_lbl = BodyLabel("1 / 4", nav)
        self._step_lbl.setStyleSheet("color: #555;")

        self._next_btn = PrimaryPushButton("Başla →", nav)
        self._next_btn.setFixedWidth(140)
        self._next_btn.clicked.connect(self._go_next)

        nav_lay.addWidget(self._back_btn)
        nav_lay.addStretch()
        nav_lay.addWidget(self._step_lbl)
        nav_lay.addStretch()
        nav_lay.addWidget(self._next_btn)
        outer.addWidget(nav)

        self._current = 0
        self._update_nav()

    # ─── Gezinme ──────────────────────────────────────────────────────────────

    def _go_next(self):
        if self._current == len(self._steps) - 1:
            self._finish()
            return
        self._current += 1
        self._stack.setCurrentIndex(self._current)
        self._progress_bar.set_step(self._current)
        self._update_nav()

    def _go_back(self):
        if self._current > 0:
            self._current -= 1
            self._stack.setCurrentIndex(self._current)
            self._progress_bar.set_step(self._current)
            self._update_nav()

    def _update_nav(self):
        total = len(self._steps)
        self._step_lbl.setText(f"{self._current + 1} / {total}")
        self._back_btn.setVisible(self._current > 0)
        if self._current == total - 1:
            self._next_btn.setText("Tamamla ✓")
        else:
            self._next_btn.setText("Devam →")

    def _finish(self):
        # Klasör kaydet
        folder_step: _FolderStep = self._steps[1]
        folder = folder_step.get_folder()
        if folder:
            cfg.set_value('download_dir', folder)
            os.makedirs(folder, exist_ok=True)

        # Kalite kaydet
        quality_step: _QualityStep = self._steps[2]
        cfg.set_value('onboarding_quality', quality_step.get_quality())

        # Onboarding tamamlandı
        cfg.set_value('onboarding_done', True)
        self.accept()


# ─── Adım İlerleme Çubuğu ────────────────────────────────────────────────────

class _StepProgressBar(QWidget):
    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self.total = total
        self.current = 0
        self.setFixedHeight(6)
        self.setStyleSheet("background: transparent;")

    def set_step(self, step: int):
        self.current = step
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        # Background
        p.setBrush(QBrush(QColor('#2d2d2d')))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, 3, 3)
        # Progress
        pct = (self.current + 1) / self.total
        p.setBrush(QBrush(QColor('#0078D4')))
        p.drawRoundedRect(0, 0, int(w * pct), h, 3, 3)
        p.end()


# ─── Yardımcı: onboarding gerekli mi? ────────────────────────────────────────

def should_show_onboarding() -> bool:
    return not cfg.get('onboarding_done', False)


def run_onboarding_if_needed(parent=None) -> bool:
    """
    Onboarding gerekli ise dialogu gösterir.
    True döner → onboarding tamamlandı veya gerekmiyordu.
    """
    if not should_show_onboarding():
        return True
    dlg = OnboardingDialog(parent)
    result = dlg.exec()
    return result == QDialog.DialogCode.Accepted
