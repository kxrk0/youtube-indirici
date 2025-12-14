from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QCheckBox, QLabel
from qfluentwidgets import MessageBoxBase, SubtitleLabel, PrimaryPushButton, PushButton, CheckBox

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
