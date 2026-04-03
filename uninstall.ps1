# CodeGPT Uninstaller
$installDir = "$env:LOCALAPPDATA\codegpt"

Write-Host "Uninstalling CodeGPT..." -ForegroundColor Yellow

# Remove binary
if (Test-Path $installDir) {
    Remove-Item -Recurse -Force $installDir
    Write-Host "  Removed $installDir" -ForegroundColor Green
}

# Remove from PATH
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -like "*$installDir*") {
    $newPath = ($userPath.Split(";") | Where-Object { $_ -ne $installDir }) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "  Removed from PATH" -ForegroundColor Green
}

# Ask about data
$answer = Read-Host "  Delete user data (~/.codegpt)? (y/n)"
if ($answer -eq "y") {
    $dataDir = "$HOME\.codegpt"
    if (Test-Path $dataDir) {
        Remove-Item -Recurse -Force $dataDir
        Write-Host "  Removed $dataDir" -ForegroundColor Green
    }
}

Write-Host "Uninstalled." -ForegroundColor Green
