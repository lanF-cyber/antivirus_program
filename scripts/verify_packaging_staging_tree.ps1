param(
    [Parameter(Mandatory = $true)]
    [string]$RunDirectory
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$generatorScript = "scripts/verify_packaging_staging_tree.ps1"

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

function Test-ArtifactEntry {
    param(
        [string]$ArtifactRootPath,
        [object]$Mapping
    )

    $targetPath = Join-Path $ArtifactRootPath ($Mapping.destination -replace '/', '\')
    if ($Mapping.kind -eq "directory") {
        return (Test-Path -LiteralPath $targetPath -PathType Container)
    }
    return (Test-Path -LiteralPath $targetPath -PathType Leaf)
}

function Test-PathAbsent {
    param(
        [string]$ArtifactRootPath,
        [string]$RelativePath
    )

    $targetPath = Join-Path $ArtifactRootPath ($RelativePath -replace '/', '\')
    return -not (Test-Path -LiteralPath $targetPath)
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

function Get-ArtifactRelativeEntries {
    param([string]$ArtifactRootPath)

    if (-not (Test-Path -LiteralPath $ArtifactRootPath -PathType Container)) {
        return @()
    }

    return @(
        Get-ChildItem -LiteralPath $ArtifactRootPath -Recurse -Force |
            ForEach-Object { Get-NormalizedRelativePath -BasePath $ArtifactRootPath -TargetPath $_.FullName }
    )
}

function Get-ArtifactRelativeFiles {
    param([string]$ArtifactRootPath)

    if (-not (Test-Path -LiteralPath $ArtifactRootPath -PathType Container)) {
        return @()
    }

    return @(
        Get-ChildItem -LiteralPath $ArtifactRootPath -Recurse -Force -File |
            ForEach-Object { Get-NormalizedRelativePath -BasePath $ArtifactRootPath -TargetPath $_.FullName }
    )
}

function Get-RuleMatches {
    param(
        [string[]]$ArtifactEntries,
        [object[]]$Rules
    )

    $matches = @()
    foreach ($rule in $Rules) {
        foreach ($entry in $ArtifactEntries) {
            if (Test-RulePatternMatch -Pattern $rule.pattern -ArtifactRelativePath $entry) {
                $matches += "$($rule.id):$entry"
            }
        }
    }

    return @($matches | Sort-Object -Unique)
}

$script:passCount = 0
$script:warnCount = 0
$script:failCount = 0
$script:checkResults = @()

$runDirectoryResolved = if ([System.IO.Path]::IsPathRooted($RunDirectory)) {
    [System.IO.Path]::GetFullPath($RunDirectory)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $root $RunDirectory))
}

$assemblyRecordPath = Join-Path $runDirectoryResolved "assembly-record.json"
if (-not (Test-Path -LiteralPath $assemblyRecordPath -PathType Leaf)) {
    throw "assembly-record.json was not found in $runDirectoryResolved."
}

$assemblyRecord = Get-Content -LiteralPath $assemblyRecordPath -Raw | ConvertFrom-Json
$artifactRootPath = $assemblyRecord.artifact_root_path
$smokeCheckPath = Join-Path $runDirectoryResolved "smoke-check.json"

$artifactEntries = Get-ArtifactRelativeEntries -ArtifactRootPath $artifactRootPath
$artifactFiles = Get-ArtifactRelativeFiles -ArtifactRootPath $artifactRootPath

if (Test-Path -LiteralPath $artifactRootPath -PathType Container) {
    $expectedLeaf = Split-Path -Leaf $artifactRootPath
    if ($expectedLeaf -eq $assemblyRecord.artifact_root_name) {
        Register-Result "PASS" "Artifact root" "Artifact root exists at the expected path."
    } else {
        Register-Result "FAIL" "Artifact root" "Artifact root path exists but the leaf name does not match the recorded artifact root name."
    }
} else {
    Register-Result "FAIL" "Artifact root" "Artifact root path does not exist."
}

$artifactPyproject = Join-Path $artifactRootPath "pyproject.toml"
$runtimeMapping = @($assemblyRecord.include_mappings | Where-Object { $_.id -eq "runtime_scanbox" })
$runtimeRootRelative = if ($runtimeMapping.Count -eq 1) { $runtimeMapping[0].destination } else { "runtime/scanbox" }
$artifactInit = Join-Path $artifactRootPath (($runtimeRootRelative -replace '/', '\') + "\__init__.py")
$artifactProjectVersion = Get-ProjectVersion -Path $artifactPyproject
$artifactInitVersion = Get-InitVersion -Path $artifactInit

if ([string]::IsNullOrWhiteSpace($artifactProjectVersion)) {
    Register-Result "FAIL" "Version metadata" "Could not read [project].version from artifact pyproject.toml."
} elseif ([string]::IsNullOrWhiteSpace($artifactInitVersion)) {
    Register-Result "FAIL" "Version metadata" "Could not read __version__ from artifact runtime package."
} elseif ($artifactProjectVersion -ne $artifactInitVersion) {
    Register-Result "FAIL" "Version metadata" "Artifact version sources do not match."
} elseif ($artifactProjectVersion -ne $assemblyRecord.version) {
    Register-Result "FAIL" "Version metadata" "Artifact version metadata does not match the assembly record version."
} else {
    Register-Result "PASS" "Version metadata" "Artifact version metadata is traceable and consistent."
}

$missingMappings = @()
foreach ($mapping in @($assemblyRecord.include_mappings | Where-Object { $_.required -eq $true })) {
    if (-not (Test-ArtifactEntry -ArtifactRootPath $artifactRootPath -Mapping $mapping)) {
        $missingMappings += "$($mapping.id):$($mapping.destination)"
    }
}
if ($missingMappings.Count -eq 0) {
    Register-Result "PASS" "Required mappings" "All required artifact mappings are present."
} else {
    Register-Result "FAIL" "Required mappings" ("Missing: " + ($missingMappings -join ", "))
}

$repoOnlyRules = @($assemblyRecord.exclude_rules | Where-Object { $_.category -in @("repo_only", "metadata") })
$repoOnlyMatches = Get-RuleMatches -ArtifactEntries $artifactEntries -Rules $repoOnlyRules
if ($repoOnlyMatches.Count -eq 0) {
    Register-Result "PASS" "Repo-only exclusions" "Repo-only and excluded metadata content are absent from the artifact."
} else {
    Register-Result "FAIL" "Repo-only exclusions" ("Unexpected content present: " + ($repoOnlyMatches -join ", "))
}

$externalRules = @($assemblyRecord.exclude_rules | Where-Object { $_.category -eq "external" })
$externalMatches = Get-RuleMatches -ArtifactEntries $artifactEntries -Rules $externalRules
$unexpectedExternalBinaries = @($artifactFiles | Where-Object {
    $_.ToLowerInvariant().EndsWith("/clamscan.exe") -or
    $_.ToLowerInvariant().EndsWith("/freshclam.exe") -or
    $_.ToLowerInvariant().EndsWith("/capa.exe")
})
$unexpectedDatabaseFiles = @($artifactFiles | Where-Object {
    $_.ToLowerInvariant().EndsWith(".cvd") -or
    $_.ToLowerInvariant().EndsWith(".cld") -or
    $_.ToLowerInvariant().EndsWith(".cdiff")
})
$externalFindings = @($externalMatches + $unexpectedExternalBinaries + $unexpectedDatabaseFiles | Sort-Object -Unique)
if ($externalFindings.Count -eq 0) {
    Register-Result "PASS" "External exclusions" "External-not-bundled content is absent from the artifact."
} else {
    Register-Result "FAIL" "External exclusions" ("Unexpected content present: " + ($externalFindings -join ", "))
}

$transientRules = @($assemblyRecord.exclude_rules | Where-Object { $_.category -eq "transient" })
$transientMatches = Get-RuleMatches -ArtifactEntries $artifactEntries -Rules $transientRules
$runtimeRelativePrefix = (Normalize-PathFragment $runtimeRootRelative).Trim('/')
$runtimePyCache = @($artifactEntries | Where-Object { $_ -eq "$runtimeRelativePrefix/__pycache__" -or $_ -like "$runtimeRelativePrefix/**/__pycache__" })
$runtimePyc = @($artifactFiles | Where-Object { $_ -like "$runtimeRelativePrefix/*.pyc" -or $_ -like "$runtimeRelativePrefix/**/*.pyc" })
$transientFindings = @($transientMatches | Sort-Object -Unique)
if ($runtimePyCache.Count -gt 0) {
    $transientFindings += "runtime/scanbox contains __pycache__"
}
if ($runtimePyc.Count -gt 0) {
    $transientFindings += "runtime/scanbox contains *.pyc"
}
$transientFindings = @($transientFindings | Sort-Object -Unique)
if ($transientFindings.Count -eq 0) {
    Register-Result "PASS" "Transient exclusions" "Transient Python cache content is absent from the artifact."
} else {
    Register-Result "FAIL" "Transient exclusions" ($transientFindings -join "; ")
}

$maintainerScriptRules = @($assemblyRecord.exclude_rules | Where-Object {
    $_.pattern -eq "scripts/verify_release_readiness.ps1" -or $_.pattern -eq "scripts/acceptance_*.ps1"
})
$maintainerScriptMatches = Get-RuleMatches -ArtifactEntries $artifactEntries -Rules $maintainerScriptRules
if ($maintainerScriptMatches.Count -eq 0) {
    Register-Result "PASS" "Maintainer scripts" "Maintainer-only scripts are absent from the artifact."
} else {
    Register-Result "FAIL" "Maintainer scripts" ("Unexpected scripts present: " + ($maintainerScriptMatches -join ", "))
}

$requiredOperatorMappings = @($assemblyRecord.include_mappings | Where-Object { $_.operator_facing -eq $true })
$missingOperatorMappings = @()
foreach ($mapping in $requiredOperatorMappings) {
    if (-not (Test-ArtifactEntry -ArtifactRootPath $artifactRootPath -Mapping $mapping)) {
        $missingOperatorMappings += "$($mapping.id):$($mapping.destination)"
    }
}

$retainFirstFindings = @()
foreach ($relativePath in @($assemblyRecord.retain_first_paths)) {
    if (Test-PathAbsent -ArtifactRootPath $artifactRootPath -RelativePath $relativePath) {
        $retainFirstFindings += $relativePath
    }
}

$allowedDocFiles = @(
    $assemblyRecord.include_mappings |
        Where-Object { $_.kind -eq "file" -and ((Normalize-PathFragment $_.destination).Trim('/')).StartsWith("docs/") } |
        ForEach-Object { (Normalize-PathFragment $_.destination).Trim('/') }
) | Sort-Object -Unique
$actualDocFiles = @($artifactFiles | Where-Object { $_.StartsWith("docs/") }) | Sort-Object -Unique
$unexpectedDocFiles = @($actualDocFiles | Where-Object { $_ -notin $allowedDocFiles })
$missingAllowedDocFiles = @($allowedDocFiles | Where-Object { $_ -notin $actualDocFiles })

$operatorFindings = @()
if ($missingOperatorMappings.Count -gt 0) {
    $operatorFindings += @($missingOperatorMappings)
}
if ($retainFirstFindings.Count -gt 0) {
    $operatorFindings += @($retainFirstFindings | ForEach-Object { "missing retain-first path: $_" })
}
if ($missingAllowedDocFiles.Count -gt 0) {
    $operatorFindings += @($missingAllowedDocFiles | ForEach-Object { "missing docs subset file: $_" })
}
if ($unexpectedDocFiles.Count -gt 0) {
    $operatorFindings += @($unexpectedDocFiles | ForEach-Object { "unexpected docs file: $_" })
}

if ($operatorFindings.Count -eq 0) {
    Register-Result "PASS" "Operator subset" "Operator-facing subset, docs subset, and retained notices are present."
} else {
    Register-Result "FAIL" "Operator subset" ($operatorFindings -join "; ")
}

$overall = if ($failCount -gt 0) { "FAIL" } elseif ($warnCount -gt 0) { "WARN" } else { "PASS" }
$smokeCheckRecord = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    generator_script = $generatorScript
    run_directory = $runDirectoryResolved
    artifact_root_path = $artifactRootPath
    overall = $overall
    pass_count = $passCount
    warn_count = $warnCount
    fail_count = $failCount
    checks = $checkResults
}

$smokeCheckRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $smokeCheckPath -Encoding utf8

Write-Host ""
Write-Host "Summary: OVERALL=$overall PASS=$passCount WARN=$warnCount FAIL=$failCount"

if ($failCount -gt 0) {
    exit 1
}

exit 0
