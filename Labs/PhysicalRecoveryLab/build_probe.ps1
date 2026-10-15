$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$out = Join-Path $root 'Saved/Robotics'
$jolt = Join-Path $root 'Intermediate/JoltMigration/Install/Development'
& 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/Tools/Launch-VsDevShell.ps1' -SkipAutomaticLocation -Arch amd64 -HostArch amd64
& cl.exe /nologo /std:c++20 /O2 /MD /EHsc /GR- /fp:precise /DJPH_SHARED_LIBRARY /DJPH_DOUBLE_PRECISION /DJPH_OBJECT_STREAM /DJPH_ENABLE_ASSERTS "/I$jolt/include" (Join-Path $PSScriptRoot 'jolt_probe.cpp') "/Fo$out/jolt_probe.obj" "/Fe$out/jolt_probe.exe" /link (Join-Path $jolt 'lib/ProphecyJolt_5_6_Development.lib')
if ($LASTEXITCODE -ne 0) { throw 'Jolt probe build failed' }
$env:PATH = (Join-Path $jolt 'bin') + ';' + $env:PATH
& (Join-Path $out 'jolt_probe.exe') (Join-Path $out 'jolt-calibration.csv')
if ($LASTEXITCODE -ne 0) { throw 'Jolt probe failed' }
