$ErrorActionPreference = 'Stop'
$labRoot = Split-Path -Parent $PSScriptRoot
$outDir = Join-Path $labRoot 'Saved/Results'
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
$msvcRoot = 'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.44.35207'
$sdkRoot = 'C:/Program Files (x86)/Windows Kits/10'
$sdkVersion = '10.0.26100.0'
$kernelExe = Join-Path $outDir 'test_kernel.exe'
$kernelObj = Join-Path $outDir 'test_kernel.obj'
& "$msvcRoot/bin/Hostx64/x64/cl.exe" /nologo /std:c++17 /O2 /EHsc /MT `
    "/I$msvcRoot/include" "/I$sdkRoot/Include/$sdkVersion/ucrt" `
    "/I$sdkRoot/Include/$sdkVersion/shared" "/I$sdkRoot/Include/$sdkVersion/um" `
    "/Fe:$kernelExe" "/Fo:$kernelObj" "$PSScriptRoot/test_kernel.cpp" `
    /link "/LIBPATH:$msvcRoot/lib/x64" `
    "/LIBPATH:$sdkRoot/Lib/$sdkVersion/ucrt/x64" "/LIBPATH:$sdkRoot/Lib/$sdkVersion/um/x64"
if ($LASTEXITCODE -ne 0) { throw 'Kernel test build failed' }
$kernelResult = & $kernelExe
$kernelExit = $LASTEXITCODE
$kernelResult | Set-Content -LiteralPath (Join-Path $outDir 'kernel-validation.json') -Encoding utf8
$kernelResult
if ($kernelExit -ne 0) { throw 'Kernel validation failed' }
