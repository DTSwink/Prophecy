param([Parameter(Mandatory=$true)][string]$StateDir)
$ErrorActionPreference = 'Stop'
# Match exact workspace scripts and this scope's known manifest/run arguments.
# Never use a historical PID alone, never stop a trainer or a billing guard.
$scope = (Resolve-Path -LiteralPath $StateDir).Path
$dashboard = Join-Path $PSScriptRoot 'dashboard.py'
$bridge = Join-Path $PSScriptRoot 'bridge.py'
$manifests = @(Get-ChildItem -LiteralPath $scope -Filter '*-dashboard.json' -File)
$runs = @($manifests | ForEach-Object { $_.Name -replace '-dashboard.json$', '' })
$targets = @(Get-CimInstance Win32_Process | Where-Object {
    $cmd = $_.CommandLine
    if ($_.Name -notmatch '^python(w)?\.exe$' -or -not $cmd) { return $false }
    if ($cmd.Contains('"' + $dashboard + '"')) {
        return @($manifests | Where-Object { $cmd.Contains('"' + $_.FullName + '"') }).Count -gt 0
    }
    if ($cmd.Contains('"' + $bridge + '"') -and $cmd -match '--name\s+([A-Za-z0-9_]+)(?:\s|$)') {
        return $Matches[1] -in $runs
    }
    return $false
})
$stopped = @()
foreach ($item in $targets) {
    $now = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $item.ProcessId)
    if ($now -and $now.CreationDate -eq $item.CreationDate -and $now.CommandLine -eq $item.CommandLine) {
        & taskkill /PID $item.ProcessId /T /F 2>&1 | Out-Null
        $remaining = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $item.ProcessId)
        if ($remaining -and $remaining.CreationDate -eq $item.CreationDate) { throw "Could not stop observer $($item.ProcessId)" }
        $stopped += $item.ProcessId
    }
}
ConvertTo-Json -InputObject $stopped -Compress
