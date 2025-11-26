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

Programı çalıştırmak için bilgisayarınızda **Python 3.8** veya üzeri kurulu olmalıdır.

### 1. Projeyi İndirin
Bu repoyu klonlayın veya ZIP olarak indirip bir klasöre çıkarın.

```bash
git clone https://github.com/kxrk0/youtube-indirici.git
cd youtube-indirici
```

### 2. Otomatik Kurulum (Önerilen)
Proje klasöründeki `install_and_run.bat` dosyasına çift tıklayın. Bu işlem:
1.  Sanal ortam (venv) oluşturur.
2.  Gerekli kütüphaneleri yükler.
3.  Programı başlatır.

### 3. Manuel Kurulum
Eğer manuel kurmak isterseniz:

```bash
# Sanal ortam oluştur
python -m venv venv

# Sanal ortamı aktif et (Windows)
.\venv\Scripts\activate

# Gereksinimleri yükle
pip install -r requirements.txt

# Programı başlat
python main.py
```

---

## 🖥️ Kullanım

1.  **Video Linkini Yapıştırın:** YouTube video bağlantısını kopyalayın, program otomatik algılayacaktır.
2.  **Kalite Seçin:** İster 4K video, ister sadece MP3 ses dosyasını seçin.
3.  **İndirin:** "İndirmeyi Başlat" butonuna basın.
4.  **Kütüphane:** İndirme bitince "Kütüphane" sekmesinden videonuza ulaşabilir, oynatabilir veya klasörünü açabilirsiniz.

---

## ⚙️ Gereksinimler

*   Python 3.8+
*   FFmpeg (Proje klasöründe `ffmpeg-8.0.1-essentials_build` içinde gelmektedir, ayrıca kurulmasına gerek yoktur).
*   İnternet bağlantısı :)

---

## 🤝 Katkıda Bulunma

Projeyi geliştirmek isterseniz Pull Request göndermekten çekinmeyin! Hata bildirimleri için "Issues" sekmesini kullanabilirsiniz.

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır.