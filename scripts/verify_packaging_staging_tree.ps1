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

function Find-ArtifactFiles {
    param(
        [string]$BasePath,
        [string[]]$Names
    )

    if (-not (Test-Path -LiteralPath $BasePath -PathType Container)) {
        return @()
    }

    $lookup = @{}
    foreach ($name in $Names) {
        $lookup[$name.ToLowerInvariant()] = $true
    }

    return @(Get-ChildItem -LiteralPath $BasePath -Recurse -Force -File | Where-Object {
        $lookup.ContainsKey($_.Name.ToLowerInvariant())
    })
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
$artifactInit = Join-Path $artifactRootPath "runtime\scanbox\__init__.py"
$artifactProjectVersion = Get-ProjectVersion -Path $artifactPyproject
$artifactInitVersion = Get-InitVersion -Path $artifactInit

if ([string]::IsNullOrWhiteSpace($artifactProjectVersion)) {
    Register-Result "FAIL" "Version metadata" "Could not read [project].version from artifact pyproject.toml."
} elseif ([string]::IsNullOrWhiteSpace($artifactInitVersion)) {
    Register-Result "FAIL" "Version metadata" "Could not read __version__ from artifact runtime/scanbox/__init__.py."
} elseif ($artifactProjectVersion -ne $artifactInitVersion) {
    Register-Result "FAIL" "Version metadata" "Artifact version sources do not match."
} elseif ($artifactProjectVersion -ne $assemblyRecord.version) {
    Register-Result "FAIL" "Version metadata" "Artifact version metadata does not match the assembly record version."
} else {
    Register-Result "PASS" "Version metadata" "Artifact version metadata is traceable and consistent."
}

$missingMappings = @()
foreach ($mapping in $assemblyRecord.include_mappings) {
    if (-not (Test-ArtifactEntry -ArtifactRootPath $artifactRootPath -Mapping $mapping)) {
        $missingMappings += $mapping.destination
    }
}
if ($missingMappings.Count -eq 0) {
    Register-Result "PASS" "Required mappings" "All required artifact mappings are present."
} else {
    Register-Result "FAIL" "Required mappings" ("Missing: " + ($missingMappings -join ", "))
}

$repoOnlyPaths = @(
    "tests",
    "reports",
    "docs/release-workflow.md",
    "docs/release-prep-dry-run.md",
    "docs/release-notes-template.md",
    "docs/release-notes-dry-run-example.md",
    "docs/milestones"
)
$presentRepoOnlyPaths = @($repoOnlyPaths | Where-Object { -not (Test-PathAbsent -ArtifactRootPath $artifactRootPath -RelativePath $_) })
if ($presentRepoOnlyPaths.Count -eq 0) {
    Register-Result "PASS" "Repo-only exclusions" "Repo-only content is absent from the artifact."
} else {
    Register-Result "FAIL" "Repo-only exclusions" ("Unexpected content present: " + ($presentRepoOnlyPaths -join ", "))
}

$externalPaths = @(
    "config/scanbox.local.toml",
    "config/clamav/freshclam.local.conf"
)
$presentExternalPaths = @($externalPaths | Where-Object { -not (Test-PathAbsent -ArtifactRootPath $artifactRootPath -RelativePath $_) })
$unexpectedExternalBinaries = Find-ArtifactFiles -BasePath $artifactRootPath -Names @("clamscan.exe", "freshclam.exe", "capa.exe")
$unexpectedDatabaseFiles = @(Get-ChildItem -LiteralPath $artifactRootPath -Recurse -Force -File -ErrorAction SilentlyContinue | Where-Object {
    @(".cvd", ".cld", ".cdiff") -contains $_.Extension.ToLowerInvariant()
})

$externalFindings = @()
if ($presentExternalPaths.Count -gt 0) {
    $externalFindings += $presentExternalPaths
}
if ($unexpectedExternalBinaries.Count -gt 0) {
    $externalFindings += @($unexpectedExternalBinaries | ForEach-Object { $_.FullName })
}
if ($unexpectedDatabaseFiles.Count -gt 0) {
    $externalFindings += @($unexpectedDatabaseFiles | ForEach-Object { $_.FullName })
}

if ($externalFindings.Count -eq 0) {
    Register-Result "PASS" "External exclusions" "External-not-bundled content is absent from the artifact."
} else {
    Register-Result "FAIL" "External exclusions" ("Unexpected content present: " + ($externalFindings -join ", "))
}

$runtimeRoot = Join-Path $artifactRootPath "runtime\scanbox"
$runtimePyCache = @(Get-ChildItem -LiteralPath $runtimeRoot -Recurse -Force -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue)
$runtimePyc = @(Get-ChildItem -LiteralPath $runtimeRoot -Recurse -Force -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Extension.ToLowerInvariant() -eq ".pyc"
})
$allPyCache = @(Get-ChildItem -LiteralPath $artifactRootPath -Recurse -Force -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue)
$allPyc = @(Get-ChildItem -LiteralPath $artifactRootPath -Recurse -Force -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Extension.ToLowerInvariant() -eq ".pyc"
})
$venvDirectory = Test-Path -LiteralPath (Join-Path $artifactRootPath ".venv")

$transientFindings = @()
if ($runtimePyCache.Count -gt 0) {
    $transientFindings += "runtime/scanbox contains __pycache__"
}
if ($runtimePyc.Count -gt 0) {
    $transientFindings += "runtime/scanbox contains *.pyc"
}
if ($allPyCache.Count -gt 0) {
    $transientFindings += "artifact contains __pycache__"
}
if ($allPyc.Count -gt 0) {
    $transientFindings += "artifact contains *.pyc"
}
if ($venvDirectory) {
    $transientFindings += "artifact contains .venv"
}

if ($transientFindings.Count -eq 0) {
    Register-Result "PASS" "Transient exclusions" "Transient Python cache content is absent."
} else {
    Register-Result "FAIL" "Transient exclusions" ($transientFindings -join "; ")
}

$maintainerScriptPaths = @(
    "scripts/acceptance_v1.ps1",
    "scripts/acceptance_v2_quarantine.ps1",
    "scripts/acceptance_v2_directory.ps1",
    "scripts/verify_release_readiness.ps1"
)
$presentMaintainerScripts = @($maintainerScriptPaths | Where-Object { -not (Test-PathAbsent -ArtifactRootPath $artifactRootPath -RelativePath $_) })
if ($presentMaintainerScripts.Count -eq 0) {
    Register-Result "PASS" "Maintainer scripts" "Maintainer-only scripts are absent from the artifact."
} else {
    Register-Result "FAIL" "Maintainer scripts" ("Unexpected scripts present: " + ($presentMaintainerScripts -join ", "))
}

$operatorRequiredPaths = @(
    "scripts/verify_env.ps1",
    "docs/dependencies.md",
    "rules/yara/manifest.json",
    "rules/capa/manifest.json",
    "rules/capa/bundled/LICENSE.txt"
)
$missingOperatorPaths = @($operatorRequiredPaths | Where-Object { Test-PathAbsent -ArtifactRootPath $artifactRootPath -RelativePath $_ })
if ($missingOperatorPaths.Count -eq 0) {
    Register-Result "PASS" "Operator subset" "Operator-facing subset and required notices are present."
} else {
    Register-Result "FAIL" "Operator subset" ("Missing: " + ($missingOperatorPaths -join ", "))
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
