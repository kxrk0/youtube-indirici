# YouTube Studio Downloader - Geliştirme TODO

> Son Güncelleme: 2025-12-14 09:40
> Durum: ✅ P1 TAMAMLANDI

---

## 🔴 P0 - Kritik (Öncelikli) ✅ TAMAMLANDI

### 1. ✅ İndirme İptal Desteği
- [x] `Downloader.cancel_download()` implement et
- [x] `DownloadTask` sınıfı ile thread-safe iptal
- [x] UI'da iptal butonu aktif, `cancel_requested` signal
- [x] İptal durumunda "İptal Edildi" gösterimi

### 2. ✅ Hata Yönetimi İyileştirmesi
- [x] Retry mekanizması (3 deneme)
- [x] `socket_timeout: 30` ve `fragment_retries: 5`
- [x] Hata mesajı gösterimi (`set_error` metodu)

### 3. ✅ İlerleme Doğruluğu
- [x] Fragment-based indirmelerde doğru yüzde (`fragment_index / fragment_count`)
- [x] ETA ve hız bilgisi aktarımı

---

## 🟠 P1 - Yüksek Öncelik ✅ TAMAMLANDI

### 4. ✅ Çoklu Dil Desteği (i18n)
- [x] Dil dosyaları yapısı (JSON) - `locales/`
- [x] Türkçe (`tr.json`) - varsayılan
- [x] İngilizce (`en.json`)  
- [x] Almanca (`de.json`)
- [x] i18n modülü (`src/utils/i18n.py`)
- [x] `tr()` fonksiyonu ile çeviri
- [x] Dil seçici (`LanguageSettingCard`) entegrasyonu

### 5. ✅ Tema Kişiselleştirme
- [x] Accent color picker (`AccentColorCard`)
- [x] 10 Fluent Design renk seçeneği
- [x] Seçili renk vurgulama

### 6. ✅ Sistem Tepsisi Entegrasyonu
- [x] Minimize to tray (`closeEvent` override)
- [x] Tray icon menu (Göster, İndirilenler, Çıkış)
- [x] Bildirimler (`showMessage`)
- [x] Tray ikonu tıklama (`show_window`)

### 7. ✅ Otomatik Güncelleme
- [x] `src/utils/updater.py` modülü
- [x] GitHub releases API kontrolü
- [x] Versiyon karşılaştırma
- [x] Başlangıçta güncelleme kontrolü
- [x] Güncelleme bildirimi (InfoBar)

---

## 🟡 P2 - Orta Öncelik (Kısmen Tamamlandı)

### 8. ⏳ Format Seçici İyileştirmesi
- [ ] Codec bilgisi (AV1, H.264, VP9)
- [ ] Dosya boyutu tahmini
- [ ] HDR desteği gösterimi

### 9. ⏳ Batch İndirme
- [ ] URL listesi yapıştırma
- [ ] Toplu format seçimi
- [ ] Sıralı indirme kuyruğu

### 10. ✅ İndirme Geçmişi
- [x] SQLite veritabanı (`src/core/database.py`)
- [x] Kayıt ekleme/sorgulama
- [x] İstatistik hesaplama
- [x] Downloader entegrasyonu
- [ ] Geçmiş sayfası UI

### 11. ⏳ Ses Normalizasyonu
- [ ] FFmpeg loudnorm filtresi
- [ ] Ayarlanabilir hedef dB

### 12. ⏳ Video Kesme
- [ ] Başlangıç/bitiş zamanı seçici
- [ ] FFmpeg trim entegrasyonu

---

## 🟢 P3 - Düşük Öncelik (Kısmen Tamamlandı)

### 13. ⏳ Shorts Desteği
- [ ] Shorts URL algılama
- [ ] Dikey video optimizasyonu

### 14. ⏳ Live Stream Kayıt
- [ ] Canlı yayın algılama
- [ ] Kayıt başlat/durdur

### 15. ⏳ Diğer Platformlar
- [ ] Vimeo
- [ ] Twitter/X
- [ ] Dailymotion

### 16. ⏳ Özel FFmpeg Komutları
- [ ] Custom post-processing
- [ ] Ayarlar sayfasında editör

### 17. ✅ Klavye Kısayolları
- [x] Ctrl+V: Panodan URL yapıştır
- [x] Ctrl+D: İndirmeyi başlat
- [x] Escape: Ana sayfaya dön
- [x] Ctrl+Q: Çıkış

---

## 🔵 P4 - Gelecek

### 18. ⏳ Mobil Uygulama API
### 19. ⏳ Cloud Sync
### 20. ⏳ Browser Extension v2
### 21. ⏳ Format Dönüştürücü

---

## 📁 Yeni Dosyalar

| Dosya | Açıklama |
|-------|----------|
| `src/core/database.py` | SQLite indirme geçmişi veritabanı |
| `src/ui/gpu_widgets.py` | GPU-optimized scroll widget'ları |
| `src/utils/i18n.py` | Çoklu dil desteği modülü |
| `src/utils/updater.py` | Otomatik güncelleme modülü |
| `locales/tr.json` | Türkçe çeviriler |
| `locales/en.json` | İngilizce çeviriler |
| `locales/de.json` | Almanca çeviriler |
| `TODO.md` | Bu dosya |

## 📝 Notlar

- Her özellik için test yaz
- UI değişikliklerinde screenshot al
- GEMINI.md'yi güncel tut
- Uygulama sürümü: v2.1.0
