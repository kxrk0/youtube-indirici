#!/bin/bash

echo "============================================"
echo "YouTube İndirici Kurulum ve Çalıştırma Aracı"
echo "============================================"
echo

# Python kontrolü - farklı komutları dene
PYTHON_CMD=""

echo "Python komutları kontrol ediliyor..."

# python3 komutunu dene
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    echo "Python3 bulundu!"
# python komutu dene
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    echo "Python bulundu!"
# py komutu dene
elif command -v py &> /dev/null; then
    PYTHON_CMD="py"
    echo "Py bulundu!"
else
    echo "Python bulunamadı! Lütfen Python 3.6 veya daha yeni bir sürüm kurun."
    echo "Python yüklü olmasına rağmen bu hatayı alıyorsanız:"
    echo "1. Terminalden 'python --version', 'python3 --version' veya 'py --version' komutlarını deneyerek hangisinin çalıştığını kontrol edin"
    echo "2. Python'un PATH'e eklendiğinden emin olun"
    echo
    echo "Python indirme sayfası: https://www.python.org/downloads/"
    exit 1
fi

# Sanal ortam oluşturma
if [ ! -d "venv" ]; then
    echo "Sanal ortam oluşturuluyor..."
    $PYTHON_CMD -m venv venv
fi

# Sanal ortamı aktifleştirme
source venv/bin/activate

# Bağımlılıkları kurma
echo "Bağımlılıklar kuruluyor..."
pip install -r requirements.txt || $PYTHON_CMD -m pip install -r requirements.txt

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
$PYTHON_CMD main.py

# Temizlik
deactivate

echo
read -p "Devam etmek için Enter tuşuna basın..." key 