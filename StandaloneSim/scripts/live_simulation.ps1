param(
    [switch]$BackgroundFirstLaunch
)

$ErrorActionPreference = 'Stop'
$standaloneRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Split-Path -Parent $standaloneRoot
$buildRoot = Join-Path $standaloneRoot 'build'
$canonicalExe = Join-Path $buildRoot 'viewer_raylib\Release\prophecy_viewer.exe'
$runtimeRoot = Join-Path $buildRoot 'live'
$runtimeData = Join-Path $runtimeRoot 'data'
$sourceData = Join-Path $standaloneRoot 'data'
$iconPath = Join-Path $standaloneRoot 'assets\ProphecySimulationIcon.ico'
$buildLog = Join-Path $runtimeRoot 'build-latest.log'
$launcherLog = Join-Path $runtimeRoot 'launcher.log'

New-Item -ItemType Directory -Force -Path $runtimeRoot, $runtimeData | Out-Null

$openEventCreated = $false
$openEvent = [System.Threading.EventWaitHandle]::new(
    $false,
    [System.Threading.EventResetMode]::AutoReset,
    'Local\ProphecyStandaloneSimulationOpenViewer',
    [ref]$openEventCreated)
$createdNew = $false
$mutex = [System.Threading.Mutex]::new($true, 'Local\ProphecyStandaloneSimulationLiveLauncher', [ref]$createdNew)
if (-not $createdNew) {
    $null = $openEvent.Set()
    $openEvent.Dispose()
    $mutex.Dispose()
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class ProphecyWindowOrder
{
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr window);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool SetWindowPos(IntPtr window, IntPtr insertAfter, int x, int y, int width, int height, uint flags);

    public static bool ShowAtBottom(IntPtr window)
    {
        const uint flags = 0x0001u | 0x0002u | 0x0010u | 0x0040u | 0x0200u;
        return SetWindowPos(window, new IntPtr(1), 0, 0, 0, 0, flags);
    }
}
'@

$script:stopRequested = $false
$script:rebuildRequested = $false
$script:restartRequested = $false
$script:viewerProcess = $null
$script:runtimeExe = $null
$script:viewerWanted = $true

function Write-LauncherLog {
    param([string]$Message)
    Add-Content -LiteralPath $launcherLog -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
}

function Find-CMake {
    $command = Get-Command cmake -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $bundled = 'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    return $null
}

function Get-SourceStamp {
    $roots = @(
        (Join-Path $standaloneRoot 'sim_core'),
        (Join-Path $standaloneRoot 'viewer_raylib'),
        (Join-Path $standaloneRoot 'data')
    )
    $files = foreach ($root in $roots) {
        if (Test-Path -LiteralPath $root) {
            Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object {
                $_.Extension -in @('.cpp', '.h', '.hpp', '.json', '.txt') -or $_.Name -eq 'CMakeLists.txt'
            }
        }
    }
    $rootCMake = Join-Path $standaloneRoot 'CMakeLists.txt'
    if (Test-Path -LiteralPath $rootCMake) { $files += Get-Item -LiteralPath $rootCMake }
    if (-not $files) { return 0L }
    return [long](($files | Measure-Object -Property LastWriteTimeUtc -Maximum).Maximum.Ticks)
}

function Invoke-ViewerBuild {
    $cmake = Find-CMake
    if (-not $cmake) {
        Set-Content -LiteralPath $buildLog -Value 'CMake was not found.'
        return $false
    }

    Write-LauncherLog 'Build started.'
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $buildRoot 'CMakeCache.txt'))) {
            $buildScript = Join-Path $PSScriptRoot 'build.ps1'
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $buildScript -Configuration Release *> $buildLog
        } else {
            & $cmake --build $buildRoot --config Release --target prophecy_viewer --parallel *> $buildLog
        }
        $succeeded = $LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $canonicalExe)
    } catch {
        Add-Content -LiteralPath $buildLog -Value $_.Exception.ToString()
        $succeeded = $false
    }
    Write-LauncherLog "Build finished. success=$succeeded"
    return $succeeded
}

function Stop-Viewer {
    if ($script:viewerProcess -and -not $script:viewerProcess.HasExited) {
        $null = $script:viewerProcess.CloseMainWindow()
        if (-not $script:viewerProcess.WaitForExit(1200)) {
            Stop-Process -Id $script:viewerProcess.Id -Force -ErrorAction SilentlyContinue
            $script:viewerProcess.WaitForExit(1200)
        }
    }
    $script:viewerProcess = $null
}

function Start-Viewer {
    param(
        [string]$Executable = $script:runtimeExe,
        [switch]$Background
    )
    if (-not $Executable -or -not (Test-Path -LiteralPath $Executable)) { return $false }
    $script:runtimeExe = $Executable
    $restoreForeground = if ($Background) { [ProphecyWindowOrder]::GetForegroundWindow() } else { [IntPtr]::Zero }
    $arguments = if ($Background) {
        @('--background-reload', '--restore-foreground', $restoreForeground.ToInt64().ToString())
    } else {
        @()
    }
    $startParameters = @{
        FilePath = $Executable
        WorkingDirectory = $runtimeRoot
        PassThru = $true
    }
    if ($arguments.Count -gt 0) {
        $startParameters.ArgumentList = $arguments
    }
    $script:viewerProcess = Start-Process @startParameters
    if ($Background) {
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            Start-Sleep -Milliseconds 25
            $script:viewerProcess.Refresh()
            if ($script:viewerProcess.HasExited) { break }
            if ($script:viewerProcess.MainWindowHandle -ne [IntPtr]::Zero) {
                $null = [ProphecyWindowOrder]::ShowAtBottom($script:viewerProcess.MainWindowHandle)
                if ($restoreForeground -ne [IntPtr]::Zero) {
                    $null = [ProphecyWindowOrder]::SetForegroundWindow($restoreForeground)
                }
                break
            }
        }
    }
    Write-LauncherLog "Viewer started. pid=$($script:viewerProcess.Id) background=$Background executable=$Executable"
    return $true
}

function Publish-And-RestartViewer {
    param([switch]$Background)
    if (-not (Test-Path -LiteralPath $canonicalExe)) { return $false }

    Get-ChildItem -LiteralPath $runtimeData -File | Remove-Item -Force
    Copy-Item -Path (Join-Path $sourceData '*') -Destination $runtimeData -Recurse -Force
    $version = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $nextExe = Join-Path $runtimeRoot "ProphecySimulation-live-$version.exe"
    Copy-Item -LiteralPath $canonicalExe -Destination $nextExe -Force

    Stop-Viewer
    $started = Start-Viewer -Executable $nextExe -Background:$Background
    if ($started) {
        Get-ChildItem -LiteralPath $runtimeRoot -File -Filter 'ProphecySimulation-live-*.exe' |
            Where-Object { $_.FullName -ne $nextExe } |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
    return $started
}

$tray = [System.Windows.Forms.NotifyIcon]::new()
$ownsIcon = Test-Path -LiteralPath $iconPath
$loadedIcon = if ($ownsIcon) {
    [System.Drawing.Icon]::new($iconPath)
} else {
    [System.Drawing.SystemIcons]::Application
}
$tray.Icon = $loadedIcon
$tray.Text = 'Prophecy live simulation'
$tray.Visible = $true

$menu = [System.Windows.Forms.ContextMenuStrip]::new()
$restartItem = $menu.Items.Add('Open / Restart viewer')
$rebuildItem = $menu.Items.Add('Rebuild now')
$null = $menu.Items.Add([System.Windows.Forms.ToolStripSeparator]::new())
$exitItem = $menu.Items.Add('Exit live simulation')
$restartItem.add_Click({ $script:restartRequested = $true })
$rebuildItem.add_Click({ $script:rebuildRequested = $true })
$exitItem.add_Click({ $script:stopRequested = $true })
$tray.add_DoubleClick({ $script:restartRequested = $true })
$tray.ContextMenuStrip = $menu

try {
    Write-LauncherLog 'Live launcher started.'
    if (-not (Test-Path -LiteralPath $canonicalExe)) {
        if (-not (Invoke-ViewerBuild)) {
            Write-LauncherLog "Initial build failed. See $buildLog"
        }
    }
    if (Test-Path -LiteralPath $canonicalExe) {
        $null = Publish-And-RestartViewer -Background:$BackgroundFirstLaunch
    }

    $lastStamp = Get-SourceStamp
    $pendingBuildAt = $null

    while (-not $script:stopRequested) {
        [System.Windows.Forms.Application]::DoEvents()
        if ($openEvent.WaitOne(0)) {
            $script:restartRequested = $true
        }
        $stamp = Get-SourceStamp
        if ($stamp -ne $lastStamp) {
            $lastStamp = $stamp
            $pendingBuildAt = [DateTime]::UtcNow.AddMilliseconds(850)
        }
        if ($script:rebuildRequested) {
            $script:rebuildRequested = $false
            $pendingBuildAt = [DateTime]::UtcNow
        }
        if ($script:restartRequested) {
            $script:restartRequested = $false
            $script:viewerWanted = $true
            Stop-Viewer
            if (Invoke-ViewerBuild) {
                $null = Publish-And-RestartViewer -Background
            } else {
                $null = Start-Viewer -Background
            }
        }

        if ($pendingBuildAt -and [DateTime]::UtcNow -ge $pendingBuildAt) {
            $pendingBuildAt = $null
            if (Invoke-ViewerBuild) {
                if ($script:viewerWanted) {
                    $null = Publish-And-RestartViewer -Background
                } else {
                    Write-LauncherLog 'Build succeeded; viewer remains closed by user.'
                }
            } else {
                Write-LauncherLog "Build failed; current viewer remains active. See $buildLog"
            }
            $lastStamp = Get-SourceStamp
        }

        if ($script:viewerProcess -and $script:viewerProcess.HasExited) {
            $exitCode = $script:viewerProcess.ExitCode
            $script:viewerProcess = $null
            $script:viewerWanted = $false
            Write-LauncherLog "Viewer exited with code $exitCode; it will remain closed."
        }
        Start-Sleep -Milliseconds 250
    }
} finally {
    Stop-Viewer
    $tray.Visible = $false
    $tray.Dispose()
    $menu.Dispose()
    if ($ownsIcon) { $loadedIcon.Dispose() }
    Write-LauncherLog 'Live launcher stopped.'
    $openEvent.Dispose()
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
