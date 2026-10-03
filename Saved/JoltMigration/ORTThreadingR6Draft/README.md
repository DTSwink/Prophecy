# R6 ORT capture and optional Development factor — draft

This draft is relative to the promoted R5 active source and tools. It is not applied, compiled, cooked or run in UE. The only proposed C++ file is ProphecyPhysicsBenchmarkNNJolt.cpp. The runner/validator retain their existing filenames so their normal sibling lookup still works after a later coordinated promotion; do not run this isolated folder as a package runner.

## Native capture

The benchmark reads the already-loaded NNERuntimeORT settings CDO immediately before spawning its manager, then after FinishSpawning initializes the manager's models. The reflected fields are pool sharing, intra/inter thread counts and graph execution mode. Counts must be nonnegative, enum value/name must match UE5.7, and typed fields must remain unchanged across initialization. Missing config cache/module/class/CDO/properties fail explicitly. An absent raw config key remains a valid captured absence because compiled defaults supply the selected fields.

Both snapshots are retained in the benchmark state and later written into actual_nn_scope as `ort_cpu_threading_before_models` and `ort_cpu_threading_after_models`. Each contains settings class/selected Editor-or-Game struct, typed values, raw Engine-config value when present, whether -ini override support is compiled in, and `session_worker_execution_directly_observed=false`. The environment copied counts earlier at ORT module startup; this is selected-settings provenance and does not claim direct session worker observation. No private ORT headers or engine changes are used, and no settings are mutated. All capture work occurs during setup outside measured samples.

## Optional runner factor

`-OrtIntraOpThreads 0` is the default and adds no startup override. The controlled package baseline is expected to retain Game defaults: local pools, intra=1, inter=1, SEQUENTIAL. Values 1 and 2 are accepted only for Development and append exactly one startup argument containing the full tuple `(bUseGlobalThreadPool=False,IntraOpNumThreads=N,InterOpNumThreads=1,ExecutionMode=SEQUENTIAL)`. Shipping rejects nonzero before any process/output directory is created because its Game build disables -ini overrides. The runner records the requested factor/tuple and passes the factor to the validator. No configuration or model file is written.

The validator requires both snapshots, exact settings class/Game target, false pool sharing, selected thread counts matching the factor (0 means baseline 1), inter=1, SEQUENTIAL, correctly typed raw-config presence and truthful capture scope. Nonzero factors additionally require the exact startup tuple in both raw captures. A missing R6 capture intentionally rejects; old R5 comparisons should use their archived matching validator. The independent comparator compatibility draft, if present, is owned by remaining_tick_audit and recorded in its separate evidence/patch.

## Review and bounded verification

- Independent installed-source reflection review found no compile/API blocker: TEnumAsByte reflects as FByteProperty; its Enum is public; GetDefaultObject(false) does not create a CDO; const ContainerPtrToValuePtr and property getters match the helper; module PreDefault startup already creates the settings CDO.
- PowerShell AST parsing passes. Six tests execute only the exact extracted factor guard and argument-construction AST nodes. Default 0 adds nothing on Development/Shipping; 1/2 emit the expected tuple on Development and reject Shipping. The runner itself was not executed and no process was launched.
- `ValidatorFixtures-20260909-212422.json` records 56 whole-validator fixtures passing. These use deliberately augmented in-memory R4 data, fabricated future capture/R5 lifecycle evidence, and—in the positive Shipping case—fabricated configuration flags. They are contract tests, not native benchmark acceptance. Historical and active source/tool/report bytes are unchanged.
- Final source/tool hashes and exact R5 baselines are in Evidence.json and FinalManifest.json. C++ has not been compiled or runtime tested. R5's later successful package runs are separate baseline evidence and do not validate this unpromoted R6 code.
