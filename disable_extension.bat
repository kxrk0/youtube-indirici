@echo off
:: Tarayıcı eklentisi / native messaging host'u tamamen kaldırır.
:: Uygulama artık yalnızca masaüstü GUI üzerinden elle URL ile çalışır.
setlocal
cd /d "%~dp0"

echo ============================================================
echo  YDL İndirici — Tarayıcı Eklentisi Kaldırma
echo ============================================================
echo.

:: 1) Chrome + Edge native messaging registry kayıtlarını sil
set REG_KEY_CHROME=HKCU\Software\Google\Chrome\NativeMessagingHosts\com.youtube_indirici.host
set REG_KEY_EDGE=HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.youtube_indirici.host

reg delete "%REG_KEY_CHROME%" /f >nul 2>&1
if %errorlevel%==0 ( echo [OK] Chrome native host kaydı silindi. ) else ( echo [--] Chrome kaydı bulunamadı/atlandı. )

reg delete "%REG_KEY_EDGE%" /f >nul 2>&1
if %errorlevel%==0 ( echo [OK] Edge native host kaydı silindi. ) else ( echo [--] Edge kaydı bulunamadı/atlandı. )

:: 2) Manifest dosyasını sil (native_host klasörü içinde)
if exist "native_host\com.youtube_indirici.host.json" (
    del /f /q "native_host\com.youtube_indirici.host.json" >nul 2>&1
    echo [OK] Native host manifest silindi.
)

echo.
echo Tamamlandı. Tarayıcı eklentisi artık uygulamaya bağlanamaz.
echo Masaüstü uygulamasını (install_and_run.bat) çalıştırıp URL'yi elle girin.
echo.
pause
