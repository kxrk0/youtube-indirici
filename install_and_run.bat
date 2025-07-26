@echo off
echo ============================================
echo YouTube Indirici Kurulum ve Calistirma Araci
echo ============================================
echo.

:: Python kontrolü
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python bulunamadi! Lutfen Python 3.6 veya daha yeni bir surum kurun.
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Sanal ortam oluşturma
if not exist venv\ (
    echo Sanal ortam olusturuluyor...
    python -m venv venv
)

:: Sanal ortamı aktifleştirme
call venv\Scripts\activate.bat

:: Bağımlılıkları kurma
echo Bagimliliklar kuruluyor...
pip install -r requirements.txt

:: FFmpeg kontrolü
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo FFmpeg bulunamadi! MP3 donusumu ve yuksek kaliteli video indirme icin gerekli.
    echo Uygulamayı yine de çalıştıracağız, ancak bu özellikler çalışmayabilir.
    echo.
)

:: Uygulamayı çalıştırma
echo.
echo YouTube Indirici baslatiliyor...
python main.py

:: Temizlik
call venv\Scripts\deactivate.bat

echo.
pause 