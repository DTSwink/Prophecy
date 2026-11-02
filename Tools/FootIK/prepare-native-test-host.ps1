param([switch]$Link)
$ErrorActionPreference='Stop'
$projectRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$testRoot=Join-Path $projectRoot 'Saved/Diagnostics/FootIKPort20261030/NativeHost'
$engineRoot='C:/Program Files/Epic Games/UE_5.7/Engine'
# This is an owned cold automation host, not the user's editor launcher. It
# reuses UBT's exact compiled objects and link response, changing output paths
# only. A different task may keep the original project DLLs loaded throughout.
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot 'GameAnimationSample3.uproject') -Destination $testRoot
Copy-Item -LiteralPath (Join-Path $projectRoot 'Config') -Destination $testRoot -Recurse -Force
foreach($name in @('Content','Tools','StandaloneSim')) {
    $destination=Join-Path $testRoot $name
    if(!(Test-Path -LiteralPath $destination)){New-Item -ItemType Junction -Path $destination -Target (Join-Path $projectRoot $name) | Out-Null}
}
$evidence=Join-Path $testRoot 'Saved/Diagnostics'
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$fixtureLink=Join-Path $evidence 'FootIKPort20261030'
if(!(Test-Path -LiteralPath $fixtureLink)){New-Item -ItemType Junction -Path $fixtureLink -Target (Join-Path $projectRoot 'Saved/Diagnostics/FootIKPort20261030') | Out-Null}
$binary=Join-Path $testRoot 'Binaries/Win64'
$pluginRoot=Join-Path $testRoot 'Plugins/ProphecyJolt'
$pluginBinary=Join-Path $pluginRoot 'Binaries/Win64'
New-Item -ItemType Directory -Force -Path $binary,$pluginBinary | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot 'Plugins/ProphecyJolt/ProphecyJolt.uplugin') -Destination $pluginRoot
$sourcePlugin=Join-Path $pluginRoot 'Source'
if(!(Test-Path -LiteralPath $sourcePlugin)){New-Item -ItemType Junction -Path $sourcePlugin -Target (Join-Path $projectRoot 'Plugins/ProphecyJolt/Source') | Out-Null}
foreach($name in @('GameAnimationSample3','ProphecyEditor','ProphecyFootIKMath')){
    $source=Join-Path $projectRoot "Binaries/Win64/UnrealEditor-$name.dll"
    if(Test-Path -LiteralPath $source){Copy-Item -LiteralPath $source -Destination $binary -Force}
}
Get-ChildItem -LiteralPath (Join-Path $projectRoot 'Plugins/ProphecyJolt/Binaries/Win64') -Filter '*.dll' -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $pluginBinary -Force
}
if($Link){
    $linker='C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/link.exe'
    $receipt=@()
    foreach($name in @('ProphecyFootIKMath','ProphecyJolt','GameAnimationSample3','ProphecyEditor')){
        $relative=if($name -eq 'ProphecyJolt'){'Plugins/ProphecyJolt/Intermediate'}else{'Intermediate'}
        $response=Join-Path $projectRoot "$relative/Build/Win64/x64/UnrealEditor/Development/$name/UnrealEditor-$name.dll.rsp"
        if(!(Test-Path -LiteralPath $response)){throw "Missing normal UBT link response: $response"}
        $destination=if($name -eq 'ProphecyJolt'){$pluginBinary}else{$binary}
        $text=[IO.File]::ReadAllText($response)
        $output=(Join-Path $destination "UnrealEditor-$name.dll").Replace('\','/')
        $pdb=(Join-Path $destination "UnrealEditor-$name.pdb").Replace('\','/')
        $implib=(Join-Path $destination "UnrealEditor-$name.lib").Replace('\','/')
        $text=[regex]::Replace($text,'(?m)^/OUT:.*$',('/OUT:"'+$output+'"'))
        $text=[regex]::Replace($text,'(?m)^/PDB:.*$',('/PDB:"'+$pdb+'"'))
        $text=[regex]::Replace($text,'(?m)^/IMPLIB:.*$',('/IMPLIB:"'+$implib+'"'))
        if($text -notmatch '(?m)^/IMPLIB:'){$text+="`n/IMPLIB:`"$implib`"`n"}
        $localResponse=Join-Path $testRoot "$name.link.rsp"
        [IO.File]::WriteAllText($localResponse,$text,[Text.UTF8Encoding]::new($false))
        & $linker "@$localResponse"
        if($LASTEXITCODE -ne 0){throw "Isolated link failed: $name"}
        $receipt+=@{module=$name;normalResponse=$response;responseSHA256=(Get-FileHash -LiteralPath $response -Algorithm SHA256).Hash;dllSHA256=(Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash}
    }
    $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $testRoot 'link-receipt.json') -Encoding utf8
}
$buildId=([IO.File]::ReadAllText((Join-Path $engineRoot 'Binaries/Win64/UnrealEditor.modules'))|ConvertFrom-Json).BuildId
@{BuildId=$buildId;Modules=@{GameAnimationSample3='UnrealEditor-GameAnimationSample3.dll';ProphecyEditor='UnrealEditor-ProphecyEditor.dll';ProphecyFootIKMath='UnrealEditor-ProphecyFootIKMath.dll'}} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $binary 'UnrealEditor.modules') -Encoding utf8
@{BuildId=$buildId;Modules=@{ProphecyJolt='UnrealEditor-ProphecyJolt.dll';ProphecyJoltEditor='UnrealEditor-ProphecyJoltEditor.dll'}} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $pluginBinary 'UnrealEditor.modules') -Encoding utf8
Write-Output $testRoot
