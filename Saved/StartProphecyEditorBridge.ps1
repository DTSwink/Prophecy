param(
    [int]$Port = 8765,
    [int]$ResX = 1280,
    [int]$ResY = 720,
    [string]$ExtraArgs = ""
)

$ProjectRoot = "C:\Users\singerie\Documents\Unreal Projects\Prophecy"
$ProjectPath = Join-Path $ProjectRoot "GameAnimationSample3.uproject"
$EditorPath = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe"

$env:PROPHECY_EDITOR_BRIDGE = "1"
$env:PROPHECY_EDITOR_BRIDGE_PORT = "$Port"

$Arguments = @(
    "`"$ProjectPath`"",
    "-log",
    "-ResX=$ResX",
    "-ResY=$ResY"
)

if ($ExtraArgs.Trim().Length -gt 0) {
    $Arguments += $ExtraArgs
}

Start-Process -FilePath $EditorPath -ArgumentList $Arguments -WorkingDirectory $ProjectRoot

$HealthUri = "http://127.0.0.1:$Port/health"
for ($i = 0; $i -lt 120; ++$i) {
    try {
        $Health = Invoke-RestMethod -UseBasicParsing -Uri $HealthUri -TimeoutSec 1
        $Health | ConvertTo-Json -Depth 8
        exit 0
    } catch {
        Start-Sleep -Seconds 1
    }
}

Write-Error "Unreal launched, but the Prophecy editor bridge did not answer at $HealthUri within 120 seconds."
exit 1

