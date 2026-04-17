param(
    [string]$ExpectedBranch = "main",
    [string]$ExpectedRemoteRef = "origin/main"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")

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

    Write-Check -Level $Level -Label $Label -Message $Message
}

function Invoke-GitCapture {
    param(
        [string[]]$Arguments
    )

    $output = & git @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    [pscustomobject]@{
        ExitCode = $exitCode
        Output = @($output)
        Text = (@($output) -join [Environment]::NewLine).Trim()
    }
}

function Get-ProjectVersion {
    param(
        [string]$Path
    )

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
    param(
        [string]$Path
    )

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

function All-PathsExist {
    param(
        [string[]]$Paths
    )

    $missing = @()
    foreach ($path in $Paths) {
        $resolved = Join-Path $root $path
        if (-not (Test-Path -LiteralPath $resolved)) {
            $missing += $path
        }
    }

    [pscustomobject]@{
        Missing = $missing
        AllExist = ($missing.Count -eq 0)
    }
}

$script:passCount = 0
$script:warnCount = 0
$script:failCount = 0

$branchResult = Invoke-GitCapture -Arguments @("branch", "--show-current")
if ($branchResult.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($branchResult.Text)) {
    Register-Result "FAIL" "Branch" "Could not determine the current branch."
} elseif ($branchResult.Text -eq $ExpectedBranch) {
    Register-Result "PASS" "Branch" "Current branch is '$ExpectedBranch'."
} else {
    Register-Result "FAIL" "Branch" "Current branch is '$($branchResult.Text)', expected '$ExpectedBranch'."
}

$statusResult = Invoke-GitCapture -Arguments @("status", "--short")
if ($statusResult.ExitCode -ne 0) {
    Register-Result "FAIL" "Working tree" "Could not read git status."
} elseif ([string]::IsNullOrWhiteSpace($statusResult.Text)) {
    Register-Result "PASS" "Working tree" "Working tree is clean."
} else {
    Register-Result "FAIL" "Working tree" "Working tree is not clean."
}

$remoteResult = Invoke-GitCapture -Arguments @("remote")
$originExists = $false
if ($remoteResult.ExitCode -ne 0) {
    Register-Result "WARN" "Origin remote" "Could not read git remotes."
} else {
    $remotes = @($remoteResult.Output | ForEach-Object { ([string]$_).Trim() }) | Where-Object { $_ }
    if ($remotes -contains "origin") {
        $originExists = $true
        Register-Result "PASS" "Origin remote" "Remote 'origin' is configured."
    } else {
        Register-Result "WARN" "Origin remote" "Remote 'origin' is not configured."
    }
}

$headResult = Invoke-GitCapture -Arguments @("rev-parse", "HEAD")
$headSha = $null
if ($headResult.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($headResult.Text)) {
    $headSha = $headResult.Text
}

$originMainRefExists = $false
$originMainSha = $null
if (-not $originExists) {
    Register-Result "WARN" "Origin main ref" "Skipped because remote 'origin' is not configured."
} else {
    $remoteRefResult = Invoke-GitCapture -Arguments @("rev-parse", "--verify", "refs/remotes/$ExpectedRemoteRef")
    if ($remoteRefResult.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($remoteRefResult.Text)) {
        $originMainRefExists = $true
        $originMainSha = $remoteRefResult.Text
        Register-Result "PASS" "Origin main ref" "Local ref 'refs/remotes/$ExpectedRemoteRef' exists."
    } else {
        Register-Result "WARN" "Origin main ref" "Local ref 'refs/remotes/$ExpectedRemoteRef' was not found."
    }
}

if ([string]::IsNullOrWhiteSpace($headSha)) {
    Register-Result "FAIL" "HEAD alignment" "Could not resolve local HEAD."
} elseif (-not $originExists) {
    Register-Result "WARN" "HEAD alignment" "Skipped because remote 'origin' is not configured."
} elseif (-not $originMainRefExists) {
    Register-Result "WARN" "HEAD alignment" "Skipped because local ref 'refs/remotes/$ExpectedRemoteRef' was not found."
} elseif ($headSha -eq $originMainSha) {
    Register-Result "PASS" "HEAD alignment" "Local HEAD matches local ref 'refs/remotes/$ExpectedRemoteRef'."
} else {
    Register-Result "FAIL" "HEAD alignment" "Local HEAD does not match local ref 'refs/remotes/$ExpectedRemoteRef'."
}

$projectVersion = Get-ProjectVersion -Path (Join-Path $root "pyproject.toml")
$initVersion = Get-InitVersion -Path (Join-Path $root "src\scanbox\__init__.py")
if ([string]::IsNullOrWhiteSpace($projectVersion)) {
    Register-Result "FAIL" "Version sync" "Could not parse [project].version from pyproject.toml."
} elseif ([string]::IsNullOrWhiteSpace($initVersion)) {
    Register-Result "FAIL" "Version sync" "Could not parse __version__ from src/scanbox/__init__.py."
} elseif ($projectVersion -eq $initVersion) {
    Register-Result "PASS" "Version sync" "Version is consistent at '$projectVersion'."
} else {
    Register-Result "FAIL" "Version sync" "pyproject.toml='$projectVersion' and src/scanbox/__init__.py='$initVersion' do not match."
}

$workflowDocs = All-PathsExist -Paths @(
    "docs\release-workflow.md",
    "docs\release-notes-template.md",
    "docs\release-prep-dry-run.md",
    "docs\release-notes-dry-run-example.md"
)
if ($workflowDocs.AllExist) {
    Register-Result "PASS" "Workflow docs" "Core release workflow documents are present."
} else {
    Register-Result "FAIL" "Workflow docs" ("Missing: " + ($workflowDocs.Missing -join ", "))
}

$acceptanceScripts = All-PathsExist -Paths @(
    "scripts\acceptance_v1.ps1",
    "scripts\acceptance_v2_quarantine.ps1",
    "scripts\acceptance_v2_directory.ps1"
)
if ($acceptanceScripts.AllExist) {
    Register-Result "PASS" "Acceptance scripts" "Baseline acceptance scripts are present."
} else {
    Register-Result "FAIL" "Acceptance scripts" ("Missing: " + ($acceptanceScripts.Missing -join ", "))
}

Write-Host ""
$overallResult = if ($failCount -gt 0) { "FAIL" } elseif ($warnCount -gt 0) { "WARN" } else { "PASS" }
Write-Host "Summary: OVERALL=$overallResult PASS=$passCount WARN=$warnCount FAIL=$failCount"
Write-Host "origin/main alignment is checked against local refs only."

if ($failCount -gt 0) {
    exit 1
}

exit 0
