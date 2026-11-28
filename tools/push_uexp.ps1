# Одна команда: заливает Jeju_World.uexp в репозиторий через git (не через релизы).
#   powershell -ExecutionPolicy Bypass -File tools\push_uexp.ps1 -Source C:\path\Jeju_World.uexp
param([Parameter(Mandatory=$true)][string]$Source)

$ErrorActionPreference = "Stop"
$name   = Split-Path $Source -Leaf
$remote = "https://github.com/SamlKroll/mt_save.git"
$work   = Join-Path $env:TEMP ("uexp_" + [guid]::NewGuid().ToString("N").Substring(0,8))

Write-Host "== 1/4 клонирую репозиторий =="
git clone --depth 1 $remote "$work\repo" | Out-Null
Set-Location "$work\repo"
New-Item -ItemType Directory -Force -Path assets | Out-Null

$size = (Get-Item $Source).Length
Write-Host "== 2/4 $name : $size байт =="

if ($size -lt 95000000) {
    Write-Host "   файл меньше 95 МБ — кладу целиком"
    Copy-Item $Source "assets\$name"
} else {
    Write-Host "   файл большой — режу на части по 90 МБ"
    $fs = [System.IO.File]::OpenRead($Source)
    $buf = New-Object byte[] (90MB)
    $i = 0
    while (($read = $fs.Read($buf, 0, $buf.Length)) -gt 0) {
        $part = "assets\$name.part{0:D2}" -f $i
        $out  = New-Object byte[] $read
        [Array]::Copy($buf, $out, $read)
        [System.IO.File]::WriteAllBytes((Join-Path $work\repo $part), $out)
        Write-Host ("   {0}  {1} байт" -f $part, $read)
        $i++
    }
    $fs.Close()
}

Write-Host "== 3/4 коммит =="
git add assets
git -c user.name="upload" -c user.email="upload@local" commit -m "assets: $name for patching" | Out-Null

Write-Host "== 4/4 push =="
git push origin HEAD:main

Write-Host ""
Write-Host "готово. напиши в чат: залил"
Write-Host "временная копия: $work"
