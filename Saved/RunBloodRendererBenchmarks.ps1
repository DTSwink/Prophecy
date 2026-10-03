param(
    [int]$Count = 2000,
    [int]$UpdatesPerFrame = 256,
    [double]$Seconds = 5.0,
    [double]$Warmup = 1.0,
    [double]$FieldHalfExtent = 1100.0,
    [double]$MinRadius = 10.0,
    [double]$MaxRadius = 22.0,
    [string[]]$Methods = @("Decal", "ISM", "HISM", "MeshDecal", "Procedural"),
    [string]$Label = "comparison_2k"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$project = Join-Path $projectRoot "GameAnimationSample3.uproject"
$editor = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe"
$outDir = Join-Path $projectRoot "Saved\BloodRendererBenchmarks"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

foreach ($method in $Methods) {
    $safeMethod = $method.ToLowerInvariant()
    $shot = "Saved/BloodRendererBenchmarks/${Label}_${safeMethod}.png"
    $json = "Saved/BloodRendererBenchmarks/${Label}_${safeMethod}.json"
    $argString = '"' + $project + '"' +
        " -game -windowed -ResX=1280 -ResY=720 -log -unattended -NoSplash" +
        " -ProphecyBloodBenchmark" +
        " -ProphecyBloodMethod=$method" +
        " -ProphecyBloodCount=$Count" +
        " -ProphecyBloodUpdatesPerFrame=$UpdatesPerFrame" +
        " -ProphecyBloodSeconds=$Seconds" +
        " -ProphecyBloodWarmup=$Warmup" +
        " -ProphecyBloodFieldHalfExtent=$FieldHalfExtent" +
        " -ProphecyBloodMinRadius=$MinRadius" +
        " -ProphecyBloodMaxRadius=$MaxRadius" +
        " -ProphecyBloodShot=$shot" +
        " -ProphecyBloodJson=$json" +
        " -ProphecyBloodBenchmarkExit"

    Write-Output "Running $method -> $json"
    $process = Start-Process -FilePath $editor -ArgumentList $argString -PassThru -Wait
    Write-Output "$method exit code: $($process.ExitCode)"
}

$rows = foreach ($file in Get-ChildItem -LiteralPath $outDir -Filter "$Label*.json" | Sort-Object Name) {
    $data = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
    [pscustomobject]@{
        method = $data.method
        stains = $data.stain_count
        updates_per_frame = $data.updates_per_frame
        populate_total_ms = [math]::Round([double]$data.populate_total_ms, 3)
        populate_chunk_first_ms = [math]::Round([double]$data.populate_chunk_first_ms, 3)
        populate_chunk_last_ms = [math]::Round([double]$data.populate_chunk_last_ms, 3)
        populate_chunk_max_ms = [math]::Round([double]$data.populate_chunk_max_ms, 3)
        warm_fps = [math]::Round([double]$data.warm_fps, 2)
        warm_update_batch_ms = [math]::Round([double]$data.warm_update_batch_ms, 4)
        screenshot_path = $data.screenshot_path
    }
}

$csv = Join-Path $outDir "$Label.csv"
$rows | Export-Csv -NoTypeInformation -LiteralPath $csv
$rows | Format-Table -AutoSize
Write-Output "Saved summary: $csv"
