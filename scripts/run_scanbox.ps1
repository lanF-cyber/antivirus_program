param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScanboxArgs
)

$ErrorActionPreference = "Stop"
$artifactRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$runtimeRoot = Join-Path $artifactRoot "runtime"
$runtimePackageRoot = Join-Path $runtimeRoot "scanbox"
$repoPackageRoot = Join-Path $artifactRoot "src\scanbox"

function Resolve-ArtifactPath {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return [System.IO.Path]::GetFullPath($Value)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $artifactRoot $Value))
}

$hasArtifactRuntime = Test-Path -LiteralPath $runtimePackageRoot -PathType Container
$hasRepoRuntime = Test-Path -LiteralPath $repoPackageRoot -PathType Container

if (-not $hasArtifactRuntime -or $hasRepoRuntime) {
    throw "scripts/run_scanbox.ps1 only supports unpacked artifact context with runtime/scanbox present and src/scanbox absent."
}

$pythonResolved = Resolve-ArtifactPath $PythonExe
if (-not $pythonResolved -or -not (Test-Path -LiteralPath $pythonResolved -PathType Leaf)) {
    throw "Python executable was not found. Use .\.venv\Scripts\python.exe or pass -PythonExe with a valid path."
}

$pathSeparator = [System.IO.Path]::PathSeparator
$originalPythonPath = $env:PYTHONPATH
$effectivePythonPath = if ([string]::IsNullOrWhiteSpace($originalPythonPath)) {
    [string]$runtimeRoot
} else {
    ([string]$runtimeRoot + $pathSeparator + $originalPythonPath)
}

Push-Location $artifactRoot
try {
    $env:PYTHONPATH = $effectivePythonPath
    & $pythonResolved -m scanbox @ScanboxArgs
    exit $LASTEXITCODE
} finally {
    if ($null -eq $originalPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $originalPythonPath
    }
    Pop-Location
}
