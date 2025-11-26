@echo off
echo ============================================
echo YouTube Indirici Kurulum ve Calistirma Araci
echo ============================================
echo.

:: Python kontrolü - farklı komutları dene
set PYTHON_CMD=none

:: "python" komutunu dene
echo Python komutu kontrol ediliyor...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    echo Python bulundu!
    goto :python_found
)

:: "py" komutunu dene
echo Py komutu kontrol ediliyor...
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    echo Py bulundu!
    goto :python_found
)

:: "python3" komutunu dene
echo Python3 komutu kontrol ediliyor...
python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python3
    echo Python3 bulundu!
    goto :python_found
)

:: Hiçbir Python komutu bulunamadıysa
echo Python bulunamadi! Lutfen Python 3.6 veya daha yeni bir surum kurun.
echo Python yuklu olmasina ragmen bu hatayi aliyorsaniz:
echo 1. Python kurulum sirasinda "Add Python to PATH" secenegini isaretlediginizden emin olun
echo 2. veya komut satirinda "python", "py" veya "python3" komutlarindan hangisinin calistigini kontrol edin
echo.
echo Python indirme sayfasi: https://www.python.org/downloads/
pause
exit /b 1

:python_found

:: Sanal ortam oluşturma
if not exist venv\ (
    echo Sanal ortam olusturuluyor...
    %PYTHON_CMD% -m venv venv
)

:: Sanal ortamı aktifleştirme
call venv\Scripts\activate.bat

:: Bağımlılıkları kurma
echo Bagimliliklar kuruluyor...
pip install -r requirements.txt || %PYTHON_CMD% -m pip install -r requirements.txt

:: FFmpeg kontrolü
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    if exist "ffmpeg-8.0.1-essentials_build\bin\ffmpeg.exe" (
        echo Yerel FFmpeg bulundu.
    ) else (
        echo FFmpeg bulunamadi! MP3 donusumu ve yuksek kaliteli video indirme icin gerekli.
        echo Uygulamayi yine de calistiracagiz, ancak bu ozellikler calismayabilir.
        echo.
    )
)

:: Uygulamayı çalıştırma
echo.
echo YouTube Indirici baslatiliyor...
%PYTHON_CMD% main.py

:: Temizlik
call venv\Scripts\deactivate.bat

echo.
pause 