# YouTube İndirici

Modern ve kullanımı kolay YouTube video, shorts ve MP3 indirici uygulaması.

![GitHub License](https://img.shields.io/github/license/yourusername/youtube-indirici)

## Proje Tanımı

Bu uygulama, YouTube videolarını en yüksek kalitede indirebilen, kullanımı kolay bir ara yüze sahip Python uygulamasıdır. PyQt6 ve yt-dlp kullanılarak geliştirilmiştir.

## Özellikler

- YouTube videoları, Shorts videoları ve MP3 ses dosyalarını indirme
- Orijinal kaliteyi koruma, hiçbir kalite kaybı yaşatmadan
- Video çözünürlüğü ve format seçimi (MP4, WebM vb.)
- Videoların meta verilerini kaydetme (başlık, kanal ismi, tarih)
- Modern, sade ve duyarlı (responsive) arayüz
- Sürükle-bırak ve panodan otomatik URL algılama
- İndirme ilerleme çubuğu
- Çapraz platform desteği (Windows, Linux, macOS)
- FFmpeg ile yüksek kaliteli MP3 dönüşümü

## Gereksinimler

- Python 3.6+
- PyQt6
- yt-dlp
- FFmpeg (MP3 dönüşümü için)

## Kurulum

Detaylı kurulum adımları için [INSTALLATION.md](INSTALLATION.md) dosyasına bakın.

Hızlı kurulum:

1. Python 3.6 veya daha yüksek bir sürüm kurun
2. Projeyi klonlayın: `git clone https://github.com/GITHUB_KULLANICI_ADI/youtube-indirici.git`
3. Gerekli kütüphaneleri yükleyin: `pip install -r requirements.txt`
4. FFmpeg'i kurun (MP3 ve yüksek kaliteli video indirmek için gerekli):
   - Windows: [FFmpeg İndirme Sayfası](https://www.gyan.dev/ffmpeg/builds/)
   - MacOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`

## Kullanım

Uygulamayı başlatmak için:

```bash
python main.py
```

1. YouTube video URL'sini yapıştırın veya sürükleyip bırakın
2. "Bilgi Al" butonuna tıklayarak video bilgilerini alın
3. İndirmek istediğiniz format türünü (video veya ses) seçin
4. Video indiriyorsanız, istediğiniz kalite/format seçeneğini belirleyin
5. İndirme konumunu ayarlayın
6. "İndir" butonuna tıklayın ve indirme tamamlanana kadar bekleyin

## Geliştirme

### Proje Yapısı

- `main.py`: Ana uygulama girişi
- `src/core/`: İndirme motoru ve temel işlevsellik
- `src/ui/`: Kullanıcı arayüzü bileşenleri
- `src/utils/`: Yardımcı fonksiyonlar ve araçlar

## Lisans

MIT

## Teşekkürler

- [yt-dlp](https://github.com/yt-dlp/yt-dlp): Güçlü YouTube indirme motoru
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/): Kullanıcı arayüzü çerçevesi
- [FFmpeg](https://ffmpeg.org/): Medya dönüştürücü 