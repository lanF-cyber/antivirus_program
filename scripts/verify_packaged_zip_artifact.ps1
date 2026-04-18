param(
    [Parameter(Mandatory = $true)]
    [string]$RunDirectory
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$generatorScript = "scripts/verify_packaged_zip_artifact.ps1"
$verificationBasis = "zip-level verification is based on archive entry inspection only, not extraction-based runtime validation."
$expectedReproducibilityProfile = "normalized-zip-v1"
$expectedNormalizedEntryTimestampUtc = "2000-01-01T00:00:00Z"
$expectedNormalizedEntryTimestamp = [DateTimeOffset]::ParseExact(
    $expectedNormalizedEntryTimestampUtc,
    "yyyy-MM-ddTHH:mm:ssZ",
    [System.Globalization.CultureInfo]::InvariantCulture,
    [System.Globalization.DateTimeStyles]::AssumeUniversal
)

function Write-Check {
    param(
        [ValidateSet("PASS", "WARN", "FAIL")]
        [string]$Level,
        [string]$Label,
        [string]$Message
    )

    $prefix = "[$Level]"
    switch ($Level) {
        "PASS" { Write-Host "$prefix $Label - $Message" -ForegroundColor Green }
        "WARN" { Write-Host "$prefix $Label - $Message" -ForegroundColor Yellow }
        "FAIL" { Write-Host "$prefix $Label - $Message" -ForegroundColor Red }
    }
}

function Register-Result {
    param(
        [ValidateSet("PASS", "WARN", "FAIL")]
        [string]$Level,
        [string]$Label,
        [string]$Message
    )

    switch ($Level) {
        "PASS" { $script:passCount += 1 }
        "WARN" { $script:warnCount += 1 }
        "FAIL" { $script:failCount += 1 }
    }

    $script:checkResults += [ordered]@{
        label = $Label
        status = $Level
        message = $Message
    }

    Write-Check -Level $Level -Label $Label -Message $Message
}

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

function Get-NormalizedZipEntryName {
    param([string]$Value)

    $normalized = Normalize-PathFragment $Value
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return $null
    }

    return $normalized
}

function Test-RequiredFileEntry {
    param(
        [string[]]$ArtifactRelativeEntries,
        [string]$RelativePath
    )

    $normalized = (Normalize-PathFragment $RelativePath).Trim('/')
    return ($ArtifactRelativeEntries -contains $normalized)
}

function Test-RequiredDirectoryEntry {
    param(
        [string[]]$ArtifactRelativeEntries,
        [string]$RelativePath
    )

    $normalized = (Normalize-PathFragment $RelativePath).Trim('/')
    if ($ArtifactRelativeEntries -contains $normalized) {
        return $true
    }

    foreach ($entry in $ArtifactRelativeEntries) {
        if ($entry.StartsWith($normalized + "/")) {
            return $true
        }
    }

    return $false
}

function Get-NormalizedEntryNamesHash {
    param([string[]]$NormalizedEntryNames)

    $joinedNames = $NormalizedEntryNames -join "`n"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($joinedNames)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hashBytes = $sha256.ComputeHash($bytes)
        return ([System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLowerInvariant())
    } finally {
        $sha256.Dispose()
    }
}

function Test-NormalizedArchiveTimestamp {
    param(
        [Parameter(Mandatory = $true)]
        [DateTimeOffset]$Timestamp,

        [Parameter(Mandatory = $true)]
        [DateTimeOffset]$ExpectedTimestamp
    )

    return (
        $Timestamp.Year -eq $ExpectedTimestamp.Year -and
        $Timestamp.Month -eq $ExpectedTimestamp.Month -and
        $Timestamp.Day -eq $ExpectedTimestamp.Day -and
        $Timestamp.Hour -eq $ExpectedTimestamp.Hour -and
        $Timestamp.Minute -eq $ExpectedTimestamp.Minute -and
        $Timestamp.Second -eq $ExpectedTimestamp.Second
    )
}

$script:passCount = 0
$script:warnCount = 0
$script:failCount = 0
$script:checkResults = @()

$runDirectoryPath = Resolve-RunDirectoryPath $RunDirectory
$assemblyRecordPath = Join-Path $runDirectoryPath "assembly-record.json"
$fingerprintPath = Join-Path $runDirectoryPath "artifact-fingerprint.json"
$zipCheckPath = Join-Path $runDirectoryPath "zip-check.json"

if (-not (Test-Path -LiteralPath $assemblyRecordPath -PathType Leaf)) {
    throw "assembly-record.json was not found in $runDirectoryPath."
}

if (-not (Test-Path -LiteralPath $fingerprintPath -PathType Leaf)) {
    throw "artifact-fingerprint.json was not found in $runDirectoryPath."
}

$assemblyRecord = Get-Content -LiteralPath $assemblyRecordPath -Raw | ConvertFrom-Json
$fingerprintRecord = Get-Content -LiteralPath $fingerprintPath -Raw | ConvertFrom-Json
$artifactRootName = [string]$assemblyRecord.artifact_root_name
$expectedZipName = $artifactRootName + ".zip"
$expectedArtifactRootPath = Join-Path $runDirectoryPath $artifactRootName
$expectedZipPath = Join-Path $runDirectoryPath $expectedZipName
$zipPath = [string]$fingerprintRecord.zip_path

$zipExists = Test-Path -LiteralPath $zipPath -PathType Leaf
$fingerprintFindings = @()
if ([System.IO.Path]::GetFullPath([string]$assemblyRecord.run_directory) -ne $runDirectoryPath) {
    $fingerprintFindings += "assembly-record run_directory does not match the requested run directory"
}
if ([System.IO.Path]::GetFullPath([string]$assemblyRecord.artifact_root_path) -ne $expectedArtifactRootPath) {
    $fingerprintFindings += "assembly-record artifact_root_path does not match the requested run directory"
}
if ([System.IO.Path]::GetFullPath([string]$fingerprintRecord.run_directory) -ne $runDirectoryPath) {
    $fingerprintFindings += "artifact-fingerprint run_directory does not match the requested run directory"
}
if (-not $zipExists) {
    $fingerprintFindings += "zip file is missing"
}
if ([System.IO.Path]::GetFullPath($zipPath) -ne $expectedZipPath) {
    $fingerprintFindings += "zip path does not match the requested run directory"
}
if ([System.IO.Path]::GetFileName($zipPath) -ne $expectedZipName) {
    $fingerprintFindings += "zip filename does not match artifact_root_name"
}
if ([string]$fingerprintRecord.zip_name -ne $expectedZipName) {
    $fingerprintFindings += "artifact-fingerprint zip_name does not match artifact_root_name"
}
if ([string]$fingerprintRecord.zip_sha256_algorithm -ne "sha256") {
    $fingerprintFindings += "artifact-fingerprint zip_sha256_algorithm must be 'sha256'"
}

if ($zipExists) {
    $zipHash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
    if ($zipHash.Hash.ToLowerInvariant() -ne ([string]$fingerprintRecord.zip_sha256).ToLowerInvariant()) {
        $fingerprintFindings += "zip_sha256 does not match the actual archive hash"
    }

    $zipItem = Get-Item -LiteralPath $zipPath
    if ([int64]$zipItem.Length -ne [int64]$fingerprintRecord.size_bytes) {
        $fingerprintFindings += "size_bytes does not match the actual archive size"
    }
}

if ($fingerprintFindings.Count -eq 0) {
    Register-Result "PASS" "Fingerprint" "Zip fingerprint metadata is present and matches the archive."
} else {
    Register-Result "FAIL" "Fingerprint" ($fingerprintFindings -join "; ")
}

$normalizedEntryNames = @()
$artifactRelativeEntries = @()
$topLevelSegments = @()
$actualEntryTimestamps = @()

if ($zipExists) {
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        foreach ($entry in $archive.Entries) {
            $normalizedEntryName = Get-NormalizedZipEntryName $entry.FullName
            if ([string]::IsNullOrWhiteSpace($normalizedEntryName)) {
                continue
            }

            $normalizedEntryNames += $normalizedEntryName
            $actualEntryTimestamps += $entry.LastWriteTime
            $trimmedEntry = $normalizedEntryName.Trim('/')
            if ([string]::IsNullOrWhiteSpace($trimmedEntry)) {
                continue
            }

            $segments = $trimmedEntry.Split('/')
            if ($segments.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($segments[0])) {
                $topLevelSegments += $segments[0]
            }

            if ($trimmedEntry -eq $artifactRootName) {
                continue
            }

            $prefix = $artifactRootName + "/"
            if ($trimmedEntry.StartsWith($prefix)) {
                $artifactRelativeEntries += $trimmedEntry.Substring($prefix.Length)
            }
        }
    } finally {
        $archive.Dispose()
    }
}

$topLevelDirectories = @($topLevelSegments | Sort-Object -Unique)
$actualArchiveEntryCount = $normalizedEntryNames.Count
$zipRootFindings = @()
if (-not $zipExists) {
    $zipRootFindings += "zip file is missing"
} else {
    if ($topLevelDirectories.Count -ne 1) {
        $zipRootFindings += "archive must contain exactly one top-level directory"
    } elseif ($topLevelDirectories[0] -ne $artifactRootName) {
        $zipRootFindings += "top-level directory name must equal artifact_root_name"
    }
}

if ($zipRootFindings.Count -eq 0) {
    Register-Result "PASS" "Zip root" "Archive contains exactly one normalized top-level directory with the expected name."
} else {
    Register-Result "FAIL" "Zip root" ($zipRootFindings -join "; ")
}

$expectedNormalizedEntryNames = @()
if ($zipExists -and $topLevelDirectories.Count -eq 1 -and $topLevelDirectories[0] -eq $artifactRootName) {
    $rootEntry = $artifactRootName + "/"
    $directoryEntries = @($normalizedEntryNames | Where-Object {
        $_ -ne $rootEntry -and $_.EndsWith("/")
    } | Sort-Object)
    $fileEntries = @($normalizedEntryNames | Where-Object {
        -not $_.EndsWith("/")
    } | Sort-Object)
    $expectedNormalizedEntryNames = @($rootEntry) + $directoryEntries + $fileEntries
}

$entryOrderStatus = "not_checked"
$entryOrderFindings = @()
if (-not $zipExists) {
    $entryOrderFindings += "zip file is missing"
} elseif ($expectedNormalizedEntryNames.Count -eq 0) {
    $entryOrderFindings += "expected normalized entry sequence could not be derived"
} else {
    $actualSequence = $normalizedEntryNames -join "`n"
    $expectedSequence = $expectedNormalizedEntryNames -join "`n"
    if ($actualSequence -ne $expectedSequence) {
        $entryOrderFindings += "archive entries are not stored in normalized-zip-v1 order"
        $entryOrderStatus = "invalid"
    } else {
        $entryOrderStatus = "valid"
    }
}

if ($entryOrderFindings.Count -eq 0) {
    Register-Result "PASS" "Entry order" "Archive entries follow the normalized-zip-v1 sequence."
} else {
    Register-Result "FAIL" "Entry order" ($entryOrderFindings -join "; ")
}

$timestampFindings = @()
if (-not $zipExists) {
    $timestampFindings += "zip file is missing"
} else {
    foreach ($timestamp in $actualEntryTimestamps) {
        if (-not (Test-NormalizedArchiveTimestamp -Timestamp $timestamp -ExpectedTimestamp $expectedNormalizedEntryTimestamp)) {
            $timestampFindings += "archive entry timestamps are not normalized"
            break
        }
    }
}

if ($timestampFindings.Count -eq 0) {
    Register-Result "PASS" "Entry timestamps" "Archive entry timestamps are normalized."
} else {
    Register-Result "FAIL" "Entry timestamps" ($timestampFindings -join "; ")
}

$requiredFileEntries = @(
    "README.md",
    "pyproject.toml",
    "config/scanbox.toml",
    "config/clamav/freshclam.conf",
    "rules/yara/manifest.json",
    "rules/capa/manifest.json",
    "scripts/verify_env.ps1",
    "docs/dependencies.md",
    "rules/capa/bundled/LICENSE.txt"
)
$requiredDirectoryEntries = @(
    "runtime/scanbox"
)

$requiredEntryFindings = @()
foreach ($relativePath in $requiredFileEntries) {
    if (-not (Test-RequiredFileEntry -ArtifactRelativeEntries $artifactRelativeEntries -RelativePath $relativePath)) {
        $requiredEntryFindings += "missing required file: $relativePath"
    }
}
foreach ($relativePath in $requiredDirectoryEntries) {
    if (-not (Test-RequiredDirectoryEntry -ArtifactRelativeEntries $artifactRelativeEntries -RelativePath $relativePath)) {
        $requiredEntryFindings += "missing required directory: $relativePath"
    }
}

if ($requiredEntryFindings.Count -eq 0) {
    Register-Result "PASS" "Required entries" "Required artifact-root-relative archive entries are present."
} else {
    Register-Result "FAIL" "Required entries" ($requiredEntryFindings -join "; ")
}

$forbiddenEntries = @(
    "scripts/verify_release_readiness.ps1",
    "scripts/acceptance_v1.ps1",
    "scripts/acceptance_v2_quarantine.ps1",
    "scripts/acceptance_v2_directory.ps1"
)

$forbiddenEntryFindings = @()
foreach ($relativePath in $forbiddenEntries) {
    if (Test-RequiredFileEntry -ArtifactRelativeEntries $artifactRelativeEntries -RelativePath $relativePath) {
        $forbiddenEntryFindings += "unexpected forbidden file: $relativePath"
    }
}

if ($forbiddenEntryFindings.Count -eq 0) {
    Register-Result "PASS" "Forbidden entries" "Maintainer-only scripts are absent from the archive."
} else {
    Register-Result "FAIL" "Forbidden entries" ($forbiddenEntryFindings -join "; ")
}

$actualNormalizedEntryNamesHash = if ($zipExists) {
    Get-NormalizedEntryNamesHash -NormalizedEntryNames $normalizedEntryNames
} else {
    $null
}

$profileFindings = @()
if ([string]$fingerprintRecord.zip_reproducibility_profile -ne $expectedReproducibilityProfile) {
    $profileFindings += "zip_reproducibility_profile must be '$expectedReproducibilityProfile'"
}
if ([string]$fingerprintRecord.normalized_entry_timestamp_utc -ne $expectedNormalizedEntryTimestampUtc) {
    $profileFindings += "normalized_entry_timestamp_utc must be '$expectedNormalizedEntryTimestampUtc'"
}
if ([int]$fingerprintRecord.archive_entry_count -ne $actualArchiveEntryCount) {
    $profileFindings += "archive_entry_count does not match the actual archive entry count"
}
if ([string]$fingerprintRecord.top_level_root_name -ne $artifactRootName) {
    $profileFindings += "top_level_root_name does not match artifact_root_name"
}
if ([string]$fingerprintRecord.normalized_entry_names_sha256 -ne $actualNormalizedEntryNamesHash) {
    $profileFindings += "normalized_entry_names_sha256 does not match the actual normalized entry sequence"
}

if ($profileFindings.Count -eq 0) {
    Register-Result "PASS" "Reproducibility profile" "Fingerprint reproducibility fields match the normalized archive profile."
} else {
    Register-Result "FAIL" "Reproducibility profile" ($profileFindings -join "; ")
}

$overall = if ($failCount -gt 0) { "FAIL" } elseif ($warnCount -gt 0) { "WARN" } else { "PASS" }
$zipCheckRecord = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    generator_script = $generatorScript
    run_directory = $runDirectoryPath
    zip_path = $zipPath
    overall = $overall
    pass_count = $passCount
    warn_count = $warnCount
    fail_count = $failCount
    verification_basis = $verificationBasis
    reproducibility_profile = $expectedReproducibilityProfile
    normalized_entry_timestamp_utc = $expectedNormalizedEntryTimestampUtc
    actual_archive_entry_count = $actualArchiveEntryCount
    actual_normalized_entry_names_sha256 = $actualNormalizedEntryNamesHash
    entry_order_status = $entryOrderStatus
    checks = $checkResults
}

$zipCheckRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $zipCheckPath -Encoding utf8

Write-Host ""
Write-Host "Summary: OVERALL=$overall PASS=$passCount WARN=$warnCount FAIL=$failCount"

if ($failCount -gt 0) {
    exit 1
}

exit 0
