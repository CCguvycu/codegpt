# build-mobile.ps1 — package mobile.py as an Android APK via Flet.
#
# Prereqs (one-time):
#   pip install flet
#   Install Android Studio + accept SDK licenses
#   Set ANDROID_HOME and JAVA_HOME (Flet needs JDK 17+)
#
# Usage:
#   .\build-mobile.ps1               # debug APK
#   .\build-mobile.ps1 -Release      # release APK (unsigned)
#   .\build-mobile.ps1 -Clean        # nuke build/ first

param(
    [switch]$Release,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  CodeGPT Mobile — APK Build" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

# Sanity checks
if (-not (Get-Command flet -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'flet' not on PATH. Run: pip install flet" -ForegroundColor Red
    exit 1
}
if (-not $env:JAVA_HOME) {
    Write-Host "ERROR: JAVA_HOME not set. Set it to your JDK 17+ install." -ForegroundColor Red
    exit 1
}
if (-not $env:ANDROID_HOME) {
    Write-Host "ERROR: ANDROID_HOME not set. Install Android SDK + Android Studio first." -ForegroundColor Red
    exit 1
}

if ($Clean -and (Test-Path "build")) {
    Write-Host "▸ Cleaning build/" -ForegroundColor Yellow
    Remove-Item -Recurse -Force build
}

# Flet build needs an entry point. mobile.py is ours.
# It expects the app file to be importable; we pass it directly.
$buildArgs = @("build", "apk", "--module-name", "mobile")
if ($Release) {
    Write-Host "▸ Building RELEASE APK" -ForegroundColor Green
} else {
    Write-Host "▸ Building DEBUG APK" -ForegroundColor Green
    $buildArgs += "--build-mode", "debug"
}

Write-Host "▸ flet $($buildArgs -join ' ')" -ForegroundColor DarkGray
& flet @buildArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "BUILD FAILED (exit $LASTEXITCODE)" -ForegroundColor Red
    exit $LASTEXITCODE
}

# Locate output — filter by build-mode subpath instead of grabbing first match.
# Flet drops APKs under build/<...>/outputs/apk/{debug,release}/app-*.apk.
$expectedSubpath = if ($Release) { "outputs\apk\release" } else { "outputs\apk\debug" }
$apkCandidates = Get-ChildItem -Recurse -Filter "*.apk" -Path "build" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -like "*$expectedSubpath*" } |
    Sort-Object LastWriteTime -Descending
$apk = $apkCandidates | Select-Object -First 1
if (-not $apk) {
    # Fallback: any .apk under build/, newest first.
    $apk = Get-ChildItem -Recurse -Filter "*.apk" -Path "build" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($apk) {
        Write-Host "WARN: No APK found under $expectedSubpath, falling back to newest." -ForegroundColor Yellow
    }
}
if ($apk) {
    $sizeMB = [math]::Round($apk.Length / 1MB, 1)
    Write-Host ""
    Write-Host "==================================" -ForegroundColor Green
    Write-Host "  BUILD OK" -ForegroundColor Green
    Write-Host "==================================" -ForegroundColor Green
    Write-Host "  APK : $($apk.FullName)" -ForegroundColor White
    Write-Host "  Size: $sizeMB MB" -ForegroundColor White
    Write-Host ""
    Write-Host "Install on connected device:" -ForegroundColor Cyan
    Write-Host "  adb install -r `"$($apk.FullName)`"" -ForegroundColor White
} else {
    Write-Host "BUILD finished but no .apk found under build/" -ForegroundColor Yellow
}
