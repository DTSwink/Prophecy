# Local AVX2/FMA diagnostic draft

Source-only checkpoint, 2026-09-09. No active files changed and no build, CPU probe, editor/game or benchmark was run by this agent. Existing PowerShell scripts parse and `git apply --check ExistingFiles.patch` passes against the recorded baseline. The dependency and consumer still need compilation and runtime validation by root.

The profile is **AVX2 + FMA + precise floating point**, not no-FMA. It preserves double world positions, existing native float quantities, CRT, exceptions, RTTI setting, solver iterations, PHAT angles, collision profiles, NN precision/cadence and all bodies/bones. Cross-platform determinism and AVX512 remain OFF. No speedup is assumed.

## Promotion inventory

Apply `ExistingFiles.patch` for these five tracked files, after checking `BaselineHashes.json`:

- `Tools/Jolt/BuildJolt.ps1`
- `Tools/Jolt/CMakeLists.txt`
- `Plugins/ProphecyJolt/Source/ProphecyJoltLibrary/ProphecyJoltLibrary.Build.cs`
- `Plugins/ProphecyJolt/Source/ProphecyJolt/ProphecyJolt.Build.cs`
- `Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltModule.cpp`

Copy only these five new source files from the draft into the corresponding active paths:

- `Tools/Jolt/ProphecyJoltBuildContract.h`
- `Tools/Jolt/ProphecyJoltBuildContract.cpp`
- `Tools/Jolt/CpuPreflight/CMakeLists.txt`
- `Tools/Jolt/CpuPreflight/ProphecyJoltCpuPreflight.cpp`
- `Tools/Jolt/InvokeJoltAvx2Diagnostic.ps1`

Full changed-file copies are provided for review, but the isolated patch preserves unrelated concurrent work. `MakeDraft.py` is provenance/generation tooling only, not a project source file to promote. Do not rerun it against changed active sources without reviewing the resulting new baseline.

## Dependency and ABI behavior

`BuildJolt.ps1 -Configuration Development -Simd AVX2` prepares a separate native dependency at:

```text
Intermediate/JoltMigration/Build/AVX2/Development/
Intermediate/JoltMigration/Install/AVX2/Development/
  bin/ProphecyJolt_5_6_Development_AVX2.dll
  lib/ProphecyJolt_5_6_Development_AVX2.lib
  include/ProphecyJoltBuildContract.h
  tools/ProphecyJoltCpuPreflight.exe
  manifest.json
```

Shipping follows the same layout with Shipping in place of Development. This draft uses `_AVX2` as the suffix after configuration; it supersedes the audit's merely proposed alternative filename order. The existing SSE2 `Build/Development`, `Install/Development`, `ProphecyJolt_5_6_Development.dll/lib` and Shipping equivalents remain untouched when AVX2 is selected. Default `-Simd SSE2` retains their names and schema 2. The new native accessor is built only for AVX2, so an existing known-good SSE2 dependency does not need rebuilding merely to use the new consumer source.

Schema 3 records AVX2, actual declared FMA=true, instruction mask 2015 (`0x7df`), contract version 1, native DLL/import/header/probe hashes, toolchain, and CPU preflight evidence. The external Build.cs validates the selected profile and hashes before linking. It publishes all matching `JPH_USE_*` macros. The runtime Build.cs sets module-local `MinCpuArchX64.AVX2`; SSE2 explicitly selects `None`. The game/editor modules retain their existing compiler ISA.

The native accessor has C linkage and only integer/character-pointer return types. It reports the DLL's effective Jolt version/ABI feature ID, ISA mask, policy mask and configuration string. Compile-time assertions verify both the DLL and native consumer have the declared complete ISA and policy. Startup compares both before owning Factory/allocators/types. Jolt's existing version check remains. The precise policy bit is a recipe declaration, backed by the wrapper's final `/fp:precise` and the module's `FPSemanticsMode.Precise`; the ISA/FMA bits are computed from actual Jolt/compiler macros.

### UE engine/game boundary audit

Module-local AVX2 also sets `PLATFORM_ALWAYS_HAS_AVX_2`, which changes UE's transient `VectorRegister4Double` from a 16-aligned pair of 128-bit registers to a 32-aligned union containing `__m256d`. This raw register type is not an ABI-neutral public payload. Current ProphecyJolt public interfaces expose none of it, `TVectorRegisterType`, or `TPersistentVectorRegisterType` directly.

UE explicitly preserves persistent math storage: [VectorRegister.h:54-100](C:/Program%20Files/Epic%20Games/UE_5.7/Engine/Source/Runtime/Core/Public/Math/VectorRegister.h:54) selects `alignas(16) double[4]` storage for AVX while retaining the 16-aligned two-register representation for SSE2. [TransformVectorized.h:42-79](C:/Program%20Files/Epic%20Games/UE_5.7/Engine/Source/Runtime/Core/Public/Math/TransformVectorized.h:42) uses this persistent type for Rotation, Translation and Scale, preserving FTransform's three 32-byte blocks, 96-byte size and 16-byte alignment. [Quat.h:38-59](C:/Program%20Files/Epic%20Games/UE_5.7/Engine/Source/Runtime/Core/Public/Math/Quat.h:38) stores four scalar doubles with explicit 16-byte alignment (32 bytes); [Vector.h:50-77](C:/Program%20Files/Epic%20Games/UE_5.7/Engine/Source/Runtime/Core/Public/Math/Vector.h:50) stores three scalar doubles (24 bytes, alignment 8). [UnrealMathSSE.h:637-647](C:/Program%20Files/Epic%20Games/UE_5.7/Engine/Source/Runtime/Core/Public/Math/UnrealMathSSE.h:637) deliberately uses an unaligned 256-bit double load under AVX because callers guarantee only 16-byte alignment. The FProphecy snapshots/state/targets containing these types consequently retain the same source-defined member storage; their remaining members are ordinary Unreal scalars/containers/handles, not raw SIMD registers.

The module now asserts these four relevant sizes/alignments for both profiles. This is a narrow layout guard, **not proof of every FProphecy struct offset, inline function, calling convention or engine ABI**. The UBT AVX2 branch changes ISA macros/flags and does not add `/Gv`/`__vectorcall`; current public functions keep their declared ordinary C++ signatures. Root must inspect the compiled response files and run the actual game-module-to-plugin live fixtures, including nonidentity transforms, pose/body roundtrips and teardown. Foundation tests compiled wholly inside the plugin are not sufficient boundary evidence on their own.

There are a few forward-declared native accessors (`GetNativeBodyShape`, `GetNativeBodyMassProperties`, and the standalone equivalents) in the prepared-rig/body headers. Their current callers are exclusively plugin-private implementation/tests; the game/editor do not construct or pass those native mass objects. Any future module that includes Jolt to use these accessors must adopt the matching native ISA/ABI contract too. This qualifies the shorthand statement that the current game-facing boundary uses Unreal types.

`MathTypes.h:20-24` changes `DVec3Arg` from reference to value when AVX is enabled. A DLL-only replacement is therefore invalid. Inspect the new runtime `.rsp`/`Definitions.h`, native `.vcxproj`, startup native contract log and staged import name after compiling. AVX2 expected: `/arch:AVX2`, final precise FP, no `/arch:AVX512`, native instruction mask 2015 and policy mask 3. Native version ID must match the consumer's double/assert/object-stream configuration.

## Scoped consumer build and restoring SSE2

The opt-in selector is the **process environment variable** `PROPHECY_JOLT_SIMD=AVX2`; its default is SSE2. Both external and consumer modules read it. Since an environment change is not a tracked UBT makefile dependency, **every build that selects or changes this diagnostic profile must pass `-NoUBTMakefiles`**. This is required even when returning to SSE2. UBT still handles incremental compile actions; the changed module ISA/definitions/import arguments cause the relevant consumer rebuild. Never use a cached UBT makefile prepared for the other profile.

Example for the current local project, after stopping UE/game normally and preserving the known SSE2 consumer binaries/receipts and hashes:

```powershell
& 'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Tools/Jolt/BuildJolt.ps1' -Configuration Development -Simd AVX2
$previousJoltSimd = [Environment]::GetEnvironmentVariable('PROPHECY_JOLT_SIMD', 'Process')
try {
    [Environment]::SetEnvironmentVariable('PROPHECY_JOLT_SIMD', 'AVX2', 'Process')
    & 'C:/Program Files/Epic Games/UE_5.7/Engine/Build/BatchFiles/Build.bat' GameAnimationSample3Editor Win64 Development '-Project=C:/Users/singerie/Documents/Unreal Projects/Prophecy/GameAnimationSample3.uproject' -WaitMutex -NoUBTMakefiles
    if ($LASTEXITCODE -ne 0) { throw 'AVX2 consumer build failed.' }
}
finally {
    [Environment]::SetEnvironmentVariable('PROPHECY_JOLT_SIMD', $previousJoltSimd, 'Process')
}
```

Returning to SSE2 uses the same scoped block with `SSE2` and `-NoUBTMakefiles`, referencing the preserved original installation. Restoring the environment alone does not restore the on-disk compiled module. Distinct native DLL filenames do not by themselves preserve a runnable prior `UnrealEditor-ProphecyJolt.dll`: preserve/rebuild its matching consumer as well. No Live Coding ISA switching, simultaneous mixed-profile globals or machine-wide environment changes are intended.

## CPU preflight and launch

The baseline probe is a completely separate MSVC x64 target, statically linked to its CRT and with no Jolt/UE imports. A compile-time guard rejects any AVX compiler mode. It checks CPUID SSE2/SSE4.1/SSE4.2/POPCNT, AVX/AVX2, F16C/FMA, extended LZCNT, BMI1/TZCNT and BMI2; XGETBV is executed only after XSAVE and OSXSAVE are reported and AVX requires XCR0 bits 1+2. It prints raw bits, effective supported/required/missing instruction masks and a supported result. Exit 1 refuses launch. The reported instruction mask covers this profile's requirements; it is not a complete CPU capability inventory.

The dependency build compiles and runs the probe **before** compiling/using the AVX2 DLL. Later launches must run it again. `InvokeJoltAvx2Diagnostic.ps1` verifies the installed probe's hash, runs it, writes a new UTF-8 JSON sidecar (including refusals), and only invokes the supplied executable/argument array after admission. It does not alter affinity, priority, power, QoS or machine settings. The output directory must already exist and the sidecar path must be absolute and unused.

Use that wrapper around the normal benchmark launcher process (for example `powershell.exe` plus the existing launcher arguments), or directly around `UnrealEditor-Cmd.exe` with the established arguments. Preserve argument arrays rather than construct an interpolated shell command. The sidecar records the dependency manifest hash; root should also retain consumer binary hashes and verify the native contract startup log for the measured run.

This is deliberately a **local diagnostic launch boundary**. The current Jolt DLL is a normal import, loaded before module startup; the AVX2 consumer itself may execute advanced instructions during load. The startup fingerprint check is not a CPU safety fallback. Directly launching a built AVX2 editor/game bypasses the external guard. A portable in-process SSE2/AVX2 selector would require a separate baseline module with no eager AVX2 imports and is outside this checkpoint.

## Validation and cooked data scope

No solver/cook source or assets are changed here. For the performance fixture, continue preparing shapes freshly from its immutable rig/body descriptors. Do not overwrite the existing SSE2 cooked fixture. Before using this profile in a cooked game, generate a separate AVX2 fixture and repeat complete archive/child/material/COM/bounds/ray and Shipping readback checks. The present shape archive has no ISA/FMA key and this draft does not assert cross-profile compatibility; see `Saved/JoltMigration/Avx2ProfileAudit.md`.

Required next checks: dependency/consumer build; exported fingerprint and CPUID admission; foundation/rig/body/joint/query/servo/lifetime suite; one-/two-agent live smoke; actual NN 100-agent workload with all 22/21/88 functionality, 30 Hz real CPU NN, 60 Hz physics/presentation, capsule motion, feedback, callback invalidation, queries and cleanup. Then repeat matched SSE2/AVX2 runs with identical worker count, P-class diagnostic, movement-only, query padding, DuringPhysics/batching and samples. Report full world distributions and Jolt phases together. No trajectory-equivalence, reduced cadence, retuning, reduced bones or performance-victory claim is introduced.

## Exact command sequence after review

From the project root, first check then apply `Saved/JoltMigration/Avx2ProfileDraft/ExistingFiles.patch` and copy the five new files listed above to their exact active destinations. Preserve baseline consumer DLL/PDB/receipts and hashes before the build. The dependency/build scoped commands above are the next steps; neither was executed for this draft.

After a successful AVX2 consumer build, run the existing foundation suite through preflight:

```powershell
$projectPath = 'C:/Users/singerie/Documents/Unreal Projects/Prophecy'
$runStamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$guard = Join-Path $projectPath 'Tools/Jolt/InvokeJoltAvx2Diagnostic.ps1'
& $guard -Executable powershell.exe -PreflightOutput "$projectPath/Saved/JoltMigration/avx2_foundation_$runStamp.cpu.json" -ProgramArguments @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$projectPath/Tools/Jolt/RunFoundationTests.ps1", '-NoLockIdleReads')
```

This suite's launcher waits and checks clean automation results. The following existing benchmark launcher returns an owned process ID immediately; wait for its completion and validate its report before launching another UE process. Use a fresh label and preflight path for each run:

```powershell
$runStamp = Get-Date -Format 'yyyyMMdd_HHmmss'
& $guard -Executable powershell.exe -PreflightOutput "$projectPath/Saved/JoltMigration/avx2_smoke_$runStamp.cpu.json" -ProgramArguments @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$projectPath/Tools/NN/RunSterilePhysicsBenchmark.ps1",
    '-Methods', 'NNJoltCrowd', '-Count', '2', '-Warmup', '30', '-Samples', '60', '-Repeats', '1',
    '-FloorOnly', '-MovementOnly', '-DuringPhysics', '-PClassGameThread', '-NoLockIdleReads',
    '-JoltWorkerThreads', '7', '-QueryTreePaddingCm', '40', '-ProcessPriority', 'Normal',
    '-Label', "avx2_nn_smoke_$runStamp")
```

Once smoke/queries/lifecycle pass, the matched full workload uses the same argument list with `Count=100`, `Warmup=120`, `Samples=360` and a new `avx2_nn_100_*` label. Keep worker count 7 and NoLock only when comparing against the newest corresponding SSE2 worker-7/NoLock baseline; comparing against an older worker-3/locking run would confound the ISA effect. Run separate repeated processes rather than use `Repeats>1`, which the actual-NN fixture deliberately rejects. Record the matching native startup fingerprint and CPU sidecar for every AVX2 process.

To restore SSE2 after all AVX2 children have exited, reuse the scoped build block above with `PROPHECY_JOLT_SIMD='SSE2'` and `-NoUBTMakefiles`; do not rebuild/overwrite the preserved SSE2 dependency. Confirm the rebuilt module imports the original unsuffixed DLL and startup is the SSE2 profile. Then run the same foundation/smoke/full workload through the original launchers for comparison. Environment restoration and binary/profile restoration are distinct steps; no global environment/power/affinity setting is changed by these commands.
