; YouTube Studio Downloader kurucusu (NSIS 3, Unicode).
; Derleme: installer/build_release.py (sürümü ve dist klasörünü /D ile verir).
;
; Kullanıcı klasörüne kurulur (yönetici izni gerekmez): uygulama ayar ve geçmişini EXE'nin
; yanına (cache\) yazıyor, kendi kendini güncellerken de aynı klasöre yazabilmeli.
; Sessiz kurulum (güncelleyici):  Kurulum.exe /S /D=C:\kurulu\klasör

Unicode true
ManifestDPIAware true
RequestExecutionLevel user
SetCompressor /SOLID lzma

!ifndef VERSION
  !error "VERSION tanımlı değil: makensis /DVERSION=2.6.2 /DDIST=... /DOUTFILE=..."
!endif
!ifndef DIST
  !error "DIST tanımlı değil: PyInstaller çıktısı (dist\YouTubeIndirici)"
!endif
!ifndef OUTFILE
  !error "OUTFILE tanımlı değil"
!endif

!define APP_NAME "YouTube Studio Downloader"
!define APP_EXE "YouTubeIndirici.exe"
!define APP_KEY "YouTubeIndirici"
!define PUBLISHER "kxrk0"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}"

Name "${APP_NAME}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\${APP_KEY}"
InstallDirRegKey HKCU "Software\${APP_KEY}" "InstallDir"
BrandingText "${APP_NAME} ${VERSION}"

VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "FileDescription" "${APP_NAME} kurulumu"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "CompanyName" "${PUBLISHER}"
VIAddVersionKey "LegalCopyright" "${PUBLISHER}"

!include "MUI2.nsh"

!define MUI_ICON "..\assets\app.ico"
!define MUI_UNICON "..\assets\app.ico"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "${APP_NAME}'ı aç"

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Turkish"

; Uygulama açıkken EXE kilitli; üzerine yazılamaz. Kullanıcıya kapatmasını söyler.
; Sessiz kurulumda (güncelleyici) betik uygulamanın kapanmasını zaten bekliyor; yine açıksa iptal.
!macro WAIT_FOR_APP_CLOSED
  wait_app:
    IfFileExists "$INSTDIR\${APP_EXE}" 0 app_closed
    ClearErrors
    FileOpen $0 "$INSTDIR\${APP_EXE}" a
    IfErrors 0 app_unlocked
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "${APP_NAME} açık. Kapatıp (bildirim alanındaki simgeden Çıkış) Yeniden Dene'ye bas." /SD IDCANCEL IDRETRY wait_app
    Abort
  app_unlocked:
    FileClose $0
  app_closed:
!macroend

Section "Uygulama" SecApp
  SectionIn RO
  SetOutPath "$INSTDIR"
  !insertmacro WAIT_FOR_APP_CLOSED

  ; Eski sürümün kitaplıkları kalmasın. cache\ (ayarlar, geçmiş, kapaklar) korunur.
  RMDir /r "$INSTDIR\_internal"
  File /r "${DIST}\*"

  WriteUninstaller "$INSTDIR\Kaldir.exe"
  WriteRegStr HKCU "Software\${APP_KEY}" "InstallDir" "$INSTDIR"

  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME} kaldır.lnk" "$INSTDIR\Kaldir.exe"

  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Kaldir.exe"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\Kaldir.exe" /S'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  !insertmacro WAIT_FOR_APP_CLOSED
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APP_NAME}"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\Kaldir.exe"
  ; cache\ (indirme geçmişi, ayarlar) kullanıcının verisi; sorup siler.
  IfFileExists "$INSTDIR\cache\*.*" 0 keep_data
    MessageBox MB_YESNO|MB_ICONQUESTION "İndirme geçmişi ve ayarlar da silinsin mi? İndirdiğin dosyalara dokunulmaz." /SD IDNO IDNO keep_data
    RMDir /r "$INSTDIR\cache"
  keep_data:
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  DeleteRegKey HKCU "Software\${APP_KEY}"
SectionEnd
