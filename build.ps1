# Build ai.exe locally
# Run: powershell -File build.ps1

$ErrorActionPreference = "Stop"

Write-Host "Building CodeGPT -> ai.exe" -ForegroundColor Cyan

# Install build deps
pip install pyinstaller requests rich prompt-toolkit

# Build
pyinstaller ai.spec --noconfirm

# Verify
if (Test-Path "dist\ai.exe") {
    $size = [math]::Round((Get-Item "dist\ai.exe").Length / 1MB, 1)
    Write-Host "Build complete: dist\ai.exe ($size MB)" -ForegroundColor Green
    & dist\ai.exe --version
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
