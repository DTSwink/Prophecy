<#
.SYNOPSIS
Launches and validates an already-staged Prophecy Jolt smoke host. Does not build or cook.
.DESCRIPTION
Pass the direct staged game executable in Binaries/Win64, not a package-root bootstrap.
A pass requires exit code zero, the host's stdout SUCCESS marker, no FAILED marker,
and boolean success:true in its newly created fixture JSON. The owned process gets
TimeoutSeconds to exit, with at most five additional seconds for timeout cleanup.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Executable,

    [ValidateRange(1, 1800)]
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# IsPathRooted alone also accepts drive-relative C:foo and root-relative \foo.
if ($Executable -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/][^\\/]+[\\/])') {
    throw '-Executable must be an absolute Windows file path.'
}
$joltResolvedExecutable = Resolve-Path -LiteralPath $Executable
if ($joltResolvedExecutable.Provider.Name -ne 'FileSystem') {
    throw '-Executable must resolve to the filesystem.'
}
$joltExecutableItem = Get-Item -LiteralPath $joltResolvedExecutable.ProviderPath
if ($joltExecutableItem.PSIsContainer) { throw '-Executable must name a file.' }
$joltAllowedNames = @('ProphecyJoltSmokeHost.exe', 'ProphecyJoltSmokeHost-Win64-Shipping.exe')
if ($joltExecutableItem.Name -notin $joltAllowedNames) {
    throw "Unexpected executable basename '$($joltExecutableItem.Name)'. Only the staged ProphecyJoltSmokeHost is allowed."
}
$joltExecutablePath = $joltExecutableItem.FullName
$joltExecutableHash = (Get-FileHash -LiteralPath $joltExecutablePath -Algorithm SHA256).Hash
$joltProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).ProviderPath
$joltReportParent = Join-Path $joltProjectRoot 'Saved/JoltMigration'
[System.IO.Directory]::CreateDirectory($joltReportParent) | Out-Null
$joltReportDirectory = Join-Path $joltReportParent ('PackagedFixture-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff'))
# No -Force: a timestamp collision fails instead of reusing somebody else's report directory.
New-Item -ItemType Directory -Path $joltReportDirectory | Out-Null
$joltResultPath = Join-Path $joltReportDirectory 'fixture.json'
$joltStdoutPath = Join-Path $joltReportDirectory 'stdout.log'
$joltStderrPath = Join-Path $joltReportDirectory 'stderr.log'
$joltRunnerPath = Join-Path $joltReportDirectory 'runner.json'
foreach ($joltOutputPath in @($joltResultPath, $joltStdoutPath, $joltStderrPath, $joltRunnerPath)) {
    if (Test-Path -LiteralPath $joltOutputPath) { throw "Report path is already in use: $joltOutputPath" }
}

$joltArguments = '-nullrhi -unattended -nosplash -nosound -stdout -FullStdOutLogOutput' +
    ' -ProphecyJoltValidateFixture -ProphecyJoltFixtureResult="' + $joltResultPath + '"'
$joltSuccessMarker = 'PROPHECY_JOLT_FIXTURE_VALIDATION_SUCCESS'
$joltFailedMarker = 'PROPHECY_JOLT_FIXTURE_VALIDATION_FAILED'
$joltFailures = [System.Collections.Generic.List[string]]::new()
$joltOwnedProcess = $null
$joltOwnedProcessId = $null
$joltExitCode = $null
$joltTimedOut = $false
$joltTimeoutKillIssued = $false
$joltExited = $false
$joltPriorityApplied = $false
$joltJsonSuccess = $false
$joltStdoutSuccess = $false
$joltFailureMarkerFound = $false
$joltStartedUtc = [DateTime]::UtcNow
$joltElapsed = [System.Diagnostics.Stopwatch]::StartNew()

try {
    $joltOwnedProcess = Start-Process -FilePath $joltExecutablePath -ArgumentList $joltArguments `
        -WorkingDirectory $joltExecutableItem.DirectoryName -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $joltStdoutPath -RedirectStandardError $joltStderrPath
    $joltOwnedProcessId = $joltOwnedProcess.Id
    Write-Output "Packaged Jolt fixture process $joltOwnedProcessId; report $joltReportDirectory"
    try {
        $joltOwnedProcess.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
        $joltPriorityApplied = $true
    }
    catch {
        $joltFailures.Add("Could not apply BelowNormal priority: $($_.Exception.Message)")
    }

    while (-not $joltExited) {
        $joltRemainingMilliseconds = [int][Math]::Max(0, ($TimeoutSeconds * 1000.0) - $joltElapsed.Elapsed.TotalMilliseconds)
        $joltExited = $joltOwnedProcess.WaitForExit([Math]::Min(1000, $joltRemainingMilliseconds))
        if ($joltExited) { break }
        if ($joltElapsed.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
            $joltTimedOut = $true
            $joltFailures.Add("Owned smoke-host process exceeded $TimeoutSeconds seconds.")
            # This is the Process object returned by our Start-Process, never a name/PID lookup.
            # Do not enumerate or terminate any existing editor, game, bootstrap child or process tree.
            if (-not $joltOwnedProcess.HasExited) {
                try {
                    $joltOwnedProcess.Kill()
                    $joltTimeoutKillIssued = $true
                }
                catch {
                    if (-not $joltOwnedProcess.HasExited) {
                        $joltFailures.Add("Could not terminate owned timed-out process: $($_.Exception.Message)")
                    }
                }
            }
            $joltExited = $joltOwnedProcess.WaitForExit(5000)
            if (-not $joltExited) { $joltFailures.Add('Owned process did not exit within the bounded timeout cleanup wait.') }
            break
        }
    }
    if ($joltExited) { $joltExitCode = $joltOwnedProcess.ExitCode }
}
catch {
    $joltFailures.Add("Process launch/wait failed: $($_.Exception.Message)")
}

# A timed Process.WaitForExit does not promise asynchronous stdout handlers have drained.
# Allow a bounded two-second output-settle interval; never use an unbounded WaitForExit().
if ($joltExited) {
    $joltSettleDeadline = [DateTime]::UtcNow.AddSeconds(2)
    do {
        try {
            if (Test-Path -LiteralPath $joltStdoutPath -PathType Leaf) {
                $joltPreview = [System.IO.File]::ReadAllText($joltStdoutPath)
                if ($joltPreview.Contains($joltSuccessMarker) -or $joltPreview.Contains($joltFailedMarker)) { break }
            }
        }
        catch { } # A final read below reports any persistent read error as a validation failure.
        Start-Sleep -Milliseconds 50
    } while ([DateTime]::UtcNow -lt $joltSettleDeadline)
}

try {
    $joltStdout = [System.IO.File]::ReadAllText($joltStdoutPath)
    $joltStderr = [System.IO.File]::ReadAllText($joltStderrPath)
    $joltStdoutSuccess = $joltStdout.Contains($joltSuccessMarker)
    $joltFailureMarkerFound = $joltStdout.Contains($joltFailedMarker) -or $joltStderr.Contains($joltFailedMarker)
    if (-not $joltStdoutSuccess) { $joltFailures.Add('Stdout is missing the fixture SUCCESS marker.') }
    if ($joltFailureMarkerFound) { $joltFailures.Add('Captured output contains a fixture FAILED marker.') }
}
catch {
    $joltFailures.Add("Could not read captured stdout/stderr: $($_.Exception.Message)")
}
try {
    $joltFixtureResult = Get-Content -Raw -Encoding UTF8 -LiteralPath $joltResultPath | ConvertFrom-Json
    if ($null -ne $joltFixtureResult) {
        $joltSuccessProperty = $joltFixtureResult.PSObject.Properties['success']
        $joltJsonSuccess = $null -ne $joltSuccessProperty -and $joltSuccessProperty.Value -is [bool] -and $joltSuccessProperty.Value
    }
    if (-not $joltJsonSuccess) { $joltFailures.Add('Fixture JSON does not contain boolean success:true.') }
}
catch {
    $joltFailures.Add("Fixture JSON is missing, unreadable or invalid: $($_.Exception.Message)")
}
if ($null -eq $joltExitCode -or $joltExitCode -ne 0) {
    $joltFailures.Add("Smoke-host exit code was not zero (value: '$joltExitCode').")
}
$joltElapsed.Stop()
$joltPassed = $joltFailures.Count -eq 0 -and $joltJsonSuccess -and $joltStdoutSuccess -and
    -not $joltFailureMarkerFound -and $joltExitCode -eq 0 -and -not $joltTimedOut -and $joltPriorityApplied
$joltRunner = [ordered]@{
    schema = 1
    success = [bool]$joltPassed
    executable = $joltExecutablePath
    executableSha256 = $joltExecutableHash
    arguments = $joltArguments
    workingDirectory = $joltExecutableItem.DirectoryName
    startedUtc = $joltStartedUtc.ToString('o')
    finishedUtc = [DateTime]::UtcNow.ToString('o')
    elapsedSeconds = $joltElapsed.Elapsed.TotalSeconds
    timeoutSeconds = $TimeoutSeconds
    processId = $joltOwnedProcessId
    processExited = $joltExited
    exitCode = $joltExitCode
    timedOut = $joltTimedOut
    timeoutKillIssued = $joltTimeoutKillIssued
    requestedPriority = 'BelowNormal'
    priorityApplied = $joltPriorityApplied
    fixtureJsonSuccess = $joltJsonSuccess
    stdoutSuccessMarker = $joltStdoutSuccess
    failedMarkerFound = $joltFailureMarkerFound
    fixtureResult = $joltResultPath
    stdout = $joltStdoutPath
    stderr = $joltStderrPath
    runnerResult = $joltRunnerPath
    failures = @($joltFailures.ToArray())
}
$joltRunnerJson = $joltRunner | ConvertTo-Json -Depth 6
$joltRunnerBytes = [System.Text.UTF8Encoding]::new($false).GetBytes($joltRunnerJson)
$joltRunnerStream = [System.IO.File]::Open($joltRunnerPath, [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
try { $joltRunnerStream.Write($joltRunnerBytes, 0, $joltRunnerBytes.Length) }
finally { $joltRunnerStream.Dispose() }
if ($null -ne $joltOwnedProcess) { $joltOwnedProcess.Dispose() }
if (-not $joltPassed) { throw "Packaged Jolt fixture validation failed. See $joltRunnerPath" }
[pscustomobject]@{ Success = $true; ExitCode = $joltExitCode; Report = $joltRunnerPath; FixtureResult = $joltResultPath } | ConvertTo-Json
