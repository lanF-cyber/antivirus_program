param(
    [Parameter(Mandatory = $true)]
    [string]$BaselineRunDirectory,
    [Parameter(Mandatory = $true)]
    [string]$CandidateRunDirectory
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$generatorScript = "scripts/compare_packaged_zip_consistency.ps1"
$zipVerifyScript = Join-Path $root "scripts\verify_packaged_zip_artifact.ps1"

function Resolve-RunDirectoryPath {
    param([string]$Value)

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return [System.IO.Path]::GetFullPath($Value)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $root $Value))
}

function Invoke-ZipVerifyAndRead {
    param([string]$RunDirectoryPath)

    $zipCheckPath = Join-Path $RunDirectoryPath "zip-check.json"
    & powershell -ExecutionPolicy Bypass -File $zipVerifyScript -RunDirectory $RunDirectoryPath
    $exitCode = $LASTEXITCODE
    if (-not (Test-Path -LiteralPath $zipCheckPath -PathType Leaf)) {
        throw "zip-check.json was not produced for $RunDirectoryPath."
    }

    $zipCheckRecord = Get-Content -LiteralPath $zipCheckPath -Raw | ConvertFrom-Json
    if ($exitCode -ne 0 -or $zipCheckRecord.overall -ne "PASS") {
        throw "Zip verify must pass before consistency comparison. Run: $RunDirectoryPath"
    }

    return $zipCheckRecord
}

function Add-Difference {
    param(
        [System.Collections.Generic.List[object]]$List,
        [string]$Field,
        $BaselineValue,
        $CandidateValue
    )

    if ($BaselineValue -ne $CandidateValue) {
        $List.Add([ordered]@{
            field = $Field
            baseline = $BaselineValue
            candidate = $CandidateValue
        }) | Out-Null
    }
}

$baselineRunDirectoryPath = Resolve-RunDirectoryPath $BaselineRunDirectory
$candidateRunDirectoryPath = Resolve-RunDirectoryPath $CandidateRunDirectory
$candidateOutputPath = Join-Path $candidateRunDirectoryPath "zip-consistency-check.json"
$baselineFingerprintPath = Join-Path $baselineRunDirectoryPath "artifact-fingerprint.json"
$candidateFingerprintPath = Join-Path $candidateRunDirectoryPath "artifact-fingerprint.json"

if (-not (Test-Path -LiteralPath $baselineFingerprintPath -PathType Leaf)) {
    throw "artifact-fingerprint.json was not found in $baselineRunDirectoryPath."
}
if (-not (Test-Path -LiteralPath $candidateFingerprintPath -PathType Leaf)) {
    throw "artifact-fingerprint.json was not found in $candidateRunDirectoryPath."
}

$baselineZipCheck = Invoke-ZipVerifyAndRead -RunDirectoryPath $baselineRunDirectoryPath
$candidateZipCheck = Invoke-ZipVerifyAndRead -RunDirectoryPath $candidateRunDirectoryPath
$baselineFingerprint = Get-Content -LiteralPath $baselineFingerprintPath -Raw | ConvertFrom-Json
$candidateFingerprint = Get-Content -LiteralPath $candidateFingerprintPath -Raw | ConvertFrom-Json

$notComparableFields = [System.Collections.Generic.List[object]]::new()
Add-Difference -List $notComparableFields -Field "artifact_root_name" -BaselineValue $baselineFingerprint.artifact_root_name -CandidateValue $candidateFingerprint.artifact_root_name
Add-Difference -List $notComparableFields -Field "version" -BaselineValue $baselineFingerprint.version -CandidateValue $candidateFingerprint.version
Add-Difference -List $notComparableFields -Field "platform" -BaselineValue $baselineFingerprint.platform -CandidateValue $candidateFingerprint.platform
Add-Difference -List $notComparableFields -Field "manifest_version" -BaselineValue $baselineFingerprint.manifest_version -CandidateValue $candidateFingerprint.manifest_version
Add-Difference -List $notComparableFields -Field "zip_reproducibility_profile" -BaselineValue $baselineFingerprint.zip_reproducibility_profile -CandidateValue $candidateFingerprint.zip_reproducibility_profile

$traceabilityDifferences = [System.Collections.Generic.List[object]]::new()
Add-Difference -List $traceabilityDifferences -Field "generated_at_utc" -BaselineValue $baselineFingerprint.generated_at_utc -CandidateValue $candidateFingerprint.generated_at_utc
Add-Difference -List $traceabilityDifferences -Field "generator_script" -BaselineValue $baselineFingerprint.generator_script -CandidateValue $candidateFingerprint.generator_script
Add-Difference -List $traceabilityDifferences -Field "run_directory" -BaselineValue $baselineFingerprint.run_directory -CandidateValue $candidateFingerprint.run_directory
Add-Difference -List $traceabilityDifferences -Field "artifact_root_path" -BaselineValue $baselineFingerprint.artifact_root_path -CandidateValue $candidateFingerprint.artifact_root_path
Add-Difference -List $traceabilityDifferences -Field "zip_path" -BaselineValue $baselineFingerprint.zip_path -CandidateValue $candidateFingerprint.zip_path
Add-Difference -List $traceabilityDifferences -Field "source_commit" -BaselineValue $baselineFingerprint.source_commit -CandidateValue $candidateFingerprint.source_commit
Add-Difference -List $traceabilityDifferences -Field "manifest_source" -BaselineValue $baselineFingerprint.manifest_source -CandidateValue $candidateFingerprint.manifest_source
Add-Difference -List $traceabilityDifferences -Field "staging_verify_path" -BaselineValue $baselineFingerprint.staging_verify_path -CandidateValue $candidateFingerprint.staging_verify_path

$criticalMatches = [System.Collections.Generic.List[string]]::new()
$criticalDifferences = [System.Collections.Generic.List[object]]::new()
$comparisonProfile = "not_comparable"
$comparable = $false
$overall = "WARN"
$reason = "not_comparable"

if ($notComparableFields.Count -eq 0) {
    $comparable = $true
    $comparisonProfile = [string]$candidateFingerprint.zip_reproducibility_profile
    $reason = $null

    foreach ($field in @(
        "normalized_entry_timestamp_utc",
        "archive_entry_count",
        "normalized_entry_names_sha256",
        "zip_sha256_algorithm",
        "zip_sha256",
        "size_bytes"
    )) {
        $baselineValue = $baselineFingerprint.$field
        $candidateValue = $candidateFingerprint.$field
        if ($baselineValue -eq $candidateValue) {
            $criticalMatches.Add($field) | Out-Null
        } else {
            $criticalDifferences.Add([ordered]@{
                field = $field
                baseline = $baselineValue
                candidate = $candidateValue
            }) | Out-Null
        }
    }

    if ($criticalDifferences.Count -eq 0) {
        $overall = "PASS"
    } else {
        $overall = "FAIL"
    }
}

$result = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    generator_script = $generatorScript
    baseline_run_directory = $baselineRunDirectoryPath
    candidate_run_directory = $candidateRunDirectoryPath
    comparison_profile = $comparisonProfile
    overall = $overall
    comparable = $comparable
    reason = $reason
    critical_matches = @($criticalMatches)
    critical_differences = @($criticalDifferences)
    traceability_differences = @($traceabilityDifferences)
    baseline_zip_check_overall = $baselineZipCheck.overall
    candidate_zip_check_overall = $candidateZipCheck.overall
}

$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $candidateOutputPath -Encoding utf8

Write-Host "Zip consistency comparison completed."
Write-Host "Candidate output: $candidateOutputPath"
Write-Host "Summary: OVERALL=$overall COMPARABLE=$comparable"

if ($overall -eq "FAIL") {
    exit 1
}

exit 0
