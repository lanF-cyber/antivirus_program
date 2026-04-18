param(
    [Parameter(Mandatory = $true)]
    [string]$RunDirectory
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$generatorScript = "scripts/package_packaging_staging_tree.ps1"
$stagingVerifyScript = Join-Path $root "scripts\verify_packaging_staging_tree.ps1"

function Resolve-RunDirectoryPath {
    param([string]$Value)

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return [System.IO.Path]::GetFullPath($Value)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $root $Value))
}

function Normalize-PathFragment {
    param([string]$Value)

    if ($null -eq $Value) {
        return $null
    }

    return (($Value -replace '\\', '/').Trim())
}

function Get-NormalizedRelativePath {
    param(
        [string]$BasePath,
        [string]$TargetPath
    )

    $resolvedBase = (Resolve-Path -LiteralPath $BasePath).Path.TrimEnd('\')
    $resolvedTarget = (Resolve-Path -LiteralPath $TargetPath).Path
    $basePrefix = $resolvedBase + '\'

    if ($resolvedTarget.StartsWith($basePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        return (Normalize-PathFragment $resolvedTarget.Substring($basePrefix.Length))
    }

    $baseUri = [System.Uri]($basePrefix)
    $targetUri = [System.Uri]($resolvedTarget)
    $relative = [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($targetUri).ToString())
    return (Normalize-PathFragment $relative)
}

function Invoke-StagingVerify {
    param(
        [string]$RunDirectoryPath,
        [string]$SmokeCheckPath
    )

    & powershell -ExecutionPolicy Bypass -File $stagingVerifyScript -RunDirectory $RunDirectoryPath
    $exitCode = $LASTEXITCODE

    if (-not (Test-Path -LiteralPath $SmokeCheckPath -PathType Leaf)) {
        throw "Staging verify did not produce $SmokeCheckPath."
    }

    $smokeCheckRecord = Get-Content -LiteralPath $SmokeCheckPath -Raw | ConvertFrom-Json
    if ($exitCode -ne 0) {
        throw "Staging verify failed for $RunDirectoryPath. Zip packaging refuses non-PASS staging runs."
    }

    if ($smokeCheckRecord.overall -ne "PASS") {
        throw "Staging verify overall result must be PASS before zip packaging. Current result: $($smokeCheckRecord.overall)."
    }

    return $smokeCheckRecord
}

function New-ZipFromArtifactRoot {
    param(
        [string]$ArtifactRootPath,
        [string]$ArtifactRootName,
        [string]$ZipPath
    )

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }

    $zipStream = [System.IO.File]::Open($ZipPath, [System.IO.FileMode]::CreateNew)
    try {
        $archive = New-Object System.IO.Compression.ZipArchive($zipStream, [System.IO.Compression.ZipArchiveMode]::Create, $false)
        try {
            $null = $archive.CreateEntry(($ArtifactRootName + "/"))

            $directories = @(Get-ChildItem -LiteralPath $ArtifactRootPath -Recurse -Force -Directory | Sort-Object FullName)
            foreach ($directory in $directories) {
                $relativePath = Get-NormalizedRelativePath -BasePath $ArtifactRootPath -TargetPath $directory.FullName
                $entryName = $ArtifactRootName + "/" + ($relativePath.Trim('/') + "/")
                $null = $archive.CreateEntry($entryName)
            }

            $files = @(Get-ChildItem -LiteralPath $ArtifactRootPath -Recurse -Force -File | Sort-Object FullName)
            foreach ($file in $files) {
                $relativePath = Get-NormalizedRelativePath -BasePath $ArtifactRootPath -TargetPath $file.FullName
                $entryName = $ArtifactRootName + "/" + $relativePath.Trim('/')
                $null = [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                    $archive,
                    $file.FullName,
                    $entryName,
                    [System.IO.Compression.CompressionLevel]::Optimal
                )
            }
        } finally {
            $archive.Dispose()
        }
    } finally {
        $zipStream.Dispose()
    }
}

$runDirectoryPath = Resolve-RunDirectoryPath $RunDirectory
$assemblyRecordPath = Join-Path $runDirectoryPath "assembly-record.json"
$smokeCheckPath = Join-Path $runDirectoryPath "smoke-check.json"
$fingerprintPath = Join-Path $runDirectoryPath "artifact-fingerprint.json"

if (-not (Test-Path -LiteralPath $assemblyRecordPath -PathType Leaf)) {
    throw "assembly-record.json was not found in $runDirectoryPath."
}

$assemblyRecord = Get-Content -LiteralPath $assemblyRecordPath -Raw | ConvertFrom-Json
$artifactRootPath = [System.IO.Path]::GetFullPath([string]$assemblyRecord.artifact_root_path)
$artifactRootName = [string]$assemblyRecord.artifact_root_name
$expectedArtifactRootPath = Join-Path $runDirectoryPath $artifactRootName
$recordedRunDirectory = [System.IO.Path]::GetFullPath([string]$assemblyRecord.run_directory)
$recordedSmokeCheckPath = if ([string]::IsNullOrWhiteSpace([string]$assemblyRecord.smoke_check_path)) {
    $smokeCheckPath
} else {
    [System.IO.Path]::GetFullPath([string]$assemblyRecord.smoke_check_path)
}

if ([string]::IsNullOrWhiteSpace($artifactRootName)) {
    throw "assembly-record.json does not contain artifact_root_name."
}

if ($recordedRunDirectory -ne $runDirectoryPath) {
    throw "assembly-record.json run_directory does not match the requested run directory."
}

if ($artifactRootPath -ne $expectedArtifactRootPath) {
    throw "assembly-record.json artifact_root_path does not match the requested run directory."
}

if ($recordedSmokeCheckPath -ne $smokeCheckPath) {
    throw "assembly-record.json smoke_check_path does not match the requested run directory."
}

if (-not (Test-Path -LiteralPath $artifactRootPath -PathType Container)) {
    throw "Artifact root path does not exist: $artifactRootPath"
}

if ((Split-Path -Leaf $artifactRootPath) -ne $artifactRootName) {
    throw "Artifact root path leaf does not match artifact_root_name."
}

$stagingVerifyRecord = Invoke-StagingVerify -RunDirectoryPath $runDirectoryPath -SmokeCheckPath $smokeCheckPath

$zipName = $artifactRootName + ".zip"
$zipPath = Join-Path $runDirectoryPath $zipName
New-ZipFromArtifactRoot -ArtifactRootPath $artifactRootPath -ArtifactRootName $artifactRootName -ZipPath $zipPath

if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
    throw "Zip packaging did not produce $zipPath."
}

$zipHash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
$zipItem = Get-Item -LiteralPath $zipPath

$fingerprintRecord = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    generator_script = $generatorScript
    run_directory = $runDirectoryPath
    artifact_root_name = $artifactRootName
    artifact_root_path = $artifactRootPath
    zip_name = $zipName
    zip_path = $zipPath
    version = $assemblyRecord.version
    platform = $assemblyRecord.platform
    source_commit = $assemblyRecord.source_commit
    manifest_source = $assemblyRecord.manifest_source
    manifest_version = $assemblyRecord.manifest_version
    zip_sha256_algorithm = "sha256"
    zip_sha256 = $zipHash.Hash.ToLowerInvariant()
    size_bytes = [int64]$zipItem.Length
    staging_verify_path = $smokeCheckPath
    staging_verify_overall = $stagingVerifyRecord.overall
}

$fingerprintRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $fingerprintPath -Encoding utf8

Write-Host "Packaging zip created."
Write-Host "Run directory: $runDirectoryPath"
Write-Host "Zip artifact: $zipPath"
Write-Host "Artifact fingerprint: $fingerprintPath"
