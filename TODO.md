# YouTube Studio Downloader - Geliştirme TODO

> Son Güncelleme: 2025-12-14 10:00
> Durum: ✅ P0, P1, P2 TAMAMLANDI

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

## 🟢 P3 - Düşük Öncelik

### 13. ⏳ Shorts Desteği
- [ ] Shorts URL algılama
- [ ] Dikey video optimizasyonu

### 14. ⏳ Live Stream Kayıt
- [ ] Canlı yayın algılama
- [ ] Kayıt başlat/durdur

### 15. ⏳ Diğer Platformlar
- [ ] Vimeo, Twitter/X, Dailymotion

### 16. ⏳ Özel FFmpeg Komutları
- [ ] Custom post-processing

### 17. ✅ Klavye Kısayolları
- [x] Ctrl+V, Ctrl+D, Ctrl+Q, Escape

---

## 🔵 P4 - Gelecek

- [ ] Mobil Uygulama API
- [ ] Cloud Sync
- [ ] Browser Extension v2
- [ ] Format Dönüştürücü

---

## 📁 Dosya Yapısı

```
src/
├── core/
│   ├── downloader.py   # İndirme motoru (iptal, trim, normalize)
│   └── database.py     # SQLite geçmiş
├── ui/
│   ├── main_window.py  # Ana UI (tray, kısayollar, batch, trim)
│   ├── components.py   # Video bilgi kartı
│   ├── dialogs.py      # Playlist, Schedule dialog
│   └── gpu_widgets.py  # GPU-optimized scroll
└── utils/
    ├── helpers.py      # Yardımcı fonksiyonlar
    ├── i18n.py         # Çoklu dil desteği
    └── updater.py      # Otomatik güncelleme

locales/
├── tr.json             # Türkçe
├── en.json             # English
└── de.json             # Deutsch
```

## 📝 Sürüm: v2.2.0
