# YouTube Studio Downloader - Geliştirme TODO

> Son Güncelleme: 2026-06-06
> Durum: ✅ P0, P1, P2, P3, Geliştirme Önerileri TAMAMLANDI

---

## 🔴 P0 - Kritik ✅ TAMAMLANDI

### 1. ✅ İndirme İptal Desteği
- [x] `DownloadTask` sınıfı ile thread-safe iptal
- [x] UI'da iptal butonu aktif
- [x] İptal durumunda "İptal Edildi" gösterimi

### 2. ✅ Hata Yönetimi İyileştirmesi
- [x] Retry mekanizması (3 deneme)
- [x] Timeout handling (30s socket, 5 fragment retry)

### 3. ✅ İlerleme Doğruluğu
- [x] Fragment-based yüzde hesaplama

---

## 🟠 P1 - Yüksek Öncelik ✅ TAMAMLANDI

### 4. ✅ Çoklu Dil Desteği (i18n)
- [x] JSON dil dosyaları (`locales/tr.json`, `en.json`, `de.json`)
- [x] i18n modülü (`src/utils/i18n.py`)
- [x] Dil seçici UI entegrasyonu

### 5. ✅ Tema Kişiselleştirme
- [x] Accent color picker (10 Fluent renk)
- [x] Seçili renk vurgulama

### 6. ✅ Sistem Tepsisi Entegrasyonu
- [x] Minimize to tray
- [x] Tray menü (Göster, İndirilenler, Çıkış)
- [x] Bildirimler

### 7. ✅ Otomatik Güncelleme
- [x] GitHub releases API kontrolü
- [x] Güncelleme bildirimi (InfoBar)

---

## 🟡 P2 - Orta Öncelik ✅ TAMAMLANDI

### 8. ✅ Format Seçici İyileştirmesi
- [x] Codec bilgisi (AV1, H.264, VP9, H.265)
- [x] FPS bilgisi (60fps, 120fps vb.)
- [x] HDR desteği gösterimi
- [x] Dosya boyutu tahminleri

### 9. ✅ Batch İndirme
- [x] URL listesi yapıştırma dialogu
- [x] Toplu indirme butonu
- [x] Sıralı kuyruk işleme

### 10. ✅ İndirme Geçmişi
- [x] SQLite veritabanı (`src/core/database.py`)
- [x] Downloader entegrasyonu
- [x] İstatistik hesaplama

### 11. ✅ Ses Normalizasyonu
- [x] FFmpeg loudnorm filtresi (-16 LUFS)
- [x] UI checkbox seçeneği

### 12. ✅ Video Kesme (Trim)
- [x] Başlangıç/bitiş zamanı input'ları
- [x] HH:MM:SS ve saniye formatı desteği
- [x] yt-dlp download_ranges entegrasyonu

---

## 🟢 P3 - Düşük Öncelik ✅ TAMAMLANDI

### 13. ✅ Shorts Desteği
- [x] Shorts URL algılama (`detect_platform` → `youtube_shorts`)
- [x] Çok platform URL doğrulama güncellendi

### 14. ✅ Live Stream Kayıt
- [x] Canlı yayın algılama (`is_live` / `was_live` flag)
- [x] `download_livestream()` motoru (yt-dlp live_from_start)
- [x] UI: 🔴 rozet, "Kaydı Başlat" butonu, gerçek zamanlı boyut gösterimi
- [x] Kayıt iptal desteği

### 15. ✅ Diğer Platformlar
- [x] Vimeo, Twitter/X, Dailymotion URL desteği
- [x] `detect_platform()` yardımcı fonksiyon
- [x] URL placeholder güncellendi

### 16. ✅ Özel FFmpeg Komutları
- [x] Ayarlar'da "Özel FFmpeg Argümanları" text girişi
- [x] Video ve ses indirme pipeline'larına aktarılıyor

### 17. ✅ Klavye Kısayolları
- [x] Ctrl+V, Ctrl+D, Ctrl+Q, Escape

---

## 🐛 Kritik Bug Düzeltmeleri (v2.3.0)
- [x] `download_video` thread hiç başlamıyordu (dead code `_parse_time` içindeydi)
- [x] `main.py` + `MainWindow` iki ayrı `Downloader()` yaratıyordu; Flask API yanlış instance kullanıyordu
- [x] `add_scheduled_task` `write_sub` parametresi eksikti (imza uyuşmazlığı)
- [x] Proxy `download_video` / `download_audio`'ya iletilmiyordu

---

## ✅ Geliştirme Önerileri (v2.3.0)

### 1. ✅ main_window.py Bölünmesi
- [x] `src/ui/workers.py` — ThumbnailWorker, InfoFetchWorker, DownloadWorker, FormatConverterWorker
- [x] `src/ui/home.py` — HomeInterface, SkeletonWidget, VideoInfoSkeleton, ScheduleDialog
- [x] `src/ui/queue.py` — QueueInterface, DownloadItemCard
- [x] `src/ui/library.py` — LibraryInterface, LibraryItem
- [x] `src/ui/settings.py` — SettingsInterface + tüm kart sınıfları
- [x] `src/ui/main_window.py` — sadece MainWindow (navigation shell)

### 2. ✅ İndirme Geçmişi Sayfası
- [x] `src/ui/history.py` — HistoryInterface
- [x] İstatistik kartı (toplam, bugün, bu ay, boyut)
- [x] Arama/filtreleme
- [x] Silme ve toplu temizleme

### 3. ✅ Paralel İndirme Limiti
- [x] `threading.Semaphore(3)` ile en fazla 3 eş zamanlı indirme
- [x] DownloadWorker.run() içinde semaphore acquire/release

### 4. ✅ Ayarlar Kalıcılığı
- [x] `src/utils/config.py` — JSON tabanlı kalıcı config
- [x] Tema, renk, proxy, hız limiti, FFmpeg args, indirme dizini kaydediliyor
- [x] SettingsInterface config.py ile entegre

### 5. ✅ Shorts Dikey Format Düzeltmesi
- [x] `detect_platform('youtube_shorts')` kontrolü DownloadWorker içinde
- [x] Shorts URL'ler için `bestvideo[width<=720]+bestaudio/best` format seçici

### 6. ✅ Format Dönüştürücü
- [x] LibraryItem sağ tık menüsü (contextMenuEvent)
- [x] MP3, MP4, MKV dönüştürme seçenekleri
- [x] FormatConverterWorker — FFmpeg tabanlı, arka planda çalışır

### 7. ✅ Tarayıcı Eklentisi İyileştirmeleri
- [x] background.js — `GET /ping` ile token alma
- [x] `X-API-Key` header ile tüm POST istekleri güvence altında
- [x] Token cache'leme ve 401 sonrası yenileme

### 8. ✅ Windows Native Bildirimleri
- [x] `win11toast` entegrasyonu (opsiyonel, yüklü değilse tray bildirimine düşer)
- [x] İndirme tamamlandığında native Windows bildirimi

### 9. ✅ Flask Güvenliği
- [x] `GET /ping` — token dağıtım endpoint'i (sadece localhost)
- [x] `X-API-Key` header doğrulaması tüm POST endpoint'lerinde
- [x] API anahtarı `config.json`'da kalıcı olarak saklanır
- [x] Rastgele 32-byte hex anahtar (64 karakter)

### 10. ✅ Test Kapsamı
- [x] `tests/test_downloader.py` — 20+ unit test
- [x] helpers, updater, config, database, DownloadTask testleri
- [x] pytest ile çalışır

---

## 🔵 P5 - Gelecek

- [ ] Mobil Uygulama API
- [ ] Cloud Sync

---

## 📁 Dosya Yapısı

```
src/
├── core/
│   ├── downloader.py    # İndirme motoru
│   └── database.py      # SQLite geçmiş
├── ui/
│   ├── main_window.py   # MainWindow (navigation shell)
│   ├── home.py          # HomeInterface
│   ├── queue.py         # QueueInterface, DownloadItemCard
│   ├── library.py       # LibraryInterface, LibraryItem + format dönüştürücü
│   ├── settings.py      # SettingsInterface + kart sınıfları
│   ├── history.py       # HistoryInterface
│   ├── workers.py       # Tüm QThread worker'ları
│   ├── components.py    # VideoInfoCard
│   ├── dialogs.py       # PlaylistSelectionDialog
│   └── gpu_widgets.py   # setup_smooth_scroll + GPU widget'ları
└── utils/
    ├── helpers.py       # Yardımcı fonksiyonlar
    ├── i18n.py          # Çoklu dil desteği
    ├── updater.py       # Otomatik güncelleme
    └── config.py        # Kalıcı JSON config

tests/
└── test_downloader.py   # Unit testler
```

## 📝 Sürüm: v2.3.0
