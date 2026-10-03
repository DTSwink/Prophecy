# Focused ORT CPU threading research

Recommended next measurement: **packaged Development intra-op threads 1 → 2**, with per-session pools, inter-op=1, sequential graph execution, the same executable/models, batch 100 and 30 Hz inference. This is one existing startup runtime factor. No active file/config changes, UE launches or benchmarks were performed for this research. It is a candidate to measure, not a proven speedup or explanation for the whole remaining manager cost.

## What is actually running

The current native fixture explicitly selects NNERuntimeORTCpu, 30 Hz and four-step foot processing (ProphecyPhysicsBenchmarkNNJolt.cpp:165–171). ValidateManager requires CPU execution and all three model instances' batch size 100 (:58–70). FPolicyModel sets [100,152] input for run/walk and [100,281] for upper, invokes synchronous RunSync, and does not resize these instances during the fixture (ProphecyNNLocomotionManager.cpp:67,82–87,563–613,2357). Each instance has its own ORT session.

The walking benchmark validates bRun=false for every lane (NNJolt.cpp:82). Input construction maps that intent to Walk (Manager.cpp:2919,2946). RunModelBatch only invokes a model if an enabled lane needs it (:3005–3029). Thus the **run session is loaded and validated but not inferred on measured walking frames**; walk and upper run sequentially. In a mixed run/walk workload, run and walk would execute sequentially against the same read-only input buffer, then selected walk outputs replace their lanes (:3031–3042).

Upper cannot simply be dispatched alongside lower inference: StepSimulation applies the new lower output before constructing the upper inputs (Manager.cpp:2781–2792), and those upper inputs contain freshly updated pelvis/lower state (:3185–3223). Retaining this dependency preserves current model semantics. The inference statistic includes RunModelBatch's small selection/copy work and RunUpperModelBatch; it is not a direct per-model ORT-only timer.

## Installed UE 5.7 runtime controls

Sources are under `C:/Program Files/Epic Games/UE_5.7/Engine/Plugins/NNE/NNERuntimeORT/Source/NNERuntimeORT/Private/`.

| Control | Packaged Game default | Editor-target default | Installed application point |
|---|---:|---:|---|
| bUseGlobalThreadPool | false | true | Module.cpp:48–58; Env.cpp:38–51 |
| IntraOpNumThreads | 1 | 0 | Utils.cpp:460–468; Env.cpp:41–42 |
| InterOpNumThreads | 1 | 0 | Same; inter-op matters only for parallel graph execution |
| ExecutionMode | SEQUENTIAL | SEQUENTIAL | Model.cpp:40–48,526 |

These are Config Engine developer settings, **not threading CVars** (`NNERuntimeORTSettings.h:18–64`). The compile-time WITH_EDITOR branch selects the settings, so launching UnrealEditor with -game retains Editor defaults. No corresponding overrides were found in project Config, isolated snapshot Config, or installed Engine Config. Editor/package timing differences therefore have a concrete runtime configuration difference worth controlling, but their different binaries/runs do not establish causation.

The plugin loads PreDefault (NNERuntimeORT.uplugin:24) and copies thread counts from its settings CDO during StartupModule (Module.cpp:107). Its environment is then lazily created; new session options read that captured environment configuration (Utils.cpp:452–468). The settings are marked restart-required. A late config/CVar edit is not a valid way to change existing sessions.

The CPU session applies the selected graph execution mode, ORT_ENABLE_ALL optimization and CPU arena (Model.cpp:526–528; Utils.cpp:375–380). Existing `nne.ort.enableprofiling` is sampled when session options are created (Utils.cpp:20–27,473–485). It enables ORT trace files, not faster inference; keep it out of timed acceptance. No plugin CVar exposes intra/inter threads, affinity or spin controls. Bundled headers expose the ORT API's spin/affinity options, but the UE settings wrapper does not forward them. They are not current existing-factor measurements without additional integration work.

ORT documents intra-op count as total participating threads: two means the caller plus one worker. Explicit thread counts do not set the workers' affinity. Parallel graph execution can help branching graphs or add overhead; workers spin by default. Therefore a small 1→2 test is preferable as the first isolated factor to enabling all cores or simultaneously changing graph mode/pool sharing. [Official ORT thread management](https://onnxruntime.ai/docs/performance/tune-performance/threading.html). The installed headers use ORT API 20; this proposal does not rely on newer web-documented spin-duration/backoff options.

## Startup override, Development only

The source-supported additional argument for a fresh packaged Development process is:

```text
-ini:Engine:[/Script/NNERuntimeORT.NNERuntimeORTSettings]:GameThreadingOptions=(bUseGlobalThreadPool=False,IntraOpNumThreads=2,InterOpNumThreads=1,ExecutionMode=SEQUENTIAL)
```

Use the same explicit tuple with IntraOpNumThreads=1 for the baseline. This preserves every other setting and avoids ambiguous inherited defaults. `Core/Private/Misc/ConfigCacheIni.cpp:2234–2330` applies startup ini overrides; FParse::Expression protects commas inside balanced parentheses (`Core/Private/Misc/Parse.cpp:1395–1502`). `-ExecCmds="GetIni Engine:/Script/NNERuntimeORT.NNERuntimeORTSettings GameThreadingOptions"` can print the config-cache value for an initial Development probe (`Engine/Private/UnrealEngine.cpp:10391`). That log alone does not inspect native ORT worker execution.

**Do not prescribe -ini for the current Shipping Game target.** `Core/Public/Misc/ConfigCacheIni.h:53` defines ALLOW_INI_OVERRIDE_FROM_COMMANDLINE as `(UE_SERVER || !UE_BUILD_SHIPPING)` and the parser is compiled under that condition. `Source/GameAnimationSample3.Target.cs` is TargetType.Game, not Server, and adds no override. A later Shipping experiment needs an explicit isolated packaged Engine-config revision with the chosen tuple, or a separately designed startup control; no Shipping command-line override effect is claimed.

## Narrow R6 provenance option and acceptance

`CaptureOrtCpuThreadingSettings.cpp` is a proposed, uncompiled benchmark helper. It reflects the already-loaded native settings class/CDO and its selected Editor/Game struct, reads typed pool/thread/execution fields and the raw GEngineIni value, and reports whether command-line ini overrides are compiled in. It uses public reflection/config APIs and does not include private ORT headers or mutate the engine/settings. Capture it immediately before manager/model creation and again after initialization, and require unchanged typed fields matching the experiment. Given the plugin's earlier startup copy, this is selected-configuration provenance, not a direct getter for existing session thread counts. No project code currently writes these settings after startup. A one-off untimed ORT profile can establish actual extra-worker participation if necessary.

Run the factor only after the R5 lifecycle smoke passes. Preserve all current native workload/NN/body/bone/query/lifecycle gates and compare both total world tick and the NN/interstitial split. The possible gain is in walk/upper inference, not the separate ~0.924 ms resample or ~0.577 ms publication intervals identified by the phase audit. Keep models, tensors, cadence, lower→upper dependency, batch 100, physical-feedback mode and processor/Jolt worker policy fixed. Existing startup upper parity runs automatically (Manager.cpp:1765,2379–2438), but checks only the first output lane of one repeated-input vector; do not call it an exhaustive bitwise tensor oracle. More threads preserve the configured model calculation, but floating-point output equivalence should remain subject to the existing numerical quality checks rather than a bitwise guarantee.
