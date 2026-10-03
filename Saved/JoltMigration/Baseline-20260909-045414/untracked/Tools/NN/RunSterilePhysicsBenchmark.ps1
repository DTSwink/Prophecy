param(
    [int]$Count=100,
    [int]$Warmup=120,
    [int]$Samples=300,
    [int]$Repeats=3,
    [string]$Label='sterile_100',
    [string]$Methods='',
    [switch]$FloorOnly,
    [string]$Engine='C:/Program Files/Epic Games/UE_5.7'
)
$ErrorActionPreference='Stop'
if ($Label -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Label must contain only letters, digits, underscores or hyphens.' }
$benchRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$benchProject=Join-Path $benchRoot 'GameAnimationSample3.uproject'
$benchDir=Join-Path $benchRoot 'Saved/Benchmarks'
New-Item -ItemType Directory -Force -Path $benchDir | Out-Null
$benchJson=Join-Path $benchDir "$Label.json"
if (Test-Path -LiteralPath $benchJson) { throw "Report already exists: $benchJson. Use another label." }
$benchLog=Join-Path $benchDir "$Label.log"
if ($Methods -and $Methods -notmatch '^[a-zA-Z,]+$') { throw 'Methods must be comma-separated native method names.' }
$benchArgs='"'+$benchProject+'" /Engine/Maps/Entry?game=/Script/Engine.GameModeBase'+
    ' -game -nullrhi -RenderOffscreen -nosound -unattended -NoSplash -NoLoadingScreen -NoLiveCoding -NoScreenMessages -NoVSync -nowrite'+
    ' -ProphecyPhysicsBenchmark'+
    " -PhysicsBenchCount=$Count -PhysicsBenchWarmup=$Warmup -PhysicsBenchSamples=$Samples -PhysicsBenchRepeats=$Repeats"+
    ' -PhysicsBenchJson="'+$benchJson+'" -abslog="'+$benchLog+'"'
if ($Methods) { $benchArgs+=' -PhysicsBenchMethods="'+$Methods+'"' }
if ($FloorOnly) { $benchArgs+=' -PhysicsBenchFloorOnly' }
$benchProcess=Start-Process -FilePath (Join-Path $Engine 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe') -ArgumentList $benchArgs -WindowStyle Hidden -PassThru
$benchProcess.PriorityClass='BelowNormal'
[pscustomobject]@{ProcessId=$benchProcess.Id;Report=$benchJson;Log=$benchLog;Priority='BelowNormal';Rendering='NullRHI + RenderOffscreen'} | ConvertTo-Json
