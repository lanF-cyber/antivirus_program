param(
    [string]$FreshClamExe = "freshclam.exe",
    [switch]$UpdateClamDb
)

$ErrorActionPreference = "Stop"

Write-Host "ScanBox explicit update helper"
Write-Host "This script does not run automatically."
Write-Host "Use official sources and pinned refs from docs\dependencies.md."

if ($UpdateClamDb) {
    Write-Host "Updating ClamAV database via freshclam..."
    & $FreshClamExe
}

Write-Host "For bundled YARA and capa rules, refresh the local snapshot manually from the pinned official refs."
