param(
    [Parameter()]
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")

function Resolve-RepoPath {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return [System.IO.Path]::GetFullPath($Value)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $root $Value))
}

function Restore-EnvVar {
    param(
        [string]$Name,
        [AllowNull()]
        [string]$Value
    )

    if ($null -eq $Value) {
        Remove-Item "Env:$Name" -ErrorAction SilentlyContinue
        return
    }

    Set-Item "Env:$Name" -Value $Value
}

$pythonResolved = Resolve-RepoPath $PythonExe
if (-not $pythonResolved -or -not (Test-Path -LiteralPath $pythonResolved)) {
    Write-Host "Python executable was not found: $PythonExe" -ForegroundColor Red
    exit 1
}

$timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssfffZ")
$runDirectory = Join-Path $root "reports\pytest-standalone\$timestamp"
$tempRoot = Join-Path $runDirectory "tmp-env"
$baseTemp = Join-Path $runDirectory "pytest-basetemp"
$cacheDir = Join-Path $runDirectory "pytest-cache"

New-Item -ItemType Directory -Force -Path $tempRoot, $baseTemp, $cacheDir | Out-Null

$originalTemp = $env:TEMP
$originalTmp = $env:TMP
$env:TEMP = $tempRoot
$env:TMP = $tempRoot

$pytestCommandArguments = @(
    "-m", "pytest",
    "-q",
    "--basetemp", $baseTemp,
    "-o", "cache_dir=$cacheDir"
)
if ($PytestArgs) {
    $pytestCommandArguments += $PytestArgs
}

Write-Host "python_exe=$pythonResolved"
Write-Host "run_directory=$runDirectory"
Write-Host "temp_root=$tempRoot"
Write-Host "basetemp=$baseTemp"
Write-Host "cache_dir=$cacheDir"

$exitCode = 1
try {
    & $pythonResolved @pytestCommandArguments
    $exitCode = $LASTEXITCODE
} finally {
    Restore-EnvVar -Name "TEMP" -Value $originalTemp
    Restore-EnvVar -Name "TMP" -Value $originalTmp
}

exit $exitCode
