param(
    [string]$OutputRoot = ".\reports\packaging-staging",
    [ValidateSet("windows-x64")]
    [string]$Platform = "windows-x64",
    [switch]$SkipSmokeCheck
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$generatorScript = "scripts/assemble_packaging_staging_tree.ps1"

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

function New-UtcTimestamp {
    return [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
}

function Invoke-GitCapture {
    param([string[]]$Arguments)

    $output = & git @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    [pscustomobject]@{
        ExitCode = $exitCode
        Output = @($output)
        Text = (@($output) -join [Environment]::NewLine).Trim()
    }
}

function Get-ProjectVersion {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $lines = Get-Content -LiteralPath $Path
    $inProjectSection = $false
    foreach ($line in $lines) {
        if ($line -match '^\s*\[project\]\s*$') {
            $inProjectSection = $true
            continue
        }

        if ($inProjectSection -and $line -match '^\s*\[') {
            break
        }

        if ($inProjectSection -and $line -match '^\s*version\s*=\s*"([^"]+)"\s*$') {
            return $Matches[1]
        }
    }

    return $null
}

function Get-InitVersion {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $lines = Get-Content -LiteralPath $Path
    foreach ($line in $lines) {
        if ($line -match '^\s*__version__\s*=\s*"([^"]+)"\s*$') {
            return $Matches[1]
        }
    }

    return $null
}

function Get-NormalizedRelativePath {
    param(
        [string]$BasePath,
        [string]$TargetPath
    )

    $baseUri = [System.Uri]((Resolve-Path -LiteralPath $BasePath).Path.TrimEnd('\') + '\')
    $targetUri = [System.Uri](Resolve-Path -LiteralPath $TargetPath).Path
    $relative = [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($targetUri).ToString())
    return ($relative -replace '\\', '/')
}

function Get-ScopedExcludeReason {
    param(
        [string]$MappingSource,
        [string]$RelativePath,
        [bool]$IsDirectory
    )

    $pathParts = @($RelativePath -split '/')
    if ($pathParts -contains "__pycache__") {
        return "transient_python_cache"
    }

    if (-not $IsDirectory -and $RelativePath.ToLowerInvariant().EndsWith(".pyc")) {
        return "transient_python_bytecode"
    }

    if ($MappingSource -eq "rules/capa/bundled") {
        if ($RelativePath -eq ".gitattributes") {
            return "repo_service_metadata"
        }
        if ($RelativePath -eq "README.md") {
            return "vendored_readme_not_required"
        }
        if ($RelativePath -eq ".github" -or $RelativePath.StartsWith(".github/")) {
            return "repo_service_metadata"
        }
    }

    return $null
}

function Copy-FileMapping {
    param(
        [string]$SourcePath,
        [string]$DestinationPath
    )

    $result = [ordered]@{
        copied_count = 0
        skipped_count = 0
        failed_count = 0
        notes = @()
    }

    try {
        if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
            $result.failed_count = 1
            $result.notes += "required_source_missing"
            return $result
        }

        $destinationParent = Split-Path -Parent $DestinationPath
        New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
        Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
        $result.copied_count = 1
        return $result
    } catch {
        $result.failed_count = 1
        $result.notes += $_.Exception.Message
        return $result
    }
}

function Copy-DirectoryMapping {
    param(
        [string]$SourcePath,
        [string]$DestinationPath,
        [string]$MappingSource
    )

    $result = [ordered]@{
        copied_count = 0
        skipped_count = 0
        failed_count = 0
        notes = @()
    }

    if (-not (Test-Path -LiteralPath $SourcePath -PathType Container)) {
        $result.failed_count = 1
        $result.notes += "required_source_missing"
        return $result
    }

    New-Item -ItemType Directory -Force -Path $DestinationPath | Out-Null

    $items = Get-ChildItem -LiteralPath $SourcePath -Force
    foreach ($item in $items) {
        $relativePath = Get-NormalizedRelativePath -BasePath $SourcePath -TargetPath $item.FullName
        $excludeReason = Get-ScopedExcludeReason -MappingSource $MappingSource -RelativePath $relativePath -IsDirectory $item.PSIsContainer
        if ($excludeReason) {
            $result.skipped_count += 1
            continue
        }

        if ($item.PSIsContainer) {
            $childDestination = Join-Path $DestinationPath $item.Name
            $childResult = Copy-DirectoryMapping -SourcePath $item.FullName -DestinationPath $childDestination -MappingSource $MappingSource
            $result.copied_count += [int]$childResult.copied_count
            $result.skipped_count += [int]$childResult.skipped_count
            $result.failed_count += [int]$childResult.failed_count
            $result.notes += @($childResult.notes)
            continue
        }

        try {
            $destinationFile = Join-Path $DestinationPath $item.Name
            Copy-Item -LiteralPath $item.FullName -Destination $destinationFile -Force
            $result.copied_count += 1
        } catch {
            $result.failed_count += 1
            $result.notes += $_.Exception.Message
        }
    }

    return $result
}

function Get-MappingStatus {
    param(
        [int]$CopiedCount,
        [int]$SkippedCount,
        [int]$FailedCount
    )

    if ($FailedCount -gt 0) {
        return "failed"
    }
    if ($CopiedCount -gt 0 -and $SkippedCount -gt 0) {
        return "copied_with_skips"
    }
    if ($CopiedCount -gt 0) {
        return "copied"
    }
    if ($SkippedCount -gt 0) {
        return "skipped_only"
    }
    return "copied_empty"
}

$pyprojectPath = Join-Path $root "pyproject.toml"
$initPath = Join-Path $root "src\scanbox\__init__.py"
$pyprojectVersion = Get-ProjectVersion -Path $pyprojectPath
$initVersion = Get-InitVersion -Path $initPath

if ([string]::IsNullOrWhiteSpace($pyprojectVersion)) {
    throw "Could not parse [project].version from pyproject.toml."
}

if ([string]::IsNullOrWhiteSpace($initVersion)) {
    throw "Could not parse __version__ from src/scanbox/__init__.py."
}

if ($pyprojectVersion -ne $initVersion) {
    throw "Version mismatch: pyproject.toml='$pyprojectVersion' and src/scanbox/__init__.py='$initVersion'."
}

$version = $pyprojectVersion
$artifactRootName = "scanbox-v$version-$Platform"
$outputRootResolved = Resolve-RepoPath $OutputRoot
$timestamp = New-UtcTimestamp
$runDirectory = Join-Path $outputRootResolved $timestamp
$artifactRootPath = Join-Path $runDirectory $artifactRootName
$assemblyRecordPath = Join-Path $runDirectory "assembly-record.json"
$smokeCheckPath = Join-Path $runDirectory "smoke-check.json"

New-Item -ItemType Directory -Force -Path $runDirectory | Out-Null
New-Item -ItemType Directory -Force -Path $artifactRootPath | Out-Null

$sourceCommit = "unavailable"
$gitHead = Invoke-GitCapture -Arguments @("rev-parse", "HEAD")
if ($gitHead.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($gitHead.Text)) {
    $sourceCommit = $gitHead.Text
}

$includeMappings = @(
    [ordered]@{ source = "README.md"; destination = "README.md"; kind = "file"; required = $true; notes = "operator-facing top-level entrypoint" },
    [ordered]@{ source = "pyproject.toml"; destination = "pyproject.toml"; kind = "file"; required = $true; notes = "version metadata visibility and traceability" },
    [ordered]@{ source = "src/scanbox"; destination = "runtime/scanbox"; kind = "directory"; required = $true; notes = "artifact-internal runtime subset" },
    [ordered]@{ source = "config/scanbox.toml"; destination = "config/scanbox.toml"; kind = "file"; required = $true; notes = "default config template" },
    [ordered]@{ source = "config/clamav/freshclam.conf"; destination = "config/clamav/freshclam.conf"; kind = "file"; required = $true; notes = "default freshclam template" },
    [ordered]@{ source = "rules/yara/bundled"; destination = "rules/yara/bundled"; kind = "directory"; required = $true; notes = "bundled YARA runtime content" },
    [ordered]@{ source = "rules/yara/manifest.json"; destination = "rules/yara/manifest.json"; kind = "file"; required = $true; notes = "YARA rule metadata" },
    [ordered]@{ source = "rules/capa/bundled"; destination = "rules/capa/bundled"; kind = "directory"; required = $true; notes = "bundled capa runtime content" },
    [ordered]@{ source = "rules/capa/manifest.json"; destination = "rules/capa/manifest.json"; kind = "file"; required = $true; notes = "capa rule metadata" },
    [ordered]@{ source = "scripts/verify_env.ps1"; destination = "scripts/verify_env.ps1"; kind = "file"; required = $true; notes = "operator-facing verification helper" },
    [ordered]@{ source = "docs/dependencies.md"; destination = "docs/dependencies.md"; kind = "file"; required = $true; notes = "operator-facing dependency reference" }
)

$excludeRules = @(
    [ordered]@{ pattern = "tests/**"; scope = "global"; reason = "repo_only"; priority = 1 },
    [ordered]@{ pattern = "reports/**"; scope = "global"; reason = "repo_only"; priority = 1 },
    [ordered]@{ pattern = ".git/**"; scope = "global"; reason = "repo_only"; priority = 1 },
    [ordered]@{ pattern = ".venv/**"; scope = "global"; reason = "repo_only"; priority = 1 },
    [ordered]@{ pattern = "scripts/acceptance_*.ps1"; scope = "global"; reason = "maintainer_only"; priority = 1 },
    [ordered]@{ pattern = "scripts/verify_release_readiness.ps1"; scope = "global"; reason = "maintainer_only"; priority = 1 },
    [ordered]@{ pattern = "docs/release-*.md"; scope = "global"; reason = "maintainer_only"; priority = 1 },
    [ordered]@{ pattern = "docs/milestones/**"; scope = "global"; reason = "maintainer_only"; priority = 1 },
    [ordered]@{ pattern = "config/scanbox.local.toml"; scope = "global"; reason = "local_override"; priority = 1 },
    [ordered]@{ pattern = "config/clamav/freshclam.local.conf"; scope = "global"; reason = "local_override"; priority = 1 },
    [ordered]@{ pattern = "**/__pycache__/**"; scope = "global"; reason = "transient_python_cache"; priority = 1 },
    [ordered]@{ pattern = "**/*.pyc"; scope = "global"; reason = "transient_python_bytecode"; priority = 1 },
    [ordered]@{ pattern = ".github/**"; scope = "rules/capa/bundled"; reason = "repo_service_metadata"; priority = 2 },
    [ordered]@{ pattern = ".gitattributes"; scope = "rules/capa/bundled"; reason = "repo_service_metadata"; priority = 2 },
    [ordered]@{ pattern = "README.md"; scope = "rules/capa/bundled"; reason = "vendored_readme_not_required"; priority = 2 }
)

$mappingResults = @()
$copySummary = [ordered]@{
    mapping_count = $includeMappings.Count
    copied_mappings = 0
    copied_with_skips_mappings = 0
    failed_mappings = 0
    copied_files = 0
    skipped_entries = 0
    failed_entries = 0
}

foreach ($mapping in $includeMappings) {
    $sourcePath = Join-Path $root $mapping.source
    $destinationPath = Join-Path $artifactRootPath ($mapping.destination -replace '/', '\')

    if ($mapping.kind -eq "file") {
        $result = Copy-FileMapping -SourcePath $sourcePath -DestinationPath $destinationPath
    } else {
        $result = Copy-DirectoryMapping -SourcePath $sourcePath -DestinationPath $destinationPath -MappingSource $mapping.source
    }

    $status = Get-MappingStatus -CopiedCount ([int]$result.copied_count) -SkippedCount ([int]$result.skipped_count) -FailedCount ([int]$result.failed_count)

    switch ($status) {
        "copied" { $copySummary.copied_mappings += 1 }
        "copied_with_skips" { $copySummary.copied_with_skips_mappings += 1 }
        default {
            if ([int]$result.failed_count -gt 0) {
                $copySummary.failed_mappings += 1
            }
        }
    }

    $copySummary.copied_files += [int]$result.copied_count
    $copySummary.skipped_entries += [int]$result.skipped_count
    $copySummary.failed_entries += [int]$result.failed_count

    $mappingResults += [ordered]@{
        source = $mapping.source
        destination = $mapping.destination
        kind = $mapping.kind
        status = $status
        copied_count = [int]$result.copied_count
        skipped_count = [int]$result.skipped_count
        failed_count = [int]$result.failed_count
        notes = @($result.notes | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    }
}

$assemblyRecord = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    generator_script = $generatorScript
    repo_root = [string]$root
    run_directory = $runDirectory
    artifact_root_name = $artifactRootName
    artifact_root_path = $artifactRootPath
    version = $version
    platform = $Platform
    source_commit = $sourceCommit
    version_sources = [ordered]@{
        pyproject_version = $pyprojectVersion
        init_version = $initVersion
    }
    include_mappings = $includeMappings
    exclude_rules = $excludeRules
    copy_summary = $copySummary
    mapping_results = $mappingResults
    smoke_check_path = $smokeCheckPath
}

$assemblyRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $assemblyRecordPath -Encoding utf8

if ($copySummary.failed_entries -gt 0) {
    throw "Assembly failed. See $assemblyRecordPath for mapping details."
}

if (-not $SkipSmokeCheck) {
    & powershell -ExecutionPolicy Bypass -File (Join-Path $root $generatorScript.Replace("assemble_packaging_staging_tree", "verify_packaging_staging_tree")) -RunDirectory $runDirectory
    if ($LASTEXITCODE -ne 0) {
        throw "Packaging smoke-check failed. See $smokeCheckPath for details."
    }
}

Write-Host "Packaging staging-tree assembled."
Write-Host "Run directory: $runDirectory"
Write-Host "Artifact root: $artifactRootPath"
Write-Host "Assembly record: $assemblyRecordPath"
if (-not $SkipSmokeCheck) {
    Write-Host "Smoke check: $smokeCheckPath"
}
