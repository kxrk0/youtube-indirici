# YouTube İndirici - Kurulum Talimatları

Bu belge, YouTube İndirici uygulaması ve tarayıcı eklentisinin kurulumu için adım adım talimatları içerir.

## Gereksinimler

- Python 3.6 veya üzeri
- Tarayıcı eklentisi için Chrome/Edge/Firefox (Manifest V3 destekli)
- FFmpeg (MP3 dönüşümü ve yüksek kaliteli video indirmek için)

## 1. Python Uygulaması Kurulumu

### 1.1. Python'u Yükleme

Eğer sisteminizde Python kurulu değilse, [Python resmi web sitesinden](https://www.python.org/downloads/) işletim sisteminize uygun Python sürümünü indirin ve kurun.

### 1.2. Uygulamayı İndirme

Uygulamayı GitHub üzerinden klonlayın veya ZIP olarak indirin:

```bash
git clone https://github.com/GITHUB_KULLANICI_ADI/youtube-indirici.git
cd youtube-indirici
```

### 1.3. Sanal Ortam Oluşturma (İsteğe Bağlı ama Önerilir)

Sanal ortam oluşturarak paketleri izole bir şekilde kurmak daha sağlıklıdır:

Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 1.4. Bağımlılıkları Kurma

Gerekli Python paketlerini yükleyin:

```bash
pip install -r requirements.txt
```

### 1.5. FFmpeg Kurulumu

FFmpeg, MP3 dönüşümü ve yüksek kaliteli video indirme için gereklidir.

**Windows:**
1. [FFmpeg indirme sayfasından](https://www.gyan.dev/ffmpeg/builds/) essentials build'i indirin
2. Dosyaları çıkartın ve `bin` klasörünü sisteminizin PATH değişkenine ekleyin
   - Alternatif olarak, FFmpeg klasörünü `ffmpeg` olarak bu projedeki ana dizine kopyalayabilirsiniz

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt update
sudo apt install ffmpeg
```

## 2. Tarayıcı Eklentisi Kurulumu

### 2.1. Geliştirici Modunda Yükleme

**Chrome / Edge:**
1. Tarayıcınızda `chrome://extensions` (Chrome) veya `edge://extensions` (Edge) adresine gidin
2. Sağ üst köşeden "Geliştirici modu"nu aktifleştirin
3. "Paketlenmemiş öğe yükle" butonuna tıklayın
4. Bu projedeki `extension` klasörünü seçin

**Firefox:**
1. `about:debugging#/runtime/this-firefox` adresine gidin
2. "Geçici Eklenti Yükle" butonuna tıklayın
3. `extension` klasöründeki `manifest.json` dosyasını seçin

### 2.2. Eklenti İzinlerini Onaylama

Tarayıcınız, eklentinin istediği izinleri onaylamanızı isteyecektir. "İzin ver" butonuna tıklayarak izinleri onaylayın.

## 3. Uygulamayı Çalıştırma

### 3.1. Python Uygulamasını Başlatma

Windows:
```bash
run.bat
```

macOS/Linux:
```bash
./run.sh
```

veya doğrudan:
```bash
python main.py
```

### 3.2. Eklentiyi Kullanma

1. Herhangi bir YouTube video sayfasına gidin
2. Video oynatıcısının altındaki kontrol panelinde "İndir" butonunu göreceksiniz
3. Bu butona tıkladığınızda bir dropdown menü açılacak
4. İstediğiniz kalite veya ses formatını seçin
5. Seçim yaptığınızda, Python uygulaması indirmeyi otomatik olarak başlatacaktır

## 4. Sorun Giderme

### Python Uygulaması Sorunları

- **Bağımlılıklar yüklenirken hata alıyorsanız:** pip sürümünüzü güncelleyin `pip install --upgrade pip`
- **FFmpeg bulunamadı hatası:** FFmpeg'in kurulu olduğundan veya PATH değişkenine eklendiğinden emin olun
- **Uygulama başlarken hata alıyorsanız:** Konsol çıktısını kontrol edin ve hata mesajlarını inceleyin

### Tarayıcı Eklentisi Sorunları

- **İndir butonu görünmüyor:** YouTube'un arayüz değişikliklerinden kaynaklanabilir. Tarayıcıyı yenileyin veya sayfayı tekrar yükleyin
- **İndirme başlatılamadı:** Python uygulamasının çalıştığından emin olun
- **CORS hatası:** Python uygulamasının çalıştığı portu (5000) kontrol edin ve güvenlik duvarı ayarlarını kontrol edin

### Sık Karşılaşılan Hatalar

- **"Python uygulamasına bağlanılamadı" hatası:** Python uygulamasının çalıştığından ve 5000 portunu dinlediğinden emin olun
- **"Geçersiz URL" hatası:** YouTube URL'sinin doğru olduğundan emin olun
- **İndirme başlıyor ama tamamlanmıyor:** FFmpeg'in doğru kurulduğundan emin olun

## İletişim ve Destek

Sorunlar, öneriler veya katkılar için:
- GitHub üzerinden issue açın
- E-posta: ornekmail@example.com 