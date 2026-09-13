# Live Jolt character adapter: verified first functional slice

Verified checkpoint: 9 September 2026, 09:58 local artifact series. The opt-in character binding, velocity servo, pose output and hit-identity bridge are implemented. The native live fixture passes in air and with an explicitly mirrored floor. Production defaults remain unchanged. “Live” here means a real actor/component tick pipeline and evaluated skeletal sockets; these NullRHI runs do not prove rendered pixels, blood paint, NN inference or crowd performance.

The evidence table below preserves that first checkpoint. The implementation overview has since been updated for shared multi-rig stepping; later actual-NN 100-character and real-RHI mask results are recorded in [current status](JoltIntegrationStatus.md) and [performance evidence](Jolt100AgentPerformance.md). Those newer tests supersede the first slice's single-character coverage limits, without implying a completed gameplay migration.

The user requires useful physical animation, solid bodies/joints, blood staining and speed. Exact Chaos/Jolt trajectories are not an acceptance requirement. Stock hard Jolt angular limits use the original PHAT angle values without retuning; the authored soft settings remain provenance.

## Verified evidence

The [combined main Editor target build](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/UEBuild-20260909-095544.log>) succeeded. The [foundation report](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/Foundation-20260909-095553-725/index.json>) records **33 successful tests, zero failures, zero test warnings/errors and zero not-run tests**. Coverage includes frames/units, shapes and archives, hard joints, actual velocity-listener scheduling, native sleep/wake/caps, pose composition, ray queries, world/rig ownership and teardown. Earlier packaged Development/Shipping proofs cover the compound foundation; this newer character code still needs its own package validation.

The [actual-native-filter manual run](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_manual_native_filters_20260909_0957.json>) completes capture/replay in air and floor cases with no report error. Its independent [Jolt air report](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_manual_native_filters_20260909_0957-jolt-air.json>) and [Jolt floor report](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_manual_native_filters_20260909_0957-jolt-floor.json>) each consume 60 sealed packets for 22 bodies/21 joints and record `completed_and_torn_down=true`. Final input identity and the first Chaos pre/post-servo state are exact. The separate Chaos trajectory-repeatability comparison still exceeds its original thresholds; it is explicitly diagnostic, not a release gate.

The [live character report](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_live_character_20260909_0958.json>) records `live_jolt_validation.success=true` for both cases, with no report error. Each case has 30 warmup frames followed by 60 measured fixed 1/60-second frames, substepping and async physics disabled, and native synthetic 30 Hz authored poses without NN models or Blueprint actors.

| Check | Air, no gravity | Floor, gravity |
|---|---:|---:|
| Validated frames | 60 | 60 |
| Jolt rig bodies / joints | 22 / 21 | 22 / 21 |
| Feedback/socket bones per frame | 88 | 88 |
| Chaos dynamic bodies | 0 | 0 |
| Maximum feedback/socket position difference | 2.726e-13 cm | 3.252e-13 cm |
| Maximum normalized orientation difference | 2.415e-6 degrees | 2.415e-6 degrees |
| Maximum scale difference | 0 | 0 |
| Mean synchronous Jolt step | 0.0809 ms | 0.0813 ms |
| Mean world tick | 0.7704 ms | 0.7547 ms |

Every measured frame validates a real Jolt ray mapped to the original actor, `PhysicalMesh` and bone, and rejects an altered body generation. Completed pose revisions advance from the primed revision 1 through 2–61. The public Physical→Kinematic transition removes all 22 rig bodies and 21 joints, rejects all 22 old handles, and leaves an initialized world with zero bodies in air or only the registered floor. The Chaos count covers native dynamic actor states exposed by registered primitive-component BodyInstances, deduplicated by BodyInstance.

These timings are **one-character NullRHI diagnostics**, not a Chaos speedup, rendered FPS or scalable crowd result. World tick includes target assembly, Jolt stepping and synchronous skeletal evaluation; detailed frame validation runs outside that timed interval. No recurrent NN manager update or model inference runs in this fixture. The historical 100-agent Chaos FullSim/NativeWorld timings use different drives and counts and cannot serve as its speedup denominator.

## Implemented ownership and update path

[`UProphecyJoltCharacterComponent`](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Public/ProphecyJoltCharacterComponent.h>) is a game-module binding. It uses the per-UWorld owner, accepts the current separate manual `PhysicalMesh` with 22 bodies/21 joints and unit component scale, and owns one generation-safe rig within that shared world. Multiple rigs now share one PhysicsSystem and step-client coordinator. The physics plugin remains independent of gameplay classes. The owner must already be initialized; air is valid, and any floor/obstacle registration is explicit. It does not automatically import the UE level.

Activation captures the live Chaos rig and matching bone/body offsets while Chaos state is valid, prepares native geometry, and creates the complete Jolt rig before committing ownership. Native primitive dimensions and connector frames already include UE's effective scale decisions. Shape/COM/inertia/joint scale is not applied twice; visual bone scales are stored separately. Simulation object channels and responses come from actual native shape filters, with raw BodyInstance and per-shape query filters retained as provenance.

After creation, the binding releases the manual Chaos callback, disables PhysicalAnimation driving and Chaos simulation, retains the same mesh/material/UObject identity as a **QueryOnly** receiver, and installs [`UProphecyJoltPoseAnimInstance`](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Public/ProphecyJoltPoseAnimInstance.h>). It primes a completed pose immediately. The Agent wrapper checks the initialized healthy world before mutating mode and restores the previous mode on failed activation. Identity-only rig ownership checks remain usable for cleanup after simulation faults or during teardown, while rejecting replacement generations.

The current shared schedule is:

1. The existing manager/root publisher precedes Agent Tick when a real manager is present.
2. Agent/Blueprint finalizes authored targets. `ReadNNFutureWorldPose` supplies interpolation and rigid-forearm presentation. The existing automatic and explicit manual publishers route to Jolt while bound.
3. One coordinator tick follows all registered publishing actors and advances the world once. PrePhysics remains the default; the explicit DuringPhysics option overlaps independent UE query-scene work. Character components have no empty per-agent tick. Automatic-publication gates and current-frame publication checks remain; explicit stepping is refused while any registered client requests automatic stepping.
4. For two or more eligible native characters, the coordinator captures plain completed-body inputs on the game thread, composes full poses in a joined parallel batch, then publishes in original client order. A callback that changes a later carrier or authored packet invalidates that packet and takes the serial path.
5. Normal `TickAnimation`/synchronous `RefreshBoneTransforms` publish the pose. The one-shot native PostEvaluate hook updates all retained query bodies before buffer flip/finalization callbacks, using current exact geometry/bounds and the public scene acceleration update. Ordinary PhysicalMesh ticking is disabled. Publication guards preserve ownership across callbacks; disabling one rig leaves surviving clients and the shared world intact.

Targets retain the existing global/per-body drive gates and strengths, including missing-map defaults and strengths above one. The controller denominator remains the published `max(epsilon, min(frame delta, maximum substep))` when substepping is enabled; it is distinct from actual integration duration. The owner uses native Jolt caps/waking behavior rather than promising identical Chaos arithmetic. The live report specifically exercises one collision step per 1/60-second frame; multi-step servo behavior is separately covered by native tests.

An automatic-step failure latches `IsSteppingStopped` while retaining Jolt ownership and the error. Later packet publication cannot erase that failure or silently resume simulation. Explicit Disable then Enable is the recovery path. The successful fixture validates normal activation and teardown; it does not exercise every activation-failure or stopped-state recovery branch.

Character removal immediately unregisters the step client and destroys its rig. If removal occurs inside its owned animation-publication callback, the detached cleanup state stays alive until evaluation returns; restoration then completes within that same call and engine frame. The mesh regains its saved settings and native NN locomotion AnimInstance, and evaluates the current kinematic pose. No timer or extra world tick is used. During cleanup, Physical/HalfSim changes and Jolt admission are refused; repeated Kinematic requests are harmless. Direct component cleanup also sets the Agent's cached Kinematic mode before restored animation callbacks run. Destroyed owners, unregistered meshes and changed skeletal assets are not restored.

R5's packaged two-agent smoke and two complete 100-agent runs pass the new restoration checks: native removal happens inside finalization, the exact NN class is restored afterward, fresh head-local shifts of 17/24 cm are consumed in the same engine frame, and the direct cleanup callback observes Kinematic mode. The old SetAnimInstanceClass warning is absent. These lifecycle checks run outside measured samples. Earlier R4 ownership checks did not prove animation restoration; use `Saved/JoltMigration/PackagedR5ComparisonDraft/BaselineR5Development.md` for the corrected evidence. Main-project Editor binaries still require rebuilding before testing this latest source in the main project.

## Completed pose and feedback

The shared [`ProphecyJolt::Pose` composer](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Public/ProphecyJoltPose.h>) reconstructs physical bone world transforms from completed body origins and cached rigid offsets. It walks the full mesh reference skeleton in parent order, preserves authored/reference local transforms for nonphysical descendants, and includes the existing finger-layer hook. It then derives local/component/world transforms with visual scale. The AnimInstance snapshots completed local transforms on the game thread; worker evaluation uses immutable data and the current compact-to-mesh bone mapping.

[`AProphecyAgent::SampleActualComponentPose`](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyAgent.cpp>) routes to the binding while Jolt owns the character. It converts the stored completed **world** pose into the same inherited AgentMesh feedback frame used by the existing manager. A subsequent root move therefore cannot reinterpret old component-space coordinates. The public feedback entry point agrees with all 88 evaluated sockets. Later real-manager runs also validate 180 NN steps and 18,000 physical-feedback samples across 100 characters; see the performance evidence for exact workload and limitations.

The authored `FProphecyNNPoseStore` is not overwritten with Jolt output. `GetSimulationMode`, Physical→Kinematic transition handling, kinematic pose application and the manual finger helper recognize Jolt ownership. The existing capsule/manager remains the locomotion root owner. HalfSim and other drive variants are not made functional merely by these guards.

## Blood bridge and remaining acceptance

`MakeHitResult` converts a current owned Jolt ray handle into the original Agent/PhysicalMesh and the mapped bone. It validates generation and current native state, preserves impact point/normal and ray fraction, sets skeletal `Item` to the source PHAT body index, and leaves `FaceIndex=INDEX_NONE`. A native Jolt subshape ID is never presented as a UE render-triangle index. The payload has no source segment, so its distance remains zero.

The [existing skeletal paint path](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyBloodTexturePaintManager.cpp:667>) can use this receiver, `BoneName` and the completed physical bone pose for its UV fallback. The live test proves native query-to-receiver identity and stale-handle rejection; it does **not** call that paint path or verify render targets, UV placement, material response or moving-skin blood pixels. QueryOnly proxies preserve their configured response channels; the native ray bridge is not proof that every stock UE/Niagara blood trace channel already reaches them.

Later real-D3D12 fixtures have exercised the paint path for character, static mesh and independently promoted instanced receivers, including localized mask pixels and source-collider retirement; see the [blood bridge evidence](JoltBloodBridge.md) and current status. These are texture-mask/identity checks, not full rendered gameplay or Niagara GPU export acceptance. The immediate priority is the user's 100-agent CPU goal, still unmet by the actual-NN pipeline. The next gameplay checkpoint is native sword/prop ownership, followed by the retained controls/modes, world/streaming, cutting, blood/Niagara, rope/boat and combined rendered workload. Production defaults remain opt-in.
