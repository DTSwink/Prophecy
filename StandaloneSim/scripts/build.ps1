param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release',
    [switch]$TestsOnly
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root 'build'
$cmake = (Get-Command cmake -ErrorAction SilentlyContinue).Source

if (-not $cmake) {
    $cmake = 'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
}
if (-not (Test-Path -LiteralPath $cmake)) {
    throw 'CMake was not found. Install Visual Studio C++ CMake tools or add cmake to PATH.'
}

$viewer = if ($TestsOnly) { 'OFF' } else { 'ON' }
& $cmake -S $root -B $build -G 'Visual Studio 17 2022' -A x64 "-DPROPHECY_BUILD_VIEWER=$viewer"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $cmake --build $build --config $Configuration --parallel
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $cmake --build $build --config $Configuration --target RUN_TESTS
exit $LASTEXITCODE
