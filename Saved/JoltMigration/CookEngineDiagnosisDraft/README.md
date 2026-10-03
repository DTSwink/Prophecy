# R2 cook diagnosis and short-output draft

R2's 21 cook errors consist of seven absolute cooked-file paths exceeding UE's 260-character check, followed by fourteen references to those same seven unsaved packages. The `NeverCook or is not cookable` text is the downstream reference validator's general diagnostic. It does not establish a plugin-content exclusion conflict in this run. All seven failed file names are 261–276 characters. The proposed output layout reduces them to 224–239 characters without changing package identities, references, plugins, shader settings or validation.

Evidence: [R2 UAT log](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/NNCrowd-20260909-144331-647/Packages/Development-20260909-150202-771/UAT.log:410>), first MetaHuman failure at line 567, final summary at line 1564. `PathLengthEvidence.json` records all seven old/proposed paths. UE's [CookSavePackage.cpp](</C:/Program Files/Epic Games/UE_5.7/Engine/Source/Editor/UnrealEd/Private/Cooker/CookSavePackage.cpp:352>) converts the save name to an absolute path and returns `ESavePackageResult::Error` when its length is at least `FPlatformMisc::GetMaxPathLength()`.

There are also five missing `/Game` constructor assets and `/Game/Input/TIS_MobileControls` referenced by `DefaultInput.ini:91`. Adding those packages and their dependencies to the isolated manifest is separate from the output-path fix. Root owns that manifest revision. The validation policy must continue rejecting unresolved packages.

## Why these plugin assets appear in an Entry cook

`-map=/Engine/Maps/Entry` selects the map, but does not exclude startup/config/CDO asset references. [UCookOnTheFlyServer::GenerateInitialRequests](</C:/Program Files/Epic Games/UE_5.7/Engine/Source/Editor/UnrealEd/Private/CookOnTheFlyServer.cpp:11415>) collects startup soft references, then adds startup hard/soft references after the requested files at lines 11514–11548. This wrapper does not opt out of those references.

The snapshot preserves enabled Mover and MetaHumanCharacter from the source project. [Mover.uplugin](</C:/Program Files/Epic Games/UE_5.7/Engine/Plugins/Experimental/Mover/Mover.uplugin:54>) enables Water; [Water.uplugin](</C:/Program Files/Epic Games/UE_5.7/Engine/Plugins/Experimental/Water/Water.uplugin:31>) enables Landmass. [ALandmassActor's constructor](</C:/Program Files/Epic Games/UE_5.7/Engine/Plugins/Experimental/Landmass/Source/Editor/Private/LandmassActor.cpp:24>) synchronously loads `BrushBounds` into a default subobject. This supplies a concrete startup route without requiring a Landmass actor placed in Entry.

The MetaHuman route has direct runtime cook evidence: UAT lines 434 and 565 report an unexpected load of `/MetaHumanCharacter/Materials/MI_GeneratePreBakedGrooms` while cooking `/MetaHumanCharacter/TextureGraphs/TG_BakedGrooms` and `/HairStrands/Materials/HairDebugMaterial`. UE says it conservatively adds that package because the source did not declare it as an import. The loaded material-instance asset contains the exact package reference `/MetaHumanCharacter/Materials/M_BakedGrooms` (ASCII byte offset 1873). [CookOnTheFlyServer.cpp:4901](</C:/Program Files/Epic Games/UE_5.7/Engine/Source/Editor/UnrealEd/Private/CookOnTheFlyServer.cpp:4901>) implements that conservative path. The initial first loader of every MetaHuman startup asset was not instrumented in R2; do not present a fully traced first-loader chain as established. The observed dynamic-load route and the explicit save failures suffice to justify the path fix.

## UAT option verified end to end

Use `-CookOutputDir=<absolute short path>/Cook/Windows`, with the leaf **Windows**.

1. [ProjectParams.cs:870](</C:/Program Files/Epic Games/UE_5.7/Engine/Source/Programs/AutomationTool/AutomationUtils/ProjectParams.cs:870>) parses the `CookOutputDir` UAT option.
2. [CookCommand.Automation.cs:74](</C:/Program Files/Epic Games/UE_5.7/Engine/Source/Programs/AutomationTool/Scripts/CookCommand.Automation.cs:74>) forwards it as the cook commandlet's `-outputdir`.
3. [CookCommandlet.cpp:333](</C:/Program Files/Epic Games/UE_5.7/Engine/Source/Editor/UnrealEd/Private/Commandlets/CookCommandlet.cpp:333>) parses it and supplies it to `Initialize` at line 388.
4. [CookOnTheFlyServer.cpp:7099](</C:/Program Files/Epic Games/UE_5.7/Engine/Source/Editor/UnrealEd/Private/CookOnTheFlyServer.cpp:7099>) uses this exact override for single-platform CookByTheBook. It does not append Windows in that case.
5. [CopyBuildToStagingDirectory.Automation.cs:1273](</C:/Program Files/Epic Games/UE_5.7/Engine/Source/Programs/AutomationTool/Scripts/CopyBuildToStagingDirectory.Automation.cs:1273>) uses `Params.CookOutputDir` for cooked files and metadata. It appends the platform only if the directory's leaf is not already that platform. Supplying the Windows leaf therefore makes cook and stage agree exactly.

`-stagingdirectory` separately moves staging output to the fresh short sibling `Stage`. No snapshot relocation, source/config change, symbolic link, hardlink or drive mapping is required.

## Draft review and promotion

`Build-NNCrowdPackage.ps1` is a full proposed copy; `Build-NNCrowdPackage.patch` is its four-hunk diff. Only draft files were written. `PatchEvidence.json` records the active input and draft hashes. Active script was unchanged when draft generation completed. PowerShell parsing passed with zero errors; UE/build/package execution was not performed by this agent.

The draft creates a fresh `C:/Users/singerie/.codex/tmp/ProphecyJolt/NNPkg-<configuration>-<UTC timestamp>` directory after rejecting reparse-point ancestors. It creates `Cook/Windows` and `Stage` there, records a create-new `ownership.json` bound to the snapshot SHA and future package report, passes the cook override, and checks every expected `/Game` cooked package in that exact output. The final package report contains absolute cook/stage paths and the ownership record/hash. Existing runtime runner uses the package's explicit stage path, so its path guard continues to apply.

Root should verify the active script still matches `PatchEvidence.json` before promotion, then review and apply the diff. The manifest revision for the additional required assets remains necessary. On the next cook, require clean completion and existing package closure, DLL/model, query-control and runtime checks. This draft does not claim package success or any performance gain.
