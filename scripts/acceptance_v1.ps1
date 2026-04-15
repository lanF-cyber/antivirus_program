param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$ConfigPath = ".\config\scanbox.toml",
    [int]$StepTimeoutSeconds = 180,
    [switch]$IncludeLocalEnhancements
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

    $startedAt = Get-Date
    [void]$process.Start()

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

function Stop-OnFailure {
    if ($script:failCount -gt 0) {
        Write-Host ""
        Write-Host "Summary: PASS=$passCount FAIL=$failCount"
        Write-Host "Acceptance artifacts: $outputDir"
        exit 1
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

function Invoke-ScanCheck {
    param(
        [string]$Label,
        [string]$Target,
        [int]$ExpectedExitCode,
        [string]$ExpectedStatus,
        [string]$ExpectedCapaState,
        [string]$ExpectedCapaSkipReason,
        [string]$StdoutFileName,
        [string]$StderrFileName
    )

    $stdoutPath = Join-Path $outputDir $StdoutFileName
    $stderrPath = Join-Path $outputDir $StderrFileName
    $result = Invoke-LoggedProcess `
        -FilePath $pythonResolved `
        -ArgumentList @("-m", "scanbox", "scan", $Target, "--config", $configResolved) `
        -StdoutPath $stdoutPath `
        -StderrPath $stderrPath `
        -TimeoutSeconds $StepTimeoutSeconds

    if ($result.TimedOut) {
        Register-Result "FAIL" $Label "Timed out after $StepTimeoutSeconds seconds. See $stdoutPath and $stderrPath."
        Stop-OnFailure
        return
    }

    if ($result.ExitCode -ne $ExpectedExitCode) {
        Register-Result "FAIL" $Label "Exit code was $($result.ExitCode), expected $ExpectedExitCode. See $stdoutPath and $stderrPath."
        Stop-OnFailure
        return
    }

    $stdoutText = Get-Content -LiteralPath $stdoutPath -Raw
    try {
        $report = $stdoutText | ConvertFrom-Json
    } catch {
        Register-Result "FAIL" $Label "stdout was not valid JSON. See $stdoutPath."
        Stop-OnFailure
        return
    }

    if ($report.overall_status -ne $ExpectedStatus) {
        Register-Result "FAIL" $Label "overall_status was '$($report.overall_status)', expected '$ExpectedStatus'."
        Stop-OnFailure
        return
    }

    if ($ExpectedCapaState -and $report.engines.capa.state -ne $ExpectedCapaState) {
        Register-Result "FAIL" $Label "engines.capa.state was '$($report.engines.capa.state)', expected '$ExpectedCapaState'."
        Stop-OnFailure
        return
    }

    if ($ExpectedCapaSkipReason) {
        $actualSkipReason = $report.engines.capa.raw_summary.skip_reason
        if ($actualSkipReason -ne $ExpectedCapaSkipReason) {
            Register-Result "FAIL" $Label "capa skip_reason was '$actualSkipReason', expected '$ExpectedCapaSkipReason'."
            Stop-OnFailure
            return
        }
    }

    Register-Result "PASS" $Label "Exit code and report status matched expectation in $($result.DurationSeconds)s."
}

function Invoke-OptionalLocalEnhancement {
    $stdoutPath = Join-Path $outputDir "python.stdout.json"
    $stderrPath = Join-Path $outputDir "python.stderr.log"
    $fullPath = Join-Path $outputDir "python.full.json"
    $result = Invoke-LoggedProcess `
        -FilePath $pythonResolved `
        -ArgumentList @("-m", "scanbox", "scan", ".\.venv\Scripts\python.exe", "--config", $configResolved, "--report-out", $fullPath) `
        -StdoutPath $stdoutPath `
        -StderrPath $stderrPath `
        -TimeoutSeconds $StepTimeoutSeconds

    if ($result.TimedOut) {
        Register-Result "FAIL" "python.exe enhancement" "Timed out after $StepTimeoutSeconds seconds. See $stdoutPath and $stderrPath."
        return
    }

    if ($result.ExitCode -ne 0) {
        Register-Result "FAIL" "python.exe enhancement" "Exit code was $($result.ExitCode). See $stdoutPath and $stderrPath."
        return
    }

    $stdoutText = Get-Content -LiteralPath $stdoutPath -Raw
    try {
        $report = $stdoutText | ConvertFrom-Json
    } catch {
        Register-Result "FAIL" "python.exe enhancement" "stdout was not valid JSON. See $stdoutPath."
        return
    }

    if ($report.engines.capa.state -ne "ok") {
        Register-Result "FAIL" "python.exe enhancement" "engines.capa.state was '$($report.engines.capa.state)', expected 'ok'."
        return
    }

    $stdoutBytes = (Get-Item -LiteralPath $stdoutPath).Length
    $fullBytes = (Get-Item -LiteralPath $fullPath).Length
    Register-Result "PASS" "python.exe enhancement" "capa manual sample passed in $($result.DurationSeconds)s. stdout=${stdoutBytes}B full=${fullBytes}B."
}

$pythonResolved = Resolve-RepoPath $PythonExe
$configResolved = Resolve-RepoPath $ConfigPath
$powershellResolved = (Get-Command powershell).Source

if (-not $pythonResolved -or -not (Test-Path -LiteralPath $pythonResolved)) {
    Write-Step "FAIL" "Python" "Python executable was not found. Use .\.venv\Scripts\python.exe or pass -PythonExe with a valid path."
    exit 1
}

if (-not $configResolved -or -not (Test-Path -LiteralPath $configResolved)) {
    Write-Step "FAIL" "Config" "Config file was not found. Pass -ConfigPath with a valid path."
    exit 1
}

$timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$outputDir = Join-Path $root "reports\acceptance-v1\$timestamp"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$passCount = 0
$failCount = 0

Write-Host "ScanBox v1 acceptance"
Write-Host "Repo root: $root"
Write-Host "Config: $configResolved"
Write-Host "Output dir: $outputDir"
Write-Host "Step timeout: $StepTimeoutSeconds seconds"
if ($IncludeLocalEnhancements) {
    Write-Host "Local enhancements: enabled"
} else {
    Write-Host "Local enhancements: disabled"
}
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

Run-MustPassProcessStep `
    -Label "verify_env" `
    -FilePath $powershellResolved `
    -ArgumentList @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $root "scripts\verify_env.ps1")) `
    -StdoutFileName "verify_env.stdout.log" `
    -StderrFileName "verify_env.stderr.log"

Invoke-ScanCheck `
    -Label "hello.txt" `
    -Target ".\tests\fixtures\benign\hello.txt" `
    -ExpectedExitCode 0 `
    -ExpectedStatus "clean_by_known_checks" `
    -ExpectedCapaState "skipped_not_applicable" `
    -ExpectedCapaSkipReason "not_applicable_for_target" `
    -StdoutFileName "hello.stdout.json" `
    -StderrFileName "hello.stderr.log"

Invoke-ScanCheck `
    -Label "script.ps1" `
    -Target ".\tests\fixtures\benign\script.ps1" `
    -ExpectedExitCode 0 `
    -ExpectedStatus "clean_by_known_checks" `
    -ExpectedCapaState "skipped_not_applicable" `
    -ExpectedCapaSkipReason "script_file_not_supported_in_v1_policy" `
    -StdoutFileName "script.stdout.json" `
    -StderrFileName "script.stderr.log"

Invoke-ScanCheck `
    -Label "eicar.com" `
    -Target ".\tests\fixtures\eicar\eicar.com" `
    -ExpectedExitCode 1 `
    -ExpectedStatus "known_malicious" `
    -ExpectedCapaState "skipped_not_applicable" `
    -ExpectedCapaSkipReason "not_applicable_for_target" `
    -StdoutFileName "eicar.stdout.json" `
    -StderrFileName "eicar.stderr.log"

if ($IncludeLocalEnhancements) {
    Invoke-OptionalLocalEnhancement
}

Write-Host ""
Write-Host "Summary: PASS=$passCount FAIL=$failCount"
Write-Host "Acceptance artifacts: $outputDir"

if ($failCount -gt 0) {
    exit 1
}

exit 0
