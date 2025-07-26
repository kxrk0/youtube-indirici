# Kurulum Kılavuzu

Bu kılavuz, YouTube İndirici uygulamasını kurma ve çalıştırma adımlarını açıklamaktadır.

## Gereksinimler

* Python 3.6 veya daha yeni
* Git (opsiyonel, sadece klonlama için gerekli)
* FFmpeg (MP3 dönüşümü ve yüksek kaliteli video indirme için)

## Adım 1: Projeyi İndir

İki şekilde projeyi indirebilirsin:

### A) Git ile Klonlama (Önerilen)

```bash
git clone https://github.com/GITHUB_KULLANICI_ADI/youtube-indirici.git
cd youtube-indirici
```

### B) ZIP olarak İndirme

1. GitHub deposuna git (https://github.com/GITHUB_KULLANICI_ADI/youtube-indirici)
2. "Code" butonuna tıkla ve "Download ZIP" seçeneğini seç
3. ZIP dosyasını indirip istediğin bir klasöre çıkart
4. Komut satırında çıkarttığın klasöre git:
   ```bash
   cd youtube-indirici
   ```

## Adım 2: Python Sanal Ortamı Oluştur (Opsiyonel ama Önerilen)

### Windows için:

```bash
python -m venv venv
venv\Scripts\activate
```

### macOS / Linux için:

```bash
python3 -m venv venv
source venv/bin/activate
```

## Adım 3: Bağımlılıkları Kur

```bash
# Windows için:
pip install -r requirements.txt

# macOS / Linux için:
pip3 install -r requirements.txt
```

## Adım 4: FFmpeg Kur

FFmpeg, MP3 dönüşümü ve yüksek kaliteli video indirme için gereklidir.

### Windows için:

1. [FFmpeg resmi sitesinden](https://www.ffmpeg.org/download.html) veya [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) adresinden indirin
2. İndirilen zip dosyasını açın
3. "bin" klasöründeki üç dosyayı (ffmpeg.exe, ffplay.exe, ffprobe.exe) uygulama ana klasörüne kopyalayın

Alternatif olarak, [Chocolatey](https://chocolatey.org/) kullanıyorsanız:
```bash
choco install ffmpeg
```

### macOS için:

```bash
brew install ffmpeg
```

### Linux için:

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg
```

## Adım 5: Uygulamayı Çalıştır

### Windows için:

```bash
# Komut satırı ile:
python main.py

# veya direkt olarak:
.\run.bat
```

### macOS / Linux için:

```bash
# Çalıştırma izni ver:
chmod +x run.sh

# Çalıştır:
./run.sh

# veya direkt olarak:
python3 main.py
```

## Sorun Giderme

1. **"pip is not recognized" hatası alıyorsanız:**
   - Alternatif olarak `python -m pip install -r requirements.txt` komutu deneyin
   
2. **FFmpeg bulunamadı uyarısı alıyorsanız:**
   - FFmpeg dosyalarının doğru konuma kopyalandığını kontrol edin
   - FFmpeg'in sistem PATH'ine eklenip eklenmediğini kontrol edin

3. **PyQt6 kurulum hatası alıyorsanız:**
   - Visual C++ veya diğer derleme araçlarını kurmanız gerekebilir
   - `pip install PyQt6-Qt6 PyQt6-sip` komutunu ayrı ayrı çalıştırmayı deneyin

4. **MP3 indirme çalışmıyorsa:**
   - FFmpeg'in doğru kurulduğundan emin olun

## Güncelleme

Proje güncellemelerini almak için:

```bash
git pull origin main
pip install -r requirements.txt  # Yeni bağımlılıkları güncelle
```

## İletişim

Herhangi bir sorun yaşarsanız, GitHub üzerinden issue açabilir veya bana direkt mesaj gönderebilirsiniz. 