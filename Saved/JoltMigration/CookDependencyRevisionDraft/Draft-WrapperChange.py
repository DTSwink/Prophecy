"""Create draft wrapper from current short-output wrapper; no active mutations."""
import hashlib
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE.parent / 'PackagedNNCrowdDraft/Build-NNCrowdPackage.ps1'
original = SOURCE.read_text(encoding='utf-8-sig')
text = original

def replace(old, new):
    global text
    assert text.count(old) == 1, old[:80]
    text = text.replace(old, new)

replace('$native=Assert-NNDependency $project $Configuration', r'''# r3 distinguishes all copied source references from runtime cooked requirements.
$requiredCookedGamePackages=@($data.gamePackageClosure)
$requiredCookedExternalPackages=@()
$hasCookSet=$data.PSObject.Properties.Name -contains 'requiredCookedGamePackages'
if($hasCookSet){
    if($data.PSObject.Properties.Name -notcontains 'requiredCookedExternalPackages' -or
       $data.PSObject.Properties.Name -notcontains 'externalPackageInputs'){throw 'Incomplete r3 cook-requirement contract.'}
    if((Get-NNHash $data.inventory) -ne $data.inventorySha256){throw 'Fresh dependency inventory changed.'}
    $cookRegistry=Get-Content -LiteralPath $data.inventory -Raw|ConvertFrom-Json
    if($cookRegistry.kind -ne 'ProphecyFreshCookRegistry' -or -not $cookRegistry.success){throw 'Required cook set lacks a successful fresh registry export.'}
    $requiredCookedGamePackages=@($data.requiredCookedGamePackages)
    $requiredCookedExternalPackages=@($data.requiredCookedExternalPackages)
    if(@(Compare-Object @($requiredCookedGamePackages|Sort-Object) @($cookRegistry.runtimeGamePackageClosure|Sort-Object)).Count -or
       @(Compare-Object @($requiredCookedExternalPackages|Sort-Object) @($cookRegistry.runtimeExternalPackageClosure|Sort-Object)).Count -or
       @(Compare-Object @($data.gamePackageClosure|Sort-Object) @($cookRegistry.gamePackageClosure|Sort-Object)).Count -or
       @(Compare-Object @($data.gamePackageRoots|Sort-Object) @($cookRegistry.rootPackages|Sort-Object)).Count){throw 'Snapshot source/cook closure does not match the pinned fresh graph.'}
    foreach($required in $requiredCookedGamePackages){if($required -notin $data.gamePackageClosure){throw "Runtime package missing from copied closure: $required"}}
    foreach($file in $data.externalPackageInputs){if((Get-NNHash $file.path) -ne $file.sha256){throw "External package input changed: $($file.path)"}}
}
$native=Assert-NNDependency $project $Configuration''')
replace('$stagedModels=@(); $nativeDlls=@(); $cookedPackages=@(); $receipts=@(); $controls=$null', '$stagedModels=@(); $nativeDlls=@(); $cookedPackages=@(); $cookedExternalPackages=@(); $uncookedEditorOnlyPackages=@(); $receipts=@(); $controls=$null')
replace('''        if($cooked.Count -ne 1){throw "Expected cooked package missing: $package"}
        $cookedPackages += [pscustomobject]@{package=$package;file=$cooked[0];sha256=(Get-NNHash $cooked[0])}
    }
    foreach($file in (Get-ChildItem -LiteralPath $stage -Recurse -File -Filter '*.dll')){''', r'''        $required=$package -in $requiredCookedGamePackages
        if($cooked.Count -gt 1 -or ($required -and $cooked.Count -ne 1)){throw "Expected cooked runtime package missing or ambiguous: $package"}
        if($cooked.Count -eq 1){
            $cookedPackages += [pscustomobject]@{package=$package;file=$cooked[0];sha256=(Get-NNHash $cooked[0]);requiredAtRuntime=$required}
        } else {
            $uncookedEditorOnlyPackages += $package
        }
    }
    foreach($package in $requiredCookedExternalPackages){
        $source=@($data.externalPackageInputs|Where-Object{$_.package -eq $package -and [IO.Path]::GetExtension($_.path) -in @('.uasset','.umap')})
        if($source.Count -ne 1){throw "Expected one recorded external main package: $package"}
        $sourcePath=Resolve-NNAbsolute $source[0].path
        $engineRoot=Resolve-NNAbsolute $engine
        if(-not $sourcePath.StartsWith($engineRoot+'\',[StringComparison]::OrdinalIgnoreCase)){throw "Unreviewed external mount outside engine installation: $package"}
        $relative=$sourcePath.Substring($engineRoot.Length+1)
        $cooked=Join-Path $cookOutput $relative
        Assert-NNFile $cooked
        $cookedExternalPackages += [pscustomobject]@{package=$package;file=$cooked;sha256=(Get-NNHash $cooked)}
    }
    if($hasCookSet){
        foreach($file in $data.externalPackageInputs){if((Get-NNHash $file.path) -ne $file.sha256){throw "External package input changed during cook: $($file.path)"}}
        if((Get-NNHash $data.inventory) -ne $data.inventorySha256){throw 'Fresh dependency inventory changed during cook.'}
    }
    foreach($file in (Get-ChildItem -LiteralPath $stage -Recurse -File -Filter '*.dll')){''')
replace('''        stagedModels=$stagedModels;stagedNativeDlls=$nativeDlls;cookedGamePackages=$cookedPackages;receipts=$receipts''', '''        stagedModels=$stagedModels;stagedNativeDlls=$nativeDlls;cookedGamePackages=$cookedPackages;receipts=$receipts
        requiredCookedGamePackages=$requiredCookedGamePackages;requiredCookedExternalPackages=$requiredCookedExternalPackages
        cookedExternalPackages=$cookedExternalPackages;uncookedCopiedEditorOnlyPackages=$uncookedEditorOnlyPackages
        cookDependencyInventory=$data.inventory;cookDependencyInventorySha256=$data.inventorySha256''')

out = HERE / 'Build-NNCrowdPackage.ps1'
with out.open('x', encoding='utf-8', newline='\n') as f:
    f.write(text)
with (HERE / 'WrapperBaseline.sha256.txt').open('x', encoding='utf-8') as f:
    f.write(hashlib.sha256(SOURCE.read_bytes()).hexdigest().upper() + '\n' + str(SOURCE) + '\n')
print('Draft generated:', out)
