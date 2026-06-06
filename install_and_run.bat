@echo off
:: Scriptin bulunduğu dizine geç (System32 veya başka yerden çalışma sorununu çözer)
cd /d "%~dp0"

echo ============================================
echo YouTube Indirici Kurulum ve Calistirma Araci
echo ============================================
echo.

:: Python kontrolü
set PYTHON_CMD=none

echo Python komutu kontrol ediliyor...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    echo Python bulundu!
    goto :python_found
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    echo Py bulundu!
    goto :python_found
)

python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python3
    echo Python3 bulundu!
    goto :python_found
)

echo Python bulunamadi! Lutfen Python 3.6+ kurun: https://www.python.org/downloads/
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
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo pip hatasi, dogrudan deneniyor...
    %PYTHON_CMD% -m pip install -r requirements.txt
)

:: FFmpeg kontrolü ve otomatik indirme
echo.
echo FFmpeg kontrol ediliyor...

:: Sistem FFmpeg'i kontrol et
where ffmpeg >nul 2>&1
if %errorlevel% equ 0 (
    echo Sistem FFmpeg bulundu.
    goto :ffmpeg_ok
)

:: Yerel FFmpeg klasörlerini kontrol et (ffmpeg*/bin/ffmpeg.exe)
for /d %%D in (ffmpeg*) do (
    if exist "%%D\bin\ffmpeg.exe" (
        echo Yerel FFmpeg bulundu: %%D
        goto :ffmpeg_ok
    )
)
if exist "ffmpeg\bin\ffmpeg.exe" (
    echo Yerel FFmpeg bulundu: ffmpeg\bin
    goto :ffmpeg_ok
)
if exist "ffmpeg-bin\ffmpeg.exe" (
    echo Yerel FFmpeg bulundu: ffmpeg-bin
    goto :ffmpeg_ok
)

:: FFmpeg yok — otomatik indir
echo FFmpeg bulunamadi. Otomatik indiriliyor...
echo (Bu islemi ilk seferinde 1-3 dakika surebilir, dosya ~80MB)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$url = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'; " ^
  "$out = 'ffmpeg-essentials.zip'; " ^
  "try { " ^
  "  Write-Host 'Indiriliyor: ' + $url; " ^
  "  Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing; " ^
  "  Write-Host 'Cikartiliyor...'; " ^
  "  Expand-Archive -Path $out -DestinationPath '.' -Force; " ^
  "  Remove-Item $out; " ^
  "  Write-Host 'FFmpeg kuruldu!'; " ^
  "} catch { " ^
  "  Write-Host 'HATA: FFmpeg indirilemedi - ' + $_.Exception.Message; " ^
  "}"

:: İndirme sonrası tekrar kontrol et
for /d %%D in (ffmpeg*) do (
    if exist "%%D\bin\ffmpeg.exe" (
        echo FFmpeg basariyla kuruldu: %%D
        goto :ffmpeg_ok
    )
)

echo UYARI: FFmpeg kurulamadi. MP3 donusumu ve yuksek kaliteli video calismayabilir.
echo Manuel kurulum: https://www.gyan.dev/ffmpeg/builds/
echo.

:ffmpeg_ok

:: Uygulamayı çalıştırma
echo.
echo YouTube Indirici baslatiliyor...
echo.
%PYTHON_CMD% main.py

:: Temizlik
call venv\Scripts\deactivate.bat

echo.
pause
