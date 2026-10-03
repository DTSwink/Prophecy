# Engine ISPC boundary report (draft only)

Adds one read-only helper and two report fields to the current benchmark: each case's audit `engine_ispc_settings`, and final `engine_ispc_settings_at_finish`. No per-frame work, settings changes, command-line enable switch, builds, or Unreal launches.

The report reads three actual runtime bool CVars, their value text/flags, and the loaded Engine module's filename/status. A stock registration of all three while Engine is loaded is positive evidence that that Engine was built with ISPC support in a non-Shipping configuration. Missing registration is **unknown**, never proof of disabled Engine compilation; stock Shipping builds retain fixed compiled defaults and omit these runtime controls. `FindConsoleVariable` already excludes unregistered and INI-only placeholders. Bool type is checked as an additional guard.

Effective normalization is `a.BonePose.ISPC`. Effective component-space construction is `a.SkinnedAsset.ISPC && a.SkeletalMesh.ISPC`: false on the deprecated switch overrides the modern setting. These are code-path selectors, not execution counters or the dispatched CPU ISA. Nothing reads the game module's `INTEL_ISPC`.

## Verified installed Engine build evidence

Source/build artifact root: `C:/Program Files/Epic Games/UE_5.7/Engine`, read 2026-09-09.

- `Intermediate/Build/Win64/x64/UnrealEditor/Development/Engine/SharedDefinitions.Engine.Cpp20.h`: line 47 `WITH_EDITOR 1`, line 80 `UE_BUILD_DEVELOPMENT 1`, line 209 `INTEL_ISPC 1`. SHA256 `46edd91a2c8bb8fb9c10f55223979a5487c199be124d454bcb378a9773d95647`. This is the installed Engine's generated definition file, not a game-module assumption; runtime module/control evidence is still recorded independently.
- `Source/Programs/UnrealBuildTool/Platform/Windows/UEBuildWindows.cs:1405`: Windows target setup enables `Target.bCompileISPC`.
- `Source/ThirdParty/Intel/ISPC/IntelISPC.Build.cs:13`: external IntelISPC module publishes `INTEL_ISPC` from `Target.bCompileISPC`.
- `Source/Runtime/Engine/Engine.Build.cs:151-169`: Engine privately depends on IntelISPC.
- `Source/Runtime/Engine/Private/Animation/BonePose.cpp:18-27`: normalization default is 1; runtime control only in `INTEL_ISPC && !UE_BUILD_SHIPPING`; lines 30-55 select ISPC vs ordinary per-transform normalization.
- `Source/Runtime/Engine/Private/SkinnedAsset.cpp:25-34`: modern CS default is 1, same compile/Shipping registration guard. Lines 422-446 implement deprecated-false precedence. Lines 491-541 select ISPC vs parent-ordered scalar CS construction.
- `Source/Runtime/Engine/Private/Components/SkeletalMeshComponent.cpp:88-99`: deprecated setting defaults to 1 with the same registration guard.
- `Source/Runtime/Core/Private/HAL/ConsoleManager.cpp:1674-1677`: stock bool-ref registrations report `IsVariableBool()`. Lines 2368-2382 exclude unregistered variables; 2427-2429 exclude INI placeholders.
- `Source/Runtime/Core/Public/Modules/ModuleManager.h:126-145,287`: exported read-only QueryModule returns loaded state and filename.

No explicit setting for these three names or default macros was found in project Config, Source, Tools/Jolt, installed Engine/Config, or checked existing benchmark/Jolt logs. Unrelated Intel ISPC **texture compression** log lines are not animation evidence. No disabled value has been observed; consequently this draft includes **no enable path**. The next ordinary benchmark run will establish the actual values before any toggle is considered.

## Promotion / checks

Apply `EngineISPCReport.apply-patch.txt` to the active source. Baseline benchmark SHA256 at preparation: `64104a8b0fc98d9b31904d73291eb734ea44833324b4a1a866bd05a7060c74f8`. Parent may have nearby concurrent provenance edits; the hunks use local anchors rather than replacing the file.

Source-checked all called public APIs. No builds or runtime claims. Source verification should apply the hunks in memory and confirm that active files remain unchanged. Existing benchmark execution can verify start/finish report fields; no new physics test is necessary for a read-only boundary report.

Verification completed: all four hunk anchors matched exactly once and applied in memory against the parent's newer active source SHA256 `2541259646d4459798af3b7c259ebcb0d57ab0f38171cf6423855accf603b5a9`; active bytes were unchanged by verification. No runtime or build was executed.
