# Kayıt defterindeki bir PATH değerine tek klasör ekler ya da çıkarır; kurucu FFmpeg için kullanıyor.
#
# Neden NSIS değil: standart NSIS dizeleri 1024 karakter. Daha uzun PATH yaygın; okuma o zaman
# boş dönüyor ve geri yazmak PATH'i siler.
# Neden [Environment]::SetEnvironmentVariable değil: değeri REG_SZ olarak yazıyor,
# %SystemRoot%\system32 gibi girdiler açılmaz olur.
#
# Önce -Dir'in bütün kopyaları çıkarılır (harf duyarsız, sondaki '\' yok sayılır): Add sonda
# tam bir kopya bırakır, tekrar çalıştırmak bir şey değiştirmez.
# Çıkış kodu 0: yapıldı (ya da değişecek bir şey yoktu); 1: başarısız, neden stderr'de.
param(
    [Parameter(Mandatory = $true)][ValidateSet('Add', 'Remove')][string]$Action,
    [Parameter(Mandatory = $true)][string]$Dir,
    [string]$RegistryKey = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
)

$ErrorActionPreference = 'Stop'
try {
    $key = Get-Item -LiteralPath $RegistryKey
    $hasPath = $key.GetValueNames() -contains 'Path'
    $old = if ($hasPath) { [string]$key.GetValue('Path', '', 'DoNotExpandEnvironmentNames') } else { '' }
    $kind = if ($hasPath) { $key.GetValueKind('Path') } else { [Microsoft.Win32.RegistryValueKind]::ExpandString }

    $target = $Dir.TrimEnd('\')
    $entries = @($old -split ';' | Where-Object { $_.TrimEnd('\') -ne $target })
    if ($Action -eq 'Add') {
        # Eski değer ';' ile bitiyorsa son girdi boş; arkasına eklemek PATH'e ';;' koyar.
        while ($entries.Count -gt 0 -and $entries[-1] -eq '') { $entries = @($entries | Select-Object -SkipLast 1) }
        $entries += $target
    }
    $new = $entries -join ';'

    if ($new -ceq $old) { exit 0 }
    if ($new -eq '') {
        Remove-ItemProperty -LiteralPath $RegistryKey -Name 'Path'
    } else {
        Set-ItemProperty -LiteralPath $RegistryKey -Name 'Path' -Value $new -Type $kind
    }
    exit 0
} catch {
    [Console]::Error.WriteLine("PATH ${Action} basarisiz ('$Dir', ${RegistryKey}): $($_.Exception.Message)")
    exit 1
}
