Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-FightHash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash }
function Write-FightJson([string]$Path, $Value) {
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 40))
    $stream=[IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    try {$stream.Write($bytes,0,$bytes.Length)} finally {$stream.Dispose()}
}
function Resolve-FightPath([string]$Path) {
    if($Path -notmatch '^[A-Za-z]:[\\/]' -or $Path -match '["\r\n]'){throw "Expected an absolute local Windows path: $Path"}
    [IO.Path]::GetFullPath($Path)
}
function New-FightDirectory([string]$Path) {
    $Path=Resolve-FightPath $Path
    if(Test-Path -LiteralPath $Path){throw "Output already exists: $Path"}
    $ancestor=[IO.Path]::GetDirectoryName($Path)
    while($ancestor){
        if(Test-Path -LiteralPath $ancestor){
            $item=Get-Item -LiteralPath $ancestor -Force
            if(!$item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw "Unsafe output ancestor: $ancestor"}
        }
        $next=[IO.Path]::GetDirectoryName($ancestor); if($next -eq $ancestor){break}; $ancestor=$next
    }
    [IO.Directory]::CreateDirectory($Path)|Out-Null
    $Path
}
function Assert-FightIdle {
    $running=@(Get-CimInstance Win32_Process|Where-Object {
        $_.Name -match '^(UnrealEditor(?:-Cmd)?|GameAnimationSample3(?:-Win64-[A-Za-z]+)?|UnrealBuildTool|UnrealPak|cl|link)\.exe$' -or
        ($_.Name -match '^(dotnet|cmd)\.exe$' -and $_.CommandLine -match '(UnrealBuildTool\.dll|AutomationTool\.dll|[\\/]RunUAT\.bat)')
    })
    if($running.Count){throw "UE/build processes are running; nothing was closed: $(($running|ForEach-Object{"$($_.Name):$($_.ProcessId)"}) -join ', ')"}
}
function Get-FightTree([string]$Directory) {
    if(!(Test-Path -LiteralPath $Directory -PathType Container)){throw "Missing input directory: $Directory"}
    $all=@(Get-ChildItem -LiteralPath $Directory -Recurse -Force)
    if(@($all|Where-Object{$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count){throw "Reparse point in input tree: $Directory"}
    @($all|Where-Object{!$_.PSIsContainer}|Sort-Object FullName)
}
function Get-FightFileRecords([string[]]$Paths) {
    @($Paths|Sort-Object -Unique|ForEach-Object{
        $item=Get-Item -LiteralPath $_ -ErrorAction Stop
        [pscustomobject]@{path=$item.FullName;bytes=$item.Length;sha256=(Get-FightHash $item.FullName)}
    })
}
function Assert-FightRecords($Expected,$Actual,[string]$Context) {
    $wanted=@{}; foreach($file in $Expected){$wanted[$file.path]=$file}
    if($wanted.Count -ne @($Actual).Count){throw "$Context file set changed."}
    foreach($file in $Actual){
        if(!$wanted.ContainsKey($file.path) -or $wanted[$file.path].sha256 -ne $file.sha256 -or $wanted[$file.path].bytes -ne $file.bytes){throw "$Context changed: $($file.path)"}
    }
}
function Get-FightInputs([string]$ProjectRoot,[string]$Engine,[string]$Registry) {
    if((Get-FightHash $Registry) -ne '620ADCCCC1D03AF07F3B937BD784975D627535B568C5E57BC3C3DCC11F4655A1'){throw 'Fresh fight registry changed; review its graph before using another inventory.'}
    $graph=Get-Content -LiteralPath $Registry -Raw|ConvertFrom-Json
    if($graph.kind -ne 'ProphecyFreshCookRegistry' -or $graph.success -ne $true -or $graph.projectDirectory -ne $ProjectRoot){throw 'Registry project/success mismatch.'}
    $paths=[Collections.Generic.List[string]]::new()
    foreach($name in @('GameAnimationSample3.uproject')){$paths.Add((Join-Path $ProjectRoot $name))}
    foreach($tree in @('Source','Config','StandaloneSim/sim_core/include','Intermediate/JoltMigration/Install/Development','Intermediate/JoltMigration/Install/Shipping')){
        foreach($file in (Get-FightTree (Join-Path $ProjectRoot $tree))){$paths.Add($file.FullName)}
    }
    foreach($file in (Get-FightTree (Join-Path $ProjectRoot 'Plugins/ProphecyJolt'))){
        if($file.FullName.Substring($ProjectRoot.Length+1).Replace('\','/') -notmatch '^Plugins/ProphecyJolt/(Binaries|Intermediate|Saved|\.git)/'){$paths.Add($file.FullName)}
    }
    foreach($file in $graph.files){
        if((Get-FightHash $file.path) -ne $file.sha256){throw "Registry asset changed: $($file.path)"}
        $paths.Add($file.path)
    }
    foreach($relative in @('Engine/Build/Build.version','Engine/Build/BatchFiles/Build.bat','Engine/Build/BatchFiles/RunUAT.bat',
        'Engine/Binaries/Win64/UnrealEditor.exe','Engine/Binaries/Win64/UnrealEditor-Cmd.exe','Engine/Content/Maps/Entry.umap')){$paths.Add((Join-Path $Engine $relative))}
    $paths.Add($Registry)
    foreach($file in (Get-ChildItem -LiteralPath $PSScriptRoot -File -Filter '*.ps1')){$paths.Add($file.FullName)}
    Get-FightFileRecords $paths.ToArray()
}
function Assert-FightInputs($Manifest) {
    Assert-FightRecords $Manifest.files (Get-FightInputs $Manifest.projectRoot $Manifest.engine $Manifest.registry) 'Pinned source/config/dependency/content'
}
function Get-FightDependency([string]$ProjectRoot,[string]$Configuration) {
    $install=Join-Path $ProjectRoot "Intermediate/JoltMigration/Install/$Configuration"
    $manifestPath=Join-Path $install 'manifest.json'; $native=Get-Content -LiteralPath $manifestPath -Raw|ConvertFrom-Json
    if($native.schema -ne 2 -or $native.version -ne '5.6.0' -or $native.sourceSha -ne 'e77f175595e64cb44218cc9d9d56fc365ad0e36a' -or
        $native.configuration -ne $Configuration -or $native.simd -ne 'SSE2' -or $native.runtime -ne 'MD' -or $native.library -ne 'shared' -or
        $native.worldPrecision -ne 'double' -or !$native.cppExceptions -or $native.assertions -ne ($Configuration -eq 'Development')){throw 'Jolt dependency contract mismatch.'}
    if($native.dllFilename -ne "ProphecyJolt_5_6_$Configuration.dll" -or $native.importLibraryFilename -ne "ProphecyJolt_5_6_$Configuration.lib" -or
        (Get-FightHash (Join-Path $install "bin/$($native.dllFilename)")) -ne $native.dllSha256 -or
        (Get-FightHash (Join-Path $install "lib/$($native.importLibraryFilename)")) -ne $native.importLibrarySha256){throw 'Jolt dependency names/hashes mismatch.'}
    $native
}
function Invoke-FightBatch([string]$Executable,[string[]]$Arguments,[string]$Log) {
    Assert-FightIdle
    $savedPreference=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        & $Executable @Arguments 2>&1|Tee-Object -FilePath $Log -ErrorAction Stop|Out-Host
        $code=$LASTEXITCODE
    } finally {$ErrorActionPreference=$savedPreference}
    if($code -ne 0){throw "Native command failed with exit $code; see $Log"}
}
