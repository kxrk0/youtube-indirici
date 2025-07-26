#!/bin/bash

echo "============================================"
echo "YouTube İndirici Kurulum ve Çalıştırma Aracı"
echo "============================================"
echo

# Python kontrolü
if ! command -v python3 &> /dev/null; then
    echo "Python 3 bulunamadı! Lütfen Python 3.6 veya daha yeni bir sürüm kurun."
    echo "https://www.python.org/downloads/"
    exit 1
fi

# Sanal ortam oluşturma
if [ ! -d "venv" ]; then
    echo "Sanal ortam oluşturuluyor..."
    python3 -m venv venv
fi

# Sanal ortamı aktifleştirme
source venv/bin/activate

# Bağımlılıkları kurma
echo "Bağımlılıklar kuruluyor..."
pip install -r requirements.txt

# FFmpeg kontrolü
if ! command -v ffmpeg &> /dev/null; then
    echo "FFmpeg bulunamadı! MP3 dönüşümü ve yüksek kaliteli video indirme için gerekli."
    echo "Aşağıdaki komutla kurabilirsiniz:"
    echo "  - Debian/Ubuntu: sudo apt install ffmpeg"
    echo "  - macOS: brew install ffmpeg"
    echo
    echo "Uygulamayı yine de çalıştıracağız, ancak bu özellikler çalışmayabilir."
    echo
fi

# Çalıştırma iznini ayarlama
chmod +x run.sh

# Uygulamayı çalıştırma
echo
echo "YouTube İndirici başlatılıyor..."
python3 main.py

# Temizlik
deactivate

echo
read -p "Devam etmek için Enter tuşuna basın..." key 