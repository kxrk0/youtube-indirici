# 🎬 YouTube Studio Downloader

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python)
![PyQt6](https://img.shields.io/badge/UI-PyQt6%20Fluent-green?style=for-the-badge&logo=qt)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?style=for-the-badge&logo=windows)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**YouTube Studio Downloader**, modern Windows 11 (Fluent Design) arayüzüne sahip, yüksek performanslı ve kullanıcı dostu bir YouTube video indirme aracıdır. Videoları 4K kalitesinde indirebilir, MP3'e dönüştürebilir ve dahili kütüphanesiyle yönetebilirsiniz.

---

## ✨ Özellikler

*   🎨 **Modern Arayüz:** Windows 11 tarzı "Mica" efektli, şık ve karanlık/aydınlık mod destekli tasarım.
*   🚀 **Yüksek Performans:** 60 FPS akıcı arayüz ve çoklu parça indirme teknolojisi ile maksimum hız.
*   📺 **4K/8K Desteği:** En yüksek çözünürlükte video indirme imkanı (WebM -> MP4 otomatik dönüşüm).
*   🎵 **MP3 Dönüştürücü:** Videoları tek tıkla yüksek kaliteli ses dosyasına çevirin.
*   📚 **Akıllı Kütüphane:** İndirdiğiniz dosyaları kapak resimleriyle (thumbnail) listeleyin ve yönetin.
*   ⚡ **Otomatik Algılama:** Panoya kopyaladığınız linkleri otomatik tanır ve hazırlar.
*   🧩 **Tarayıcı Eklentisi:** (Opsiyonel) Tarayıcınızdan tek tıkla indirme başlatın.

---

## 🛠️ Kurulum

1. [Son sürüm sayfasından](https://github.com/kxrk0/youtube-indirici/releases/latest) `YouTubeIndirici_<sürüm>-Setup.exe` dosyasını indirin.
2. Çalıştırın; Windows yönetici izni ister (program `C:\Program Files\YouTubeIndirici` klasörüne kurulur).
3. Kurulum bitince masaüstündeki **YouTube Studio Downloader** kısayoluyla açın.

Kurulum ayrıca:
* FFmpeg bilgisayarda yoksa `C:\Program Files\FFmpeg` klasörüne kurup sistem PATH'ine ekler.
* Başlat menüsüne kısayol ve "Uygulamalar" listesine kaldırıcı ekler.
* Güncellemeleri uygulama kendisi önerir ve kurar.

Ayarlar ve indirme geçmişi `%LOCALAPPDATA%\YouTubeIndirici` klasöründe durur; kaldırırken silinip silinmeyeceği sorulur.

### Kaynak koddan çalıştırma (geliştirme)

Python 3.11, Node.js ve (MP3/birleştirme için) PATH'te FFmpeg gerekir.

```bash
git clone https://github.com/kxrk0/youtube-indirici.git
cd youtube-indirici
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
cd webui && npm install && npm run build && cd ..
python main.py
```

Kurucuyu üretmek için: `venv\Scripts\python.exe installer\build_release.py` (NSIS gerekir: `winget install NSIS.NSIS`).

---

## 🖥️ Kullanım

1.  **Video Linkini Yapıştırın:** YouTube video bağlantısını kopyalayın, program otomatik algılayacaktır.
2.  **Kalite Seçin:** İster 4K video, ister sadece MP3 ses dosyasını seçin.
3.  **İndirin:** "İndirmeyi Başlat" butonuna basın.
4.  **Kütüphane:** İndirme bitince "Kütüphane" sekmesinden videonuza ulaşabilir, oynatabilir veya klasörünü açabilirsiniz.

---

## ⚙️ Gereksinimler

*   Windows 10 veya 11 (64 bit)
*   İnternet bağlantısı :)

---

## 🤝 Katkıda Bulunma

Projeyi geliştirmek isterseniz Pull Request göndermekten çekinmeyin! Hata bildirimleri için "Issues" sekmesini kullanabilirsiniz.

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır.