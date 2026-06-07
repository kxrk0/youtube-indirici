#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QFileDialog
import subprocess
import sys

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


class SpeedPresetCard(SettingCard):
    """Hız önayar butonları — slider ile senkronize"""

    PRESETS = [("Sınırsız", 0), ("1 MB/s", 1), ("5 MB/s", 5), ("10 MB/s", 10), ("25 MB/s", 25)]

    def __init__(self, slider_ref, parent=None):
        super().__init__(FluentIcon.SPEED_HIGH, "Hız Önayarları", "Tek tıkla hız limiti seç", parent)
        self._slider = slider_ref
        row = QHBoxLayout()
        row.setSpacing(6)
        for label, val in self.PRESETS:
            btn = PushButton(label, self)
            btn.setFixedWidth(80)
            btn.clicked.connect(lambda checked, v=val: self._slider.setValue(v))
            row.addWidget(btn)
        row.addStretch()
        self.hBoxLayout.addLayout(row)
        self.hBoxLayout.addSpacing(16)


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


class _YtDlpUpdateWorker(QThread):
    done = pyqtSignal(bool, str)

    def run(self):
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'],
                capture_output=True, text=True, timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )
            if result.returncode == 0:
                self.done.emit(True, "yt-dlp başarıyla güncellendi.")
            else:
                self.done.emit(False, result.stderr[-300:] or result.stdout[-300:])
        except Exception as e:
            self.done.emit(False, str(e))


class YtDlpUpdateCard(SettingCard):
    def __init__(self, parent=None):
        super().__init__(FluentIcon.UPDATE, "yt-dlp Güncelle", "İndirici motorunu en son sürüme güncelle", parent)
        self._btn = PushButton("Güncelle", self)
        self._btn.setFixedWidth(100)
        self._btn.clicked.connect(self._start_update)
        self.hBoxLayout.addWidget(self._btn, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self._worker = None

    def _start_update(self):
        self._btn.setEnabled(False)
        self._btn.setText("Güncelleniyor...")
        self._worker = _YtDlpUpdateWorker()
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, success: bool, msg: str):
        self._btn.setEnabled(True)
        self._btn.setText("Güncelle")
        InfoBar.success(title="Güncelleme", content=msg, duration=5000, parent=self.window()) if success else \
        InfoBar.error(title="Güncelleme Hatası", content=msg[:200], duration=6000, parent=self.window())


class _ProxyTestWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, proxy: str):
        super().__init__()
        self._proxy = proxy

    def run(self):
        try:
            import urllib.request
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({'http': self._proxy, 'https': self._proxy})
            )
            with opener.open('http://httpbin.org/ip', timeout=10) as resp:
                ip = resp.read().decode()[:200]
            self.done.emit(True, f"Bağlantı başarılı: {ip}")
        except Exception as e:
            self.done.emit(False, str(e))


class ProxySettingCard(SettingCard):
    def __init__(self, icon, title, content, config_key: str = "", parent=None):
        super().__init__(icon, title, content, parent)
        self.config_key = config_key
        container = QVBoxLayout()
        row = QHBoxLayout()
        self.line_edit = LineEdit(self)
        self.line_edit.setPlaceholderText(content)
        self.line_edit.setFixedWidth(220)
        if config_key:
            self.line_edit.setText(cfg.get(config_key, ''))
            self.line_edit.editingFinished.connect(self._save)
        self._test_btn = PushButton("Test", self)
        self._test_btn.setFixedWidth(60)
        self._test_btn.clicked.connect(self._test_proxy)
        row.addWidget(self.line_edit)
        row.addSpacing(8)
        row.addWidget(self._test_btn)
        container.addLayout(row)
        self.hBoxLayout.addLayout(container)
        self.hBoxLayout.addSpacing(16)
        self._worker = None

    def _save(self):
        if self.config_key:
            cfg.set_value(self.config_key, self.line_edit.text().strip())

    def _test_proxy(self):
        proxy = self.line_edit.text().strip()
        if not proxy:
            InfoBar.warning(title="Proxy", content="Proxy adresi boş!", duration=3000, parent=self.window())
            return
        self._test_btn.setEnabled(False)
        self._test_btn.setText("...")
        self._worker = _ProxyTestWorker(proxy)
        self._worker.done.connect(self._on_test_done)
        self._worker.start()

    def _on_test_done(self, success: bool, msg: str):
        self._test_btn.setEnabled(True)
        self._test_btn.setText("Test")
        InfoBar.success(title="Proxy Test", content=msg[:200], duration=5000, parent=self.window()) if success else \
        InfoBar.error(title="Proxy Test Başarısız", content=msg[:200], duration=5000, parent=self.window())


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

        self.speed_preset_card = SpeedPresetCard(self.speed_card.slider, parent=self.view)
        group2.addSettingCard(self.speed_preset_card)

        self.auto_organize_card = SwitchSettingCard(
            FluentIcon.FOLDER, "Platforma Göre Klasörle",
            "Her platformu ayrı klasöre indir (YouTube/, SoundCloud/...)", parent=self.view
        )
        saved_organize = cfg.get('auto_organize', False)
        self.auto_organize_card.switchButton.setChecked(bool(saved_organize))
        self.auto_organize_card.switchButton.checkedChanged.connect(
            lambda v: cfg.set_value('auto_organize', v)
        )
        group2.addSettingCard(self.auto_organize_card)

        self.concurrent_card = SliderSettingCard(
            FluentIcon.SPEED_HIGH, "Eş Zamanlı İndirme Sayısı", "3 paralel indirme",
            config_key='max_concurrent', parent=self.view
        )
        self.concurrent_card.slider.setRange(1, 8)
        saved_cc = int(cfg.get('max_concurrent', 3))
        self.concurrent_card.slider.setValue(saved_cc)
        self._on_concurrent_changed(saved_cc)
        self.concurrent_card.slider.valueChanged.connect(self._on_concurrent_changed)
        group2.addSettingCard(self.concurrent_card)

        self.filename_tpl_card = LineEditSettingCard(
            FluentIcon.EDIT, "Dosya Adı Şablonu",
            "%(title)s.%(ext)s",
            config_key='filename_template', parent=self.view
        )
        group2.addSettingCard(self.filename_tpl_card)

        self.proxy_card = ProxySettingCard(
            FluentIcon.GLOBE, "Proxy Sunucusu", "Örn: http://user:pass@host:port",
            config_key='proxy', parent=self.view
        )
        group2.addSettingCard(self.proxy_card)

        self.ffmpeg_args_card = LineEditSettingCard(
            FluentIcon.EDIT, "Özel FFmpeg Argümanları", "Örn: -vf scale=1280:720",
            config_key='custom_ffmpeg_args', parent=self.view
        )
        group2.addSettingCard(self.ffmpeg_args_card)
        self.ytdlp_update_card = YtDlpUpdateCard(parent=self.view)
        group2.addSettingCard(self.ytdlp_update_card)
        self.v_layout.addWidget(group2)

        # Webhook
        group_webhook = SettingCardGroup("Webhook / Entegrasyon", self.view)
        self.webhook_card = LineEditSettingCard(
            FluentIcon.LINK, "İndirme Webhook URL",
            "İndirme bitince POST gönder (Zapier, n8n, vs.)",
            config_key='webhook_url', parent=self.view
        )
        group_webhook.addSettingCard(self.webhook_card)
        self.v_layout.addWidget(group_webhook)

        # Abonelik / Otomatik Kontrol
        group_subs = SettingCardGroup("Kanal Abonelikleri", self.view)
        self.sub_interval_card = SliderSettingCard(
            FluentIcon.SYNC, "Kontrol Sıklığı", "Her 6 saatte bir kontrol",
            config_key='sub_check_hours', parent=self.view
        )
        self.sub_interval_card.slider.setRange(1, 24)
        saved_si = int(cfg.get('sub_check_hours', 6))
        self.sub_interval_card.slider.setValue(saved_si)
        self._on_sub_interval_changed(saved_si)
        self.sub_interval_card.slider.valueChanged.connect(self._on_sub_interval_changed)
        group_subs.addSettingCard(self.sub_interval_card)
        self.manage_subs_card = SettingCard(
            FluentIcon.LIBRARY, "Abonelikleri Yönet",
            "Kanal/playlist ekle, düzenle, sil", parent=self.view
        )
        self._subs_btn = PushButton("Yönet", self.manage_subs_card)
        self._subs_btn.setFixedWidth(90)
        self._subs_btn.clicked.connect(self._open_sub_manager)
        self.manage_subs_card.hBoxLayout.addWidget(self._subs_btn)
        self.manage_subs_card.hBoxLayout.addSpacing(16)
        group_subs.addSettingCard(self.manage_subs_card)
        self.v_layout.addWidget(group_subs)

        # Proxy Pool
        group_proxy_pool = SettingCardGroup("Proxy Pool", self.view)
        self.proxy_pool_card = SettingCard(
            FluentIcon.GLOBE, "Proxy Listesi",
            "Her satıra bir proxy (hata olunca sonrakine geç)", parent=self.view
        )
        from PyQt6.QtWidgets import QTextEdit as _QTextEdit
        self._proxy_pool_edit = _QTextEdit(self.proxy_pool_card)
        self._proxy_pool_edit.setPlaceholderText("http://user:pass@host:port\nhttp://host2:port")
        self._proxy_pool_edit.setFixedHeight(80)
        self._proxy_pool_edit.setStyleSheet("background:#1a1a2e; color:#ddd; border-radius:4px;")
        saved_pool = cfg.get('proxy_pool', '')
        self._proxy_pool_edit.setPlainText(saved_pool)
        self._proxy_pool_edit.textChanged.connect(
            lambda: cfg.set_value('proxy_pool', self._proxy_pool_edit.toPlainText()))
        self.proxy_pool_card.hBoxLayout.addWidget(self._proxy_pool_edit)
        self.proxy_pool_card.hBoxLayout.addSpacing(16)
        group_proxy_pool.addSettingCard(self.proxy_pool_card)
        self.v_layout.addWidget(group_proxy_pool)

        # Tema Tasarımcısı
        group_theme = SettingCardGroup("Tema Tasarımcısı", self.view)
        self.corner_radius_card = SliderSettingCard(
            FluentIcon.PALETTE, "Köşe Yarıçapı", "8 px",
            config_key='corner_radius', parent=self.view
        )
        self.corner_radius_card.slider.setRange(0, 20)
        saved_cr = int(cfg.get('corner_radius', 8))
        self.corner_radius_card.slider.setValue(saved_cr)
        self.corner_radius_card.setContent(f"{saved_cr} px")
        self.corner_radius_card.slider.valueChanged.connect(self._on_corner_radius_changed)
        group_theme.addSettingCard(self.corner_radius_card)

        self.accent_card = SettingCard(FluentIcon.PALETTE, "Vurgu Rengi (Hex)",
                                        "Örn: #0078D4", parent=self.view)
        from qfluentwidgets import LineEdit as _LE
        self._accent_input = _LE(self.accent_card)
        self._accent_input.setFixedWidth(120)
        self._accent_input.setText(cfg.get('accent_color', '#0078D4'))
        self._accent_input.setPlaceholderText('#0078D4')
        apply_btn = PushButton("Uygula", self.accent_card)
        apply_btn.setFixedWidth(80)
        apply_btn.clicked.connect(self._apply_accent_color)
        self.accent_card.hBoxLayout.addWidget(self._accent_input)
        self.accent_card.hBoxLayout.addWidget(apply_btn)
        self.accent_card.hBoxLayout.addSpacing(16)
        group_theme.addSettingCard(self.accent_card)
        self.v_layout.addWidget(group_theme)

        # Plugin Yöneticisi
        group_plugins = SettingCardGroup("Plugin Sistemi", self.view)
        self.plugin_card = SettingCard(
            FluentIcon.APPLICATION, "Plugin Yöneticisi",
            "plugins/ klasöründeki Python eklentilerini yönet", parent=self.view
        )
        open_plugins_btn = PushButton("Klasörü Aç", self.plugin_card)
        open_plugins_btn.setFixedWidth(110)
        open_plugins_btn.clicked.connect(self._open_plugins_folder)
        reload_plugins_btn = PushButton("Yenile", self.plugin_card)
        reload_plugins_btn.setFixedWidth(80)
        reload_plugins_btn.clicked.connect(self._reload_plugins)
        self.plugin_card.hBoxLayout.addWidget(open_plugins_btn)
        self.plugin_card.hBoxLayout.addWidget(reload_plugins_btn)
        self.plugin_card.hBoxLayout.addSpacing(16)
        group_plugins.addSettingCard(self.plugin_card)
        self.v_layout.addWidget(group_plugins)

        # İçerik Otomatik Kategorizasyon
        group_autocat = SettingCardGroup("Otomatik Kategorizasyon", self.view)
        self.autocat_card = SettingCard(
            FluentIcon.TAG, "Kategorizasyon Kuralları",
            "URL/başlık/kanal eşleşmesine göre klasöre yönlendir", self.view
        )
        autocat_open_btn = PushButton("Kuralları Düzenle")
        autocat_open_btn.clicked.connect(self._open_autocat_editor)
        self.autocat_card.hBoxLayout.addWidget(autocat_open_btn)
        self.autocat_card.hBoxLayout.addSpacing(16)
        group_autocat.addSettingCard(self.autocat_card)
        self.v_layout.addWidget(group_autocat)

        # Zamanlanmış Görevler
        group_sched = SettingCardGroup("Zamanlanmış Görevler", self.view)
        self.sched_card = SettingCard(
            FluentIcon.CALENDAR, "Zamanlayıcı Yöneticisi",
            "Belirli saatte otomatik indirme görevi ekle/sil", self.view
        )
        sched_open_btn = PushButton("Yönet")
        sched_open_btn.clicked.connect(self._open_scheduler_manager)
        self.sched_card.hBoxLayout.addWidget(sched_open_btn)
        self.sched_card.hBoxLayout.addSpacing(16)
        group_sched.addSettingCard(self.sched_card)
        self.v_layout.addWidget(group_sched)

        # Otomatik Kapanma
        group_auto = SettingCardGroup("Otomasyon", self.view)
        self.auto_shutdown_card = SwitchSettingCard(
            FluentIcon.POWER_BUTTON, "İndirme Bitince Kapat",
            "Tüm indirmeler tamamlanınca bilgisayarı kapat", parent=self.view
        )
        saved_shutdown = cfg.get('auto_shutdown', False)
        self.auto_shutdown_card.switchButton.setChecked(bool(saved_shutdown))
        self.auto_shutdown_card.switchButton.checkedChanged.connect(
            lambda v: cfg.set_value('auto_shutdown', v)
        )
        group_auto.addSettingCard(self.auto_shutdown_card)
        self.v_layout.addWidget(group_auto)

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

    def get_auto_shutdown(self) -> bool:
        return self.auto_shutdown_card.switchButton.isChecked()

    def get_auto_organize(self) -> bool:
        return self.auto_organize_card.switchButton.isChecked()

    def get_concurrent_limit(self) -> int:
        return self.concurrent_card.slider.value()

    def get_filename_template(self) -> str:
        tpl = self.filename_tpl_card.line_edit.text().strip()
        return tpl if tpl else '%(title)s.%(ext)s'

    def _on_concurrent_changed(self, value: int):
        self.concurrent_card.setContent(f"{value} paralel indirme")

    def _on_sub_interval_changed(self, value: int):
        self.sub_interval_card.setContent(f"Her {value} saatte bir kontrol")
        cfg.set_value('sub_check_hours', value)

    def get_webhook_url(self) -> str:
        return self.webhook_card.line_edit.text().strip()

    def get_sub_check_interval_ms(self) -> int:
        """Abonelik kontrol sıklığını milisaniye cinsinden döndür."""
        hours = int(cfg.get('sub_check_hours', 6))
        return hours * 3600 * 1000

    def _open_sub_manager(self):
        try:
            from src.ui.dialogs import SubscriptionManagerDialog
            dlg = SubscriptionManagerDialog(self.window())
            dlg.exec()
        except Exception as e:
            InfoBar.error(title='Hata', content=str(e)[:120], duration=4000, parent=self)

    def _on_corner_radius_changed(self, value: int):
        self.corner_radius_card.setContent(f"{value} px")
        cfg.set_value('corner_radius', value)
        # Apply to app stylesheet globally
        try:
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().setStyleSheet(
                f"CardWidget, QFrame[frameShape='6'] {{ border-radius: {value}px; }}"
            )
        except Exception:
            pass

    def _apply_accent_color(self):
        color = self._accent_input.text().strip()
        if not color.startswith('#'):
            return
        try:
            setThemeColor(color)
            cfg.set_value('accent_color', color)
            InfoBar.success(title='Tema', content=f'Vurgu rengi değiştirildi: {color}', duration=3000, parent=self)
        except Exception as e:
            InfoBar.error(title='Hata', content=str(e)[:60], duration=3000, parent=self)

    def _open_plugins_folder(self):
        import os, platform
        from src.core.plugin_manager import get_plugins_dir
        folder = get_plugins_dir()
        if platform.system() == 'Windows':
            os.startfile(folder)

    def _reload_plugins(self):
        try:
            from src.core.plugin_manager import load_plugins
            infos = load_plugins()
            InfoBar.success(title='Plugin', content=f"{len(infos)} plugin yüklendi.", duration=3000, parent=self)
        except Exception as e:
            InfoBar.error(title='Plugin Hata', content=str(e)[:100], duration=4000, parent=self)

    def get_proxy_pool(self) -> list:
        text = cfg.get('proxy_pool', '')
        return [p.strip() for p in text.strip().splitlines() if p.strip()]

    def _open_autocat_editor(self):
        try:
            from src.ui.dialogs import AutoCatEditorDialog
            dlg = AutoCatEditorDialog(self.window())
            dlg.exec()
        except Exception as e:
            InfoBar.error(title='Hata', content=str(e)[:120], duration=4000, parent=self)

    def _open_scheduler_manager(self):
        try:
            from src.ui.dialogs import SchedulerManagerDialog
            dlg = SchedulerManagerDialog(self.window())
            dlg.exec()
        except Exception as e:
            InfoBar.error(title='Hata', content=str(e)[:120], duration=4000, parent=self)
