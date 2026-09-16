# Compile iteration audit — 2026-09-16

Corrected lower feedback is active: `Prophecy.NNLowerFeedbackAlignment=1`, verified with PIE off. The compilation workaround is now installed and verified. `Source/GameAnimationSample3Editor.Target.cs` sets `WindowsPlatform.bWriteSarif=false`; the temporary Saved XML override was removed.

## Installed results

After establishing a normal editor-build baseline, a comment-only edit to the independent `ProphecyRootPelvisBoundsLibrary.cpp` produced **1 compile action**, completed in **21.99 seconds** (Live Coding patch installed successfully). A subsequent unchanged Live Coding request produced **0 compile actions**, reported `Target is up to date`, and completed in **1.27 seconds**. The original unchanged request scheduled41 actions. These are observed examples, not a guarantee that every C++ edit will take22seconds; shared-header edits and the large NN translation unit can still cost more.

Evidence: `BuildSingleBoundsFile.log` and `BuildNoChangeNoSarif.log` under `Saved/Diagnostics/LegFeedbackIsolation`. Normal baseline build: `BuildNormalNoSarif.log`,125actions/321.40seconds, three compiler workers with5.66GB available. Editor reopened on `/Game/testNN`; temporary idle FPS10 restored60. No authored assets edited or gameplay tests started.

Installation caveats discovered: changing only the Saved XML was read but left the cached compile commands unchanged in the first attempt. Regenerating the target with the explicit editor-target setting removed SARIF. That configuration change also rebuilt a shared PCH through Live Coding; its shared output then suffered a similar producing-command-history mismatch, causing71 repeated actions (`NoSarifNoChange.log`). One normal build with the saved editor closed established consistent baseline PCH history. Normal incremental Live Coding now passes the one-file/no-change checks. Do not repeat that restart for ordinary implementation edits.

## Verified local findings

The preceding small `.inl` change caused 41 compile actions and a 371.49-second build. The machine has about 16 GiB RAM. UBT saw 2.67 GB available, required 1.5 GB per action, and limited compilation to one process despite eight physical cores. Shared PCHs, adaptive unity, and the local UBA executor are already enabled.

A no-code-change diagnostic on the same editor session still requested 41 compile actions. Used `-LiveCodingLimit=1 -VeryVerbose -WriteOutdatedActions=...`; UBT rejected the 41-action request in 2.28 seconds before compilation, output deletion, or action-history save. No actual compile or editor restart occurred. Evidence: `Saved/Diagnostics/LegFeedbackIsolation/CompileAuditVerbose.log`, `CompileAuditConsole.log`, and the earlier `BuildComparisonSwitch.log`.

The verbose log explicitly marks `.sarif` report outputs as produced by outdated attributes, including unchanged `ProphecyRootFacing.cpp`. Installed UE5.7 source explains the repeated invalidation:

- `Platform/Windows/VCCompileAction.cs:286`: compiler report is a tracked produced item.
- `System/ActionGraph.cs:730`: checking produced items updates their stored producing-command hash.
- `System/HotReload.cs:702`: checks original compile commands, then patches commands for Live Coding and checks again.
- `System/HotReload.cs:931`: object/dependency filenames are rewritten to `.lc.*`; SARIF report paths remain shared by normal and Live Coding actions.
- The shared report's command hash consequently changes during the original-command check and changes back during the Live Coding check. The second check schedules recompilation even with unchanged source.

## Recommended order

1. **Completed:** disable optional SARIF file emission using `WindowsPlatform.bWriteSarif=false` in the editor target. Normal console compiler errors/warnings remain; separate machine-readable SARIF reports are lost. The installed UE5.7 XML category is WindowsPlatform, but the explicit editor target ensures this project change invalidates cached rules and is tracked in source control. One-file/no-change results are recorded above.
2. Free enough memory to allow additional compiler processes. Do not blindly disable the memory gate; with current memory pressure, extra processes can cause paging. No applications were closed and no parallelism limits were changed.
3. Move frequently edited NN implementations from `.inl` includes into independent `.cpp` files behind stable narrow interfaces. The manager currently has about 5,000 nonblank lines plus included implementation files. A separate `.inl` is still compiled as part of its including translation unit.
4. Use runtime tuning and development-only A/B switches for repeated experiments, as done for the feedback comparison, so changing experimental values does not require recompilation. Keep structural C++ edits on Live Coding where supported; do not restart solely for a working patch.

Do not delete Intermediate/DDC as a compile-speed remedy; do not disable PCHs globally or assume raising CPU count overrides the current memory bottleneck. Distributed builds need another machine and setup; they are lower priority than the proven local invalidation.

## Primary web sources consulted

- [Epic UE5.7 build configuration](https://dev.epicgames.com/documentation/en-us/unreal-engine/build-configuration-for-unreal-engine?application_version=5.7): bWriteSarif, MemoryPerActionBytes, shared PCHs, adaptive unity and build executors.
- [Epic UE5.7 Live Coding](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-live-coding-to-recompile-unreal-engine-applications-at-runtime?application_version=5.7): runtime recompilation/patching.
- [Epic Horde/UBA remote compilation](https://dev.epicgames.com/documentation/unreal-engine/horde-unreal-build-accelerator-and-remote-compilation-tutorial-for-unreal-engine): distributed compiler execution.

The SARIF invalidation diagnosis comes from this machine's installed engine source and reproduced verbose log, not an assertion that Epic has publicly acknowledged this particular bug. Post-workaround results above were measured locally.
