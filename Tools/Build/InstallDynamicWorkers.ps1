param([string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.7')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$sourceDirectory = Join-Path $EngineRoot 'Engine\Source\Programs\Shared\EpicGames.UBA'
$schedulerPath = Join-Path $sourceDirectory 'Impl\SchedulerImpl.cs'
$extensionPath = Join-Path $sourceDirectory 'Impl\DynamicMemoryScheduler.cs'
$installedDll = Join-Path $EngineRoot 'Engine\Binaries\DotNET\UnrealBuildTool\EpicGames.UBA.dll'
$projectExtension = Join-Path $PSScriptRoot 'DynamicMemoryScheduler.cs'
$stateDirectory = Join-Path $projectRoot 'Saved\BuildTools\DynamicWorkers'
$manifestPath = Join-Path $stateDirectory 'installed.json'
$version = Get-Content -LiteralPath (Join-Path $EngineRoot 'Engine\Build\Build.version') -Raw | ConvertFrom-Json
if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 7) {
    throw 'This build-tool adapter is validated for UE 5.7. Review it before installing on another engine version.'
}
$extensionHash = (Get-FileHash -LiteralPath $projectExtension).Hash
if (Test-Path -LiteralPath $manifestPath) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.extensionHash -eq $extensionHash -and
        $manifest.dllHash -eq (Get-FileHash -LiteralPath $installedDll).Hash -and
        $manifest.schedulerHash -eq (Get-FileHash -LiteralPath $schedulerPath).Hash -and
        (Test-Path -LiteralPath $extensionPath) -and
        (Get-FileHash -LiteralPath $extensionPath).Hash -eq $extensionHash) {
        Write-Output 'Dynamic worker adapter already installed; no build needed.'
        return
    }
}
$source = Get-Content -LiteralPath $schedulerPath -Raw
$changes = @(
    @('internal class SchedulerImpl : IScheduler', 'internal partial class SchedulerImpl : IScheduler'),
    @('_schedulerHandle = Scheduler_Create3(server.GetHandle(), cc, cacheClientCount, config.GetHandle());',
      "_schedulerHandle = Scheduler_Create3(server.GetHandle(), cc, cacheClientCount, config.GetHandle());`r`n`t`t`tStartDynamicMemoryLimit(maxLocalProcessors);"),
    @("protected virtual void Dispose(bool disposing)`r`n`t`t{", "protected virtual void Dispose(bool disposing)`r`n`t`t{`r`n`t`t`tStopDynamicMemoryLimit();")
)
foreach ($change in $changes) {
    if ($source.Contains($change[1])) { continue }
    if (-not $source.Contains($change[0])) { throw 'Unexpected SchedulerImpl layout; no files changed.' }
    $source = $source.Replace($change[0], $change[1])
}
New-Item -ItemType Directory -Force -Path $stateDirectory | Out-Null
foreach ($entry in @(@($schedulerPath, 'SchedulerImpl.cs.original'), @($installedDll, 'EpicGames.UBA.dll.original'))) {
    $backup = Join-Path $stateDirectory $entry[1]
    if (-not (Test-Path -LiteralPath $backup)) { Copy-Item -LiteralPath $entry[0] -Destination $backup }
}
$wasReadOnly = (Get-Item -LiteralPath $schedulerPath).IsReadOnly
try {
    Set-ItemProperty -LiteralPath $schedulerPath -Name IsReadOnly -Value $false
    [IO.File]::WriteAllText($schedulerPath, $source)
    Copy-Item -LiteralPath $projectExtension -Destination $extensionPath -Force
    $dotnet = Join-Path $EngineRoot 'Engine\Binaries\ThirdParty\DotNet\8.0.412\win-x64\dotnet.exe'
    $outputDirectory = Join-Path $stateDirectory 'compiled'
    & $dotnet build (Join-Path $sourceDirectory 'EpicGames.UBA.csproj') -c Development --no-restore -p:BuildProjectReferences=false -p:UseSharedCompilation=false "-o=$outputDirectory" --nologo
    if ($LASTEXITCODE -ne 0) { throw 'Build-tool compilation failed; installed DLL was not replaced.' }
    $dllWasReadOnly = (Get-Item -LiteralPath $installedDll).IsReadOnly
    try {
        Set-ItemProperty -LiteralPath $installedDll -Name IsReadOnly -Value $false
        Copy-Item -LiteralPath (Join-Path $outputDirectory 'EpicGames.UBA.dll') -Destination $installedDll -Force
    } finally {
        Set-ItemProperty -LiteralPath $installedDll -Name IsReadOnly -Value $dllWasReadOnly
    }
    @{ extensionHash=$extensionHash; dllHash=(Get-FileHash -LiteralPath $installedDll).Hash;
       schedulerHash=(Get-FileHash -LiteralPath $schedulerPath).Hash; engine=$EngineRoot } |
        ConvertTo-Json | Set-Content -LiteralPath $manifestPath
} finally {
    Set-ItemProperty -LiteralPath $schedulerPath -Name IsReadOnly -Value $wasReadOnly
}
