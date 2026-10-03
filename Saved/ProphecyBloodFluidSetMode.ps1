param(
    [ValidateSet("raw", "fluid", "stencil")]
    [string]$Mode = "fluid",
    [switch]$Shot,
    [int]$Port = 8765
)

$ProjectRoot = "C:\Users\singerie\Documents\Unreal Projects\Prophecy"
$ScriptPath = Join-Path $ProjectRoot "Saved\ProphecyBloodFluidABTest.py"
$TakeScreenshot = if ($Shot.IsPresent) { "True" } else { "False" }

$Code = @"
MODE = '$Mode'
TAKE_SCREENSHOT = $TakeScreenshot
exec(compile(open(r'$ScriptPath', 'r', encoding='utf-8').read(), r'$ScriptPath', 'exec'))
"@

$Body = @{
    code = $Code
    timeout = 60
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
    -Method Post `
    -UseBasicParsing `
    -Uri "http://127.0.0.1:$Port/python" `
    -ContentType "application/json" `
    -Body $Body `
    -TimeoutSec 90 |
    ConvertTo-Json -Depth 8
