# Game-module ISA diagnostic draft

Draft only. No active source was edited, no compiler/build/editor/game was launched. Ordinary game settings and native Jolt remain unchanged until root explicitly promotes/builds a selected profile. There is no predicted speedup.

## Promotion files and order

1. Inspect `BaselineHashes.json` and `ExistingFiles.patch`. The patch changes only `Source/GameAnimationSample3/GameAnimationSample3.Build.cs` and three small sites in `Private/ProphecyPhysicsBenchmark.cpp` (include, pre-fixture expected-profile validation after output-path parsing, final JSON field). It passed `git apply --check` against the current active sources. Apply the isolated patch, not whole copied files, if root has concurrent changes.
2. Copy the four new files to their mirrored active paths: `Private/ProphecyGameModuleSimdPCH.h`, `Private/ProphecyGameModuleSimd.h`, `Private/ProphecyGameModuleSimd.cpp`, and `Tools/Jolt/RunGameModuleSimdBenchmark.ps1`.
3. `MakeDraft.py` is a draft-generation utility, not a runtime/build input to promote. The two full source copies are review aids. No plugin, native dependency, normal benchmark launcher, asset, PHAT, cadence or production configuration is changed by this patch.

## Selection and preserved contracts

| Process-scoped `PROPHECY_GAME_SIMD` | Profile ID | Game PCH / minimum ISA |
| --- | --- | --- |
| unset, empty or `DEFAULT` | 0 | Existing `UseExplicitOrSharedPCHs`; no ISA override |
| `SSE2_PRIVATE` | 1 | New CoreMinimal-only private PCH, `NoSharedPCHs`, minimum `None` |
| `AVX2_PRIVATE` | 2 | Identical private PCH, minimum `AVX2` |

Both explicit profiles are Win64 x64 only and require `PROPHECY_JOLT_SIMD=SSE2` (or its unchanged default). The game rule never changes that variable or any plugin rule. `SSE2_PRIVATE` labels the x64 compiler minimum/no-AVX control; existing UE platform intrinsics can still use their normal SSE4.1 baseline. It is not a claim that the whole engine uses only SSE2 instructions.

UE5.7 `UEBuildModuleCPP.cs:1700-1752`, shared-PCH suffix generation, and `CopySettingsForSharedPCH:1891-1910` omit `MinCpuArchX64`; this experiment therefore must not reuse the normal shared PCH. `CreatePrivatePCH:1543-1554` clones the module environment, and `CppCompileEnvironment.cs:922` copies its minimum ISA. Inspect the PCH and all relevant object response files after each build to confirm that this path was actually used. A CoreMinimal-only private PCH can expose pre-existing missing explicit includes that the large UnrealEd shared PCH concealed; such compile errors need ordinary include fixes, not a return to incompatible shared-PCH reuse.

Neither profile changes FP, optimization, unity, RTTI, exceptions or language settings. Existing GameAnimationSample3 object response files show `/fp:fast /Ox /Ob2 /EHsc /GR- /std:c++20`. Preserve those settings in both controls; do not add precise only to AVX2 or relax math further. The runtime report explicitly distinguishes UE's FMA-intrinsic macro from an assurance about compiler-generated FMA: `/fp:fast` can permit different contraction/code generation, and no FMA-free or bit-identical trajectory claim is made.

Four compile-time guards verify the audited storage contracts: FVector 24/8, FQuat 32/16, FTransform 96/16, FMatrix 128/16 (size/alignment). The report additionally shows persistent and temporary double-register layouts. UE's persistent transform lanes retain 16-byte alignment; temporary VectorRegister4Double changes from 16 to 32. These are narrow storage guards, not a proof of every C++ class offset, calling convention or external inline function. Current game headers and DLL imports contain no raw SIMD boundary; NNE uses pointer/size tensor bindings, the shared mover compiles directly into this module, and plugin public calls use ordinary UE data/opaque handles.

Current object symbols prove that Pose/NNManager call Core's out-of-line `FTransform::Multiply` and `GetRelativeTransform`; NNManager also imports quaternion Slerp. Those routines, Engine skeletal/query code, ORT inference and native Jolt stay in their existing DLLs. This experiment targets game-local loops and inline math only; profiling must establish whether it helps the total world interval.

## Runtime provenance and external admission

`game_module_build_profile` is serialized into every benchmark completion/failure JSON outside timing. It reports the compiled ID/name, compiler and Unreal AVX/FMA macros, six storage observations, editor/Shipping flags and launcher's expected profile/preflight path. The benchmark validates the expected profile before loading its fixture mesh or altering time/physics settings. Mismatches still write to the already parsed requested JSON path. Explicit-profile benchmark launches require the guarded wrapper's provenance; ordinary DEFAULT runs need no new environment variables.

This runtime check cannot protect module loading. Use the external baseline CPU probe **before any process that loads the AVX2 game DLL**, including foundation tests. No in-process fallback is claimed. The new wrapper reads the existing, unchanged probe from `Install/AVX2/Development/tools`, checks its manifest hash, and requires its full conservative mask 2015, POPCNT, XSAVE/OSXSAVE and enabled AVX OS context. The probe's historical `AVX2_FMA_PRECISE` label is preserved only inside the raw probe record; the outer sidecar correctly labels this as a game-module experiment with the game's unchanged FP policy.

The wrapper writes a new `<Label>.game-simd.cpu.json` sidecar before launch, with actual hashes of the game module, Unreal Jolt consumer, staged SSE2 native DLL, native manifest, probe, Core/Engine modules, ORT DLL and editor executable. A small bounded PE reader checks that the actual Unreal Jolt consumer imports exactly `ProphecyJolt_5_6_Development.dll`, and the game imports `UnrealEditor-ProphecyJolt.dll`; it never loads either DLL. This catches an AVX2 consumer left behind while a spare SSE2 DLL happens to exist beside it. Hashes plus independent response-file inspection/native startup log establish profile provenance; filenames alone do not certify compiler flags.

The wrapper calls the existing `RunSterilePhysicsBenchmark.ps1` with sole NNJoltCrowd, one repeat, explicit floor and movement-only profile. Only the expected-profile and sidecar-path environment variables are temporarily set, inherited by the hidden child and restored immediately after launch. It returns the existing owned child PID/report, **not a completed-run success**; root must wait and validate the result before another launch. It never changes build-profile environment variables, process-wide affinity, machine power/QoS or native ISA. Optional GT placement/priority remain the already explicit existing benchmark controls.

## Exact build / test / restore recipe (not executed here)

Run from the active project root only after promotion. Stop before building if any owned or user UE/game process is active; do not stop unrelated processes. Save process environment values and restore them in `finally`. Use fresh UBT evaluation for **every** profile selection, including restoration; an environment change by itself is not sufficient proof UBT invalidated its makefile.

```powershell
$buildTool = 'C:/Program Files/Epic Games/UE_5.7/Engine/Build/BatchFiles/Build.bat'
$projectFile = (Resolve-Path 'GameAnimationSample3.uproject').Path
$savedGameProfile = [Environment]::GetEnvironmentVariable('PROPHECY_GAME_SIMD', 'Process')
$savedJoltProfile = [Environment]::GetEnvironmentVariable('PROPHECY_JOLT_SIMD', 'Process')
try {
    $env:PROPHECY_GAME_SIMD = 'SSE2_PRIVATE' # later repeat this block with AVX2_PRIVATE
    $env:PROPHECY_JOLT_SIMD = 'SSE2'
    & $buildTool GameAnimationSample3Editor Win64 Development "-Project=$projectFile" `
        -WaitMutex -NoHotReloadFromIDE -NoUBTMakefiles -MaxParallelActions=5
    if ($LASTEXITCODE -ne 0) { throw "Game profile build failed: $LASTEXITCODE" }
}
finally {
    [Environment]::SetEnvironmentVariable('PROPHECY_GAME_SIMD', $savedGameProfile, 'Process')
    [Environment]::SetEnvironmentVariable('PROPHECY_JOLT_SIMD', $savedJoltProfile, 'Process')
}
```

After each build, verify `Intermediate/Build/Win64/x64/UnrealEditor/Development/GameAnimationSample3/PCH.GameAnimationSample3.h.cpp.obj.rsp` (discover the exact PCH response-file basename) and current Pose/NNManager/QueryPose/generated object response files: private PCH, same FP and optimization flags, no AVX in SSE2 control, `/arch:AVX2` and `PLATFORM_ALWAYS_HAS_AVX[_2]=1` in AVX2. Confirm native consumer response files still lack AVX and import the SSE2 native name. Both profiles require newly compiled generated code; no Live Coding or hot-reload swap.

Run the existing baseline probe directly before any non-wrapper foundation launch and require `supported=true`, mask 2015/missing 0, exit 0; do not use the original native-AVX2 launcher, which would mislabel this experiment. Then run the current complete Jolt foundations and NN oracle tests. Do not change their numerical gates or omit rejected-input tests because AVX2 compiles differently. Profile 1 and 2 receive the same validation.

```powershell
# These launches return a PID. Wait for each owned child and inspect its new JSON.
powershell -NoProfile -File Tools/Jolt/RunGameModuleSimdBenchmark.ps1 `
    -GameProfile SSE2_PRIVATE -Label game_sse2_private_smoke -Count 2 -Warmup 60 -Samples 60 `
    -DuringPhysics -PClassGameThread -NoLockIdleReads -JoltWorkerThreads 7 -QueryTreePaddingCm 40

powershell -NoProfile -File Tools/Jolt/RunGameModuleSimdBenchmark.ps1 `
    -GameProfile SSE2_PRIVATE -Label game_sse2_private_100_A -Count 100 -Warmup 60 -Samples 360 `
    -DuringPhysics -PClassGameThread -NoLockIdleReads -JoltWorkerThreads 7 -QueryTreePaddingCm 40

# After the separately completed AVX2_PRIVATE build and equivalent foundations:
powershell -NoProfile -File Tools/Jolt/RunGameModuleSimdBenchmark.ps1 `
    -GameProfile AVX2_PRIVATE -Label game_avx2_private_smoke -Count 2 -Warmup 60 -Samples 60 `
    -DuringPhysics -PClassGameThread -NoLockIdleReads -JoltWorkerThreads 7 -QueryTreePaddingCm 40

powershell -NoProfile -File Tools/Jolt/RunGameModuleSimdBenchmark.ps1 `
    -GameProfile AVX2_PRIVATE -Label game_avx2_private_100_A -Count 100 -Warmup 60 -Samples 360 `
    -DuringPhysics -PClassGameThread -NoLockIdleReads -JoltWorkerThreads 7 -QueryTreePaddingCm 40
```

The examples deliberately leave the separate paused-Chaos diagnostic off. If root selects it, pass `-PauseChaos` to both compared profiles and label that factor. Never silently pair a paused candidate with an unpaused control. Repeat independent processes and record phase/placement variability; a single favorable frame/run is insufficient.

Acceptance retains actual three CPU models at batch 100, 30 Hz NN with 180 steps/18,000 feedback samples, 360 measured 60 Hz world frames, 36,000 agent records, 792,000 body checks, 3,168,000 bone checks, full 22/21/88, original joint settings, capsule/head query identity, zero query fallback, no synthetic producer, callback-removal/cancellation/stale-handle teardown and GT restoration. Compare reported loaded game profile to sidecar expectation, and require native/Core/Engine/ORT hashes unchanged between the controls. Retain the separately required controlled post-EndPhysics query test. This remains NullRHI elapsed world time, not rendered FPS or summed worker cycles.

**Restore** using the same build block with `PROPHECY_GAME_SIMD='DEFAULT'` and `PROPHECY_JOLT_SIMD='SSE2'`, again `-NoUBTMakefiles`, restoring process environment afterward. Verify shared-PCH/no-AVX response files and a DEFAULT runtime fingerprint on a normal launcher smoke. Do not restore only the environment while leaving the AVX2 game DLL on disk. The optional draft files may remain inert; ordinary-default PCH/ISA settings are untouched.

## Draft checks performed

- Existing-file patch applies cleanly to the recorded active baseline; no active application performed.
- PowerShell AST parsing passed.
- The extracted read-only PE-import helper was tested against current game and Jolt consumer DLLs and matched `UnrealEditor-ProphecyJolt.dll` / `ProphecyJolt_5_6_Development.dll` respectively. No target DLL or UE process was loaded.
- The retained ORT file path exists. C++ compile/layout assertions and runtime gates await root's build/test. No performance claim is made.
