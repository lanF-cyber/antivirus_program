param(
    [string]$OutputRoot = ".\reports\packaging-staging",
    [ValidateSet("windows-x64")]
    [string]$Platform = "windows-x64",
    [string]$ManifestPath = ".\packaging\packaging-manifest.json",
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

function Normalize-PathFragment {
    param([string]$Value)

    if ($null -eq $Value) {
        return $null
    }

    return (($Value -replace '\\', '/').Trim())
}

function Test-IsArtifactRelativePath {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return $false
    }

    $normalized = Normalize-PathFragment $Value
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return $false
    }

    if ($normalized.StartsWith("/") -or $normalized.StartsWith("\")) {
        return $false
    }

    if ($normalized.Contains(":")) {
        return $false
    }

    foreach ($segment in ($normalized -split '/')) {
        if ([string]::IsNullOrWhiteSpace($segment) -or $segment -eq "." -or $segment -eq "..") {
            return $false
        }
    }

    return $true
}

function Test-IsPatternRelativePath {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return $false
    }

    $normalized = Normalize-PathFragment $Value
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return $false
    }

    if ($normalized.StartsWith("/") -or $normalized.StartsWith("\")) {
        return $false
    }

    if ($normalized.Contains(":")) {
        return $false
    }

    return $true
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

function Join-ArtifactRelativePath {
    param(
        [string]$BasePath,
        [string]$ChildPath
    )

    $segments = @()
    foreach ($value in @($BasePath, $ChildPath)) {
        $normalized = Normalize-PathFragment $value
        if (-not [string]::IsNullOrWhiteSpace($normalized)) {
            $segments += $normalized.Trim('/')
        }
    }

    return (($segments -join '/').Trim('/'))
}

function Test-RulePatternMatch {
    param(
        [string]$Pattern,
        [string]$ArtifactRelativePath
    )

    $normalizedPattern = (Normalize-PathFragment $Pattern).Trim('/')
    $normalizedPath = (Normalize-PathFragment $ArtifactRelativePath).Trim('/')

    if ([string]::IsNullOrWhiteSpace($normalizedPattern) -or [string]::IsNullOrWhiteSpace($normalizedPath)) {
        return $false
    }

    $regexPattern = [regex]::Escape($normalizedPattern)
    $regexPattern = $regexPattern -replace '\\\*\\\*', '.*'
    $regexPattern = $regexPattern -replace '\\\*', '[^/]*'
    $regexPattern = $regexPattern -replace '\\\?', '[^/]'
    return ([regex]::IsMatch($normalizedPath, '^' + $regexPattern + '$'))
}

function Get-ExcludeScopePriority {
    param([string]$Scope)

    switch ($Scope) {
        "hard" { return 0 }
        "scoped" { return 1 }
        default { return 99 }
    }
}

function Get-MatchingExcludeRules {
    param(
        [string]$ArtifactRelativePath,
        [object[]]$ExcludeRules
    )

    return @(
        $ExcludeRules |
            Where-Object { Test-RulePatternMatch -Pattern $_.pattern -ArtifactRelativePath $ArtifactRelativePath } |
            Sort-Object @{ Expression = { Get-ExcludeScopePriority $_.scope } }, @{ Expression = { $_.id } }
    )
}

function Get-FirstMatchingExcludeRule {
    param(
        [string]$ArtifactRelativePath,
        [object[]]$ExcludeRules
    )

    $matches = Get-MatchingExcludeRules -ArtifactRelativePath $ArtifactRelativePath -ExcludeRules $ExcludeRules
    if ($matches.Count -gt 0) {
        return $matches[0]
    }

    return $null
}

function Add-ResultNote {
    param(
        $Result,
        [string]$Note
    )

    if ([string]::IsNullOrWhiteSpace($Note)) {
        return
    }

    if (-not ($Result.notes -contains $Note)) {
        $Result.notes += $Note
    }
}

function Get-AllowedSet {
    param([string[]]$Values)

    $set = @{}
    foreach ($value in $Values) {
        $set[$value.ToLowerInvariant()] = $true
    }
    return $set
}

function Get-UniqueIdSet {
    return @{}
}

function Add-UniqueValue {
    param(
        [hashtable]$Set,
        [string]$Value
    )

    $key = $Value.ToLowerInvariant()
    if ($Set.ContainsKey($key)) {
        return $false
    }

    $Set[$key] = $true
    return $true
}

function Assert-ManifestCondition {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw "Packaging manifest validation failed: $Message"
    }
}

function Test-IsPathCoveredByInclude {
    param(
        [string]$ArtifactRelativePath,
        [object[]]$IncludeMappings
    )

    $normalizedTarget = (Normalize-PathFragment $ArtifactRelativePath).Trim('/')
    foreach ($mapping in $IncludeMappings) {
        $destination = (Normalize-PathFragment $mapping.destination).Trim('/')
        if ($normalizedTarget -eq $destination -or $normalizedTarget.StartsWith("$destination/")) {
            return $true
        }
    }

    return $false
}

function Validate-PackagingManifest {
    param(
        [object]$Manifest,
        [string]$RepoRoot,
        [string]$ExpectedPlatform
    )

    Assert-ManifestCondition ($null -ne $Manifest) "Manifest content could not be parsed."
    Assert-ManifestCondition ($null -ne $Manifest.manifest_version) "Top-level field 'manifest_version' is required."
    Assert-ManifestCondition ($null -ne $Manifest.artifact) "Top-level field 'artifact' is required."
    Assert-ManifestCondition ($null -ne $Manifest.include_mappings) "Top-level field 'include_mappings' is required."
    Assert-ManifestCondition ($null -ne $Manifest.exclude_rules) "Top-level field 'exclude_rules' is required."
    Assert-ManifestCondition ($null -ne $Manifest.retain_first_paths) "Top-level field 'retain_first_paths' is required."

    Assert-ManifestCondition ($Manifest.artifact.platform -eq $ExpectedPlatform) "artifact.platform must match the prototype platform '$ExpectedPlatform'."
    Assert-ManifestCondition (-not [string]::IsNullOrWhiteSpace($Manifest.artifact.artifact_root_template)) "artifact.artifact_root_template is required."
    Assert-ManifestCondition (-not [string]::IsNullOrWhiteSpace($Manifest.artifact.runtime_root)) "artifact.runtime_root is required."
    Assert-ManifestCondition (Test-IsArtifactRelativePath -Value $Manifest.artifact.runtime_root) "artifact.runtime_root must be artifact-root-relative."
    Assert-ManifestCondition ($Manifest.artifact.artifact_root_template.Contains("{version}")) "artifact.artifact_root_template must contain '{version}'."
    Assert-ManifestCondition ($Manifest.artifact.artifact_root_template.Contains("{platform}")) "artifact.artifact_root_template must contain '{platform}'."
    Assert-ManifestCondition (-not ($Manifest.artifact.artifact_root_template.Contains("/") -or $Manifest.artifact.artifact_root_template.Contains("\"))) "artifact.artifact_root_template must be a root folder name template, not a path."

    $includeMappings = @($Manifest.include_mappings)
    $excludeRules = @($Manifest.exclude_rules)
    $retainFirstPaths = @($Manifest.retain_first_paths)

    Assert-ManifestCondition ($includeMappings.Count -gt 0) "include_mappings must contain at least one entry."

    $includeIdSet = Get-UniqueIdSet
    $includeDestinationSet = Get-UniqueIdSet
    $allowedKinds = Get-AllowedSet -Values @("file", "directory")
    foreach ($mapping in $includeMappings) {
        Assert-ManifestCondition (-not [string]::IsNullOrWhiteSpace($mapping.id)) "include_mappings entries require a non-empty id."
        Assert-ManifestCondition (Add-UniqueValue -Set $includeIdSet -Value ([string]$mapping.id)) "include_mappings.id values must be unique. Duplicate id '$($mapping.id)'."
        Assert-ManifestCondition (-not [string]::IsNullOrWhiteSpace($mapping.source)) "include_mappings '$($mapping.id)' requires a source."
        Assert-ManifestCondition (-not [System.IO.Path]::IsPathRooted([string]$mapping.source)) "include_mappings '$($mapping.id)' source must stay repo-relative."
        Assert-ManifestCondition (Test-IsArtifactRelativePath -Value $mapping.destination) "include_mappings '$($mapping.id)' destination must be artifact-root-relative."
        Assert-ManifestCondition (Add-UniqueValue -Set $includeDestinationSet -Value ((Normalize-PathFragment $mapping.destination).Trim('/'))) "include_mappings destinations must be unique. Duplicate destination '$($mapping.destination)'."
        Assert-ManifestCondition ($allowedKinds.ContainsKey(([string]$mapping.kind).ToLowerInvariant())) "include_mappings '$($mapping.id)' kind must be 'file' or 'directory'."
        Assert-ManifestCondition ($mapping.required -is [bool]) "include_mappings '$($mapping.id)' required must be boolean."
        Assert-ManifestCondition ($mapping.operator_facing -is [bool]) "include_mappings '$($mapping.id)' operator_facing must be boolean."

        $sourcePath = Join-Path $RepoRoot $mapping.source
        if ($mapping.required) {
            Assert-ManifestCondition (Test-Path -LiteralPath $sourcePath) "required source '$($mapping.source)' for include_mappings '$($mapping.id)' does not exist."
        }
    }

    $runtimeMapping = @($includeMappings | Where-Object { $_.id -eq "runtime_scanbox" })
    Assert-ManifestCondition ($runtimeMapping.Count -eq 1) "include_mappings must contain exactly one 'runtime_scanbox' mapping."
    Assert-ManifestCondition ((Normalize-PathFragment $runtimeMapping[0].destination).Trim('/') -eq (Normalize-PathFragment $Manifest.artifact.runtime_root).Trim('/')) "runtime_scanbox destination must match artifact.runtime_root."

    $excludeIdSet = Get-UniqueIdSet
    $allowedScopes = Get-AllowedSet -Values @("hard", "scoped")
    $allowedCategories = Get-AllowedSet -Values @("repo_only", "external", "transient", "metadata")
    foreach ($rule in $excludeRules) {
        Assert-ManifestCondition (-not [string]::IsNullOrWhiteSpace($rule.id)) "exclude_rules entries require a non-empty id."
        Assert-ManifestCondition (Add-UniqueValue -Set $excludeIdSet -Value ([string]$rule.id)) "exclude_rules.id values must be unique. Duplicate id '$($rule.id)'."
        Assert-ManifestCondition (Test-IsPatternRelativePath -Value $rule.pattern) "exclude_rules '$($rule.id)' pattern must stay artifact-root-relative."
        Assert-ManifestCondition ($allowedScopes.ContainsKey(([string]$rule.scope).ToLowerInvariant())) "exclude_rules '$($rule.id)' scope must be 'hard' or 'scoped'."
        Assert-ManifestCondition ($allowedCategories.ContainsKey(([string]$rule.category).ToLowerInvariant())) "exclude_rules '$($rule.id)' category is invalid."
        Assert-ManifestCondition (-not [string]::IsNullOrWhiteSpace($rule.reason)) "exclude_rules '$($rule.id)' reason is required."
    }

    $retainSet = Get-UniqueIdSet
    foreach ($path in $retainFirstPaths) {
        Assert-ManifestCondition (Test-IsArtifactRelativePath -Value $path) "retain_first_paths entries must be artifact-root-relative."
        Assert-ManifestCondition (Add-UniqueValue -Set $retainSet -Value ((Normalize-PathFragment $path).Trim('/'))) "retain_first_paths entries must be unique. Duplicate path '$path'."
        Assert-ManifestCondition (Test-IsPathCoveredByInclude -ArtifactRelativePath $path -IncludeMappings $includeMappings) "retain_first_paths entry '$path' is not covered by any include mapping."
    }
}

function Get-PackagingManifest {
    param(
        [string]$ManifestResolvedPath,
        [string]$RepoRoot,
        [string]$ExpectedPlatform
    )

    if (-not (Test-Path -LiteralPath $ManifestResolvedPath -PathType Leaf)) {
        throw "Packaging manifest was not found at $ManifestResolvedPath."
    }

    $manifest = Get-Content -LiteralPath $ManifestResolvedPath -Raw | ConvertFrom-Json
    Validate-PackagingManifest -Manifest $manifest -RepoRoot $RepoRoot -ExpectedPlatform $ExpectedPlatform
    return $manifest
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
            Add-ResultNote -Result $result -Note "required_source_missing"
            return $result
        }

        $destinationParent = Split-Path -Parent $DestinationPath
        New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
        Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
        $result.copied_count = 1
        return $result
    } catch {
        $result.failed_count = 1
        Add-ResultNote -Result $result -Note $_.Exception.Message
        return $result
    }
}

function Copy-DirectoryMapping {
    param(
        [string]$SourcePath,
        [string]$DestinationPath,
        [string]$ArtifactDestinationPath,
        [object[]]$ExcludeRules
    )

    $result = [ordered]@{
        copied_count = 0
        skipped_count = 0
        failed_count = 0
        notes = @()
    }

    if (-not (Test-Path -LiteralPath $SourcePath -PathType Container)) {
        $result.failed_count = 1
        Add-ResultNote -Result $result -Note "required_source_missing"
        return $result
    }

    New-Item -ItemType Directory -Force -Path $DestinationPath | Out-Null

    $items = Get-ChildItem -LiteralPath $SourcePath -Force
    foreach ($item in $items) {
        $relativePath = Get-NormalizedRelativePath -BasePath $SourcePath -TargetPath $item.FullName
        $artifactRelativePath = Join-ArtifactRelativePath -BasePath $ArtifactDestinationPath -ChildPath $relativePath
        $excludeRule = Get-FirstMatchingExcludeRule -ArtifactRelativePath $artifactRelativePath -ExcludeRules $ExcludeRules
        if ($excludeRule) {
            $result.skipped_count += 1
            Add-ResultNote -Result $result -Note ("excluded:" + $excludeRule.id)
            continue
        }

        if ($item.PSIsContainer) {
            $childDestination = Join-Path $DestinationPath $item.Name
            $childArtifactPath = Join-ArtifactRelativePath -BasePath $ArtifactDestinationPath -ChildPath $item.Name
            $childResult = Copy-DirectoryMapping -SourcePath $item.FullName -DestinationPath $childDestination -ArtifactDestinationPath $childArtifactPath -ExcludeRules $ExcludeRules
            $result.copied_count += [int]$childResult.copied_count
            $result.skipped_count += [int]$childResult.skipped_count
            $result.failed_count += [int]$childResult.failed_count
            foreach ($note in @($childResult.notes)) {
                Add-ResultNote -Result $result -Note $note
            }
            continue
        }

        try {
            $destinationFile = Join-Path $DestinationPath $item.Name
            Copy-Item -LiteralPath $item.FullName -Destination $destinationFile -Force
            $result.copied_count += 1
        } catch {
            $result.failed_count += 1
            Add-ResultNote -Result $result -Note $_.Exception.Message
        }
    }

    return $result
}

function Remove-ExcludedArtifactEntries {
    param(
        [string]$DestinationPath,
        [string]$ArtifactDestinationPath,
        [object[]]$ExcludeRules
    )

    $result = [ordered]@{
        removed_count = 0
        notes = @()
    }

    if (-not (Test-Path -LiteralPath $DestinationPath -PathType Container)) {
        return $result
    }

    $entries = @(Get-ChildItem -LiteralPath $DestinationPath -Recurse -Force | Sort-Object @{ Expression = { $_.FullName.Length } } -Descending)
    foreach ($entry in $entries) {
        if (-not (Test-Path -LiteralPath $entry.FullName)) {
            continue
        }

        $relativePath = Get-NormalizedRelativePath -BasePath $DestinationPath -TargetPath $entry.FullName
        $artifactRelativePath = Join-ArtifactRelativePath -BasePath $ArtifactDestinationPath -ChildPath $relativePath
        $excludeRule = Get-FirstMatchingExcludeRule -ArtifactRelativePath $artifactRelativePath -ExcludeRules $ExcludeRules
        if (-not $excludeRule) {
            continue
        }

        Remove-Item -LiteralPath $entry.FullName -Force -Recurse
        $result.removed_count += 1
        Add-ResultNote -Result $result -Note ("excluded:" + $excludeRule.id)
    }

    return $result
}

function Remove-LiteralExcludeTargets {
    param(
        [string]$ArtifactRootPath,
        [object[]]$ExcludeRules
    )

    $result = [ordered]@{
        removed_count = 0
        notes = @()
    }

    foreach ($rule in $ExcludeRules) {
        $normalizedPattern = (Normalize-PathFragment $rule.pattern).Trim('/')
        if ([string]::IsNullOrWhiteSpace($normalizedPattern)) {
            continue
        }

        if ($normalizedPattern -match '[\*\?]') {
            if ($normalizedPattern.EndsWith('/**')) {
                $prefix = $normalizedPattern.Substring(0, $normalizedPattern.Length - 3).TrimEnd('/')
                if ($prefix -notmatch '[\*\?]') {
                    $literalTarget = Join-Path $ArtifactRootPath ($prefix -replace '/', '\')
                    if (Test-Path -LiteralPath $literalTarget) {
                        Remove-Item -LiteralPath $literalTarget -Force -Recurse
                        $result.removed_count += 1
                        Add-ResultNote -Result $result -Note ("excluded:" + $rule.id)
                    }
                }
            }
            continue
        }

        $literalPath = Join-Path $ArtifactRootPath ($normalizedPattern -replace '/', '\')
        if (Test-Path -LiteralPath $literalPath) {
            Remove-Item -LiteralPath $literalPath -Force -Recurse
            $result.removed_count += 1
            Add-ResultNote -Result $result -Note ("excluded:" + $rule.id)
        }
    }

    return $result
}

function Remove-RuntimeTransientTargets {
    param(
        [string]$ArtifactRootPath,
        [string]$RuntimeRoot,
        [object[]]$ExcludeRules
    )

    $result = [ordered]@{
        removed_count = 0
        notes = @()
    }

    $runtimeRootPath = Join-Path $ArtifactRootPath ($RuntimeRoot -replace '/', '\')
    if (-not (Test-Path -LiteralPath $runtimeRootPath -PathType Container)) {
        return $result
    }

    $pycacheRule = @($ExcludeRules | Where-Object { $_.category -eq "transient" -and $_.pattern -like "*__pycache__*" } | Select-Object -First 1)
    $pycRule = @($ExcludeRules | Where-Object { $_.category -eq "transient" -and $_.pattern -like "*.pyc*" } | Select-Object -First 1)

    $pycacheDirectories = @(Get-ChildItem -LiteralPath $runtimeRootPath -Recurse -Force -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Sort-Object @{ Expression = { $_.FullName.Length } } -Descending)
    foreach ($directory in $pycacheDirectories) {
        if (Test-Path -LiteralPath $directory.FullName) {
            Remove-Item -LiteralPath $directory.FullName -Force -Recurse
            $result.removed_count += 1
            if ($pycacheRule.Count -gt 0) {
                Add-ResultNote -Result $result -Note ("excluded:" + $pycacheRule[0].id)
            }
        }
    }

    $pycFiles = @(Get-ChildItem -LiteralPath $runtimeRootPath -Recurse -Force -File -ErrorAction SilentlyContinue | Where-Object {
        $_.Extension.ToLowerInvariant() -eq ".pyc"
    })
    foreach ($file in $pycFiles) {
        if (Test-Path -LiteralPath $file.FullName) {
            Remove-Item -LiteralPath $file.FullName -Force
            $result.removed_count += 1
            if ($pycRule.Count -gt 0) {
                Add-ResultNote -Result $result -Note ("excluded:" + $pycRule[0].id)
            }
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
$manifestResolvedPath = Resolve-RepoPath $ManifestPath

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
$manifest = Get-PackagingManifest -ManifestResolvedPath $manifestResolvedPath -RepoRoot $root -ExpectedPlatform $Platform
$artifactRootName = $manifest.artifact.artifact_root_template.Replace("{version}", $version).Replace("{platform}", $Platform)
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

$includeMappings = @($manifest.include_mappings)
$excludeRules = @($manifest.exclude_rules)
$retainFirstPaths = @($manifest.retain_first_paths)

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
        $result = Copy-DirectoryMapping -SourcePath $sourcePath -DestinationPath $destinationPath -ArtifactDestinationPath $mapping.destination -ExcludeRules $excludeRules
        $pruneResult = Remove-ExcludedArtifactEntries -DestinationPath $destinationPath -ArtifactDestinationPath $mapping.destination -ExcludeRules $excludeRules
        $result.skipped_count += [int]$pruneResult.removed_count
        foreach ($note in @($pruneResult.notes)) {
            Add-ResultNote -Result $result -Note $note
        }
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
        mapping_id = $mapping.id
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

$finalPruneResult = Remove-ExcludedArtifactEntries -DestinationPath $artifactRootPath -ArtifactDestinationPath "" -ExcludeRules $excludeRules
if ($finalPruneResult.removed_count -gt 0) {
    $copySummary.skipped_entries += [int]$finalPruneResult.removed_count
}

$literalExcludeCleanup = Remove-LiteralExcludeTargets -ArtifactRootPath $artifactRootPath -ExcludeRules $excludeRules
if ($literalExcludeCleanup.removed_count -gt 0) {
    $copySummary.skipped_entries += [int]$literalExcludeCleanup.removed_count
}

$runtimeTransientCleanup = Remove-RuntimeTransientTargets -ArtifactRootPath $artifactRootPath -RuntimeRoot $manifest.artifact.runtime_root -ExcludeRules $excludeRules
if ($runtimeTransientCleanup.removed_count -gt 0) {
    $copySummary.skipped_entries += [int]$runtimeTransientCleanup.removed_count
}

$missingRetainFirstPaths = @(
    $retainFirstPaths | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $artifactRootPath ($_ -replace '/', '\')))
    }
)
if ($missingRetainFirstPaths.Count -gt 0) {
    $copySummary.failed_entries += $missingRetainFirstPaths.Count
}

$assemblyRecord = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    generator_script = $generatorScript
    manifest_source = $manifestResolvedPath
    manifest_version = $manifest.manifest_version
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
    retain_first_paths = $retainFirstPaths
    copy_summary = $copySummary
    mapping_results = $mappingResults
    post_copy_prune = $finalPruneResult
    literal_exclude_cleanup = $literalExcludeCleanup
    runtime_transient_cleanup = $runtimeTransientCleanup
    smoke_check_path = $smokeCheckPath
}

$assemblyRecord | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $assemblyRecordPath -Encoding utf8

if ($missingRetainFirstPaths.Count -gt 0) {
    throw ("Assembly failed. Required retain-first paths missing: " + ($missingRetainFirstPaths -join ", "))
}

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
Write-Host "Manifest source: $manifestResolvedPath"
Write-Host "Assembly record: $assemblyRecordPath"
if (-not $SkipSmokeCheck) {
    Write-Host "Smoke check: $smokeCheckPath"
}
