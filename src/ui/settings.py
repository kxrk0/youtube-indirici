#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QFileDialog

from qfluentwidgets import (
    ScrollArea, CardWidget, TitleLabel, BodyLabel,
    PushButton, PushSettingCard, HyperlinkCard, SettingCardGroup, SettingCard,
    SwitchButton, ComboBox, Slider, LineEdit, FluentIcon,
    setTheme, Theme, setThemeColor, InfoBar, InfoBarPosition
)

from src.ui.gpu_widgets import setup_smooth_scroll
from src.utils.helpers import get_os_download_dir
from src.utils.i18n import get_current_language, set_language
from src.utils import config as cfg


class SwitchSettingCard(SettingCard):
    def __init__(self, icon, title, content, parent=None):
        super().__init__(icon, title, content, parent)
        self.switchButton = SwitchButton(self)
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)


class LineEditSettingCard(SettingCard):
    def __init__(self, icon, title, content, config_key: str = "", parent=None):
        super().__init__(icon, title, content, parent)
        self.config_key = config_key
        self.line_edit = LineEdit(self)
        self.line_edit.setPlaceholderText(content)
        self.line_edit.setFixedWidth(200)
        if config_key:
            self.line_edit.setText(cfg.get(config_key, ''))
            self.line_edit.editingFinished.connect(self._save)
        self.hBoxLayout.addWidget(self.line_edit, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def _save(self):
        if self.config_key:
            cfg.set_value(self.config_key, self.line_edit.text().strip())


class LanguageSettingCard(SettingCard):
    LANGUAGES = [("tr", "Türkçe"), ("en", "English"), ("de", "Deutsch")]

    def __init__(self, icon, title, content, parent=None):
        super().__init__(icon, title, content, parent)
        self.comboBox = ComboBox(self)
        for lang_code, lang_name in self.LANGUAGES:
            self.comboBox.addItem(lang_name, userData=lang_code)
        current = get_current_language()
        for i, (code, _) in enumerate(self.LANGUAGES):
            if code == current:
                self.comboBox.setCurrentIndex(i)
                break
        self.comboBox.currentIndexChanged.connect(self.on_language_changed)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def on_language_changed(self, index: int):
        if 0 <= index < len(self.LANGUAGES):
            lang_code = self.LANGUAGES[index][0]
            set_language(lang_code)
            cfg.set_value('language', lang_code)
            InfoBar.info(
                title="Dil Değiştirildi",
                content="Değişiklikler uygulamayı yeniden başlattığınızda geçerli olacak.",
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self.window()
            )


class SliderSettingCard(SettingCard):
    def __init__(self, icon, title, content, config_key: str = "", parent=None):
        super().__init__(icon, title, content, parent)
        self.config_key = config_key
        self.slider = Slider(Qt.Orientation.Horizontal, self)
        self.slider.setFixedWidth(150)
        if config_key:
            self.slider.setValue(int(cfg.get(config_key, 0)))
            self.slider.valueChanged.connect(self._save)
        self.hBoxLayout.addWidget(self.slider, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def _save(self, value):
        if self.config_key:
            cfg.set_value(self.config_key, value)


class AccentColorCard(SettingCard):
    ACCENT_COLORS = [
        ("#0078D4", "Mavi"),
        ("#0099BC", "Turkuaz"),
        ("#00B294", "Yeşil"),
        ("#00CC6A", "Açık Yeşil"),
        ("#FFB900", "Altın"),
        ("#FF8C00", "Turuncu"),
        ("#E81123", "Kırmızı"),
        ("#C30052", "Magenta"),
        ("#9A0089", "Mor"),
        ("#881798", "Koyu Mor"),
    ]

    def __init__(self, icon, title, content, parent=None):
        super().__init__(icon, title, content, parent)
        self.color_buttons = []
        self.color_layout = QHBoxLayout()
        self.color_layout.setSpacing(8)
        for color_hex, color_name in self.ACCENT_COLORS:
            from qfluentwidgets import PushButton as PBtn
            btn = PBtn(self)
            btn.setFixedSize(28, 28)
            btn.setToolTip(color_name)
            btn.setStyleSheet(f"""
                PushButton {{
                    background-color: {color_hex};
                    border: 2px solid transparent;
                    border-radius: 14px;
                }}
                PushButton:hover {{
                    border: 2px solid white;
                }}
            """)
            btn.clicked.connect(lambda checked, c=color_hex: self.set_accent_color(c))
            self.color_buttons.append(btn)
            self.color_layout.addWidget(btn)
        self.hBoxLayout.addLayout(self.color_layout)
        self.hBoxLayout.addSpacing(16)

    def set_accent_color(self, color_hex: str):
        setThemeColor(color_hex)
        cfg.set_value('accent_color', color_hex)
        for btn in self.color_buttons:
            style = btn.styleSheet()
            if color_hex in style:
                btn.setStyleSheet(style.replace("border: 2px solid transparent", "border: 2px solid white"))
            elif "border: 2px solid white" in style:
                btn.setStyleSheet(style.replace("border: 2px solid white", "border: 2px solid transparent"))


class SettingsInterface(ScrollArea):
    """Ayarlar sayfası - config.py ile kalıcı saklama"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsInterface")
        self.view = __import__('PyQt6.QtWidgets', fromlist=['QWidget']).QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.view.setObjectName("settingsView")
        self.setStyleSheet("ScrollArea{background: transparent; border: none;}")
        self.view.setStyleSheet("QWidget#settingsView{background: transparent;}")
        setup_smooth_scroll(self, enable_kinetic=True)

        from PyQt6.QtWidgets import QVBoxLayout
        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setContentsMargins(36, 36, 36, 36)
        self.v_layout.setSpacing(20)

        self.title = TitleLabel("Ayarlar", self.view)
        self.v_layout.addWidget(self.title)

        # Dil
        group_lang = SettingCardGroup("Dil / Language", self.view)
        self.lang_card = LanguageSettingCard(FluentIcon.LANGUAGE, "Uygulama Dili", "Arayüz dilini seçin", parent=self.view)
        group_lang.addSettingCard(self.lang_card)
        self.v_layout.addWidget(group_lang)

        # Kişiselleştirme
        group1 = SettingCardGroup("Kişiselleştirme", self.view)

        self.theme_card = SwitchSettingCard(FluentIcon.BRIGHTNESS, "Uygulama Teması", "Karanlık/Aydınlık", parent=self.view)
        is_dark = cfg.get('theme', 'dark') == 'dark'
        self.theme_card.switchButton.setChecked(is_dark)
        self.theme_card.switchButton.checkedChanged.connect(self._on_theme_changed)
        group1.addSettingCard(self.theme_card)

        self.color_card = AccentColorCard(FluentIcon.PALETTE, "Vurgu Rengi", "Arayüz vurgu rengini seçin", parent=self.view)
        group1.addSettingCard(self.color_card)
        self.v_layout.addWidget(group1)

        # İndirme
        group2 = SettingCardGroup("İndirme", self.view)
        saved_dir = cfg.get('download_dir', '') or get_os_download_dir()
        self.folder_card = PushSettingCard("Klasörü Seç", FluentIcon.FOLDER, "İndirme Konumu", saved_dir, self.view)
        self.folder_card.clicked.connect(self.select_folder)
        group2.addSettingCard(self.folder_card)

        self.speed_card = SliderSettingCard(
            FluentIcon.SPEED_HIGH, "İndirme Hızı Limiti", "Sınırsız",
            config_key='speed_limit', parent=self.view
        )
        self.speed_card.slider.setRange(0, 50)
        saved_speed = int(cfg.get('speed_limit', 0))
        self.speed_card.slider.setValue(saved_speed)
        self._on_speed_changed(saved_speed)
        self.speed_card.slider.valueChanged.connect(self._on_speed_changed)
        group2.addSettingCard(self.speed_card)

        self.proxy_card = LineEditSettingCard(
            FluentIcon.GLOBE, "Proxy Sunucusu", "Örn: http://user:pass@host:port",
            config_key='proxy', parent=self.view
        )
        group2.addSettingCard(self.proxy_card)

        self.ffmpeg_args_card = LineEditSettingCard(
            FluentIcon.EDIT, "Özel FFmpeg Argümanları", "Örn: -vf scale=1280:720",
            config_key='custom_ffmpeg_args', parent=self.view
        )
        group2.addSettingCard(self.ffmpeg_args_card)
        self.v_layout.addWidget(group2)

        # Geliştiriciler
        group3 = SettingCardGroup("Geliştiriciler", self.view)
        group3.addSettingCard(HyperlinkCard("https://github.com/kxrk0", "Proje Sahibi", FluentIcon.GITHUB, "kxrk0", "Open", self.view))
        group3.addSettingCard(HyperlinkCard("https://github.com/swaffX", "Geliştirici", FluentIcon.GITHUB, "swaffX", "Open", self.view))
        self.v_layout.addWidget(group3)
        self.v_layout.addStretch()

    def _on_theme_changed(self, checked: bool):
        theme = 'dark' if checked else 'light'
        setTheme(Theme.DARK if checked else Theme.LIGHT)
        cfg.set_value('theme', theme)

    def _on_speed_changed(self, value: int):
        self.speed_card.setContent("Sınırsız" if value == 0 else f"{value} MB/s")

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "İndirme Klasörünü Seç", get_os_download_dir())
        if folder:
            self.folder_card.setContent(folder)
            cfg.set_value('download_dir', folder)

    def get_speed_limit(self):
        val = self.speed_card.slider.value()
        return f"{val}M" if val > 0 else None

    def get_proxy(self):
        return self.proxy_card.line_edit.text().strip() or None

    def get_custom_ffmpeg_args(self):
        return self.ffmpeg_args_card.line_edit.text().strip() or None

    def get_download_dir(self):
        text = self.folder_card.contentLabel.text().strip()
        return text if text else get_os_download_dir()
