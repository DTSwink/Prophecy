[CmdletBinding()]
param(
    [ValidateSet('Development', 'Shipping')]
    [string]$Configuration = 'Development',
    [Parameter(Mandatory = $true)]
    [string]$Executable,
    [Parameter(Mandatory = $true)]
    [string]$PreflightOutput,
    [string[]]$ProgramArguments = @()
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Local explicit diagnostic only. No Jolt DLL is imported by PowerShell or this
# baseline helper. Directly launching the AVX2 game/editor bypasses this guard.
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$installRoot = Join-Path $projectRoot "Intermediate/JoltMigration/Install/AVX2/$Configuration"
$manifest = Get-Content -LiteralPath (Join-Path $installRoot 'manifest.json') -Raw | ConvertFrom-Json
$probe = Join-Path $installRoot 'tools/ProphecyJoltCpuPreflight.exe'
if ($manifest.schema -ne 3 -or $manifest.simd -ne 'AVX2' -or -not $manifest.fma -or $manifest.instructionMask -ne 2015) {
    throw 'The selected dependency is not the verified AVX2/FMA diagnostic profile.'
}
if ((Get-FileHash -LiteralPath $probe -Algorithm SHA256).Hash -ne $manifest.cpuPreflightSha256) {
    throw 'CPU preflight binary hash does not match its build manifest.'
}
if ($PreflightOutput -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/][^\\/]+[\\/])') {
    throw '-PreflightOutput must be an absolute new JSON path.'
}
$outputPath = [IO.Path]::GetFullPath($PreflightOutput)
if (Test-Path -LiteralPath $outputPath) { throw "Preflight output already exists: $outputPath" }
if (-not (Test-Path -LiteralPath ([IO.Path]::GetDirectoryName($outputPath)) -PathType Container)) {
    throw 'Create the output directory before starting this diagnostic.'
}
$lines = @(& $probe)
$probeExit = $LASTEXITCODE
$result = ($lines -join [Environment]::NewLine) | ConvertFrom-Json
# Record refusals as well as successful admission; never overwrite a prior run.
$record = [ordered]@{
    schema = 1; timestampUtc = [DateTime]::UtcNow.ToString('o')
    configuration = $Configuration; profile = 'AVX2_FMA_PRECISE'
    nativeDllSha256 = $manifest.dllSha256; cpuPreflightSha256 = $manifest.cpuPreflightSha256
    executable = $Executable; probeExitCode = $probeExit; cpu = $result
}
$text = $record | ConvertTo-Json -Depth 6
$stream = [IO.File]::Open($outputPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
try {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($text + [Environment]::NewLine)
    $stream.Write($bytes, 0, $bytes.Length)
}
finally { $stream.Dispose() }
if ($probeExit -ne 0 -or -not $result.supported -or $result.required_instruction_mask -ne 2015) {
    throw "CPU/OS preflight refused AVX2/FMA launch. See $outputPath"
}
Write-Output "AVX2/FMA CPU preflight passed; report: $outputPath"
& $Executable @ProgramArguments
if ($LASTEXITCODE -ne 0) { throw "$Executable returned $LASTEXITCODE." }
