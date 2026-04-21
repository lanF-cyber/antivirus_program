param(
    [string]$RehearsalRunDirectory,
    [string]$EvidenceIndexPath
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$generatorScript = "scripts/write_packaged_candidate_reviewer_summary.ps1"

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

function Read-JsonFile {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Add-Line {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Value = ""
    )

    [void]$Lines.Add($Value)
}

function Get-DisplayValue {
    param($Value)

    if ($null -eq $Value) {
        return '`n/a`'
    }

    $stringValue = [string]$Value
    if ([string]::IsNullOrWhiteSpace($stringValue)) {
        return '`n/a`'
    }

    return ('`{0}`' -f $stringValue)
}

function Get-ConclusionLine {
    param(
        [string]$CandidateOverall,
        [string[]]$BlockingItems
    )

    switch ($CandidateOverall) {
        "PASS" { return "Blocking gates passed under the current local packaged candidate discipline." }
        "WARN" { return "Blocking gates passed, but the current workstation remains portability-qualified." }
        default {
            if ($BlockingItems.Count -gt 0) {
                return "At least one blocking gate failed, so this candidate is not ready under the current local packaged candidate discipline."
            }
            return "This candidate is not ready under the current local packaged candidate discipline."
        }
    }
}

function Get-FollowUpLabel {
    param([string]$Value)

    switch ($Value) {
        "standalone_pytest" { return "standalone pytest recommended check needs recheck or review" }
        "zip_consistency_compare" { return "zip consistency compare did not strengthen the evidence set" }
        "operator_zip_consumption_warn" { return "operator validation remains portability-qualified on the current workstation" }
        default { return $Value }
    }
}

if ([string]::IsNullOrWhiteSpace($EvidenceIndexPath) -and [string]::IsNullOrWhiteSpace($RehearsalRunDirectory)) {
    throw "Provide -RehearsalRunDirectory or -EvidenceIndexPath."
}

$resolvedRunDirectory = if ([string]::IsNullOrWhiteSpace($RehearsalRunDirectory)) { $null } else { Resolve-RepoPath $RehearsalRunDirectory }
$resolvedEvidenceIndexPath = if ([string]::IsNullOrWhiteSpace($EvidenceIndexPath)) {
    Join-Path $resolvedRunDirectory "packaged-candidate-evidence-index.json"
} else {
    Resolve-RepoPath $EvidenceIndexPath
}

if (-not (Test-Path -LiteralPath $resolvedEvidenceIndexPath -PathType Leaf)) {
    throw "Evidence index was not found: $resolvedEvidenceIndexPath"
}

if ($null -eq $resolvedRunDirectory) {
    $resolvedRunDirectory = Split-Path -Parent $resolvedEvidenceIndexPath
}

$summaryPath = Join-Path $resolvedRunDirectory "packaged-candidate-reviewer-summary.md"
$indexRecord = Read-JsonFile $resolvedEvidenceIndexPath
if ($null -eq $indexRecord) {
    throw "Could not read evidence index: $resolvedEvidenceIndexPath"
}

$operatorValidationPath = if ($null -ne $indexRecord.packaged_evidence.operator_consumption_validation) {
    Resolve-RepoPath ([string]$indexRecord.packaged_evidence.operator_consumption_validation.path)
} else {
    $null
}
$operatorValidationRecord = Read-JsonFile $operatorValidationPath

$zipConsistencyPath = if ($null -ne $indexRecord.packaged_evidence.zip_consistency_check) {
    Resolve-RepoPath ([string]$indexRecord.packaged_evidence.zip_consistency_check.path)
} else {
    $null
}
$zipConsistencyRecord = Read-JsonFile $zipConsistencyPath

$candidateOverall = [string]$indexRecord.overall.candidate_overall
$readyState = [string]$indexRecord.overall.ready_state
$blockingItems = @($indexRecord.overall.blocking_items)
$nonBlockingFollowUps = @($indexRecord.overall.non_blocking_follow_ups)

$lines = New-Object 'System.Collections.Generic.List[string]'
Add-Line $lines "# Packaged Candidate Reviewer Summary"
Add-Line $lines ""
Add-Line $lines "> Local disposable reviewer handoff only."
Add-Line $lines "> Not repo-tracked."
Add-Line $lines "> Not a formal evidence contract addition."
Add-Line $lines ""
Add-Line $lines "## Candidate Conclusion"
Add-Line $lines ""
Add-Line $lines ('- Candidate version: `{0}`' -f [string]$indexRecord.candidate.version)
Add-Line $lines ('- Candidate commit: `{0}`' -f [string]$indexRecord.candidate.commit)
Add-Line $lines ('- Candidate overall: `{0}`' -f $candidateOverall)
Add-Line $lines ('- Ready / not ready: `{0}`' -f $readyState)
Add-Line $lines ("- Conclusion: {0}" -f (Get-ConclusionLine -CandidateOverall $candidateOverall -BlockingItems $blockingItems))
Add-Line $lines ""
Add-Line $lines "## Blocking Gates"
Add-Line $lines ""

$gateOrder = @(
    "verify_release_readiness",
    "acceptance_v1",
    "acceptance_v2_quarantine",
    "acceptance_v2_directory",
    "staging_verify",
    "zip_verify",
    "operator_zip_consumption"
)

foreach ($gateName in $gateOrder) {
    $gate = $indexRecord.blocking_gates.$gateName
    Add-Line $lines ('### `{0}`' -f $gateName)
    Add-Line $lines ""
    Add-Line $lines ('- Status: `{0}`' -f [string]$gate.status)
    Add-Line $lines ("- Summary: {0}" -f (Get-DisplayValue $gate.summary))
    $pointerValue = if ($gate.artifact_path) { $gate.artifact_path } elseif ($gate.log_path) { $gate.log_path } else { $null }
    Add-Line $lines ("- Artifact / log pointer: {0}" -f (Get-DisplayValue $pointerValue))
    if (-not [string]::IsNullOrWhiteSpace([string]$gate.reason)) {
        Add-Line $lines ('- Reason: `{0}`' -f [string]$gate.reason)
    }
    Add-Line $lines ""
}

Add-Line $lines "## Supportive Evidence"
Add-Line $lines ""
Add-Line $lines '### Recommended check: `standalone_pytest`'
Add-Line $lines ""
$pytestCheck = $indexRecord.recommended_checks.standalone_pytest
Add-Line $lines ('- Executed: `{0}`' -f $(if ($pytestCheck.executed) { "yes" } else { "no" }))
Add-Line $lines ('- Status: `{0}`' -f [string]$pytestCheck.status)
Add-Line $lines ("- Summary: {0}" -f (Get-DisplayValue $pytestCheck.summary))
Add-Line $lines ("- Run directory: {0}" -f (Get-DisplayValue $pytestCheck.run_directory))
Add-Line $lines ""
Add-Line $lines '### Optional supportive evidence: `zip_consistency_compare`'
Add-Line $lines ""
$compareEvidence = $indexRecord.supportive_evidence.zip_consistency_compare
Add-Line $lines ('- Executed: `{0}`' -f $(if ($compareEvidence.executed) { "yes" } else { "no" }))
Add-Line $lines ('- Status: `{0}`' -f [string]$compareEvidence.status)
if ($compareEvidence.executed) {
    Add-Line $lines ("- Summary: {0}" -f (Get-DisplayValue $compareEvidence.summary))
    Add-Line $lines ("- Artifact pointer: {0}" -f (Get-DisplayValue $compareEvidence.artifact_path))
    if ($null -ne $zipConsistencyRecord) {
        Add-Line $lines ('- Comparable: `{0}`' -f [string]$zipConsistencyRecord.comparable)
        Add-Line $lines ("- Baseline run directory: {0}" -f (Get-DisplayValue $zipConsistencyRecord.baseline_run_directory))
    } elseif (-not [string]::IsNullOrWhiteSpace([string]$compareEvidence.baseline_run_directory)) {
        Add-Line $lines ('- Baseline run directory: `{0}`' -f [string]$compareEvidence.baseline_run_directory)
    }
} else {
    Add-Line $lines '- Status note: `not run`'
    Add-Line $lines ('- Reason: `{0}`' -f [string]$compareEvidence.reason)
}
Add-Line $lines ""

Add-Line $lines "## Non-Blocking Caveats"
Add-Line $lines ""
if ($candidateOverall -eq "WARN" -and $null -ne $operatorValidationRecord -and [string]$operatorValidationRecord.overall -eq "WARN") {
    Add-Line $lines '- `current workstation only`'
    Add-Line $lines '- `fallback-assisted diagnostic success`'
    Add-Line $lines '- `not a supported operator path PASS`'
    Add-Line $lines '- `not a formal support promise`'
    Add-Line $lines ('- `workstation_profile = {0}`' -f [string]$operatorValidationRecord.workstation_profile)
    if ($null -ne $operatorValidationRecord.fallback_steps -and @($operatorValidationRecord.fallback_steps).Count -gt 0) {
        Add-Line $lines ('- fallback steps: `{0}`' -f (@($operatorValidationRecord.fallback_steps) -join '`, `'))
    }
    if ($null -ne $operatorValidationRecord.gaps -and @($operatorValidationRecord.gaps).Count -gt 0) {
        Add-Line $lines ('- portability gaps: `{0}`' -f (@($operatorValidationRecord.gaps) -join '`, `'))
    }
}
foreach ($followUp in @($nonBlockingFollowUps)) {
    Add-Line $lines ("- {0}" -f (Get-FollowUpLabel -Value ([string]$followUp)))
}
if ($nonBlockingFollowUps.Count -eq 0 -and -not ($candidateOverall -eq "WARN" -and $null -ne $operatorValidationRecord -and [string]$operatorValidationRecord.overall -eq "WARN")) {
    Add-Line $lines '- `none`'
}
Add-Line $lines ""

Add-Line $lines "## Evidence Pointers"
Add-Line $lines ""
Add-Line $lines ("- Packaged run directory: {0}" -f (Get-DisplayValue $indexRecord.packaged_evidence.packaging_run_directory.path))
Add-Line $lines ('- `assembly-record.json`: {0}' -f (Get-DisplayValue $indexRecord.packaged_evidence.assembly_record.path))
Add-Line $lines ('- `smoke-check.json`: {0}' -f (Get-DisplayValue $indexRecord.packaged_evidence.smoke_check.path))
Add-Line $lines ("- zip artifact: {0}" -f (Get-DisplayValue $indexRecord.packaged_evidence.zip_artifact.path))
Add-Line $lines ('- `artifact-fingerprint.json`: {0}' -f (Get-DisplayValue $indexRecord.packaged_evidence.artifact_fingerprint.path))
Add-Line $lines ('- `zip-check.json`: {0}' -f (Get-DisplayValue $indexRecord.packaged_evidence.zip_check.path))
Add-Line $lines ('- `operator-consumption-validation.json`: {0}' -f (Get-DisplayValue $indexRecord.packaged_evidence.operator_consumption_validation.path))
if ([string]$compareEvidence.status -eq "NOT_RUN") {
    Add-Line $lines '- optional `zip-consistency-check.json`: `not run`'
    Add-Line $lines ('- reason: `{0}`' -f [string]$compareEvidence.reason)
} else {
    Add-Line $lines ('- optional `zip-consistency-check.json`: {0}' -f (Get-DisplayValue $indexRecord.packaged_evidence.zip_consistency_check.path))
}
Add-Line $lines ""

Add-Line $lines "## Reviewer Note"
Add-Line $lines ""
Add-Line $lines "- candidate overall comes directly from the existing evidence index"
Add-Line $lines "- blocking gate statuses are copied from the existing evidence index"
Add-Line $lines "- supportive evidence is not a blocking gate"
Add-Line $lines "- recommended checks are not blocking gates"
Add-Line $lines "- this summary is a handoff pointer layer only"

$lines | Set-Content -LiteralPath $summaryPath -Encoding utf8

Write-Host "Packaged candidate reviewer summary generated."
Write-Host "Evidence index: $resolvedEvidenceIndexPath"
Write-Host "Summary path: $summaryPath"
