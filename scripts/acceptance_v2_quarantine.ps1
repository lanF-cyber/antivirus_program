param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$ConfigPath = ".\config\scanbox.toml",
    [int]$StepTimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")

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

function Write-Step {
    param(
        [ValidateSet("PASS", "FAIL")]
        [string]$Level,
        [string]$Label,
        [string]$Message
    )

    $prefix = "[$Level]"
    switch ($Level) {
        "PASS" { Write-Host "$prefix $Label - $Message" -ForegroundColor Green }
        "FAIL" { Write-Host "$prefix $Label - $Message" -ForegroundColor Red }
    }
}

function Save-Text {
    param(
        [string]$Path,
        [AllowNull()]
        [object]$Value
    )

    if ($null -eq $Value) {
        Set-Content -LiteralPath $Path -Value "" -Encoding utf8
        return
    }

    if ($Value -is [System.Array]) {
        Set-Content -LiteralPath $Path -Value $Value -Encoding utf8
        return
    }

    Set-Content -LiteralPath $Path -Value ([string]$Value) -Encoding utf8
}

function Register-Result {
    param(
        [ValidateSet("PASS", "FAIL")]
        [string]$Level,
        [string]$Label,
        [string]$Message
    )

    if ($Level -eq "PASS") {
        $script:passCount += 1
    } else {
        $script:failCount += 1
    }

    Write-Step $Level $Label $Message
}

function Stop-OnFailure {
    if ($script:failCount -gt 0) {
        Write-Host ""
        Write-Host "Summary: PASS=$passCount FAIL=$failCount"
        Write-Host "Acceptance artifacts: $outputDir"
        exit 1
    }
}

function Join-CommandArguments {
    param([string[]]$Arguments)

    $quoted = foreach ($argument in $Arguments) {
        if ($argument -notmatch '[\s"]') {
            $argument
            continue
        }

        '"' + ($argument -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
    }

    return [string]::Join(" ", $quoted)
}

function Invoke-LoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$StdoutPath,
        [string]$StderrPath,
        [int]$TimeoutSeconds
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = Join-CommandArguments $ArgumentList
    $psi.WorkingDirectory = [string]$root
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi

    [void]$process.Start()
    $startedAt = Get-Date
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $timedOut = -not $process.WaitForExit($TimeoutSeconds * 1000)

    if ($timedOut) {
        try {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        } catch {
        }
    } else {
        $process.WaitForExit()
    }

    $null = [System.Threading.Tasks.Task]::WaitAll([System.Threading.Tasks.Task[]]@($stdoutTask, $stderrTask), 5000)

    Save-Text -Path $StdoutPath -Value $stdoutTask.Result
    Save-Text -Path $StderrPath -Value $stderrTask.Result

    [pscustomobject]@{
        ExitCode = if ($timedOut) { $null } else { $process.ExitCode }
        TimedOut = $timedOut
        DurationSeconds = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 2)
    }
}

function Run-MustPassProcessStep {
    param(
        [string]$Label,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$StdoutFileName,
        [string]$StderrFileName
    )

    $stdoutPath = Join-Path $outputDir $StdoutFileName
    $stderrPath = Join-Path $outputDir $StderrFileName
    $result = Invoke-LoggedProcess `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -StdoutPath $stdoutPath `
        -StderrPath $stderrPath `
        -TimeoutSeconds $StepTimeoutSeconds

    if ($result.TimedOut) {
        Register-Result "FAIL" $Label "Timed out after $StepTimeoutSeconds seconds. See $stdoutPath and $stderrPath."
        Stop-OnFailure
        return
    }

    if ($result.ExitCode -ne 0) {
        Register-Result "FAIL" $Label "Exit code was $($result.ExitCode). See $stdoutPath and $stderrPath."
        Stop-OnFailure
        return
    }

    Register-Result "PASS" $Label "Completed in $($result.DurationSeconds)s."
}

function Read-JsonFile {
    param([string]$Path)

    $text = Get-Content -LiteralPath $Path -Raw
    try {
        return ($text | ConvertFrom-Json)
    } catch {
        throw "JSON parse failed for $Path"
    }
}

function Get-RecordStateByScanId {
    param(
        [object]$ListResponse,
        [string]$ScanId
    )

    $record = $ListResponse.records | Where-Object { $_.scan_id -eq $ScanId } | Select-Object -First 1
    if ($null -eq $record) {
        return $null
    }

    return $record.state
}

function Invoke-QuarantineMove {
    param(
        [string]$Label,
        [string]$TargetPath,
        [string]$StdoutFileName,
        [string]$StderrFileName
    )

    $stdoutPath = Join-Path $outputDir $StdoutFileName
    $stderrPath = Join-Path $outputDir $StderrFileName
    $result = Invoke-LoggedProcess `
        -FilePath $pythonResolved `
        -ArgumentList @("-m", "scanbox", "scan", $TargetPath, "--config", $configResolved, "--quarantine", "move") `
        -StdoutPath $stdoutPath `
        -StderrPath $stderrPath `
        -TimeoutSeconds $StepTimeoutSeconds

    if ($result.TimedOut) {
        Register-Result "FAIL" $Label "Timed out after $StepTimeoutSeconds seconds. See $stdoutPath and $stderrPath."
        Stop-OnFailure
        return $null
    }

    if ($result.ExitCode -ne 1) {
        Register-Result "FAIL" $Label "Exit code was $($result.ExitCode), expected 1."
        Stop-OnFailure
        return $null
    }

    $report = Read-JsonFile $stdoutPath
    if ($report.overall_status -ne "known_malicious") {
        Register-Result "FAIL" $Label "overall_status was '$($report.overall_status)', expected 'known_malicious'."
        Stop-OnFailure
        return $null
    }

    if (-not $report.quarantine.performed) {
        Register-Result "FAIL" $Label "quarantine.performed was not true."
        Stop-OnFailure
        return $null
    }

    Register-Result "PASS" $Label "Known-malicious move completed in $($result.DurationSeconds)s."
    return $report
}

function Invoke-QuarantineListCheck {
    param(
        [string]$Label,
        [string]$StdoutFileName,
        [string]$StderrFileName,
        [int]$ExpectedTotal,
        [int]$ExpectedQuarantined,
        [int]$ExpectedRestored,
        [int]$ExpectedDeleted,
        [hashtable]$ExpectedStates
    )

    $stdoutPath = Join-Path $outputDir $StdoutFileName
    $stderrPath = Join-Path $outputDir $StderrFileName
    $result = Invoke-LoggedProcess `
        -FilePath $pythonResolved `
        -ArgumentList @("-m", "scanbox", "quarantine", "list", "--config", $configResolved) `
        -StdoutPath $stdoutPath `
        -StderrPath $stderrPath `
        -TimeoutSeconds $StepTimeoutSeconds

    if ($result.TimedOut) {
        Register-Result "FAIL" $Label "Timed out after $StepTimeoutSeconds seconds. See $stdoutPath and $stderrPath."
        Stop-OnFailure
        return $null
    }

    if ($result.ExitCode -ne 0) {
        Register-Result "FAIL" $Label "Exit code was $($result.ExitCode), expected 0."
        Stop-OnFailure
        return $null
    }

    $report = Read-JsonFile $stdoutPath
    if ($report.summary.total -ne $ExpectedTotal) {
        Register-Result "FAIL" $Label "summary.total was $($report.summary.total), expected $ExpectedTotal."
        Stop-OnFailure
        return $null
    }

    if ($report.summary.quarantined -ne $ExpectedQuarantined) {
        Register-Result "FAIL" $Label "summary.quarantined was $($report.summary.quarantined), expected $ExpectedQuarantined."
        Stop-OnFailure
        return $null
    }

    if ($report.summary.restored -ne $ExpectedRestored) {
        Register-Result "FAIL" $Label "summary.restored was $($report.summary.restored), expected $ExpectedRestored."
        Stop-OnFailure
        return $null
    }

    if ($report.summary.deleted -ne $ExpectedDeleted) {
        Register-Result "FAIL" $Label "summary.deleted was $($report.summary.deleted), expected $ExpectedDeleted."
        Stop-OnFailure
        return $null
    }

    foreach ($scanId in $ExpectedStates.Keys) {
        $actualState = Get-RecordStateByScanId -ListResponse $report -ScanId $scanId
        if ($actualState -ne $ExpectedStates[$scanId]) {
            Register-Result "FAIL" $Label "scan_id '$scanId' had state '$actualState', expected '$($ExpectedStates[$scanId])'."
            Stop-OnFailure
            return $null
        }
    }

    Register-Result "PASS" $Label "List summary matched expectation in $($result.DurationSeconds)s."
    return $report
}

function Invoke-QuarantineOperationCheck {
    param(
        [string]$Label,
        [string[]]$ArgumentList,
        [string]$ExpectedOperation,
        [string]$ExpectedScanId,
        [string]$ExpectedStateBefore,
        [string]$ExpectedStateAfter,
        [string]$StdoutFileName,
        [string]$StderrFileName
    )

    $stdoutPath = Join-Path $outputDir $StdoutFileName
    $stderrPath = Join-Path $outputDir $StderrFileName
    $result = Invoke-LoggedProcess `
        -FilePath $pythonResolved `
        -ArgumentList $ArgumentList `
        -StdoutPath $stdoutPath `
        -StderrPath $stderrPath `
        -TimeoutSeconds $StepTimeoutSeconds

    if ($result.TimedOut) {
        Register-Result "FAIL" $Label "Timed out after $StepTimeoutSeconds seconds. See $stdoutPath and $stderrPath."
        Stop-OnFailure
        return $null
    }

    if ($result.ExitCode -ne 0) {
        Register-Result "FAIL" $Label "Exit code was $($result.ExitCode), expected 0."
        Stop-OnFailure
        return $null
    }

    $report = Read-JsonFile $stdoutPath
    if (-not $report.ok) {
        Register-Result "FAIL" $Label "operation did not complete successfully."
        Stop-OnFailure
        return $null
    }

    if ($report.operation -ne $ExpectedOperation) {
        Register-Result "FAIL" $Label "operation was '$($report.operation)', expected '$ExpectedOperation'."
        Stop-OnFailure
        return $null
    }

    if ($report.scan_id -ne $ExpectedScanId) {
        Register-Result "FAIL" $Label "scan_id was '$($report.scan_id)', expected '$ExpectedScanId'."
        Stop-OnFailure
        return $null
    }

    if ($report.state_before -ne $ExpectedStateBefore) {
        Register-Result "FAIL" $Label "state_before was '$($report.state_before)', expected '$ExpectedStateBefore'."
        Stop-OnFailure
        return $null
    }

    if ($report.state_after -ne $ExpectedStateAfter) {
        Register-Result "FAIL" $Label "state_after was '$($report.state_after)', expected '$ExpectedStateAfter'."
        Stop-OnFailure
        return $null
    }

    Register-Result "PASS" $Label "Lifecycle operation matched expectation in $($result.DurationSeconds)s."
    return $report
}

$pythonResolved = Resolve-RepoPath $PythonExe
$configResolved = Resolve-RepoPath $ConfigPath

if (-not $pythonResolved -or -not (Test-Path -LiteralPath $pythonResolved)) {
    Write-Step "FAIL" "Python" "Python executable was not found. Use .\.venv\Scripts\python.exe or pass -PythonExe with a valid path."
    exit 1
}

if (-not $configResolved -or -not (Test-Path -LiteralPath $configResolved)) {
    Write-Step "FAIL" "Config" "Config file was not found. Pass -ConfigPath with a valid path."
    exit 1
}

$timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$outputDir = Join-Path $root "reports\acceptance-v2-quarantine\$timestamp"
$quarantineDir = Join-Path $outputDir "quarantine"
$runtimeTempDir = Join-Path $outputDir "tmp"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
New-Item -ItemType Directory -Force -Path $quarantineDir | Out-Null
New-Item -ItemType Directory -Force -Path $runtimeTempDir | Out-Null

$env:SCANBOX_QUARANTINE_DIRECTORY = $quarantineDir
$env:TEMP = $runtimeTempDir
$env:TMP = $runtimeTempDir

$restoreSample = Join-Path $outputDir "eicar-restore.com"
$deleteSample = Join-Path $outputDir "eicar-delete.com"
Copy-Item -LiteralPath (Join-Path $root "tests\fixtures\eicar\eicar.com") -Destination $restoreSample -Force
Copy-Item -LiteralPath (Join-Path $root "tests\fixtures\eicar\eicar.com") -Destination $deleteSample -Force

$passCount = 0
$failCount = 0

Write-Host "ScanBox V2.1 quarantine acceptance"
Write-Host "Repo root: $root"
Write-Host "Config: $configResolved"
Write-Host "Output dir: $outputDir"
Write-Host "Quarantine dir: $quarantineDir"
Write-Host "Runtime temp dir: $runtimeTempDir"
Write-Host "Step timeout: $StepTimeoutSeconds seconds"
Write-Host ""

Run-MustPassProcessStep `
    -Label "Editable install" `
    -FilePath $pythonResolved `
    -ArgumentList @("-m", "pip", "install", "-e", ".") `
    -StdoutFileName "pip-install.stdout.log" `
    -StderrFileName "pip-install.stderr.log"

Run-MustPassProcessStep `
    -Label "pytest" `
    -FilePath $pythonResolved `
    -ArgumentList @("-m", "pytest", "-q") `
    -StdoutFileName "pytest.stdout.log" `
    -StderrFileName "pytest.stderr.log"

$restoreScan = Invoke-QuarantineMove `
    -Label "quarantine move restore sample" `
    -TargetPath $restoreSample `
    -StdoutFileName "scan-restore.stdout.json" `
    -StderrFileName "scan-restore.stderr.log"

$deleteScan = Invoke-QuarantineMove `
    -Label "quarantine move delete sample" `
    -TargetPath $deleteSample `
    -StdoutFileName "scan-delete.stdout.json" `
    -StderrFileName "scan-delete.stderr.log"

$restoreScanId = $restoreScan.scan_id
$deleteScanId = $deleteScan.scan_id

$null = Invoke-QuarantineListCheck `
    -Label "quarantine list before lifecycle operations" `
    -StdoutFileName "list-before.stdout.json" `
    -StderrFileName "list-before.stderr.log" `
    -ExpectedTotal 2 `
    -ExpectedQuarantined 2 `
    -ExpectedRestored 0 `
    -ExpectedDeleted 0 `
    -ExpectedStates @{
        $restoreScanId = "quarantined"
        $deleteScanId = "quarantined"
    }

$null = Invoke-QuarantineOperationCheck `
    -Label "quarantine restore" `
    -ArgumentList @("-m", "scanbox", "quarantine", "restore", $restoreScanId, "--config", $configResolved) `
    -ExpectedOperation "restore" `
    -ExpectedScanId $restoreScanId `
    -ExpectedStateBefore "quarantined" `
    -ExpectedStateAfter "restored" `
    -StdoutFileName "restore.stdout.json" `
    -StderrFileName "restore.stderr.log"

$null = Invoke-QuarantineOperationCheck `
    -Label "quarantine delete" `
    -ArgumentList @("-m", "scanbox", "quarantine", "delete", $deleteScanId, "--config", $configResolved, "--yes") `
    -ExpectedOperation "delete" `
    -ExpectedScanId $deleteScanId `
    -ExpectedStateBefore "quarantined" `
    -ExpectedStateAfter "deleted" `
    -StdoutFileName "delete.stdout.json" `
    -StderrFileName "delete.stderr.log"

$null = Invoke-QuarantineListCheck `
    -Label "quarantine list after lifecycle operations" `
    -StdoutFileName "list-after.stdout.json" `
    -StderrFileName "list-after.stderr.log" `
    -ExpectedTotal 2 `
    -ExpectedQuarantined 0 `
    -ExpectedRestored 1 `
    -ExpectedDeleted 1 `
    -ExpectedStates @{
        $restoreScanId = "restored"
        $deleteScanId = "deleted"
    }

Write-Host ""
Write-Host "Summary: PASS=$passCount FAIL=$failCount"
Write-Host "Acceptance artifacts: $outputDir"

if ($failCount -gt 0) {
    exit 1
}

exit 0
