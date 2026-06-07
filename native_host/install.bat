@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  YouTube Indirici — Native Messaging Host Kurulumu
echo ============================================================
echo.
echo Bu araç, Chrome eklentisinin masaüstü uygulaması olmadan
echo doğrudan indirme yapabilmesini sağlar.
echo.

:: ── Extension ID al ──────────────────────────────────────────────────────────
set /p EXT_ID=Chrome uzantı ID'nizi girin (chrome://extensions adresinden alın):
if "%EXT_ID%"=="" (
    echo Hata: Uzantı ID boş olamaz.
    pause & exit /b 1
)

:: ── Python bul ───────────────────────────────────────────────────────────────
set PYTHON_CMD=none

:: Önce venv içindeki Python'u dene
if exist "%~dp0..\venv\Scripts\python.exe" (
    set PYTHON_CMD=%~dp0..\venv\Scripts\python.exe
    goto :python_found
)

python --version >nul 2>&1
if %errorlevel% equ 0 ( set PYTHON_CMD=python & goto :python_found )

py --version >nul 2>&1
if %errorlevel% equ 0 ( set PYTHON_CMD=py & goto :python_found )

echo Hata: Python bulunamadi!
echo Python 3.8+ kurun veya sanal ortamdaki python.exe'nin yolu ayarlayın.
pause & exit /b 1

:python_found
echo Python bulundu: %PYTHON_CMD%

:: ── EXE mi kaynak kod mu? ────────────────────────────────────────────────────
set HOST_PATH=
set USE_EXE=0

if exist "%~dp0..\dist\YouTubeIndirici\YouTubeIndirici.exe" (
    :: EXE modunda ana uygulama --native-host bayrağıyla çalışır
    set HOST_PATH=%~dp0..\dist\YouTubeIndirici\native_host_wrapper.bat
    set USE_EXE=1
) else (
    :: Kaynak kod modu: wrapper.bat venv python + native_host.py çalıştırır
    set HOST_PATH=%~dp0wrapper.bat
)

:: ── Wrapper batch oluştur ────────────────────────────────────────────────────
if "%USE_EXE%"=="1" (
    (
        echo @echo off
        echo "%~dp0..\dist\YouTubeIndirici\YouTubeIndirici.exe" --native-host
    ) > "%~dp0..\dist\YouTubeIndirici\native_host_wrapper.bat"
    set HOST_PATH=%~dp0..\dist\YouTubeIndirici\native_host_wrapper.bat
) else (
    (
        echo @echo off
        echo "%PYTHON_CMD%" "%~dp0native_host.py"
    ) > "%~dp0wrapper.bat"
    set HOST_PATH=%~dp0wrapper.bat
)

:: ── Manifest JSON oluştur ────────────────────────────────────────────────────
:: Ters eğik çizgileri çift yap JSON için
set JSON_PATH=!HOST_PATH:\=\\!

set MANIFEST_PATH=%APPDATA%\Microsoft\NativeMessagingHosts
mkdir "%MANIFEST_PATH%" 2>nul

(
    echo {
    echo   "name": "com.youtube_indirici.host",
    echo   "description": "YouTube Indirici Native Messaging Host",
    echo   "path": "!JSON_PATH!",
    echo   "type": "stdio",
    echo   "allowed_origins": [
    echo     "chrome-extension://%EXT_ID%/"
    echo   ]
    echo }
) > "%MANIFEST_PATH%\com.youtube_indirici.host.json"

echo Manifest oluşturuldu: %MANIFEST_PATH%\com.youtube_indirici.host.json

:: ── Registry kaydı ───────────────────────────────────────────────────────────
set REG_KEY=HKCU\Software\Google\Chrome\NativeMessagingHosts\com.youtube_indirici.host
reg add "%REG_KEY%" /ve /t REG_SZ /d "%MANIFEST_PATH%\com.youtube_indirici.host.json" /f >nul 2>&1

if %errorlevel% equ 0 (
    echo Registry kaydı eklendi.
) else (
    echo UYARI: Registry kaydı eklenemedi. Lütfen yönetici olarak çalıştırın.
)

:: Edge için de kaydet (opsiyonel)
set REG_KEY_EDGE=HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.youtube_indirici.host
reg add "%REG_KEY_EDGE%" /ve /t REG_SZ /d "%MANIFEST_PATH%\com.youtube_indirici.host.json" /f >nul 2>&1

echo.
echo ============================================================
echo  Kurulum tamamlandi!
echo.
echo  Artık masaüstü uygulaması açık olmasa da Chrome eklentisi
echo  üzerinden indirme yapabilirsiniz.
echo  Dosyalar: %USERPROFILE%\Downloads\YDL Indirilenler\
echo ============================================================
echo.
pause
