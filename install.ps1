# CodeGPT Installer — run with: irm https://raw.githubusercontent.com/ArukuX/codegpt/main/install.ps1 | iex
# Installs ai.exe to %LOCALAPPDATA%\codegpt\ and adds to PATH

$ErrorActionPreference = "Stop"

$repo = "ArukuX/codegpt"
$installDir = "$env:LOCALAPPDATA\codegpt"
$exeName = "ai.exe"
$exePath = "$installDir\$exeName"

Write-Host ""
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║  CodeGPT Installer                   ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Step 1: Get latest release
Write-Host "  [1/4] Fetching latest release..." -ForegroundColor Yellow
try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest" -Headers @{ "User-Agent" = "CodeGPT-Installer" }
    $version = $release.tag_name
    $asset = $release.assets | Where-Object { $_.name -eq $exeName } | Select-Object -First 1

    if (-not $asset) {
        Write-Host "  ERROR: No ai.exe found in release $version" -ForegroundColor Red
        exit 1
    }

    Write-Host "  Found version $version" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Cannot reach GitHub. Check internet." -ForegroundColor Red
    exit 1
}

# Step 2: Download
Write-Host "  [2/4] Downloading ai.exe..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

try {
    $downloadUrl = $asset.browser_download_url
    Invoke-WebRequest -Uri $downloadUrl -OutFile $exePath -UseBasicParsing
    Write-Host "  Downloaded to $exePath" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Download failed: $_" -ForegroundColor Red
    exit 1
}

# Step 3: Add to PATH
Write-Host "  [3/4] Adding to PATH..." -ForegroundColor Yellow
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")

if ($userPath -notlike "*$installDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$installDir", "User")
    $env:Path = "$env:Path;$installDir"
    Write-Host "  Added $installDir to user PATH" -ForegroundColor Green
} else {
    Write-Host "  Already in PATH" -ForegroundColor Green
}

# Step 4: Verify
Write-Host "  [4/4] Verifying..." -ForegroundColor Yellow
try {
    $ver = & $exePath --version 2>&1
    Write-Host "  Installed: $ver" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: Verify failed, but binary is installed" -ForegroundColor Yellow
}

# Check Ollama
Write-Host ""
if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
    Write-Host "  Ollama: found" -ForegroundColor Green
} else {
    Write-Host "  Ollama: not found — install from https://ollama.com" -ForegroundColor Yellow
    Write-Host "  Then run: ollama pull llama3.2" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║  Installation complete!               ║" -ForegroundColor Green
Write-Host "  ║                                       ║" -ForegroundColor Green
Write-Host "  ║  Open a new terminal and type: ai     ║" -ForegroundColor Green
Write-Host "  ║                                       ║" -ForegroundColor Green
Write-Host "  ║  Commands:                            ║" -ForegroundColor Green
Write-Host "  ║    ai          — start chat            ║" -ForegroundColor Green
Write-Host "  ║    ai update   — update to latest      ║" -ForegroundColor Green
Write-Host "  ║    ai doctor   — check dependencies    ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
