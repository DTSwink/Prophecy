param(
    [ValidateSet("Suspend", "Resume", "Status")]
    [string]$Action = "Status",
    [int]$ProcessId = 0,
    [switch]$Force
)

$StatePath = Join-Path $PSScriptRoot "ProphecyLivePreviewPower.json"

function Get-LivePreviewProcess {
    param([int]$RequestedPid)

    if ($RequestedPid -gt 0) {
        return Get-CimInstance Win32_Process -Filter "ProcessId = $RequestedPid" -ErrorAction SilentlyContinue
    }

    $projectPath = "C:\Users\singerie\Documents\Unreal Projects\Prophecy\GameAnimationSample3.uproject"
    Get-CimInstance Win32_Process -Filter "Name = 'UnrealEditor.exe'" |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine.Contains($projectPath) -and
            $_.CommandLine.Contains("-ProphecyNNLiveVisual")
        } |
        Sort-Object CreationDate -Descending |
        Select-Object -First 1
}

function Get-State {
    if (Test-Path -LiteralPath $StatePath) {
        try {
            return Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
        }
        catch {
            return $null
        }
    }
    return $null
}

function Set-State {
    param(
        [int]$ProcessId,
        [bool]$Suspended
    )

    [ordered]@{
        pid = $ProcessId
        suspended = $Suspended
        updated_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

if (-not ("Prophecy.NativeProcess" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;

namespace Prophecy {
    public static class NativeProcess {
        [DllImport("kernel32.dll", SetLastError=true)]
        public static extern IntPtr OpenProcess(UInt32 access, bool inheritHandle, UInt32 processId);

        [DllImport("kernel32.dll", SetLastError=true)]
        public static extern bool CloseHandle(IntPtr handle);

        [DllImport("ntdll.dll")]
        public static extern UInt32 NtSuspendProcess(IntPtr processHandle);

        [DllImport("ntdll.dll")]
        public static extern UInt32 NtResumeProcess(IntPtr processHandle);
    }
}
"@
}

$processInfo = Get-LivePreviewProcess -RequestedPid $ProcessId
if (-not $processInfo) {
    Write-Output "No live Prophecy Unreal preview process found."
    exit 1
}

$targetPid = [int]$processInfo.ProcessId
$state = Get-State
$knownSuspended = $state -and ([int]$state.pid -eq $targetPid) -and ([bool]$state.suspended)

if ($Action -eq "Status") {
    [ordered]@{
        pid = $targetPid
        name = $processInfo.Name
        known_suspended = [bool]$knownSuspended
        command_line = $processInfo.CommandLine
    } | ConvertTo-Json -Depth 3
    exit 0
}

$PROCESS_SUSPEND_RESUME = 0x0800
$handle = [Prophecy.NativeProcess]::OpenProcess($PROCESS_SUSPEND_RESUME, $false, [uint32]$targetPid)
if ($handle -eq [IntPtr]::Zero) {
    throw "Could not open process $targetPid for $Action."
}

try {
    if ($Action -eq "Suspend") {
        if ($knownSuspended -and -not $Force) {
            Write-Output "Live preview PID=$targetPid is already marked suspended."
            exit 0
        }

        $result = [Prophecy.NativeProcess]::NtSuspendProcess($handle)
        if ($result -ne 0) {
            throw "NtSuspendProcess failed for PID=$targetPid result=$result"
        }
        Set-State -ProcessId $targetPid -Suspended $true
        Write-Output "Suspended live preview PID=$targetPid"
    }
    elseif ($Action -eq "Resume") {
        if ((-not $knownSuspended) -and -not $Force) {
            Write-Output "Live preview PID=$targetPid is not marked suspended."
            exit 0
        }

        $result = [Prophecy.NativeProcess]::NtResumeProcess($handle)
        if ($result -ne 0) {
            throw "NtResumeProcess failed for PID=$targetPid result=$result"
        }
        Set-State -ProcessId $targetPid -Suspended $false
        Write-Output "Resumed live preview PID=$targetPid"
    }
}
finally {
    [void][Prophecy.NativeProcess]::CloseHandle($handle)
}
