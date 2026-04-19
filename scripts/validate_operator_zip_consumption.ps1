param(
    [Parameter(Mandatory = $true)]
    [string]$RunDirectory,

    [Parameter(Mandatory = $true)]
    [string]$BasePythonExe
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$generatorScript = "scripts/validate_operator_zip_consumption.ps1"
$zipVerifyScript = Join-Path $root "scripts\verify_packaged_zip_artifact.ps1"

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

function Invoke-NativeCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [string[]]$Arguments = @(),

        [string]$WorkingDirectory = $null,

        [hashtable]$EnvironmentOverrides = @{}
    )

    if ([string]::IsNullOrWhiteSpace($WorkingDirectory)) {
        $WorkingDirectory = $root
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

function Get-VerifyOverall {
    param(
        [string]$CommandOutput,
        [int]$ExitCode
    )

    if ($CommandOutput -match 'Summary:\s+PASS=(\d+)\s+WARN=(\d+)\s+FAIL=(\d+)') {
        $warnCount = [int]$Matches[2]
        $failCount = [int]$Matches[3]
        if ($failCount -gt 0) {
            return "FAIL"
        }
        if ($warnCount -gt 0) {
            return "WARN"
        }
        return "PASS"
    }

    if ($ExitCode -eq 0) {
        return "PASS"
    }

    return "FAIL"
}

function Get-VerifyContext {
    param([string]$CommandOutput)

    if ($CommandOutput -match '(?m)^Context:\s+([A-Za-z_][A-Za-z0-9_]*)\s*$') {
        return $Matches[1]
    }

    return "not_detected"
}

function Get-ValidationClassification {
    param(
        [bool]$FallbackUsed,
        [string]$VerifyEnvOverall,
        [int]$ScanExitCode,
        [string[]]$BlockingGaps
    )

    $supportedOperatorPathOverall = "FAIL"
    $fallbackAssistedOverall = "FAIL"

    if (-not $FallbackUsed -and $VerifyEnvOverall -eq "PASS" -and $ScanExitCode -eq 0 -and $BlockingGaps.Count -eq 0) {
        $supportedOperatorPathOverall = "PASS"
    }

    if ($VerifyEnvOverall -eq "PASS" -and $ScanExitCode -eq 0 -and $BlockingGaps.Count -eq 0) {
        $fallbackAssistedOverall = "PASS"
    }

    $overall = if ($supportedOperatorPathOverall -eq "PASS") {
        "PASS"
    } elseif ($fallbackAssistedOverall -eq "PASS") {
        "WARN"
    } else {
        "FAIL"
    }

    return [pscustomobject]@{
        SupportedOperatorPathOverall = $supportedOperatorPathOverall
        FallbackAssistedOverall = $fallbackAssistedOverall
        Overall = $overall
    }
}

function New-UtcTimestamp {
    return [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
}

function Get-SitePackagesPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe,

        [string]$WorkingDirectory = $null,

        [hashtable]$EnvironmentOverrides = @{}
    )

    $script = "import site; candidates=[p for p in site.getsitepackages() if p.endswith('site-packages')]; print(candidates[0] if candidates else '')"
    $result = Invoke-NativeCapture -FilePath $PythonExe -Arguments @("-c", $script) -WorkingDirectory $WorkingDirectory -EnvironmentOverrides $EnvironmentOverrides
    if ($result.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($result.Text)) {
        return $null
    }

    return $result.Text.Split([Environment]::NewLine)[0].Trim()
}

function Assert-ChildPath {
    param(
        [string]$ParentPath,
        [string]$ChildPath
    )

    $resolvedParent = [System.IO.Path]::GetFullPath($ParentPath).TrimEnd('\') + '\'
    $resolvedChild = [System.IO.Path]::GetFullPath($ChildPath)
    if (-not $resolvedChild.StartsWith($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to mutate path outside the run directory: $resolvedChild"
    }
}

$runDirectoryPath = Resolve-RepoPath $RunDirectory
$basePythonResolved = Resolve-RepoPath $BasePythonExe
$assemblyRecordPath = Join-Path $runDirectoryPath "assembly-record.json"
$fingerprintPath = Join-Path $runDirectoryPath "artifact-fingerprint.json"
$zipCheckPath = Join-Path $runDirectoryPath "zip-check.json"
$validationRecordPath = Join-Path $runDirectoryPath "operator-consumption-validation.json"

if (-not (Test-Path -LiteralPath $assemblyRecordPath -PathType Leaf)) {
    throw "assembly-record.json was not found in $runDirectoryPath."
}
if (-not (Test-Path -LiteralPath $fingerprintPath -PathType Leaf)) {
    throw "artifact-fingerprint.json was not found in $runDirectoryPath."
}
if (-not (Test-Path -LiteralPath $basePythonResolved -PathType Leaf)) {
    throw "BasePythonExe was not found: $basePythonResolved"
}

$assemblyRecord = Get-Content -LiteralPath $assemblyRecordPath -Raw | ConvertFrom-Json
$fingerprintRecord = Get-Content -LiteralPath $fingerprintPath -Raw | ConvertFrom-Json

$unpackRoot = Join-Path $runDirectoryPath ("operator-consumption-unpacked-" + (New-UtcTimestamp))
$artifactRoot = Join-Path $unpackRoot $assemblyRecord.artifact_root_name
$artifactPythonExe = Join-Path $artifactRoot ".venv\Scripts\python.exe"
$quickstartPath = Join-Path $artifactRoot "QUICKSTART.md"
$requirementsPath = Join-Path $artifactRoot "requirements.txt"
$localOverridePath = Join-Path $artifactRoot "config\scanbox.local.toml"
$localTempRoot = Join-Path $artifactRoot ".local-temp"

$gaps = @()
$blockingGaps = @()
$notes = @()
$verifyEnvExitCode = $null
$verifyEnvOverall = "not_run"
$verifyEnvContext = "not_detected"
$scanExitCode = $null
$quickstartDocPresent = $false
$requirementsPresent = $false
$zipVerifyOverall = "not_run"
$venvCreateExitCode = $null
$pipInstallExitCode = $null
$usedVenvFallback = $false
$fallbackSteps = @()
$dependencyExpectations = [ordered]@{
    runtime_python = "required"
    bundled_yara = "required"
    clamav = "optional_for_yara_only_first_run"
    capa = "optional_for_yara_only_first_run"
    full_external_dependencies = "required_for_full_external_dependency_path"
}

$zipVerifyResult = Invoke-NativeCapture -FilePath "powershell" -Arguments @(
    "-ExecutionPolicy", "Bypass",
    "-File", $zipVerifyScript,
    "-RunDirectory", $runDirectoryPath
) -WorkingDirectory $root

if (Test-Path -LiteralPath $zipCheckPath -PathType Leaf) {
    $zipCheckRecord = Get-Content -LiteralPath $zipCheckPath -Raw | ConvertFrom-Json
    $zipVerifyOverall = [string]$zipCheckRecord.overall
} else {
    $zipVerifyOverall = if ($zipVerifyResult.ExitCode -eq 0) { "PASS" } else { "FAIL" }
}

if ($zipVerifyResult.ExitCode -ne 0 -or $zipVerifyOverall -ne "PASS") {
    $gaps += "zip_verify_not_pass"
    $blockingGaps += "zip_verify_not_pass"
}

if ($blockingGaps.Count -eq 0) {
    Expand-Archive -LiteralPath $fingerprintRecord.zip_path -DestinationPath $unpackRoot -Force

    if (-not (Test-Path -LiteralPath $artifactRoot -PathType Container)) {
        $gaps += "artifact_root_missing_after_unpack"
        $blockingGaps += "artifact_root_missing_after_unpack"
    }
}

if ($blockingGaps.Count -eq 0) {
    $quickstartDocPresent = Test-Path -LiteralPath $quickstartPath -PathType Leaf
    $requirementsPresent = Test-Path -LiteralPath $requirementsPath -PathType Leaf

    if (-not $quickstartDocPresent) {
        $gaps += "quickstart_missing"
        $blockingGaps += "quickstart_missing"
    }
    if (-not $requirementsPresent) {
        $gaps += "requirements_missing"
        $blockingGaps += "requirements_missing"
    }
}

if ($blockingGaps.Count -eq 0) {
    New-Item -ItemType Directory -Force -Path $localTempRoot | Out-Null
    $tempEnvironment = @{
        TEMP = $localTempRoot
        TMP = $localTempRoot
    }

    $venvCreateResult = Invoke-NativeCapture -FilePath $basePythonResolved -Arguments @("-m", "venv", ".venv") -WorkingDirectory $artifactRoot -EnvironmentOverrides $tempEnvironment
    $venvCreateExitCode = $venvCreateResult.ExitCode
    if ($venvCreateExitCode -ne 0) {
        if ($venvCreateResult.Text) {
            $notes += "venv_create_primary_output=" + $venvCreateResult.Text
        }

        if (Test-Path -LiteralPath (Join-Path $artifactRoot ".venv")) {
            $partialVenvPath = Join-Path $artifactRoot ".venv"
            Assert-ChildPath -ParentPath $artifactRoot -ChildPath $partialVenvPath
            Remove-Item -LiteralPath $partialVenvPath -Force -Recurse
        }

        $fallbackVenvResult = Invoke-NativeCapture -FilePath $basePythonResolved -Arguments @("-m", "venv", "--without-pip", ".venv") -WorkingDirectory $artifactRoot -EnvironmentOverrides $tempEnvironment
        $venvCreateExitCode = $fallbackVenvResult.ExitCode
        if ($venvCreateExitCode -ne 0) {
            $gaps += "venv_create_failed"
            $blockingGaps += "venv_create_failed"
            if ($fallbackVenvResult.Text) {
                $notes += "venv_create_fallback_output=" + $fallbackVenvResult.Text
            }
        } else {
            $usedVenvFallback = $true
            $fallbackSteps += "venv_without_pip"
            if ($gaps -notcontains "supported_path_venv_with_pip_unavailable") {
                $gaps += "supported_path_venv_with_pip_unavailable"
            }
        }
    }
}

if ($blockingGaps.Count -eq 0) {
    if ($usedVenvFallback) {
        $pipInstallResult = Invoke-NativeCapture -FilePath $basePythonResolved -Arguments @("-m", "pip", "install", "--target", ".\.venv\Lib\site-packages", "-r", ".\requirements.txt") -WorkingDirectory $artifactRoot -EnvironmentOverrides $tempEnvironment
    } else {
        $pipInstallResult = Invoke-NativeCapture -FilePath $artifactPythonExe -Arguments @("-m", "pip", "install", "-r", ".\requirements.txt") -WorkingDirectory $artifactRoot -EnvironmentOverrides $tempEnvironment
    }
    $pipInstallExitCode = $pipInstallResult.ExitCode
    if ($pipInstallExitCode -ne 0) {
        if ($pipInstallResult.Text) {
            $notes += "pip_install_primary_output=" + $pipInstallResult.Text
        }

        $baseSitePackages = Get-SitePackagesPath -PythonExe $basePythonResolved -WorkingDirectory $artifactRoot -EnvironmentOverrides $tempEnvironment
        $artifactSitePackages = Get-SitePackagesPath -PythonExe $artifactPythonExe -WorkingDirectory $artifactRoot -EnvironmentOverrides $tempEnvironment

        if ([string]::IsNullOrWhiteSpace($baseSitePackages) -or [string]::IsNullOrWhiteSpace($artifactSitePackages)) {
            $gaps += "pip_install_failed"
            $blockingGaps += "pip_install_failed"
        } else {
            Get-ChildItem -LiteralPath $baseSitePackages -Force | ForEach-Object {
                Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $artifactSitePackages $_.Name) -Recurse -Force
            }
            $pipInstallExitCode = 0
            $fallbackSteps += "copy_base_site_packages"
            if ($gaps -notcontains "supported_path_runtime_dependency_install_unavailable") {
                $gaps += "supported_path_runtime_dependency_install_unavailable"
            }
        }
    }
}

if ($blockingGaps.Count -eq 0) {
    $localOverrideContent = @"
[engines.clamav]
enabled = false

[engines.capa]
enabled = false
"@
    $localOverrideContent | Set-Content -LiteralPath $localOverridePath -Encoding ascii

    $verifyEnvResult = Invoke-NativeCapture -FilePath "powershell" -Arguments @(
        "-ExecutionPolicy", "Bypass",
        "-File", ".\scripts\verify_env.ps1",
        "-PythonExe", ".\.venv\Scripts\python.exe"
    ) -WorkingDirectory $artifactRoot -EnvironmentOverrides $tempEnvironment
    $verifyEnvExitCode = $verifyEnvResult.ExitCode
    $verifyEnvOverall = Get-VerifyOverall -CommandOutput $verifyEnvResult.Text -ExitCode $verifyEnvExitCode
    $verifyEnvContext = Get-VerifyContext -CommandOutput $verifyEnvResult.Text
    if ($verifyEnvOverall -ne "PASS") {
        $gaps += "verify_env_not_pass"
        $blockingGaps += "verify_env_not_pass"
        if ($verifyEnvResult.Text) {
            $notes += "verify_env_output=" + $verifyEnvResult.Text
        }
    }
}

if ($blockingGaps.Count -eq 0) {
    $scanArgs = @(
        "-ExecutionPolicy", "Bypass",
        "-File", ".\scripts\run_scanbox.ps1",
        "-PythonExe", ".\.venv\Scripts\python.exe",
        "scan", ".\README.md"
    )
    $scanResult = Invoke-NativeCapture -FilePath "powershell" -Arguments $scanArgs -WorkingDirectory $artifactRoot -EnvironmentOverrides $tempEnvironment
    $scanExitCode = $scanResult.ExitCode
    if ($scanExitCode -ne 0) {
        $gaps += "minimal_scan_failed"
        $blockingGaps += "minimal_scan_failed"
        if ($scanResult.Text) {
            $notes += "scan_output=" + $scanResult.Text
        }
    }
}

$fallbackUsed = ($fallbackSteps.Count -gt 0)
$classification = Get-ValidationClassification -FallbackUsed $fallbackUsed -VerifyEnvOverall $verifyEnvOverall -ScanExitCode $scanExitCode -BlockingGaps $blockingGaps
$supportedOperatorPathOverall = $classification.SupportedOperatorPathOverall
$fallbackAssistedOverall = $classification.FallbackAssistedOverall
$overall = $classification.Overall
$workstationProfile = if ($overall -eq "PASS") {
    "supported_operator_path"
} elseif ($overall -eq "WARN") {
    "maintainer_fallback_assisted"
} else {
    "unsupported_operator_path"
}

if ($fallbackUsed -and $supportedOperatorPathOverall -eq "PASS") {
    throw "supported_operator_path_overall must not be PASS when fallback was used."
}

if ($overall -eq "WARN" -and -not ($gaps | Where-Object { $_ -like 'supported_path_*' })) {
    throw "overall=WARNING requires at least one portability-oriented supported_path_* gap."
}

$validationRecord = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    generator_script = $generatorScript
    run_directory = $runDirectoryPath
    artifact_context = "unpacked_zip"
    artifact_root = $artifactRoot
    python_exe = $artifactPythonExe
    base_python_exe = $basePythonResolved
    quickstart_mode = "yara_only_first_run"
    verify_env_context = $verifyEnvContext
    dependency_expectations = $dependencyExpectations
    quickstart_doc_present = $quickstartDocPresent
    requirements_present = $requirementsPresent
    zip_verify_overall = $zipVerifyOverall
    verify_env_exit_code = $verifyEnvExitCode
    verify_env_overall = $verifyEnvOverall
    venv_create_exit_code = $venvCreateExitCode
    pip_install_exit_code = $pipInstallExitCode
    fallback_used = $fallbackUsed
    fallback_steps = $fallbackSteps
    supported_operator_path_overall = $supportedOperatorPathOverall
    fallback_assisted_overall = $fallbackAssistedOverall
    workstation_profile = $workstationProfile
    scan_command = "powershell -ExecutionPolicy Bypass -File .\scripts\run_scanbox.ps1 -PythonExe .\.venv\Scripts\python.exe scan .\README.md"
    scan_exit_code = $scanExitCode
    overall = $overall
    gaps = $gaps
    notes = $notes
}

$validationRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $validationRecordPath -Encoding utf8

Write-Host "Operator consumption validation completed."
Write-Host "Run directory: $runDirectoryPath"
Write-Host "Validation record: $validationRecordPath"
Write-Host "Summary: OVERALL=$overall"

if ($overall -eq "FAIL") {
    exit 1
}

exit 0
