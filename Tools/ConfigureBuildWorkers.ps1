param(
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.7'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
& (Join-Path $PSScriptRoot 'Build\InstallDynamicWorkers.ps1') -EngineRoot $EngineRoot
$ubaDirectory = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealBuildAccelerator\x64'
$ubaConfig = Join-Path $ubaDirectory 'UbaHost.toml'
foreach ($required in @('UbaHost.dll', 'UbaCli.exe', 'UbaHost.toml')) {
    if (-not (Test-Path -LiteralPath (Join-Path $ubaDirectory $required))) {
        throw "Missing UBA installation: $required. Build configuration was not changed."
    }
}
$logicalCores = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
if ($logicalCores -lt 1) { throw 'Could not determine logical processor count.' }
$configDirectory = Join-Path $projectRoot 'Saved\UnrealBuildTool'
$configPath = Join-Path $configDirectory 'BuildConfiguration.xml'
New-Item -ItemType Directory -Force -Path $configDirectory | Out-Null
$config = New-Object System.Xml.XmlDocument
if (Test-Path -LiteralPath $configPath) {
    $config.Load($configPath)
} else {
    $config.LoadXml('<Configuration xmlns="https://www.unrealengine.com/BuildConfiguration" />')
}
$originalXml = $config.OuterXml
$namespace = 'https://www.unrealengine.com/BuildConfiguration'
function Set-BuildSetting([string]$section, [string]$name, [string]$value) {
    $sectionNode = $config.DocumentElement.SelectSingleNode("*[local-name()='$section']")
    if (-not $sectionNode) {
        $sectionNode = $config.CreateElement($section, $namespace)
        [void]$config.DocumentElement.AppendChild($sectionNode)
    }
    $node = $sectionNode.SelectSingleNode("*[local-name()='$name']")
    if (-not $node) {
        $node = $config.CreateElement($name, $namespace)
        [void]$sectionNode.AppendChild($node)
    }
    $node.InnerText = $value
}
# Preserve safe startup sizing for fallback executors. The installed UBA
# adapter refreshes the RAM limit and discovers the CPU ceiling itself.
Set-BuildSetting BuildConfiguration bAllowUBAExecutor true
Set-BuildSetting BuildConfiguration bAllowXGE false
Set-BuildSetting BuildConfiguration bAllowFASTBuild false
Set-BuildSetting BuildConfiguration bAllowSNDBS false
Set-BuildSetting BuildConfiguration bAllCores true
Set-BuildSetting BuildConfiguration MaxParallelActions '0'
$legacyAlias = $config.DocumentElement.SelectSingleNode("*[local-name()='BuildConfiguration']/*[local-name()='bAllowUBALocalExecutor']")
if ($legacyAlias) { [void]$legacyAlias.ParentNode.RemoveChild($legacyAlias) }
Set-BuildSetting UnrealBuildAccelerator bDisableRemote true
Set-BuildSetting UnrealBuildAccelerator bDisableWaitOnMem false
Set-BuildSetting UnrealBuildAccelerator bAllowKillOnMem false
$backupPath = "$configPath.before-dynamic-workers"
if ((Test-Path -LiteralPath $configPath) -and -not (Test-Path -LiteralPath $backupPath)) {
    Copy-Item -LiteralPath $configPath -Destination $backupPath
}
if ($config.OuterXml -ne $originalXml) { $config.Save($configPath) }
Write-Output "Configured local UBA: CPU ceiling $logicalCores, RAM limit refreshed every 500 ms."
Write-Output "Project config: $configPath"
Write-Output 'No editor restart or C++ build performed.'
