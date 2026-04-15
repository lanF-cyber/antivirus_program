param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

Write-Host "ScanBox setup check"

try {
    & $PythonExe --version
} catch {
    Write-Error "Python was not found on PATH. Install Python 3.11+ and rerun."
    exit 1
}

$configPath = Join-Path $PSScriptRoot "..\config\scanbox.toml"
if (-not (Test-Path $configPath)) {
    Write-Error "Missing config file: $configPath"
    exit 1
}

Write-Host "Python is available."
Write-Host "Config file found: $configPath"
Write-Host "Next steps:"
Write-Host "  1. Install Python requirements from requirements.txt and requirements-dev.txt"
Write-Host "  2. Install ClamAV and capa from official releases"
Write-Host "  3. Place or verify the bundled rules under rules\"
Write-Host "  4. Run scripts\verify_env.ps1"
