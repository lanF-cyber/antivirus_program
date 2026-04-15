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

function Assert-DirectoryReport {
    param(
        [string]$Label,
        [object]$Report
    )

    if ($Report.mode -ne "directory") {
        Register-Result "FAIL" $Label "mode was '$($Report.mode)', expected 'directory'."
        Stop-OnFailure
        return
    }

    if ($Report.target_count -ne 3) {
        Register-Result "FAIL" $Label "target_count was $($Report.target_count), expected 3."
        Stop-OnFailure
        return
    }

    if ($Report.scanned_count -ne 3) {
        Register-Result "FAIL" $Label "scanned_count was $($Report.scanned_count), expected 3."
        Stop-OnFailure
        return
    }

    if ($Report.overall_status -ne "known_malicious") {
        Register-Result "FAIL" $Label "overall_status was '$($Report.overall_status)', expected 'known_malicious'."
        Stop-OnFailure
        return
    }

    if ($Report.summary.known_malicious -ne 1) {
        Register-Result "FAIL" $Label "summary.known_malicious was $($Report.summary.known_malicious), expected 1."
        Stop-OnFailure
        return
    }

    if ($Report.summary.clean_by_known_checks -ne 2) {
        Register-Result "FAIL" $Label "summary.clean_by_known_checks was $($Report.summary.clean_by_known_checks), expected 2."
        Stop-OnFailure
        return
    }

    $actualOrder = @($Report.results | ForEach-Object { $_.relative_path })
    $expectedOrder = @(
        "hello.txt",
        "nested/eicar.com",
        "script.ps1"
    )
    if ([string]::Join("|", $actualOrder) -ne [string]::Join("|", $expectedOrder)) {
        Register-Result "FAIL" $Label "results[] order did not match the required relative-path lexicographic order."
        Stop-OnFailure
        return
    }

    $hello = $Report.results | Where-Object { $_.relative_path -eq "hello.txt" } | Select-Object -First 1
    $eicar = $Report.results | Where-Object { $_.relative_path -eq "nested/eicar.com" } | Select-Object -First 1
    $script = $Report.results | Where-Object { $_.relative_path -eq "script.ps1" } | Select-Object -First 1

    if ($null -eq $hello -or $hello.report.overall_status -ne "clean_by_known_checks") {
        Register-Result "FAIL" $Label "hello.txt child result did not report 'clean_by_known_checks'."
        Stop-OnFailure
        return
    }

    if ($null -eq $eicar -or $eicar.report.overall_status -ne "known_malicious") {
        Register-Result "FAIL" $Label "nested/eicar.com child result did not report 'known_malicious'."
        Stop-OnFailure
        return
    }

    if ($null -eq $script -or $script.report.overall_status -ne "clean_by_known_checks") {
        Register-Result "FAIL" $Label "script.ps1 child result did not report 'clean_by_known_checks'."
        Stop-OnFailure
        return
    }

    if ($script.report.engines.capa.state -ne "skipped_not_applicable") {
        Register-Result "FAIL" $Label "script.ps1 capa state was '$($script.report.engines.capa.state)', expected 'skipped_not_applicable'."
        Stop-OnFailure
        return
    }

    $skipReason = $script.report.engines.capa.raw_summary.skip_reason
    if ($skipReason -ne "script_file_not_supported_in_v1_policy") {
        Register-Result "FAIL" $Label "script.ps1 capa skip_reason was '$skipReason', expected 'script_file_not_supported_in_v1_policy'."
        Stop-OnFailure
        return
    }
}

function Invoke-DirectoryScanCheck {
    param(
        [string]$Label,
        [switch]$WithReportOut,
        [string]$StdoutFileName,
        [string]$StderrFileName
    )

    $stdoutPath = Join-Path $outputDir $StdoutFileName
    $stderrPath = Join-Path $outputDir $StderrFileName
    $arguments = @("-m", "scanbox", "scan", ".\tests\fixtures\directory_mvp", "--config", $configResolved)
    if ($WithReportOut) {
        $arguments += @("--report-out", $directoryFullReportPath)
    }

    $result = Invoke-LoggedProcess `
        -FilePath $pythonResolved `
        -ArgumentList $arguments `
        -StdoutPath $stdoutPath `
        -StderrPath $stderrPath `
        -TimeoutSeconds $StepTimeoutSeconds

    if ($result.TimedOut) {
        Register-Result "FAIL" $Label "Timed out after $StepTimeoutSeconds seconds. See $stdoutPath and $stderrPath."
        Stop-OnFailure
        return
    }

    if ($result.ExitCode -ne 1) {
        Register-Result "FAIL" $Label "Exit code was $($result.ExitCode), expected 1."
        Stop-OnFailure
        return
    }

    $report = Read-JsonFile $stdoutPath
    Assert-DirectoryReport -Label $Label -Report $report

    if ($WithReportOut) {
        if (-not (Test-Path -LiteralPath $directoryFullReportPath)) {
            Register-Result "FAIL" $Label "Full report was not written to $directoryFullReportPath."
            Stop-OnFailure
            return
        }

        $fullReport = Read-JsonFile $directoryFullReportPath
        if ($fullReport.mode -ne "directory") {
            Register-Result "FAIL" $Label "Full report mode was '$($fullReport.mode)', expected 'directory'."
            Stop-OnFailure
            return
        }

        if ($null -eq $fullReport.summary -or $null -eq $fullReport.results) {
            Register-Result "FAIL" $Label "Full report did not contain the expected top-level structure."
            Stop-OnFailure
            return
        }
    }

    Register-Result "PASS" $Label "Directory scan matched the V2.2-A baseline in $($result.DurationSeconds)s."
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
$outputDir = Join-Path $root "reports\acceptance-v2-directory\$timestamp"
$directoryFullReportPath = Join-Path $outputDir "directory.full.json"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$passCount = 0
$failCount = 0

Write-Host "ScanBox V2.2-A directory acceptance"
Write-Host "Repo root: $root"
Write-Host "Config: $configResolved"
Write-Host "Output dir: $outputDir"
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

Invoke-DirectoryScanCheck `
    -Label "directory scan stdout" `
    -StdoutFileName "directory.stdout.json" `
    -StderrFileName "directory.stderr.log"

Invoke-DirectoryScanCheck `
    -Label "directory scan report_out" `
    -WithReportOut `
    -StdoutFileName "directory-report-out.stdout.json" `
    -StderrFileName "directory-report-out.stderr.log"

Write-Host ""
Write-Host "Summary: PASS=$passCount FAIL=$failCount"
Write-Host "Acceptance artifacts: $outputDir"

if ($failCount -gt 0) {
    exit 1
}

exit 0
