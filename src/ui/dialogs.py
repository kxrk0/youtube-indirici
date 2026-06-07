from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QCheckBox, QLabel,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QWidget
)
from qfluentwidgets import MessageBoxBase, SubtitleLabel, PrimaryPushButton, PushButton, CheckBox, InfoBar, LineEdit

class PlaylistSelectionDialog(MessageBoxBase):
    """Playlistten video seçme diyaloğu"""
    def __init__(self, playlist_info, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(f"Playlist: {playlist_info.get('title', 'Bilinmiyor')}", self)
        self.video_list = QListWidget(self)
        self.entries = playlist_info.get('entries', [])
        
        # Arayüz Düzeni
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(10)
        
        # Tümünü Seç
        self.selectAllCheck = CheckBox("Tümünü Seç", self)
        self.selectAllCheck.stateChanged.connect(self.toggle_all)
        self.viewLayout.addWidget(self.selectAllCheck)
        
        # Liste
        self.video_list.setFixedHeight(300)
        self.video_list.setSelectionMode(QListWidget.SelectionMode.NoSelection) # Checkbox ile seçim
        self.viewLayout.addWidget(self.video_list)
        
        # Videoları Ekle
        self.items = []
        for entry in self.entries:
            title = entry.get('title', 'Video')
            url = entry.get('url', '')
            if not url: # flat_extract bazen id döner
                url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                
            item = QListWidgetItem(self.video_list)
            widget = QCheckBox(title)
            widget.setChecked(True) # Varsayılan seçili
            widget.setProperty("url", url)
            widget.setProperty("title", title)
            
            item.setSizeHint(widget.sizeHint())
            self.video_list.setItemWidget(item, widget)
            self.items.append(widget)
            
        self.selectAllCheck.setChecked(True)
        
        # Butonlar
        self.yesButton.setText("Seçilenleri İndir")
        self.cancelButton.setText("İptal")
        
        self.widget.setMinimumWidth(500)

    def toggle_all(self, state):
        is_checked = (state == Qt.CheckState.Checked.value)
        for widget in self.items:
            widget.setChecked(is_checked)

    def get_selected_videos(self):
        """Seçilen videoların listesini (title, url) döner"""
        selected = []
        for widget in self.items:
            if widget.isChecked():
                selected.append({
                    'title': widget.property("title"),
                    'url': widget.property("url")
                })
        return selected


class _ChannelNameWorker(QThread):
    """Kanal adını arka planda al."""
    done = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self):
        try:
            from src.core.subscription_manager import get_channel_name
            name = get_channel_name(self._url) or self._url[:60]
            self.done.emit(name)
        except Exception:
            self.done.emit(self._url[:60])


class SubscriptionManagerDialog(QDialog):
    """Kanal/playlist abonelik yönetim penceresi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kanal Abonelikleri")
        self.setMinimumSize(580, 460)
        layout = QVBoxLayout(self)

        # Ekle satırı
        add_row = QHBoxLayout()
        self._url_input = LineEdit(self)
        self._url_input.setPlaceholderText("Kanal veya playlist URL'si...")
        self._fmt_combo = QComboBox(self)
        self._fmt_combo.addItems(["video", "audio"])
        self._fmt_combo.setFixedWidth(80)
        add_btn = PushButton("Ekle", self)
        add_btn.clicked.connect(self._add_subscription)
        add_row.addWidget(self._url_input, 1)
        add_row.addWidget(self._fmt_combo)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        # Tablo
        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(["Kanal / Playlist", "Format", "Son Kontrol", ""])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table, 1)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._load()

    def _load(self):
        from src.core.database import get_download_history
        subs = get_download_history().get_subscriptions(active_only=False)
        self._table.setRowCount(0)
        for s in subs:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(s.get('name') or s.get('url', '')))
            self._table.setItem(r, 1, QTableWidgetItem(s.get('format_type', 'video')))
            last = s.get('last_checked') or '—'
            self._table.setItem(r, 2, QTableWidgetItem(str(last)[:16]))
            del_btn = PushButton("Sil", self)
            sub_id = s.get('id')
            del_btn.clicked.connect(lambda _, sid=sub_id: self._delete(sid))
            self._table.setCellWidget(r, 3, del_btn)

    def _add_subscription(self):
        url = self._url_input.text().strip()
        if not url:
            return
        fmt = self._fmt_combo.currentText()
        from src.core.database import get_download_history
        from src.utils.helpers import get_os_download_dir
        get_download_history().add_subscription(url, name=url[:60],
                                                format_type=fmt,
                                                output_path=get_os_download_dir())
        self._url_input.clear()
        self._load()
        # Kanal adını arka planda al ve güncelle
        self._name_worker = _ChannelNameWorker(url)
        self._name_worker.done.connect(lambda name: self._update_name(url, name))
        self._name_worker.start()

    def _update_name(self, url: str, name: str):
        from src.core.database import get_download_history
        db = get_download_history()
        subs = db.get_subscriptions(active_only=False)
        for s in subs:
            if s.get('url') == url:
                with db._get_connection() as conn:
                    conn.cursor().execute('UPDATE subscriptions SET name=? WHERE id=?',
                                          (name, s['id']))
                break
        self._load()

    def _delete(self, sub_id: int):
        from src.core.database import get_download_history
        get_download_history().delete_subscription(sub_id)
        self._load()


class SchedulerManagerDialog(QDialog):
    """Zamanlanmış indirme görevleri yöneticisi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Zamanlanmış Görevler")
        self.setMinimumSize(700, 450)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._table = QTableWidget(0, 6, self)
        self._table.setHorizontalHeaderLabels(["Ad", "URL", "Saat", "Tekrar", "Son Çalışma", ""])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table)

        # Add form
        form = QFormLayout()
        form.setSpacing(8)
        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText("Görev adı")
        form.addRow("Ad:", self._name_edit)
        self._url_edit = QLineEdit(self)
        self._url_edit.setPlaceholderText("https://...")
        form.addRow("URL:", self._url_edit)
        self._time_edit = QLineEdit(self)
        self._time_edit.setPlaceholderText("HH:MM  veya  YYYY-MM-DD HH:MM")
        form.addRow("Zaman:", self._time_edit)
        self._type_combo = QComboBox(self)
        self._type_combo.addItems(["video", "audio"])
        form.addRow("Tür:", self._type_combo)
        self._repeat_check = QCheckBox("Her gün tekrarla", self)
        form.addRow("", self._repeat_check)
        layout.addLayout(form)

        btns = QHBoxLayout()
        add_btn = PushButton("➕ Ekle", self)
        add_btn.clicked.connect(self._add_task)
        btns.addWidget(add_btn)
        del_btn = PushButton("🗑 Seçiliyi Sil", self)
        del_btn.clicked.connect(self._delete_selected)
        btns.addWidget(del_btn)
        btns.addStretch()
        close_btn = PushButton("Kapat", self)
        close_btn.clicked.connect(self.close)
        btns.addWidget(close_btn)
        layout.addLayout(btns)

        self._load()

    def _load(self):
        from src.core.database import get_download_history
        self._table.setRowCount(0)
        tasks = get_download_history().get_scheduled_tasks()
        for t in tasks:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(t.get('name', '')))
            self._table.setItem(row, 1, QTableWidgetItem(t.get('url', '')))
            self._table.setItem(row, 2, QTableWidgetItem(t.get('schedule_time', '')))
            self._table.setItem(row, 3, QTableWidgetItem("✓" if t.get('repeat_daily') else "—"))
            self._table.setItem(row, 4, QTableWidgetItem(str(t.get('last_run', '') or '—')))
            id_item = QTableWidgetItem(str(t['id']))
            self._table.setItem(row, 5, id_item)

    def _add_task(self):
        from src.core.database import get_download_history
        name = self._name_edit.text().strip()
        url  = self._url_edit.text().strip()
        sched = self._time_edit.text().strip()
        if not url or not sched:
            InfoBar.warning(title='Eksik', content='URL ve Zaman zorunlu.', duration=3000, parent=self)
            return
        get_download_history().add_scheduled_task(
            name=name or url[:40],
            url=url,
            schedule_time=sched,
            type_str=self._type_combo.currentText(),
            repeat_daily=self._repeat_check.isChecked()
        )
        self._name_edit.clear()
        self._url_edit.clear()
        self._time_edit.clear()
        self._load()

    def _delete_selected(self):
        from src.core.database import get_download_history
        row = self._table.currentRow()
        if row < 0:
            return
        id_item = self._table.item(row, 5)
        if id_item:
            get_download_history().delete_scheduled_task(int(id_item.text()))
            self._load()


class AutoCatEditorDialog(QDialog):
    """Otomatik kategorizasyon kural editörü."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Otomatik Kategorizasyon Kuralları")
        self.setMinimumSize(720, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._table = QTableWidget(0, 5, self)
        self._table.setHorizontalHeaderLabels(["Ad", "Alan", "Regex/Desen", "Klasör", "Tür Override"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table)

        # Add form
        form = QFormLayout()
        form.setSpacing(8)
        self._name_e  = QLineEdit(self); self._name_e.setPlaceholderText("Kural adı")
        form.addRow("Ad:", self._name_e)
        self._field_c = QComboBox(self); self._field_c.addItems(["title", "url", "channel"])
        form.addRow("Alan:", self._field_c)
        self._patt_e  = QLineEdit(self); self._patt_e.setPlaceholderText("regex deseni (case-insensitive)")
        form.addRow("Desen:", self._patt_e)
        self._dir_e   = QLineEdit(self); self._dir_e.setPlaceholderText("Alt klasör adı (ör. Müzik)")
        form.addRow("Klasör:", self._dir_e)
        self._type_c  = QComboBox(self); self._type_c.addItems(["", "audio", "video"])
        form.addRow("Tür Override:", self._type_c)
        layout.addLayout(form)

        btns = QHBoxLayout()
        add_btn = PushButton("➕ Ekle"); add_btn.clicked.connect(self._add)
        btns.addWidget(add_btn)
        del_btn = PushButton("🗑 Sil"); del_btn.clicked.connect(self._delete)
        btns.addWidget(del_btn)
        reset_btn = PushButton("↩ Varsayılana Sıfırla"); reset_btn.clicked.connect(self._reset)
        btns.addWidget(reset_btn)
        btns.addStretch()
        close_btn = PushButton("Kapat"); close_btn.clicked.connect(self.close)
        btns.addWidget(close_btn)
        layout.addLayout(btns)
        self._load()

    def _load(self):
        from src.core.auto_categorize import load_rules
        self._table.setRowCount(0)
        for r in load_rules():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(r.get('name', '')))
            self._table.setItem(row, 1, QTableWidgetItem(r.get('match_field', 'title')))
            self._table.setItem(row, 2, QTableWidgetItem(r.get('pattern', '')))
            self._table.setItem(row, 3, QTableWidgetItem(r.get('output_subdir', '')))
            self._table.setItem(row, 4, QTableWidgetItem(r.get('type_override', '')))

    def _add(self):
        from src.core.auto_categorize import add_rule
        name = self._name_e.text().strip()
        patt = self._patt_e.text().strip()
        if not name or not patt:
            InfoBar.warning(title='Eksik', content='Ad ve Desen zorunlu.', duration=3000, parent=self)
            return
        add_rule({
            'name': name,
            'match_field': self._field_c.currentText(),
            'pattern': patt,
            'output_subdir': self._dir_e.text().strip(),
            'type_override': self._type_c.currentText(),
        })
        self._name_e.clear(); self._patt_e.clear(); self._dir_e.clear()
        self._load()

    def _delete(self):
        from src.core.auto_categorize import delete_rule, load_rules
        row = self._table.currentRow()
        if row < 0:
            return
        name = self._table.item(row, 0).text()
        delete_rule(name)
        self._load()

    def _reset(self):
        from src.core.auto_categorize import reset_to_defaults
        reset_to_defaults()
        self._load()
