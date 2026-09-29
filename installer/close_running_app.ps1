# Kurulum klasöründeki EXE'den çalışan bütün süreçleri kapatır ve bitmelerini bekler.
#
# Neden: uygulama pencere kapatılınca tepside sürüyor. Güncellemeyi bir kopya başlatınca
# güncelleme betiği yalnız o kopyanın kapanmasını bekliyordu; tepsideki öteki kopya EXE'yi
# kilitli tuttuğu için sessiz kurulum iptal oldu (2.7.0 -> 2.7.1'de görüldü).
# Yalnız tam olarak -ExePath yolundan çalışanlar kapatılır; başka klasördeki kopyaya dokunulmaz.
# Çıkış kodu 0: kapatılacak süreç kalmadı; 1: kapatılamadı, neden stderr'de.
param(
    [Parameter(Mandatory = $true)][string]$ExePath,
    [int]$TimeoutSeconds = 15
)

$ErrorActionPreference = 'Stop'
try {
    $name = [IO.Path]::GetFileName($ExePath)
    $procs = @(Get-CimInstance Win32_Process -Filter "Name='$name'" |
        Where-Object { $_.ExecutablePath -and ($_.ExecutablePath -ieq $ExePath) })
    foreach ($p in $procs) {
        # Arada kendiliğinden kapanmış olabilir; o durumda yapılacak bir şey yok.
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    foreach ($p in $procs) {
        Wait-Process -Id $p.ProcessId -Timeout $TimeoutSeconds -ErrorAction SilentlyContinue
        if (Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue) {
            throw "PID $($p.ProcessId) $TimeoutSeconds sn icinde kapanmadi"
        }
    }
    exit 0
} catch {
    [Console]::Error.WriteLine("Calisan uygulama kapatilamadi ($ExePath): $($_.Exception.Message)")
    exit 1
}
