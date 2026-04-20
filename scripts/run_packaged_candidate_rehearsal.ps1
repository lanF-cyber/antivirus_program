param(
    [string]$BasePythonExe = ".\.venv\Scripts\python.exe",
    [string]$RehearsalOutputRoot = ".\reports\packaged-candidate-rehearsal",
    [string]$ConsistencyBaselineRunDirectory
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$generatorScript = "scripts/run_packaged_candidate_rehearsal.ps1"

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

function Get-RepoRelativePath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $null
    }

    $resolvedRoot = [System.IO.Path]::GetFullPath([string]$root).TrimEnd('\') + '\'
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    if ($resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $resolvedPath.Substring($resolvedRoot.Length)
    }

    return $resolvedPath
}

function New-UtcTimestamp {
    return [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssfffZ")
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

function Invoke-NativeCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [string[]]$Arguments = @(),

        [string]$WorkingDirectory = $null,

        [hashtable]$EnvironmentOverrides = @{}
    )

    if ([string]::IsNullOrWhiteSpace($WorkingDirectory)) {
        $WorkingDirectory = [string]$root
    }

    Push-Location $WorkingDirectory
    try {
        $previousErrorActionPreference = $ErrorActionPreference
        $originalEnvironment = @{}
        $ErrorActionPreference = "Continue"
        foreach ($key in $EnvironmentOverrides.Keys) {
            $originalEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
            [Environment]::SetEnvironmentVariable($key, [string]$EnvironmentOverrides[$key], "Process")
        }
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        foreach ($key in $EnvironmentOverrides.Keys) {
            [Environment]::SetEnvironmentVariable($key, $originalEnvironment[$key], "Process")
        }
        $ErrorActionPreference = $previousErrorActionPreference
        Pop-Location
    }

    $lines = @($output | ForEach-Object { "$_" })
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = $lines
        Text = ($lines -join [Environment]::NewLine).Trim()
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

function Invoke-GitCapture {
    param([string[]]$Arguments)

    $output = & git @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    return [pscustomobject]@{
        ExitCode = $exitCode
        Text = (@($output) -join [Environment]::NewLine).Trim()
    }
}

function Get-MatchValue {
    param(
        [string]$Text,
        [string]$Pattern
    )

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $null
    }

    if ($Text -match $Pattern) {
        return $Matches[1].Trim()
    }

    return $null
}

function Read-JsonIfPresent {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function New-StepRecord {
    param(
        [string]$Name,
        [string]$Status = "NOT_RUN",
        $ExitCode = $null,
        $ArtifactPath = $null,
        $Summary = $null,
        $LogPath = $null,
        [bool]$Executed = $false,
        $Reason = $null
    )

    return [ordered]@{
        name = $Name
        executed = $Executed
        status = $Status
        exit_code = $ExitCode
        artifact_path = $(if ($ArtifactPath) { Get-RepoRelativePath $ArtifactPath } else { $null })
        summary = $Summary
        log_path = $(if ($LogPath) { Get-RepoRelativePath $LogPath } else { $null })
        reason = $Reason
    }
}

function Invoke-Step {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogDirectory,
        [string]$WorkingDirectory = $null
    )

    $logPath = Join-Path $LogDirectory ($Name + ".log")
    $result = Invoke-NativeCapture -FilePath $FilePath -Arguments $Arguments -WorkingDirectory $WorkingDirectory
    $result.Output | Set-Content -LiteralPath $logPath -Encoding utf8
    return [pscustomobject]@{
        ExitCode = $result.ExitCode
        Output = $result.Output
        Text = $result.Text
        LogPath = $logPath
    }
}

function Get-JsonStatus {
    param([object]$Record)

    if ($null -eq $Record) {
        return "NOT_RUN"
    }

    if ($null -ne $Record.overall) {
        return [string]$Record.overall
    }

    return "generated"
}

function Get-LatestPassingBaselineRunDirectory {
    param(
        [string]$PackagingRoot,
        [string]$ExcludeRunDirectory
    )

    if (-not (Test-Path -LiteralPath $PackagingRoot -PathType Container)) {
        return $null
    }

    $excludeResolved = if ([string]::IsNullOrWhiteSpace($ExcludeRunDirectory)) { $null } else { [System.IO.Path]::GetFullPath($ExcludeRunDirectory) }
    $directories = @(Get-ChildItem -LiteralPath $PackagingRoot -Directory | Sort-Object Name -Descending)
    foreach ($directory in $directories) {
        if ($excludeResolved -and [System.IO.Path]::GetFullPath($directory.FullName) -eq $excludeResolved) {
            continue
        }

        $zipCheckPath = Join-Path $directory.FullName "zip-check.json"
        if (-not (Test-Path -LiteralPath $zipCheckPath -PathType Leaf)) {
            continue
        }

        $zipCheck = Read-JsonIfPresent $zipCheckPath
        if ($null -ne $zipCheck -and [string]$zipCheck.overall -eq "PASS") {
            return $directory.FullName
        }
    }

    return $null
}

$basePythonResolved = Resolve-RepoPath $BasePythonExe
if (-not $basePythonResolved -or -not (Test-Path -LiteralPath $basePythonResolved -PathType Leaf)) {
    throw "BasePythonExe was not found: $BasePythonExe"
}

$projectVersion = Get-ProjectVersion -Path (Join-Path $root "pyproject.toml")
$gitHead = Invoke-GitCapture -Arguments @("rev-parse", "HEAD")
$candidateCommit = if ($gitHead.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($gitHead.Text)) { $gitHead.Text } else { "unavailable" }
$plannedSemverTag = if ([string]::IsNullOrWhiteSpace($projectVersion)) { $null } else { "v$projectVersion" }

$rehearsalOutputRootResolved = Resolve-RepoPath $RehearsalOutputRoot
$rehearsalRunDirectory = Join-Path $rehearsalOutputRootResolved (New-UtcTimestamp)
$logDirectory = Join-Path $rehearsalRunDirectory "logs"
$evidenceIndexPath = Join-Path $rehearsalRunDirectory "packaged-candidate-evidence-index.json"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null

$powershellExe = "powershell"
$packagingRunDirectory = $null
$stagingArtifactRoot = $null
$standalonePytestRunDirectory = $null
$operatorConsumptionArtifactRoot = $null
$operatorConsumptionUnpackedRoot = $null

$blockingGates = [ordered]@{
    verify_release_readiness = (New-StepRecord -Name "verify_release_readiness")
    acceptance_v1 = (New-StepRecord -Name "acceptance_v1")
    acceptance_v2_quarantine = (New-StepRecord -Name "acceptance_v2_quarantine")
    acceptance_v2_directory = (New-StepRecord -Name "acceptance_v2_directory")
    staging_verify = (New-StepRecord -Name "staging_verify")
    zip_verify = (New-StepRecord -Name "zip_verify")
    operator_zip_consumption = (New-StepRecord -Name "operator_zip_consumption")
}

$recommendedChecks = [ordered]@{
    standalone_pytest = [ordered]@{
        executed = $false
        status = "NOT_RUN"
        summary = "not run"
        run_directory = $null
        log_path = $null
    }
}

$supportiveEvidence = [ordered]@{
    zip_consistency_compare = [ordered]@{
        executed = $false
        status = "NOT_RUN"
        reason = "not run"
        artifact_path = $null
        summary = "not run"
        log_path = $null
        baseline_run_directory = $null
    }
}

$packagedEvidence = [ordered]@{
    packaging_run_directory = [ordered]@{ path = $null; status = "NOT_RUN" }
    assembly_record = [ordered]@{ path = $null; status = "NOT_RUN" }
    smoke_check = [ordered]@{ path = $null; status = "NOT_RUN" }
    zip_artifact = [ordered]@{ path = $null; status = "NOT_RUN" }
    artifact_fingerprint = [ordered]@{ path = $null; status = "NOT_RUN" }
    zip_check = [ordered]@{ path = $null; status = "NOT_RUN" }
    operator_consumption_validation = [ordered]@{ path = $null; status = "NOT_RUN" }
    zip_consistency_check = [ordered]@{ path = $null; status = "NOT_RUN" }
}

$executionBlockingItems = New-Object 'System.Collections.Generic.List[string]'
$nonBlockingFollowUps = New-Object 'System.Collections.Generic.List[string]'
$interpretationNotes = New-Object 'System.Collections.Generic.List[string]'

$readinessStep = Invoke-Step -Name "verify_release_readiness" -FilePath $powershellExe -Arguments @(
    "-ExecutionPolicy", "Bypass",
    "-File", ".\scripts\verify_release_readiness.ps1"
) -LogDirectory $logDirectory
$readinessSummary = Get-MatchValue -Text $readinessStep.Text -Pattern '(?m)^Summary:\s+(OVERALL=.*)$'
$readinessStatus = if ($readinessStep.ExitCode -eq 0) { "PASS" } else { "FAIL" }
$blockingGates.verify_release_readiness = New-StepRecord -Name "verify_release_readiness" -Status $readinessStatus -ExitCode $readinessStep.ExitCode -ArtifactPath $readinessStep.LogPath -Summary $readinessSummary -LogPath $readinessStep.LogPath -Executed $true
if ($readinessStatus -eq "FAIL") {
    [void]$executionBlockingItems.Add("verify_release_readiness")
}

$canContinue = ($executionBlockingItems.Count -eq 0)

foreach ($acceptanceName in @("acceptance_v1", "acceptance_v2_quarantine", "acceptance_v2_directory")) {
    if (-not $canContinue) {
        $blockingGates[$acceptanceName].reason = "blocked_by_previous_failure"
        continue
    }

    $acceptanceStep = Invoke-Step -Name $acceptanceName -FilePath $powershellExe -Arguments @(
        "-ExecutionPolicy", "Bypass",
        "-File", ".\scripts\$acceptanceName.ps1"
    ) -LogDirectory $logDirectory
    $artifactPath = Get-MatchValue -Text $acceptanceStep.Text -Pattern '(?m)^Output dir:\s+(.+)$'
    if (-not $artifactPath) {
        $artifactPath = Get-MatchValue -Text $acceptanceStep.Text -Pattern '(?m)^Acceptance artifacts:\s+(.+)$'
    }
    $summary = Get-MatchValue -Text $acceptanceStep.Text -Pattern '(?m)^Summary:\s+(PASS=\d+\s+FAIL=\d+)$'
    $status = if ($acceptanceStep.ExitCode -eq 0) { "PASS" } else { "FAIL" }
    $blockingGates[$acceptanceName] = New-StepRecord -Name $acceptanceName -Status $status -ExitCode $acceptanceStep.ExitCode -ArtifactPath $artifactPath -Summary $summary -LogPath $acceptanceStep.LogPath -Executed $true
    if ($status -eq "FAIL") {
        [void]$executionBlockingItems.Add($acceptanceName)
        $canContinue = $false
    }
}

if ($canContinue) {
    $pytestStep = Invoke-Step -Name "standalone_pytest" -FilePath $powershellExe -Arguments @(
        "-ExecutionPolicy", "Bypass",
        "-File", ".\scripts\run_standalone_pytest.ps1",
        "-PythonExe", $basePythonResolved
    ) -LogDirectory $logDirectory
    $standalonePytestRunDirectory = Get-MatchValue -Text $pytestStep.Text -Pattern '(?m)^run_directory=(.+)$'
    $pytestSummary = if ($pytestStep.Output.Count -gt 0) { $pytestStep.Output[-1] } else { $null }
    $pytestStatus = if ($pytestStep.ExitCode -eq 0) { "PASS" } else { "FAIL" }
    $recommendedChecks.standalone_pytest = [ordered]@{
        executed = $true
        status = $pytestStatus
        summary = $pytestSummary
        run_directory = $(if ($standalonePytestRunDirectory) { Get-RepoRelativePath $standalonePytestRunDirectory } else { $null })
        log_path = Get-RepoRelativePath $pytestStep.LogPath
    }
    if ($pytestStatus -ne "PASS") {
        [void]$nonBlockingFollowUps.Add("standalone_pytest")
    }
}

if ($canContinue) {
    $assembleStep = Invoke-Step -Name "assemble_packaging_staging_tree" -FilePath $powershellExe -Arguments @(
        "-ExecutionPolicy", "Bypass",
        "-File", ".\scripts\assemble_packaging_staging_tree.ps1"
    ) -LogDirectory $logDirectory
    $packagingRunDirectory = Get-MatchValue -Text $assembleStep.Text -Pattern '(?m)^Run directory:\s+(.+)$'
    $packagedEvidence.packaging_run_directory.path = $(if ($packagingRunDirectory) { Get-RepoRelativePath $packagingRunDirectory } else { $null })
    $packagedEvidence.packaging_run_directory.status = if ($assembleStep.ExitCode -eq 0) { "generated" } else { "FAIL" }
    if ($assembleStep.ExitCode -ne 0) {
        [void]$executionBlockingItems.Add("assemble_packaging_staging_tree")
        $canContinue = $false
    }
}

if ($canContinue -and $packagingRunDirectory) {
    $stagingVerifyStep = Invoke-Step -Name "verify_packaging_staging_tree" -FilePath $powershellExe -Arguments @(
        "-ExecutionPolicy", "Bypass",
        "-File", ".\scripts\verify_packaging_staging_tree.ps1",
        "-RunDirectory", $packagingRunDirectory
    ) -LogDirectory $logDirectory
    $smokeCheckPath = Join-Path $packagingRunDirectory "smoke-check.json"
    $smokeCheck = Read-JsonIfPresent $smokeCheckPath
    $smokeCheckStatus = if ($null -ne $smokeCheck) { [string]$smokeCheck.overall } elseif ($stagingVerifyStep.ExitCode -eq 0) { "PASS" } else { "FAIL" }
    $blockingGates.staging_verify = New-StepRecord -Name "staging_verify" -Status $smokeCheckStatus -ExitCode $stagingVerifyStep.ExitCode -ArtifactPath $smokeCheckPath -Summary ("OVERALL=" + $smokeCheckStatus) -LogPath $stagingVerifyStep.LogPath -Executed $true
    if ($smokeCheckStatus -eq "FAIL" -or $stagingVerifyStep.ExitCode -ne 0) {
        [void]$executionBlockingItems.Add("staging_verify")
        $canContinue = $false
    }
}

if ($canContinue -and $packagingRunDirectory) {
    $packageStep = Invoke-Step -Name "package_packaging_staging_tree" -FilePath $powershellExe -Arguments @(
        "-ExecutionPolicy", "Bypass",
        "-File", ".\scripts\package_packaging_staging_tree.ps1",
        "-RunDirectory", $packagingRunDirectory
    ) -LogDirectory $logDirectory
    if ($packageStep.ExitCode -ne 0) {
        [void]$executionBlockingItems.Add("package_packaging_staging_tree")
        $canContinue = $false
    }
}

if ($packagingRunDirectory) {
    $assemblyRecordPath = Join-Path $packagingRunDirectory "assembly-record.json"
    $smokeCheckPath = Join-Path $packagingRunDirectory "smoke-check.json"
    $fingerprintPath = Join-Path $packagingRunDirectory "artifact-fingerprint.json"
    $zipCheckPath = Join-Path $packagingRunDirectory "zip-check.json"
    $operatorValidationPath = Join-Path $packagingRunDirectory "operator-consumption-validation.json"
    $consistencyCheckPath = Join-Path $packagingRunDirectory "zip-consistency-check.json"

    $assemblyRecord = Read-JsonIfPresent $assemblyRecordPath
    $smokeCheck = Read-JsonIfPresent $smokeCheckPath
    $fingerprintRecord = Read-JsonIfPresent $fingerprintPath

    $packagedEvidence.assembly_record.path = $(if ($assemblyRecordPath) { Get-RepoRelativePath $assemblyRecordPath } else { $null })
    $packagedEvidence.assembly_record.status = if ($null -ne $assemblyRecord) { "generated" } else { "NOT_RUN" }
    $packagedEvidence.smoke_check.path = $(if ($smokeCheckPath) { Get-RepoRelativePath $smokeCheckPath } else { $null })
    $packagedEvidence.smoke_check.status = Get-JsonStatus $smokeCheck
    $packagedEvidence.artifact_fingerprint.path = $(if ($fingerprintPath) { Get-RepoRelativePath $fingerprintPath } else { $null })
    $packagedEvidence.artifact_fingerprint.status = if ($null -ne $fingerprintRecord) { "generated" } else { "NOT_RUN" }
    if ($null -ne $fingerprintRecord -and -not [string]::IsNullOrWhiteSpace([string]$fingerprintRecord.zip_path)) {
        $packagedEvidence.zip_artifact.path = Get-RepoRelativePath ([string]$fingerprintRecord.zip_path)
        $packagedEvidence.zip_artifact.status = if (Test-Path -LiteralPath ([string]$fingerprintRecord.zip_path) -PathType Leaf) { "generated" } else { "FAIL" }
    }
    if ($null -ne $assemblyRecord -and -not [string]::IsNullOrWhiteSpace([string]$assemblyRecord.artifact_root_path)) {
        $stagingArtifactRoot = [string]$assemblyRecord.artifact_root_path
    }
}

if ($canContinue -and $packagingRunDirectory) {
    $zipVerifyStep = Invoke-Step -Name "verify_packaged_zip_artifact" -FilePath $powershellExe -Arguments @(
        "-ExecutionPolicy", "Bypass",
        "-File", ".\scripts\verify_packaged_zip_artifact.ps1",
        "-RunDirectory", $packagingRunDirectory
    ) -LogDirectory $logDirectory
    $zipCheckPath = Join-Path $packagingRunDirectory "zip-check.json"
    $zipCheck = Read-JsonIfPresent $zipCheckPath
    $zipVerifyStatus = if ($null -ne $zipCheck) { [string]$zipCheck.overall } elseif ($zipVerifyStep.ExitCode -eq 0) { "PASS" } else { "FAIL" }
    $blockingGates.zip_verify = New-StepRecord -Name "zip_verify" -Status $zipVerifyStatus -ExitCode $zipVerifyStep.ExitCode -ArtifactPath $zipCheckPath -Summary ("OVERALL=" + $zipVerifyStatus) -LogPath $zipVerifyStep.LogPath -Executed $true
    $packagedEvidence.zip_check.path = Get-RepoRelativePath $zipCheckPath
    $packagedEvidence.zip_check.status = Get-JsonStatus $zipCheck
    if ($zipVerifyStatus -eq "FAIL" -or $zipVerifyStep.ExitCode -ne 0) {
        [void]$executionBlockingItems.Add("zip_verify")
        $canContinue = $false
    }
}

$baselineReason = $null
$baselineRunDirectory = $null
if ($packagingRunDirectory) {
    if (-not [string]::IsNullOrWhiteSpace($ConsistencyBaselineRunDirectory)) {
        $baselineRunDirectory = Resolve-RepoPath $ConsistencyBaselineRunDirectory
        if (-not (Test-Path -LiteralPath $baselineRunDirectory -PathType Container)) {
            $baselineReason = "baseline missing"
            $baselineRunDirectory = $null
        }
    } else {
        $baselineRunDirectory = Get-LatestPassingBaselineRunDirectory -PackagingRoot (Join-Path $root "reports\packaging-staging") -ExcludeRunDirectory $packagingRunDirectory
        if (-not $baselineRunDirectory) {
            $baselineReason = "no suitable baseline"
        }
    }
}

if ($canContinue -and $packagingRunDirectory -and $baselineRunDirectory) {
    $compareStep = Invoke-Step -Name "compare_packaged_zip_consistency" -FilePath $powershellExe -Arguments @(
        "-ExecutionPolicy", "Bypass",
        "-File", ".\scripts\compare_packaged_zip_consistency.ps1",
        "-BaselineRunDirectory", $baselineRunDirectory,
        "-CandidateRunDirectory", $packagingRunDirectory
    ) -LogDirectory $logDirectory
    $consistencyCheckPath = Join-Path $packagingRunDirectory "zip-consistency-check.json"
    $consistencyCheck = Read-JsonIfPresent $consistencyCheckPath
    $compareStatus = if ($null -ne $consistencyCheck) { [string]$consistencyCheck.overall } elseif ($compareStep.ExitCode -eq 0) { "PASS" } else { "FAIL" }
    $supportiveEvidence.zip_consistency_compare = [ordered]@{
        executed = $true
        status = $compareStatus
        reason = $null
        artifact_path = Get-RepoRelativePath $consistencyCheckPath
        summary = if ($null -ne $consistencyCheck) { "OVERALL=$([string]$consistencyCheck.overall) COMPARABLE=$([string]$consistencyCheck.comparable)" } else { $null }
        log_path = Get-RepoRelativePath $compareStep.LogPath
        baseline_run_directory = Get-RepoRelativePath $baselineRunDirectory
    }
    $packagedEvidence.zip_consistency_check.path = Get-RepoRelativePath $consistencyCheckPath
    $packagedEvidence.zip_consistency_check.status = Get-JsonStatus $consistencyCheck
    if ($compareStatus -ne "PASS") {
        [void]$nonBlockingFollowUps.Add("zip_consistency_compare")
    }
} elseif ($packagingRunDirectory) {
    $supportiveEvidence.zip_consistency_compare = [ordered]@{
        executed = $false
        status = "NOT_RUN"
        reason = $(if ($baselineReason) { $baselineReason } else { "blocked_by_previous_failure" })
        artifact_path = $null
        summary = "not run"
        log_path = $null
        baseline_run_directory = $(if ($baselineRunDirectory) { Get-RepoRelativePath $baselineRunDirectory } else { $null })
    }
}

if ($canContinue -and $packagingRunDirectory) {
    $operatorStep = Invoke-Step -Name "validate_operator_zip_consumption" -FilePath $powershellExe -Arguments @(
        "-ExecutionPolicy", "Bypass",
        "-File", ".\scripts\validate_operator_zip_consumption.ps1",
        "-RunDirectory", $packagingRunDirectory,
        "-BasePythonExe", $basePythonResolved
    ) -LogDirectory $logDirectory
    $operatorValidationPath = Join-Path $packagingRunDirectory "operator-consumption-validation.json"
    $operatorValidation = Read-JsonIfPresent $operatorValidationPath
    $operatorStatus = if ($null -ne $operatorValidation) { [string]$operatorValidation.overall } elseif ($operatorStep.ExitCode -eq 0) { "PASS" } else { "FAIL" }
    $blockingGates.operator_zip_consumption = New-StepRecord -Name "operator_zip_consumption" -Status $operatorStatus -ExitCode $operatorStep.ExitCode -ArtifactPath $operatorValidationPath -Summary ("OVERALL=" + $operatorStatus) -LogPath $operatorStep.LogPath -Executed $true
    $packagedEvidence.operator_consumption_validation.path = Get-RepoRelativePath $operatorValidationPath
    $packagedEvidence.operator_consumption_validation.status = Get-JsonStatus $operatorValidation

    if ($null -ne $operatorValidation) {
        $operatorConsumptionArtifactRoot = [string]$operatorValidation.artifact_root
        if (-not [string]::IsNullOrWhiteSpace($operatorConsumptionArtifactRoot)) {
            $operatorConsumptionUnpackedRoot = Split-Path -Parent $operatorConsumptionArtifactRoot
        }
    }

    if ($operatorStatus -eq "FAIL" -or $operatorStep.ExitCode -ne 0) {
        [void]$executionBlockingItems.Add("operator_zip_consumption")
    }
}

if ($executionBlockingItems.Count -gt 0) {
    foreach ($blockingItem in @($executionBlockingItems)) {
        if (-not ($nonBlockingFollowUps -contains $blockingItem)) {
            # blocking items are tracked separately
        }
    }
}

if ($executionBlockingItems.Count -gt 0) {
    foreach ($gateName in @($blockingGates.Keys)) {
        if ($blockingGates[$gateName].status -eq "NOT_RUN" -and [string]::IsNullOrWhiteSpace([string]$blockingGates[$gateName].reason)) {
            $blockingGates[$gateName].reason = "blocked_by_previous_failure"
        }
    }
    if (-not $recommendedChecks.standalone_pytest.executed -and $recommendedChecks.standalone_pytest.status -eq "NOT_RUN") {
        $recommendedChecks.standalone_pytest.summary = "not run"
    }
    if (-not $supportiveEvidence.zip_consistency_compare.executed -and $supportiveEvidence.zip_consistency_compare.status -eq "NOT_RUN" -and $supportiveEvidence.zip_consistency_compare.reason -eq "not run") {
        $supportiveEvidence.zip_consistency_compare.reason = "blocked_by_previous_failure"
    }
}

$operatorGateStatus = [string]$blockingGates.operator_zip_consumption.status
$priorBlockingStatuses = @(
    [string]$blockingGates.verify_release_readiness.status,
    [string]$blockingGates.acceptance_v1.status,
    [string]$blockingGates.acceptance_v2_quarantine.status,
    [string]$blockingGates.acceptance_v2_directory.status,
    [string]$blockingGates.staging_verify.status,
    [string]$blockingGates.zip_verify.status
)
$allPriorBlockingPass = (($priorBlockingStatuses | Where-Object { $_ -ne "PASS" }).Count -eq 0)

$candidateOverall = "FAIL"
if ($executionBlockingItems.Count -gt 0) {
    $candidateOverall = "FAIL"
} elseif ($allPriorBlockingPass -and $operatorGateStatus -eq "PASS") {
    $candidateOverall = "PASS"
} elseif ($allPriorBlockingPass -and $operatorGateStatus -eq "WARN") {
    $candidateOverall = "WARN"
} else {
    $candidateOverall = "FAIL"
}

if ($candidateOverall -eq "WARN") {
    [void]$interpretationNotes.Add("current workstation only")
    [void]$interpretationNotes.Add("fallback-assisted diagnostic success")
    [void]$interpretationNotes.Add("not a supported operator path PASS")
    [void]$interpretationNotes.Add("not a formal support promise")
}

if ($recommendedChecks.standalone_pytest.status -eq "FAIL") {
    [void]$nonBlockingFollowUps.Add("standalone_pytest")
}
if ($supportiveEvidence.zip_consistency_compare.executed -and $supportiveEvidence.zip_consistency_compare.status -ne "PASS") {
    [void]$nonBlockingFollowUps.Add("zip_consistency_compare")
}
if ($candidateOverall -eq "WARN" -and -not ($nonBlockingFollowUps -contains "operator_zip_consumption_warn")) {
    [void]$nonBlockingFollowUps.Add("operator_zip_consumption_warn")
}

$indexRecord = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    generator_script = $generatorScript
    rehearsal_run_directory = Get-RepoRelativePath $rehearsalRunDirectory
    candidate = [ordered]@{
        version = $projectVersion
        commit = $candidateCommit
        planned_semver_tag = $plannedSemverTag
    }
    overall = [ordered]@{
        candidate_overall = $candidateOverall
        ready_state = $(if ($candidateOverall -eq "FAIL") { "not_ready" } else { "ready" })
        blocking_items = @($executionBlockingItems | Select-Object -Unique)
        non_blocking_follow_ups = @($nonBlockingFollowUps | Select-Object -Unique)
        interpretation_notes = @($interpretationNotes)
    }
    blocking_gates = $blockingGates
    recommended_checks = $recommendedChecks
    supportive_evidence = $supportiveEvidence
    packaged_evidence = $packagedEvidence
    disposable_diagnostics = [ordered]@{
        staging_artifact_root = $(if ($stagingArtifactRoot) { Get-RepoRelativePath $stagingArtifactRoot } else { $null })
        standalone_pytest_run_directory = $(if ($standalonePytestRunDirectory) { Get-RepoRelativePath $standalonePytestRunDirectory } else { $null })
        operator_consumption_unpacked_root = $(if ($operatorConsumptionUnpackedRoot) { Get-RepoRelativePath $operatorConsumptionUnpackedRoot } else { $null })
    }
}

$indexRecord | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $evidenceIndexPath -Encoding utf8

Write-Host "Packaged candidate rehearsal completed."
Write-Host "Rehearsal run directory: $rehearsalRunDirectory"
Write-Host "Evidence index: $evidenceIndexPath"
Write-Host "Summary: CANDIDATE_OVERALL=$candidateOverall READY_STATE=$($indexRecord.overall.ready_state)"

if ($candidateOverall -eq "FAIL") {
    exit 1
}

exit 0
