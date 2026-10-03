# Sword fixture draft

`ProphecyJoltSwordFixture.cpp` is a proposed new game-module source file. It is not active, compiled, or executed.

The first operation reuses the existing `ProphecyJolt::StandaloneFixture::CaptureTrainingSword` preflight. Today's unsupported final hull causes `success: false`, `asset_preflight_passed: false`, `stage: asset_preflight`, and the native error. It does not replace, simplify, edit, or save an asset and never counts this as a passing skip.

After a valid Training asset is supplied, the command constructs one native manual agent using the setup from `ProphecyPhysicsBenchmarkManual.cpp`, with the actual mannequin and PHAT, a reference-pose store source, and no NN manager. The transient world goes through actor initialization and BeginPlay; production `EquipSword` loads the actual A_Sword Blueprint and Training mesh. Four explicit shared steps exercise fixed grip, attached/physical transitions, drop velocity and body identity, UE query receiver identity, held-item owner cleanup, and independent dropped-body cleanup. Counts include bodies, PHAT/native constraints, generic grips, owner pair exclusions, and shared clients.

Proposed command after promotion/build: `Prophecy.Jolt.SwordFixture C:/absolute/new-report.json`.

This is a synchronous functionality check. It does not tick the world, run Blueprint cutting/blood behavior, render, infer NN poses, or measure performance. The fixed-grip check uses `FTransform::Equals(..., 0.02)` after one short step; this is a fixture assertion, not a gameplay quality claim. The current public sword API does not expose its joint handle, so grip type is established by production `FinishJoltGrip` selecting Fixed, while runtime checks cover the extra generic joint, 22 pair exclusions, and retained relative frame.

The only forward declaration reuses the existing capture function in the same game module; no production API change is proposed. The pose ID is refused if already occupied, and its data is cleared only after world teardown finishes. A final report cannot establish post-preflight behavior until the asset is updated and this draft is promoted, built, and run.
