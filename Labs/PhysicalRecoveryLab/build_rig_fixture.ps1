$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$out = Join-Path $root 'Saved/Robotics'
$jolt = Join-Path $root 'Intermediate/JoltMigration/Install/Development'
& (Join-Path $out 'env/Scripts/python.exe') (Join-Path $PSScriptRoot 'generate_jolt_fixture.py')
if ($LASTEXITCODE -ne 0) { throw 'Native fixture generation failed' }
& 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/Tools/Launch-VsDevShell.ps1' -SkipAutomaticLocation -Arch amd64 -HostArch amd64
& cl.exe /nologo /std:c++20 /O2 /MD /EHsc /GR- /fp:precise /DJPH_SHARED_LIBRARY /DJPH_DOUBLE_PRECISION /DJPH_OBJECT_STREAM /DJPH_ENABLE_ASSERTS "/I$jolt/include" "/I$out" (Join-Path $PSScriptRoot 'jolt_rig_fixture.cpp') "/Fo$out/jolt_rig_fixture.obj" "/Fe$out/jolt_rig_fixture.exe" /link (Join-Path $jolt 'lib/ProphecyJolt_5_6_Development.lib')
if ($LASTEXITCODE -ne 0) { throw 'Native fixture build failed' }
