# YouTube Studio Downloader - GEMINI.md

## Project Overview
**YouTube Studio Downloader** is a high-performance, modern desktop application for downloading YouTube videos and audio. It features a Windows 11-style Fluent UI, hardware-accelerated rendering, and a built-in media library. The project also includes a Flask-based local API server to handle requests from a companion browser extension.

### Key Technologies
*   **Core Language:** Python 3.8+
*   **GUI Framework:** PyQt6, `PyQt6-Fluent-Widgets` (for Modern/Fluent Design)
*   **Downloading Engine:** `yt-dlp` (fork of youtube-dl)
*   **Media Processing:** `FFmpeg` (included locally in `ffmpeg-8.0.1-essentials_build`)
*   **Extension API:** `Flask` (runs on port 5000)
*   **Concurrency:** `QThread` (UI responsiveness), `threading` (Flask server)

## Directory Structure

*   **`main.py`**: The application entry point.
    *   Initializes `QApplication` with OpenGL optimization flags (`QT_OPENGL`, `QSG_RENDER_LOOP`).
    *   Starts the Flask API server in a background daemon thread.
    *   Launches the main GUI window.
*   **`src/`**: Source code directory.
    *   **`ui/`**: User interface logic.
        *   `main_window.py`: The core UI controller. Implements `FluentWindow`, handles navigation (Home, Downloads, Library, Settings), and manages `QThread` workers for downloading and thumbnail generation.
        *   `components.py`: Custom UI widgets, specifically `VideoInfoCard` for animated video previews.
    *   **`core/`**: Backend logic.
        *   `downloader.py`: Wrapper around `yt-dlp`. Handles download configuration (formats, FFmpeg location, progress hooks) and threaded execution.
    *   **`utils/`**: Utility functions.
        *   `helpers.py`: FFmpeg detection, thumbnail extraction, clipboard handling, and formatting helpers.
*   **`extension/`**: Source code for the browser extension (Manifest V3, JS, CSS).
*   **`ffmpeg-*-essentials_build/`**: Local FFmpeg binaries to ensure portability.
*   **`cache/`**: Stores generated thumbnails for the library.

## Build & Run Instructions

### Prerequisites
*   Python 3.8 or higher.
*   Windows 10/11 (Recommended for Fluent UI effects).

### Running the Application
1.  **First Time / Auto-Setup:**
    Run `install_and_run.bat`. This script creates a virtual environment (`venv`), installs dependencies from `requirements.txt`, checks for FFmpeg, and starts the app.
2.  **Development Run:**
    If the environment is already set up, you can run `run.bat` or execute:
    ```bash
    .\venv\Scripts\activate
    python main.py
    ```

## Development Conventions

### User Interface (UI)
*   **Style:** Adhere strictly to **Fluent Design** principles. Use `qfluentwidgets` components (`CardWidget`, `PrimaryPushButton`, `FluentIcon`) instead of standard Qt widgets where possible.
*   **Performance:**
    *   All blocking I/O (network requests, file processing, heavy FFmpeg tasks) **MUST** run in a `QThread` or background thread. Never block the main GUI thread.
    *   Use `QScroller` for kinetic scrolling in list views.
    *   Set `QScrollArea` backgrounds to `transparent` to allow the window's Mica effect to show through.
*   **Responsiveness:** The UI runs at 60FPS+ due to OpenGL settings in `main.py`. Maintain this by optimizing paint events and animations.

### Functionality
*   **Downloading:**
    *   Always prefer `yt-dlp` options that utilize concurrent fragment downloading (`concurrent_fragment_downloads`) to maximize bandwidth.
    *   Videos should be merged into `mp4` containers for compatibility.
    *   Audio should be extracted as high-quality `mp3`.
*   **Library:**
    *   The library scans the download directory for media files.
    *   Thumbnails are generated asynchronously using FFmpeg (extracting the 5th second frame) and cached in `cache/thumbnails`.

### Extension Integration
*   The Flask server listens on `http://127.0.0.1:5000/download` (POST).
*   It receives JSON payloads (`videoUrl`, `format`, `formatType`) and triggers the download logic in the main application instance.

---

## 🚀 GPU Optimizasyonu (v2.1)

### Yapılan Değişiklikler
*   **ANGLE/D3D11 Backend**: Native OpenGL yerine ANGLE kullanılarak DirectX 11 üzerinden GPU hızlandırma.
*   **Threaded Render Loop**: `QSG_RENDER_LOOP=threaded` ile GPU render işlemleri ayrı thread'de.
*   **Dinamik Refresh Rate**: Monitör Hz'ine göre otomatik animasyon hızı (60Hz-240Hz+).
*   **4x MSAA**: Anti-aliasing ile daha pürüzsüz kenarlar.
*   **OpenGL ES 3.0**: D3D11 Feature Level 10+ desteği.

### Dinamik FPS Sistemi
Uygulama başlangıçta monitörün refresh rate'ini algılar ve animasyonları optimize eder:
- **60Hz** → 16ms interval, 60 FPS
- **120Hz** → 8ms interval, 120 FPS  
- **144Hz** → 7ms interval, 144 FPS
- **180Hz** → 5ms interval, 180 FPS
- **240Hz** → 4ms interval, 240 FPS

### İlgili Fonksiyonlar (helpers.py)
```python
get_monitor_refresh_rate()  # Monitör Hz değerini döndürür
get_optimal_timer_interval()  # Timer için ms interval
get_animation_speed_factor()  # 60Hz normalize faktörü
```

### Ortam Değişkenleri
```
QT_OPENGL=angle
QT_ANGLE_PLATFORM=d3d11
QSG_RENDER_LOOP=threaded
QSG_RENDERER_BATCH_SIZE=256
QML_DISABLE_DISTANCEFIELD=1
```

### Scroll Performansı
*   **Kinetic Scrolling**: `QScroller` ile momentum-based smooth scroll.
*   **VSync Kapalı**: RTX 4060 gibi güçlü GPU'lar için `setSwapInterval(0)`.
*   **Tüm ScrollArea'lar optimize edildi**: HomeInterface, QueueInterface, LibraryInterface, SettingsInterface.
*   **FlowLayout desteği**: Kütüphane sayfasında çok widget olduğunda bile akıcı scroll.

---

## 📋 Geliştirme Yol Haritası

### 🔴 Öncelikli (P0) ✅
- [x] **İndirme İptal Desteği**: `DownloadTask` sınıfı ile thread-safe iptal
- [x] **Hata Yönetimi İyileştirmesi**: Retry mekanizması (3 deneme), timeout handling
- [x] **İlerleme Doğruluğu**: Fragment-based indirmelerde doğru yüzde gösterimi

### 🟠 Yüksek (P1) ✅
- [x] **Çoklu Dil Desteği (i18n)**: Türkçe, İngilizce, Almanca (`locales/`, `src/utils/i18n.py`)
- [x] **Tema Kişiselleştirme**: Accent rengi seçimi (10 Fluent color)
- [x] **Sistem Tepsisi Entegrasyonu**: Minimize to tray, bildirimler
- [x] **Otomatik Güncelleme**: GitHub releases API (`src/utils/updater.py`)

### 🟡 Orta (P2)
- [ ] **Format Seçici İyileştirmesi**: Video codec bilgisi (AV1, H.264, VP9)
- [ ] **Batch İndirme**: URL listesi yapıştırma ve toplu indirme
- [x] **İndirme Geçmişi**: SQLite veritabanı (`src/core/database.py`)
- [ ] **Ses Normalizasyonu**: FFmpeg ile loudnorm filtresi
- [ ] **Video Kesme**: Başlangıç/bitiş zamanı ile kısmi indirme

### 🟢 Düşük (P3)
- [ ] **Shorts Desteği**: YouTube Shorts için optimize indirme
- [ ] **Live Stream Kayıt**: Canlı yayın kaydetme
- [ ] **Diğer Platformlar**: Vimeo, Dailymotion, Twitter/X desteği
- [ ] **Özel FFmpeg Komutları**: Gelişmiş kullanıcılar için custom post-processing
- [x] **Klavye Kısayolları**: Ctrl+V, Ctrl+D, Ctrl+Q, Escape

### 🔵 Gelecek (P4)
- [ ] **Mobil Uygulama API**: Flask API üzerinden mobil uygulamadan kontrol
- [ ] **Cloud Sync**: Ayarları ve geçmişi cloud'a senkronize etme
- [ ] **Browser Extension v2**: Chrome Web Store yayını, daha iyi UI
- [ ] **Format Dönüştürücü**: İndirilen dosyaları başka formatlara çevirme

---

## 📁 Proje Dosyaları (Yeni Eklenenler)

| Dosya | Açıklama |
|-------|----------|
| `src/core/database.py` | SQLite indirme geçmişi veritabanı |
| `src/ui/gpu_widgets.py` | GPU-optimized scroll widget'ları |
| `src/utils/i18n.py` | Çoklu dil desteği modülü |
| `src/utils/updater.py` | Otomatik güncelleme modülü |
| `locales/tr.json` | Türkçe çeviriler |
| `locales/en.json` | İngilizce çeviriler |
| `locales/de.json` | Almanca çeviriler |
| `TODO.md` | Geliştirme görev listesi |
