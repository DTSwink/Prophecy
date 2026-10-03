$ErrorActionPreference = 'Stop'
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) { throw 'Close Unreal before restoring the Run model.' }
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
$destination = 'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Content/locomotion/NN'
foreach ($entry in $manifest.old.PSObject.Properties) {
    $source = Join-Path $PSScriptRoot $entry.Name
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $entry.Value.sha256) { throw 'Backup hash mismatch' }
}
foreach ($entry in $manifest.old.PSObject.Properties) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $entry.Name) -Destination (Join-Path $destination $entry.Name) -Force }
Write-Output 'Previous Run model and matching contract restored.'
