@echo off
cd /d "%~dp0"

echo ============================================
echo YouTube Indirici - EXE Derleme Araci
echo ============================================
echo.

:: Mod: "clean" argümani verilirse sifirdan derle, yoksa artimli (hizli) derle
set BUILD_MODE=incremental
if /i "%1"=="clean" set BUILD_MODE=clean
if /i "%1"=="--clean" set BUILD_MODE=clean

:: Python kontrolü
set PYTHON_CMD=none
python --version >nul 2>&1
if %errorlevel% equ 0 (set PYTHON_CMD=python) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (set PYTHON_CMD=py) else (
        echo Python bulunamadi! Lutfen Python 3.8+ kurun.
        pause & exit /b 1
    )
)

:: Sanal ortam
if not exist venv\ (
    echo Sanal ortam olusturuluyor...
    %PYTHON_CMD% -m venv venv
)
call venv\Scripts\activate.bat

:: Bagimliliklar (sadece eksikse)
if not exist venv\.build_deps_ok (
    echo Bagimliliklar kuruluyor...
    pip install -r requirements.txt -q
    pip install pyinstaller pillow -q
    echo. > venv\.build_deps_ok
) else (
    echo Bagimliliklar zaten kurulu, atlaniyor.
)

:: ICO ikonu olustur (yoksa)
if not exist extension\icons\app.ico (
    echo Uygulama ikonu olusturuluyor...
    %PYTHON_CMD% create_icon.py
)

:: Temizlik sadece --clean modunda
if "%BUILD_MODE%"=="clean" (
    echo Temizlik yapiliyor ^(sifirdan derleme^)...
    if exist dist\YouTubeIndirici rmdir /s /q dist\YouTubeIndirici
    if exist build\YouTubeIndirici rmdir /s /q build\YouTubeIndirici
    echo.
    echo EXE derleniyor... ^(ilk derleme: 3-5 dakika^)
    pyinstaller youtube_indirici.spec --clean --noconfirm
) else (
    echo.
    echo EXE guncelleniyor... ^(artimli derleme: ~30-60 saniye^)
    pyinstaller youtube_indirici.spec --noconfirm
)

if %errorlevel% neq 0 (
    echo.
    echo HATA: Derleme basarisiz!
    echo Tam yeniden derleme icin: build_exe.bat --clean
    pause
    exit /b 1
)

echo.
echo ============================================
echo EXE guncellendi: dist\YouTubeIndirici\YouTubeIndirici.exe
echo ============================================
echo.

:: FFmpeg'i dist klasorune kopyala (yoksa)
if not exist dist\YouTubeIndirici\ffmpeg\bin\ffmpeg.exe (
    for /d %%D in (ffmpeg*) do (
        if exist "%%D\bin\ffmpeg.exe" (
            echo FFmpeg kopyalaniyor...
            xcopy /e /i /q "%%D" "dist\YouTubeIndirici\%%D" >nul
            goto :ffmpeg_copied
        )
    )
    if exist "ffmpeg\bin\ffmpeg.exe" (
        xcopy /e /i /q "ffmpeg" "dist\YouTubeIndirici\ffmpeg" >nul
        echo FFmpeg kopyalandi.
    )
)
:ffmpeg_copied

:: Portable mod isareti
if not exist dist\YouTubeIndirici\portable.flag (
    echo. > dist\YouTubeIndirici\portable.flag
)

:: Native Messaging wrapper olustur (eklenti bagimsiz mod icin)
echo Native Messaging wrapper olusturuluyor...
(
    echo @echo off
    echo "%~dp0dist\YouTubeIndirici\YouTubeIndirici.exe" --native-host
) > dist\YouTubeIndirici\native_host_wrapper.bat

:: Native host kurulum scriptini dist'e kopyala
if exist native_host\install.bat (
    copy /y native_host\install.bat dist\YouTubeIndirici\install_native_host.bat >nul
    echo Native host kurulum scripti kopyalandi: dist\YouTubeIndirici\install_native_host.bat
)

echo.
echo ============================================
echo EXE olusturuldu: dist\YouTubeIndirici\YouTubeIndirici.exe
echo.
echo Eklentiyi bagimsiz kullanmak icin:
echo   dist\YouTubeIndirici\install_native_host.bat
echo ============================================
echo.
pause
