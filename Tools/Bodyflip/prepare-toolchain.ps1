param([string]$CMake='C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe')
$ErrorActionPreference='Stop'
$Workspace=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$Output=Join-Path $Workspace 'Saved/Diagnostics/BodyflipPort20261030'
$Package=Join-Path $Output 'esbuild.tgz'
New-Item -ItemType Directory -Path $Output -Force | Out-Null
$Metadata=Invoke-RestMethod 'https://registry.npmjs.org/@esbuild/win32-x64/0.25.12'
Invoke-WebRequest -Uri $Metadata.dist.tarball -OutFile $Package
$Expected=$Metadata.dist.integrity.Replace('sha512-','')
$Bytes=[IO.File]::ReadAllBytes($Package)
$Hash=[Security.Cryptography.SHA512]::Create()
$Actual=[Convert]::ToBase64String($Hash.ComputeHash($Bytes));$Hash.Dispose()
if($Expected -ne $Actual){throw 'esbuild registry integrity mismatch'}
$Esbuild=Join-Path $Output 'esbuild'
New-Item -ItemType Directory -Path $Esbuild -Force | Out-Null
tar -xzf $Package -C $Esbuild
if($LASTEXITCODE -ne 0){throw 'esbuild extraction failed'}
& $CMake -S $PSScriptRoot -B (Join-Path $Output 'chakra-build') -G 'Visual Studio 17 2022' -A x64
if($LASTEXITCODE -ne 0){throw 'Bodyflip probe configure failed'}
& $CMake --build (Join-Path $Output 'chakra-build') --config Release --parallel 1
if($LASTEXITCODE -ne 0){throw 'Bodyflip probe build failed'}
