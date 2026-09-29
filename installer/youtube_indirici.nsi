; YouTube Studio Downloader kurucusu (NSIS 3, Unicode).
; Derleme: installer/build_release.py (sürümü, dist klasörünü ve FFmpeg'i /D ile verir).
;
; Program Files'a kurulur (yönetici izni ister); ayar ve geçmiş kullanıcının
; %LOCALAPPDATA%\YouTubeIndirici klasöründe (src/utils/helpers.py get_data_dir).
; FFmpeg sistemde yoksa Program Files\FFmpeg'e kurulur ve sistem PATH'ine eklenir.
; Sessiz kurulum (güncelleyici):  Kurulum.exe /S /D=C:\kurulu\klasör

Unicode true
ManifestDPIAware true
RequestExecutionLevel admin
SetCompressor /SOLID lzma

!ifndef VERSION
  !error "VERSION tanımlı değil: makensis /DVERSION=2.7.0 /DDIST=... /DFFMPEG_DIR=... /DOUTFILE=..."
!endif
!ifndef DIST
  !error "DIST tanımlı değil: PyInstaller çıktısı (dist\YouTubeIndirici)"
!endif
!ifndef FFMPEG_DIR
  !error "FFMPEG_DIR tanımlı değil: ffmpeg.exe, ffprobe.exe ve LICENSE içeren klasör"
!endif
!ifndef OUTFILE
  !error "OUTFILE tanımlı değil"
!endif

!define APP_NAME "YouTube Studio Downloader"
!define APP_EXE "YouTubeIndirici.exe"
!define APP_KEY "YouTubeIndirici"
!define APP_REG_KEY "Software\${APP_KEY}"
!define PUBLISHER "kxrk0"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}"
; src/utils/helpers.py FFMPEG_INSTALL_SUBDIR ve DATA_DIR_NAME ile aynı olmalı.
!define FFMPEG_ROOT "$PROGRAMFILES64\FFmpeg"
!define DATA_DIR_NAME "YouTubeIndirici"
; PATH değişikliği duyurusunu işlemeyen (asılı) bir pencere kurulumu en çok bu kadar bekletir (ms).
!define SETTINGCHANGE_TIMEOUT_MS 5000

Name "${APP_NAME}"
OutFile "${OUTFILE}"
InstallDir "$PROGRAMFILES64\${APP_KEY}"
InstallDirRegKey HKLM "${APP_REG_KEY}" "InstallDir"
BrandingText "${APP_NAME} ${VERSION}"

VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "FileDescription" "${APP_NAME} kurulumu"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "CompanyName" "${PUBLISHER}"
VIAddVersionKey "LegalCopyright" "${PUBLISHER}"

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinMessages.nsh"

!define MUI_ICON "..\assets\app.ico"
!define MUI_UNICON "..\assets\app.ico"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "${APP_NAME}'ı aç"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchAppAsUser

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Turkish"

; 2.6.2–2.6.3 kurucusunun kullanıcı klasörü; boşsa eski kurulum yok.
Var LegacyDir
; Eski sürümün güncelleyicisi kurulumdan sonra eski klasördeki EXE'yi açmaya çalışır; o artık
; silindiği için yeni sürümü kurucu açar.
Var LaunchAfterSilent

; Uygulama açıkken EXE kilitli; üzerine yazılamaz. Kullanıcıya kapatmasını söyler.
; Sessiz kurulumda (güncelleyici) betik uygulamanın kapanmasını zaten bekliyor; yine açıksa iptal.
; Kullanım: Push "<klasör>" / Call [un.]WaitForAppClosed
!macro DEFINE_WAIT_FOR_APP_CLOSED UN
Function ${UN}WaitForAppClosed
  Exch $R0
  Push $0
  wait_app:
    IfFileExists "$R0\${APP_EXE}" 0 app_closed
    ClearErrors
    FileOpen $0 "$R0\${APP_EXE}" a
    IfErrors 0 app_unlocked
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "${APP_NAME} açık. Kapatıp (bildirim alanındaki simgeden Çıkış) Yeniden Dene'ye bas." /SD IDCANCEL IDRETRY wait_app
    Abort
  app_unlocked:
    FileClose $0
  app_closed:
  Pop $0
  Pop $R0
FunctionEnd
!macroend
!insertmacro DEFINE_WAIT_FOR_APP_CLOSED ""
!insertmacro DEFINE_WAIT_FOR_APP_CLOSED "un."

; FFmpeg klasörünü sistem PATH'ine ekler/çıkarır. Kullanım: !insertmacro FFMPEG_PATH Add|Remove
!macro FFMPEG_PATH ACTION
  InitPluginsDir
  File "/oname=$PLUGINSDIR\path_entry.ps1" "path_entry.ps1"
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$PLUGINSDIR\path_entry.ps1" -Action ${ACTION} -Dir "${FFMPEG_ROOT}\bin"'
  Pop $0
  ${If} $0 == 0
    SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=${SETTINGCHANGE_TIMEOUT_MS}
  ${Else}
    DetailPrint "FFmpeg PATH işlemi (${ACTION}) başarısız, sonuç: $0. Uygulama FFmpeg'i ${FFMPEG_ROOT}\bin içinde yine bulur."
  ${EndIf}
!macroend

Function .onInit
  StrCpy $LaunchAfterSilent 0
  ; Eski kurulum kullanıcıya özeldi (HKCU, %LOCALAPPDATA%).
  SetShellVarContext current
  ReadRegStr $LegacyDir HKCU "${APP_REG_KEY}" "InstallDir"
  ${If} $LegacyDir != ""
  ${AndIfNot} ${FileExists} "$LegacyDir\Kaldir.exe"
    StrCpy $LegacyDir ""
  ${EndIf}
  ; 2.6.x güncelleyicisi kurucuyu /D=<eski kullanıcı klasörü> ile çağırır; oraya değil Program Files'a kur.
  ${If} $LegacyDir != ""
  ${AndIf} $INSTDIR == $LegacyDir
    StrCpy $INSTDIR "$PROGRAMFILES64\${APP_KEY}"
  ${EndIf}
  ; Kısayollar herkesin masaüstüne ve Başlat menüsüne.
  SetShellVarContext all
FunctionEnd

Function LaunchAppAsUser
  ; Kurucu yönetici olarak çalışıyor; doğrudan açılan uygulama da yönetici olur ve sürükle-bırak,
  ; bildirimler gibi şeyler normal pencerelerle çalışmaz. Explorer üzerinden açılınca oturumun
  ; normal yetkisiyle ve Explorer'ın güncel PATH'iyle açılır.
  Exec '"$WINDIR\explorer.exe" "$INSTDIR\${APP_EXE}"'
FunctionEnd

Section "Uygulama" SecApp
  SectionIn RO
  Push "$INSTDIR"
  Call WaitForAppClosed

  ${If} $LegacyDir != ""
    Push "$LegacyDir"
    Call WaitForAppClosed
    ; Eski kaldırıcı kısayolları, kaydı ve dosyaları siler; cache\ (ayar, geçmiş) kalır ve
    ; uygulama ilk açılışta onu yeni veri klasörüne kopyalar (helpers.migrate_legacy_data).
    ExecWait '"$LegacyDir\Kaldir.exe" /S _?=$LegacyDir' $0
    ${If} $0 != 0
      DetailPrint "Eski kurulum ($LegacyDir) kaldırılamadı, sonuç: $0. Elle kaldırılabilir."
    ${Else}
      Delete "$LegacyDir\Kaldir.exe"
      RMDir "$LegacyDir"
    ${EndIf}
    StrCpy $LaunchAfterSilent 1
  ${EndIf}

  SetOutPath "$INSTDIR"
  ; Eski sürümün kitaplıkları kalmasın.
  RMDir /r "$INSTDIR\_internal"
  File /r "${DIST}\*"

  WriteUninstaller "$INSTDIR\Kaldir.exe"
  WriteRegStr HKLM "${APP_REG_KEY}" "InstallDir" "$INSTDIR"

  ; Kısayolun çalışma klasörü SetOutPath'ten gelir.
  SetOutPath "$INSTDIR"
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME} kaldır.lnk" "$INSTDIR\Kaldir.exe"

  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Kaldir.exe"'
  WriteRegStr HKLM "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\Kaldir.exe" /S'
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair" 1
SectionEnd

Section "FFmpeg" SecFFmpeg
  SectionIn RO
  ; FFmpegOwned: FFmpeg'i bu kurucu koydu; güncellemede yenilenir, kaldırırken silinir.
  ReadRegStr $1 HKLM "${APP_REG_KEY}" "FFmpegOwned"
  SearchPath $0 "ffmpeg.exe"
  ${If} $1 != "1"
  ${AndIf} $0 != ""
    DetailPrint "FFmpeg zaten kurulu: $0"
    Return
  ${EndIf}

  ; Aynı yerde başkasının koyduğu FFmpeg varsa üzerine yazılmaz, yalnız PATH'e eklenir.
  ${If} $1 == "1"
  ${OrIfNot} ${FileExists} "${FFMPEG_ROOT}\bin\ffmpeg.exe"
    SetOutPath "${FFMPEG_ROOT}\bin"
    File "${FFMPEG_DIR}\ffmpeg.exe"
    File "${FFMPEG_DIR}\ffprobe.exe"
    SetOutPath "${FFMPEG_ROOT}"
    File "${FFMPEG_DIR}\LICENSE"
    WriteRegStr HKLM "${APP_REG_KEY}" "FFmpegOwned" "1"
  ${EndIf}
  !insertmacro FFMPEG_PATH Add
SectionEnd

Function .onInstSuccess
  ${If} ${Silent}
  ${AndIf} $LaunchAfterSilent == 1
    Call LaunchAppAsUser
  ${EndIf}
FunctionEnd

Function un.onInit
  SetShellVarContext all
FunctionEnd

Section "Uninstall"
  Push "$INSTDIR"
  Call un.WaitForAppClosed
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APP_NAME}"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\Kaldir.exe"
  RMDir "$INSTDIR"

  ReadRegStr $1 HKLM "${APP_REG_KEY}" "FFmpegOwned"
  ${If} $1 == "1"
    !insertmacro FFMPEG_PATH Remove
    Delete "${FFMPEG_ROOT}\bin\ffmpeg.exe"
    Delete "${FFMPEG_ROOT}\bin\ffprobe.exe"
    Delete "${FFMPEG_ROOT}\LICENSE"
    RMDir "${FFMPEG_ROOT}\bin"
    RMDir "${FFMPEG_ROOT}"
  ${EndIf}

  ; İndirme geçmişi ve ayarlar kaldıran kullanıcının verisi; sorup siler.
  SetShellVarContext current
  IfFileExists "$LOCALAPPDATA\${DATA_DIR_NAME}\*.*" 0 keep_data
    MessageBox MB_YESNO|MB_ICONQUESTION "İndirme geçmişi ve ayarlar da silinsin mi? İndirdiğin dosyalara dokunulmaz." /SD IDNO IDNO keep_data
    RMDir /r "$LOCALAPPDATA\${DATA_DIR_NAME}"
  keep_data:
  SetShellVarContext all

  DeleteRegKey HKLM "${UNINSTALL_KEY}"
  DeleteRegKey HKLM "${APP_REG_KEY}"
SectionEnd
