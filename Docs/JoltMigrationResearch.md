# Prophecy Jolt Migration Research

Jolt provides the core rigid-body, articulation, motor and query capabilities needed for a credible Prophecy migration. The strongest supported integration route is a project-owned adapter around upstream Jolt, preserving Unreal rendering and Prophecy's established gameplay interfaces. Existing Unreal plugins provide useful examples, but neither inspected integration supplies the complete character bridge this project needs. This is an engineering judgment supported by the implementation evidence below; no Jolt build, performance improvement or gameplay equivalence has yet been demonstrated for Prophecy.

## Reading guide

**Post-research implementation evidence, 9 September 2026:** [JoltIntegrationStatus.md](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Docs/JoltIntegrationStatus.md>) records successful foundation tests and Development/Shipping packaged archive restoration. The [effective rig audit](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Docs/JoltEffectiveRigAudit.md>) distinguishes manual SetV/SetW control from the existing force/torque `FullSim` benchmark. The user subsequently approved hard angular limits with unchanged PHAT angles and no retuning; custom soft constraints are deferred. Historical research claims below describe the research cutoff, not current implementation completion.

- [Decision findings](#decision-findings) summarizes the facts that change the migration approach.
- [Project baseline and contracts](#project-baseline-and-contracts) records the existing behavior and distinguishes incompatible benchmark configurations.
- [Unreal integration evidence](#unreal-integration-evidence) examines plugins, engine APIs, lifecycle, build and cooking.
- [Jolt core capabilities](#jolt-core-capabilities) covers controllers, geometry, units, constraints, timing, contacts, threading and capacity.
- [Feature compatibility inventory](#feature-compatibility-inventory) covers blood, Niagara, swords, ropes, boats, world collision and root queries.
- [Evidence limits and completion criteria](#evidence-limits-and-completion-criteria) distinguishes a successful prototype from a complete migration.
- [Sources](#sources) contains numbered references to original publications, pinned source files and installed UE source.

## Decision findings

| Finding | Evidence | Consequence |
|---|---|---|
| Jolt 5.6.0 is the verified current release at the research cutoff | Official release dated 11 July 2026; SHA `e77f175595e64cb44218cc9d9d56fc365ad0e36a` | Use version-matched APIs and immutable dependency records. [^1] |
| UnrealJolt's skeletal component creates one body and retains the first extracted shape; it does not build the PHAT articulation or publish bone poses | Pinned component implementation, not its feature name | A complete 22-body character adapter is necessary under either reuse or custom-integration routes. [^52] |
| Prophecy's active full-Sim callback directly adjusts linear/angular velocity | `ProphecyAgent.cpp:111–150` | Preserve the actual servo first; an angular-motor ragdoll would be a different controller. |
| UE's built-in physical animation and several nonvirtual physics nodes still address Chaos | Installed UE 5.7.4 source | Preserve project nodes through backend dispatch; explicitly migrate raw engine call sites. [^75] [^77] [^79] |
| Ordinary UE traces and Jolt queries are separate | UE/Niagara source and separate Jolt world implementation | Queries, hit identity, filtering and proxy synchronization are first-class work. |
| Jolt contact-added callbacks precede solving; a generic solved `NormalImpulse` is not exposed by the inspected public API | Contact listener, PhysicsSystem and estimator contracts | Capture pre-impact velocities directly; resolve any actual solved-impulse dependency instead of substituting an unlabelled estimate. [^24] [^36] |
| LinearCast CCD does not fully cover rapid rotation | Jolt's motion-quality contract | The sword's swept angular motion requires a dedicated acceptance case. [^12] |
| Existing environment JSON includes visualization-oriented geometry and omits physics/UV metadata | Project collision exporter, configuration and journals | Reuse extraction knowledge, not the cache as an indiscriminate solid Jolt world. |
| The latest 100-agent native comparison has floor contacts but no self/crowd contacts and no NN/rendering | Retained benchmark methodology | It is a matched diagnostic baseline, not proof of full-game capacity. |
| Public APIs support the essentials but do not establish field-for-field Chaos compatibility | Constraint and integration source | Soft angular limits, solved impulses, projection/mass-conditioning semantics and legacy character interaction remain explicit compatibility gates. |

## Project baseline and contracts

### Evidence snapshot

The research cutoff is **9 September 2026**. The project targets **Launcher UE 5.7**, and its installed source is **5.7.4, CL 51494982**. UE 5.7.4 is the baseline assumption for the migration; an upgrade has not been selected. Public Epic pages that default to 5.8 are identified in their source entries, with relevant behavior checked against installed 5.7.4 code.

The workspace is `C:/Users/singerie/Documents/Unreal Projects/Prophecy`, project `GameAnimationSample3.uproject`, branch `codex/standalone-sim`, HEAD `ff47695867a07b609bc885353d2e84c9ad6c18b8`. The inspected working tree has pre-existing changes, including key physics sources, journals and assets; HEAD alone does not reproduce that state. The authoritative production map is `/Game/mybasic`; the focused agent map is `/Game/testNN`.

Claims labelled **verified** are supported by the cited source or retained project evidence. **Inference**, **judgment** and **recommendation** identify analysis. **Unresolved** means that source inspection cannot establish the runtime result. An exposed class name, enabled plugin, old graph dump or historical benchmark is not proof of current asset behavior.

The attached prior discussion supplies migration context. Current code supersedes journal shorthand where the two differ; versioned implementation supersedes plugin feature summaries. Existing unfinished blood/material work and experimental controller settings are separate from migration regressions.

### Behavior that remains authoritative

| Contract | Current behavior to retain |
|---|---|
| NN timing and policies | 30 Hz recurrent lower/upper/Slash computation; existing accepted checkpoints, codecs, seeds, four-step foot-roll, and eight future roots. Backend selection does not authorize retraining or reinterpreting inputs. |
| Pose identities | 22 physical bodies are distinct from the 25-bone NN pose and the fitted 88-bone rendered skeleton. Bone/body/shape/COM/component identities need explicit maps. |
| Presentation | Above 30 FPS interpolate completed policy poses; at 30 FPS use exact policy frames; below 30 FPS advance required policy steps and present the newest completed pose. Physics scheduling remains a separate contract to measure. |
| Root authority | The shared mover owns root integration; the swept capsule low point and measured displacement are authoritative. Jolt must not replace this with an unrelated character controller or pelvis teleport. |
| Physical feedback | Named-bone linear/angular deadbands preserve zero-tolerance actual feedback and large-tolerance kinematic feedback. Calves and forearms remain IK results. |
| Attacks | Existing full/half ownership, root catch-up/rebase, target radius, attack latches and tails remain. Learned Hit timing is not a physical damage/contact event. Slash's current self-feedback must not silently become a new physical-feedback feature. |
| Fists and helpers | Existing local finger deformation, rest-pose basis transfer, closing/return controls, helper locals and parent-scale handling survive physical pose publication. |
| Mode changes | Kinematic=0, Sim/Physical=1 and HalfSim=2 preserve visible pose, retained dynamics and velocities, with the accepted transition blend. These enum values describe behavior, not solver identity. |
| Sword | Preserve calibrated grip, simulated/non-simulated holds, momentum on drop, owner-only suppression and the existing cutting behavior. |
| Standalone bridge | The standalone sim sends intent; Unreal returns resolved physical root state. Its navigation/replay/gameplay rules are not replaced by the physics backend. |
| Working environment | Preserve unrelated dirty assets/settings and accepted source. Live Coding is the normal Unreal iteration route; an actual required editor restart needs explicit authorization. |

### Active controller differs from journal shorthand

`Source/GameAnimationSample3/Private/ProphecyAgent.cpp:92-151` implements FManualFollowerSubstepCallback with direct SetV/SetW. At line114, denominator is Targets.MaximumSubstepSeconds. At lines128-131 it computes desired linear velocity from target minus current body position divided by that denominator, then blends current velocity toward it. Lines136-149 use shortest quaternion delta similarly for angular velocity. These are velocity-servo operations, not literally AddForce/AddTorque, despite journal wording. The separate HalfSim component has force/torque implementations: `ProphecyHalfSimDriveComponent.cpp:165-197`.

Targets are current interpolated/presented pose, not blindly the next NN endpoint. `ProphecyAgent.cpp:320-328` preserves PhysicsAsset bone-to-body offset using BodyFromBone and multiplies by the interpolated target. This transform conversion is necessary independently of whether a future backend exposes body origin or center-of-mass coordinates.

UE5.7.4 local source `Engine/Source/Runtime/Experimental/Chaos/Private/Chaos/PBDRigidsEvolutionGBF.cpp:571-586` invokes PreIntegrateCallback immediately before Integrate. Collision broad phase begins later in the same method. This supports investigating a pre-step Jolt servo; it does not establish identical constraint/contact outcomes.

### Pose, feedback and mode boundaries

- `ProphecyNNLocomotionManager.cpp:2597-2638`: StepSimulation resamples physical agents, builds/runs lower inference, builds/runs upper inference, applies animation layers, advances Slash. Preserve that ownership and 30Hz cadence.
- `ProphecyNNLocomotionManager.cpp:2640-2678`: resampling selection examines simulation mode plus a manual IsAnySimulatingPhysics path. Actual pose reads go through SampleActualComponentPose, making that an existing boundary for Jolt readback. Do not imply the IsAnySimulatingPhysics condition is the sole gate: non-Kinematic modes enter independently.
- `ProphecyAgent.cpp:2971-2999`: SampleActualComponentPose reads the skeletal component's component-space pose; it converts into the feedback reference component frame if a separate pose reference is used. It does not currently query raw physics bodies directly. A Jolt pose publication must be completed before this consumer reads it, or the implementation must consume an explicitly completed simulation snapshot through the same contract.
- `ProphecyNNLocomotionManager.cpp:2709+`: tolerance filtering is in meters/rotation codec and should remain independent of backend. LocalUnrealToTraining/MirrorYBasis are the existing model conversion; introducing a Jolt basis conversion must not apply this training conversion twice.
- `ProphecyModeTransitions.cpp:110+`: switch scope waits for outstanding animation evaluation, captures all visible bone/world/local transforms and body velocities, changes mode, republishes visible pose, clears deferred Chaos kinematic updates, restores state, rebases physics root, refreshes sword constraint. Port the invariants, not Chaos-specific calls.
- `ProphecyModeTransitions.cpp:54-94`: finalized pose correction handles animated parent scale and preserves nonphysical descendant locals. A new Jolt pose path must preserve rendered results without blindly running this Chaos repair a second time.
- All three simulation enum values are stable: Kinematic=0, Physical/Sim=1, HalfSim=2. They describe behavior, not the future solver choice. Backend selection is a separate concern.
- A different backend must not train/change NN policies, seed or timing, attack latches, root catch-up, fist deformation, authored helper bones, animation layer recurrence, or the external standalone intent bridge.

### Root and unit-sensitive APIs

`ProphecyAgent.cpp:901-924` obtains root capsule mass and yaw inertia from FBodyInstance; AddRootImpulse divides the input XY momentum and Z angular momentum and applies the existing mover. This is not a ragdoll-pelvis impulse and cannot be replaced by Jolt AddImpulse on a limb. Root velocity change remains cm/s and rad/s.

`ProphecyAgent.cpp:951-983` mass-weighted error is a raw vector sum over unique active bodies against current presented targets. Linear output kg*cm; angular output kg*radians. Opposing vectors cancel. It is neither RMS nor a mean and is not filtered by NN feedback deadbands.

### Effective settings need a manifest

`ProphecyAgentHalfSimulation.cpp:129-145` explicitly enables gravity, QueryAndPhysics, PhysicsBody object type and selected blocking responses in EnterHalfSimulation. This is more specific than the journal's focused-experiment note about disabled skeletal ground contacts. Record effective settings separately by mode/fixture and current Blueprint defaults before implementation; do not silently normalize them.

The all-functionality contract includes eight HalfSim methods, both PhysicalDriveMode routes, per-body include/simulate/gravity/wake/clear-force/readback, hit events, MACD controls, solver options, runtime PhysicsAsset replacement, body/all/below strengths, and manually invoked world magnetization. A capability ledger must distinguish literal engine settings from behavior that can be mapped to Jolt.

### Benchmarks must not be pooled

The latest native-agent comparison in `Docs/HalfSimPhysicsMethods.md` uses 100 agents with 22 dynamic, awake bodies each and 2,100 anatomical constraints. It supplies synthetic moving component-space pose endpoints, gravity, a floor and a head impulse, with 60 warm-up frames and 180 measured frames in one fixed-60-Hz pass. NN inference, rendering, Blueprint logic, self contacts and crowd contacts are excluded.

| Actual agent mode | Mean world tick | Final position RMS | Extra native target constraints |
|---|---:|---:|---:|
| Full Sim | 51.70 ms | 0.0146 cm | 0 |
| Half Sim, NativeWorld | 51.28 ms | 0.0366 cm | 2,200 |

These world-tick figures include native agent and pose work; they are not solver-only timings. The small difference does not establish a ranking from one short pass.

The earlier sterile controller scene measured NativeWorld at 45.09 ms; joint motors plus pelvis at 28.12 ms but with 14.38 cm / 30.04-degree RMS error; PD at 34.16 ms / 0.46 cm; and WorldOneStep at 35.35 ms / 0.02 cm. WorldOneStep is not the complete production Sim path. The 12.21 ms kinematic-with-colliders baseline came from a separate run and cannot be subtracted from 51.70 ms as exact removable overhead.

`Docs/AgentSimulationCostAudit.md` covers an older 30-Hz pelvis-plus-joint-torque configuration with NN inference. Its 0/50/100 Physical-agent total medians were 5.021 / 14.552 / 29.894 ms, with solver medians of 0.238 / 4.983 / 12.663 ms. These remain historical structural evidence, not the denominator for a new 60-Hz servo comparison.

The journal's rejected per-manager Chaos callback serialized writes and was slower than per-agent callbacks. This is evidence to profile the critical path, not proof Jolt must copy one-callback-per-agent architecture.


### Current contact configuration and retained diagnostics

The current native `ApplyCollisionMode` implementation at `ProphecyAgent.cpp:2524–2557` gives Physical mode a WorldStatic-blocking capsule and a QueryAndPhysics skeletal mesh whose responses are all Ignore for drive validation. Kinematic uses a broadly blocking capsule except Visibility/Camera and a NoCollision skeletal mesh. HalfSim independently enables gravity and selected blocking channels. These are separate from the journal's intended full production contact matrix; the current Blueprint/runtime overrides require a fresh manifest. Neither profile should be silently substituted for the other.

`ProphecyNativePhysicalAgent.h:18–46` retains seven experimental nodes, including `GetNativePhysicalAnimation` returning `UPhysicalAnimationComponent*`. A Jolt object cannot satisfy that engine-specific type. Preserve used behavior through project-owned controls and explicitly migrate consumers of the raw engine object; a diagnostic accessor is not made portable by changing an enum.

Primary project references: [project journal](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/ProjectJournal.md>), [standalone journal](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/StandaloneSim/DEV_JOURNAL.md>), [standalone Unreal contract](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/StandaloneSim/UNREAL_MIGRATION.md>), [current agent implementation](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyAgent.cpp:92>), [mode transitions](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyModeTransitions.cpp:110>), [NN manager](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp:2597>), [latest benchmark methods](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Docs/HalfSimPhysicsMethods.md>), [historical simulation cost audit](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Docs/AgentSimulationCostAudit.md>).

## Unreal integration evidence

### Versions, source provenance, and licenses

| Artifact | Evidence at cutoff | Meaning |
|---|---|---|
| Installed baseline engine | `UE_5.7/Engine/Build/Build.version`: 5.7.4, changelist 51494982, compatible changelist 47537391, branch `++UE5+Release-5.7`; LauncherInstalled.dat agrees | Use exact 5.7.4 source contracts until the engine choice changes. [^74] |
| Yadhu-S/UnrealJolt | `master` at `50e64573548ea829943604138735eee091ea0784`, committed 23 August 2026; descriptor `0.1.0`, beta true | Pin the SHA, not moving master. README says 5.8.1 and possible older-version compatibility. [^49][^50][^51] |
| UnrealJolt Jolt submodule | Gitlink `e77f175595e64cb44218cc9d9d56fc365ad0e36a`; `.gitmodules` uses `git@github.com:jrouwe/JoltPhysics.git` | Fresh recursive clones require working SSH credentials unless the submodule remote is changed to HTTPS. This exact submodule revision is independent of the core Jolt version ultimately selected. [^49][^58] |
| UnrealJolt license | MIT; copyright 2025 Yadhu-S | Preserve attribution/license for copied substantial portions. Underlying Jolt has its own MIT notice; do not erase the integration author's provenance. Build helper also attributes UE4CMake. [^59][^55] |
| BastienVdW/JoltPhysics | `main` at `74ad1d7f911796e0ec8f197be0622eb77470fdd1`, committed 8 September 2026 | Alternative source/reference, not evidence of complete Unreal replacement. [^67] |
| Bastien license metadata | README says plugin uses the same MIT license as Jolt; repository root has no separate LICENSE and GitHub license metadata returns null | Preserve upstream Jolt notice and record README license declaration; clarify plugin-specific provenance before substantial redistribution if choosing this integration. Do not call it unlicensed merely because GitHub's detector returns null. [^68][^67] |

The UnrealJolt author states directly that it does not replace Chaos, that Unreal integration is intentionally limited, and that its original own-project workload involved roughly twenty dynamic bodies. These statements are useful scope context, not a performance claim about the current version or Jolt itself. The July 2026 discussion explicitly warns that Unreal's Chaos simulation settings do not automatically control the Jolt bodies. [^60][^61]

### UnrealJolt source coverage

#### Skeletal bodies and Physics Assets

`UJoltSkeletalMeshComponent::AddOwnPhysicsAsset` disables `IsSimulatingPhysics()` through `SetSimulatePhysics(false)`, allocates a single ID, calls `ExtractJoltShape`, and creates one body at `GetOwner()->GetActorTransform()`. `ExtractJoltShape` iterates `PhysicsAsset->SkeletalBodySetups`; its callback assigns the shape only when no previous shape was assigned. The returned callback transform is deliberately unnamed/ignored. There is no use of the body's bone name or current/ref skeletal bone transform in this path. [^52]

Consequences for a 22-body asset:

- The component does not produce 22 Jolt bodies or preserve the articulated joint graph.
- A compound produced from shapes inside one `USkeletalBodySetup` is possible, but this is not a compound of all the asset's articulated bodies.
- For a single primitive body setup, geometry extraction returns primitive-local placement through its callback transform. The skeletal callback discards it, so even the retained geometry may need its missing offset reconstructed rather than relying on `VisualOffset` to solve a full asset.
- No powered-ragdoll motor targets, per-body mass overrides, asset collision-disable table, constraint profiles, constraint reference frames, drive strengths, simulation subsets, or bone-pose readback are implemented by this component.
- `JoltSetVisualTransform` only applies a local visual transform and calls `SetWorldTransform`; subsystem interpolation calls `SetActorLocationAndRotation`. Neither writes the skeletal bone arrays. [^52][^53]

The reusable part is low-level primitive conversion: `ExtractPhysicsGeometry` handles `BoxElems`, `SphereElems`, `SphylElems`, and `ConvexElems`, combining multiple primitives within one body setup. It does not handle tapered capsules, level sets, or arbitrary UE constraint types. Spheres assume uniform scale and use X; capsules use X for radius and Z for cylinder length. Each used Physics Asset shape must therefore be audited, and unsupported geometry should cause an explicit validation failure rather than silently disappear. [^53]

#### Rigid meshes, world collision, and terrain

The actor path enumerates `UStaticMeshComponent`s and creates an actor-relative compound. The newer `UJoltPhysicsComponent` exposes useful authoring knobs: mass, friction, restitution, damping, gravity, velocity limits, sleep, layers, DOFs, and iteration overrides. This is meaningful rigid-prop groundwork. The tag-only fallback retains fixed friction/restitution and a 100 kg dynamic mass in its initialization path. [^53][^62]

Complex mesh extraction reads the first Chaos cooked `TriMeshGeometries` entry, copies particles and triangle indices, swaps triangle winding, and assigns every triangle material index zero with the body setup's single physical material. It has a source TODO for mesh-shape caching. This is evidence that existing UE collision cooking can provide geometry, but not evidence of preserved triangle-to-render-mesh indices, material slots, or UV mapping. Direct blood mapping would need those identities retained separately or a UE query-only paint trace. It also means the plugin still depends on Chaos modules for collision geometry, even when Jolt owns simulation. [^53]

Landscape preparation is driven from `OnWorldBeginPlay`: find one `ALandscape`, build/cook data under `WITH_EDITOR`, then load a `UJoltDataAsset` by generated world name. The README tells the integrator to include generated `/Game/JoltData` when packaging. `FindSingleLandscape` returns the first landscape actor, and no world-partition/level-added/level-removed hook is present in the examined subsystem. Runtime spawned tagged actors do not automatically enter the initial `TActorIterator` pass. A component can initialize in `BeginPlay`, but full streaming and terrain cell ownership are not demonstrated. [^50][^53][^62]

#### Queries and gameplay contact data

Ray callbacks return location, normal, hit flag, body ID, and (C++ path) physical material. Blueprint's dynamic ray delegate exposes only four fields and omits the physical material. They are custom Jolt callbacks, not `FHitResult`, `OnComponentHit`, or Unreal collision-channel-compatible nodes. A Prophecy bridge must deliberately fill its required mesh/component, bone, subshape/face identity, surface, impact point/normal, velocity, and simulation timestamp data. [^56]

The contact listener uses an MPSC queue to transfer contact data. This is a useful pattern: physics callbacks enqueue compact native data and gameplay consumes after stepping. Its added-contact impulse is `EstimateCollisionResponse`, not the solved impulse from a completed solver iteration. Persisted contacts are emitted only above a hard-coded tangent-speed threshold for scrape FX, with zero impulse; removed contacts are a TODO. This does not satisfy general overlap begin/end lifecycle or a full contact-state feed without extension. [^57]

Concrete query defects in the pinned implementation:

| Function/path | Static source finding | Port impact |
|---|---|---|
| `RayCastShapeNarrowPhase`, lines 1289–1325 | Accepts `offset`, initializes `RShapeCast` direction to `(0,0,0)` and never uses the offset; object filter selects only default dynamic layer | Not a usable general capsule mover sweep as written; can miss ground/static-world semantics. [^53] |
| `CastShape`, lines 1328–1364 | Same zero displacement despite offset parameter; debug path dereferences sphere cast even though `ProcessShapeElement` accepts more shape classes | Sweep behavior and non-sphere debug path need correction/validation. [^53] |
| Ray normal, line 1385 | `ToUESize(collector.mContactNormal)` applies ×100 | Unit normals become length 100; wrong for callers expecting normalized normals. [^53][^54] |
| Shape-hit normal, line 1322 | Applies dimensional scaling to penetration axis and does not normalize it | Consumers cannot treat it as a unit surface normal. [^53][^54] |
| Ray collector, Helpers lines 210–211 | Creates body lock through `GetBodyLockInterfaceNoLock()` with comment assuming all bodies locked | Safe only under an explicit synchronization contract; not sufficient if port introduces overlapped asynchronous simulation. [^54] |
| Miss cases | Some callback fields read collector hit storage regardless of `HadHit` | Bridge should explicitly zero/mark invalid every miss record and validate handles before use. [^53][^54] |

#### Units and basis conversion

The plugin uses SI lengths internally: UE cm multiplied by 0.01, with X/Z/Y coordinate permutation; quaternion conversion negates corresponding vector components. Its length and position routines differ between float `Vec3` and double `RVec3`. `Helpers.h` contains explicit degrees/radians scalar helper functions. This is a sound reason to preserve dimensional distinctions in the future bridge, but the current public API does not consistently use them. [^54]

`JoltSetLinearAndAngularVelocity` applies `ToJoltVec3` to both linear and angular velocities (lines 1798–1805), scaling angular rate by 0.01. `JoltGetPhysicsState` applies `ToUESize` to angular velocity (lines 1808–1821), multiplying radians/second by 100. The source's own angular-rate contract says UE-facing APIs use degrees/second, so this is an internal inconsistency, not a matter of solver preference. `JoltAddTorque` also uses the generic linear scaling helper (lines 2070–2077). [^53][^54]

For Prophecy, distinguish position/linear velocity/acceleration, direction/unit normal, radians vs degrees, force/impulse, torque/angular impulse, inertia, and center-of-mass transforms. If choosing the X/Z/Y reflection used by UnrealJolt, axial quantities such as angular velocity and torque require the determinant/sign treatment consistent with quaternion conversion. Do not use one generic vector helper for all quantities. Validate a positive rotation, positive off-center impulse, and handedness using known expected motion on each axis. This is an engineering inference from dimensional analysis and the observed inconsistency; do not use plugin wrapper output as the numerical oracle.

### World lifetime, scheduling, and simulation ownership

`UJoltSubsystem` derives from `UTickableWorldSubsystem` without overriding world support. UE 5.7.4 `UWorldSubsystem::DoesSupportWorldType` defaults to Game, Editor, and PIE. The plugin allocates a `PhysicsSystem` during subsystem `Initialize`, replaces the process-wide `JPH::Factory::sInstance`, and calls `RegisterTypes` per subsystem. The worker is created only in `OnWorldBeginPlay`; its destructor destroys the PhysicsSystem, temp allocator, job system, factory, and global types. [^53][^56][^63][^80]

Static risks to resolve before reusing this lifetime code:

- An editor world plus PIE/multiple PIE worlds can have distinct physics systems but a single shared factory/type registry. Unconditional per-world factory overwrite and per-worker global deletion do not establish correct process ownership.
- Editor worlds that never begin play initialize a PhysicsSystem but never create its owning worker; the corresponding deinitializer only deletes the worker, not the PhysicsSystem directly.
- `UJoltSkeletalMeshComponent::OnComponentDestroyed` deletes its filters but does not remove its rigid body or interpolation entry.
- The newer `UJoltPhysicsComponent::EndPlay` removes/destroys its body. The removal function drops `BodyIDBodyMap` but does not prune `JoltBodyActors`; `RecordFrames` dereferences every entry's ID before actor weak-pointer validity is checked in the later interpolation pass. This can leave a destroyed-body ID in frame recording.
- Raw pointers to externally owned `BodyID`s are stored in several maps/arrays; body identity needs generation safety and explicit ownership rather than retaining pointers into components after destruction.
- Shape arrays use raw `const Shape*` entries and teardown assigns null pointers; this alone is not Jolt reference counting. Lifetime of caches/materials and any externally retained shape requires RAII ownership. [^52][^53][^62][^63]

These findings do not mean Jolt cannot support multiworld or streaming. They mean the plugin's present ownership model should not become Prophecy's lifetime model unchanged. A process/module-owned Jolt initialization and per-world `PhysicsSystem` with quiesced jobs and ordered per-actor teardown are the relevant integration contracts to validate.

Scheduling is a fixed-step accumulator in subsystem `Tick`, calling `PhysicsSystem::Update` synchronously via `FJoltWorker`. Jolt worker jobs may run on its internal thread pool, but the UE tick waits for each update. The accumulator has an unbounded `while` catch-up loop. Pre/post delegates execute around every fixed step; interpolation follows all catch-up steps and updates actors once. This is not proof of integration into UE's task graph, prephysics/postphysics groups, or animation task dependencies. A future scheduler must explicitly relate NN targets, physics substeps, skeletal publication, blood hit processing, camera movement, pause/time dilation, and hitch policy. [^53][^63]

The README's incomplete multicore warning is specifically about using Unreal's pool properly. Source does instantiate `JPH::JobSystemThreadPool` when multithreading is enabled; it is incorrect to summarize this as “Jolt plugin is single-threaded.” Its worker source itself labels the pool as an example implementation to replace with UE tasks. Initial performance work can use a deliberately budgeted Jolt pool while measuring oversubscription against NN/animation/render worker demand; a bespoke job adapter is not automatically needed before a first measurement. [^50][^63]

### Build and packaging findings

#### Cooked Physics Asset access and reproducible collision data

Launcher UE 5.7.4 provides the needed runtime-visible asset structures without engine patches: `UPhysicsAsset::SkeletalBodySetups` and `ConstraintSetup` are outside `WITH_EDITORONLY_DATA`; the header explicitly says body positions come from the mesh, not the asset. `CollisionDisableTable` is serialized by `UPhysicsAsset::Serialize` at PhysicsAsset.cpp:147. `UBodySetup::AggGeom`, `DefaultInstance`, `PhysMaterial`, `UVInfo`, `FaceRemap`, and `TriMeshGeometries` are runtime fields. `FKConvexElem::VertexData`, `IndexData`, and transform are ordinary UPROPERTY data, not editor-only fields. Thus a primitive/convex PHAT converter can read asset data and create Jolt shapes without instantiating Chaos simulation or rebuilding the engine. This is source-supported access, not yet a validation of this specific cooked production asset. [^83]

Keep the distinction between creating a Jolt shape from runtime geometry and relying on editor-only mesh source data. Complex/static collision can use cooked Chaos triangle geometry already loaded by `CreatePhysicsMeshes`, while visual render-mesh source/UV data may have separate cook/CPU-access constraints. `BodySetup::CreatePhysicsMeshesAsync` explicitly forbids use until completion and does not create/update a `BodyInstance` automatically. Do not invoke editor-only DDC/source-mesh routes from Shipping and assume they work. A safe bridge should validate missing/empty geometry with asset identifiers and retain a cooked collision representation for the required targets. [^83]

Jolt `Shape.h` explicitly says cooked shape binary state is not backward compatible across library versions. `SaveBinaryState` also omits external child-shape/material references unless the documented follow-up serialization/restoration or `SaveWithChildren` family is used. UnrealJolt's `JoltDataAsset.cpp` calls `SaveBinaryState` and `SaveMaterialState`, but not `SaveSubShapeState`; its current format should not be assumed suitable for arbitrary compound ragdolls. The terrain path may only use shapes not requiring those external children, but extending its archive requires deliberate coverage. [^66][^65]

A project collision cache should be tagged with converter schema version, Jolt source SHA/version, relevant ABI/build settings, platform, source asset identity/content hash, scale policy, materials, collision layers, and shape hierarchy. Stale/mismatched data must be recooked or rejected before physics starts. This is an engineering recommendation derived from Jolt's compatibility contract. Shipping must be tested from a fresh cook without previously playing the level in Editor.

Dependency source fetching/building should be an explicit reproducible step with pinned source and hash, not network access hidden in `.Build.cs`. UnrealJolt currently invokes CMake from rules evaluation (it does not itself fetch the submodule there); a lean project plugin can keep `.Build.cs` declarative and consume a prepared library, or compile pinned vendored source in one Jolt module as the alternative plugin demonstrates. Either choice must retain the complete license notices and build configuration record. [^72][^55][^69]

UnrealJolt links a CMake-built third-party library using `ModuleType.External`. The build script configures double precision, cross-platform determinism, 32-bit object layers, object stream, interprocedural optimization, and disables AVX/AVX2/F16C. Win64 selects Visual Studio 2022 and dynamic MSVC CRT. CMake is called while UBT evaluates the module rules. Development maps to Jolt Release; Shipping/Test map to Distribution. [^55]

Specific build risks:

- `-S`, `-B`, and `--build` paths are concatenated without quoting. This project's full plugin path contains a space in `Unreal Projects`, so copying this script would require path-safe process arguments or a separate deterministic dependency build step. Source lines 152–173 establish the bug; it was not executed.
- Configuration checks `Debug` twice rather than including `DebugGame`; the latter falls into Distribution. This must be chosen consciously and aligned with actual UE runtime/ABI, not accidentally inherited.
- The script relies on the selected VS generator's default toolset rather than explicitly pinning the exact UBT-selected compiler/toolset.
- CMake configure/build failure prints diagnostics and returns rather than failing the module constructor explicitly; stale libraries can obscure the true cause.
- Win64 propagates static Jolt library linkage into consuming modules. Jolt has process-global state; isolate actual Jolt calls/data ownership within one implementation module or deliberately use an exported shared library so UE module duplication and Live Coding patches cannot create divergent globals.
- Linux is explicitly built shared to avoid duplicate global state, with runtime dependencies staged. The Mac configuration requests shared output but later links `libJolt.a`; it is not an established supported target from this audit.
- The `.gitmodules` SSH URL and CMake executable-on-PATH assumption must be accounted for on a clean machine.
- Engine-version compatibility, DebugGame/Development/Shipping, cooked terrain presence, and a package opened without prior PIE are all unverified until future builds. [^55][^58]

Epic's third-party integration documentation supports keeping the dependency under a plugin directory, declaring an external module, publishing matching definitions/includes, and linking the proper library. If a DLL is chosen, `RuntimeDependencies` is part of packaging; relying only on an editor search path is insufficient. The official documentation also explains global-symbol duplication hazards on Linux and RTTI mismatch limitations. None of these patterns requires editing the engine. [^72]

Live Coding is useful for normal iteration, including project plugin modules, but it does not remove the requirement to prove a clean package with the selected dependency. Epic's documentation notes that constructor defaults do not update existing instances and reinstancing requires pointer/cache invalidation through reload delegates. For Jolt this makes live physics-world objects, callbacks, body registries, and global state relevant. Do not promise first-time module/static-library setup or ABI-changing dependency changes can safely be completed exclusively through Live Coding. Respect the project's existing no-editor-restart-without-authorization rule when implementation eventually reaches a required reload. [^73]

### UE 5.7.4 contracts relevant to keeping functionality

#### Why a subclass swap cannot transparently replace all physics behavior

| Existing UE API | UE 5.7.4 source contract | Consequence |
|---|---|---|
| `IsAnySimulatingPhysics` | Virtual, but base scans mesh `Bodies` for `FBodyInstance::IsInstanceSimulatingPhysics`; SkeletalMeshComponent.cpp:3766 | Default false when Chaos simulation is disabled. Project manager gates need backend-aware state. Merely returning true may activate engine Chaos assumptions elsewhere. [^75][^76] |
| `IsSimulatingPhysics`, `SetSimulatePhysics`, `GetBodyInstance` | Virtual overrides exist | Limited hooks do not make `FBodyInstance` a generic foreign-physics body. [^75] |
| `GetPhysicsLinearVelocity`, `GetPhysicsAngularVelocityInRadians` | Nonvirtual; reads `GetBodyInstance` or Chaos physics-object handles; PrimitiveComponentPhysics.cpp:409/477 | Existing calls through UE component APIs do not magically return Jolt state. Add project wrapper/backend readback. [^77] |
| `SetAllBodiesSimulatePhysics`, `SetAllBodiesBelowSimulatePhysics` | Nonvirtual; iterate/operate on `FBodyInstance`s; SkeletalMeshComponentPhysics.cpp:1252/1328 | Simulation mode switches must use backend operations; inherited Blueprint nodes still control Chaos. [^75][^76] |
| `SetPhysicsBlendWeight`, `SetAllMotorsAngularPositionDrive` | Nonvirtual; changes UE simulation/blend/body/constraint state | Translate project-facing semantics explicitly; cannot override away all engine internals. [^75][^76] |
| `FPhysicsActorHandle` | Alias to `Chaos::FSingleParticlePhysicsProxy*` in PhysicsInterfaceDeclaresCore.h:76 | A Jolt BodyID cannot be substituted into this interface. Engine-wide replacement means substantial source-engine work. [^81] |
| `UPhysicalAnimationComponent` | Owns engine target actors and constraints, calls `FPhysicsInterface`, releases `FChaosScene` actors | Must implement Jolt-side equivalent behaviors or preserve project wrappers, rather than expecting built-in component reuse. [^79] |

#### Rendering pose and blood timing

UE 5.7.4 exposes `RefreshBoneTransforms`, virtual `FinalizeBoneTransform`, `CompleteParallelAnimationEvaluation`, and an editable component-space transform accessor, but much of animation processing and physics blending is nonvirtual/internal. Direct writes must participate in the established task ordering and publication lifecycle; an arbitrary game-thread overwrite can race or be replaced by a later parallel animation result. [^75][^82]

Two broad plugin-native avenues exist for investigation: a dedicated skeletal control/animation publication stage consuming immutable simulated-pose buffers, or a carefully scoped skeletal component path that completes/evaluates animation and publishes bones with explicit dependencies. This audit does not claim either is already proven for Prophecy. The selected path must preserve all non-physics bones/fingers, material skinning, sockets, bounds/culling, attached sword alignment, current bone transforms used for UV stain localization, leader/follower relationships if any, LOD behavior, offscreen simulation, and SIE/PIE timing.

The publisher needs body-to-bone local offsets, because a physics body's center of mass is not necessarily the skeletal bone origin. Keep both simulation-pose and render/interpolated-pose timestamps, then transform contact information using the pose from the same instant or explicitly reproject to the interpolated pose before painting. Existing blood render targets and shaders are not invalidated by selecting Jolt; their inputs must remain semantically correct.

#### Collision queries and mixed ownership

Jolt and Chaos do not automatically collide or generate each other's events. The plugin author's comments and the separate subsystem implementation confirm this scope. A UE query-only representation can be retained for selected consumers, but it is a separately synchronized representation with update/query cost. It cannot provide automatic two-way forces to a Jolt body. [^60][^61][^53]

The central ownership rule should be explicit: one authoritative simulator per movable body. Interaction with a legacy simulated subsystem must either be ported, isolated, or bridged by deliberate force/pose exchange with measured behavior. Turning on both simulators for the same ragdoll to keep Blueprint calls working defeats both correctness and the performance objective.

### Alternative integration assessment

#### BastienVdW/JoltPhysics

This integration vendors Jolt source under a UE module, defines shared-library export/import flags, and exposes a native subsystem plus body factories, character/CharacterVirtual wrappers, fixed constraints, and vehicle types. Its source therefore illustrates direct UBT compilation and a thin native object wrapper architecture. The README still labels Blueprint integration TODO. No skeletal component/PhysicsAsset-to-ragdoll publisher was found among its integration files; upstream Jolt skeletal/ragdoll files in the vendored library must not be confused with UE bridge implementation. [^67][^68][^69][^70]

Its Jolt Build.cs comments out `JPH_DOUBLE_PRECISION` and `JPH_CROSS_PLATFORM_DETERMINISTIC`, despite README determinism language. Its subsystem tick passes frame delta directly to `PhysicsSystem::Update`, uses `JobSystemThreadPool`, and immediately finishes simulation; it does not establish a fixed-step deterministic character integration by itself. Factory initialization checks for null, but teardown deletes the process-global factory from a world subsystem without a demonstrated multiworld reference count. These are reasons to evaluate its patterns selectively rather than treating its “replacement” wording as proof. [^69][^70]

#### Comparison for Prophecy

| Route | Evidence-supported advantage | Work/risk that remains | Assessment |
|---|---|---|---|
| Adopt/backport UnrealJolt wholesale | Existing settings, rigid-mesh extraction, terrain format, queries, BP wrappers, Jolt dependency setup | No articulated character bridge; unit/query/lifecycle/build defects above; UE5.7/package compatibility unproven | Useful reference and possible donor components, but README features do not establish lowest overall work. |
| Thin project-owned native Jolt plugin using upstream Jolt | Direct control of process/world lifetime, dimensional conversion, controller semantics, query/hit contract, one module ownership; official Epic external library pattern | Must implement asset conversion, world collision, pose transfer, project wrappers, lifecycle tests | Strong candidate for shortest reliable path because Prophecy's critical bespoke character bridge must be written under either route. This is a technical judgment, not a measured cost claim. |
| Engine-wide `FPhysicsInterface` replacement | Could theoretically preserve more built-in call sites if fully implemented | Source-engine fork; broad Chaos-specific aliases/calls, animation, queries, cook, materials, events, Niagara and other systems; ongoing merge/build maintenance | Unsupported as the shortest path by available evidence; not justified merely to port project functionality. |

No public benchmark establishes that one of these integrations will beat Prophecy's current solver at the same character fidelity. Solver-only speed must be evaluated together with pose publication, remaining Chaos queries/proxies, NN, actor/component updates, collision extraction/cooking, and worker contention.

### Remaining uncertainties to carry into the plan

- Exact selected engine version and target build/platform matrix; this audit proves only baseline source compatibility signals, not a compiled UE5.7 plugin.
- Exact shapes/constraints/masses/collision-disable pairs in the production Physics Asset and all Blueprint call sites; another audit must inventory assets through a safe read-only export before any migration is declared complete.
- Choice of publication path that preserves the project's animation/finger/sword/blood behavior without an added stale-pose frame.
- Whether the shipped map needs landscape, streaming proxies, ISM/HISM, Nanite fallback collision, movable static geometry, or runtime collision cooking at the first acceptance milestone.
- User-defined performance target and acceptable motion/tuning tolerance; absent a numeric target, define baseline measurements and agree criteria before a broad conversion.
- Exact Jolt compile options and version to pin independently of existing Unreal integrations.
- Whether any legacy systems need Chaos query proxies after gameplay queries are ported; retain only evidenced requirements and measure their cost.


## Jolt core capabilities

### Timing, feedback, direct drives, and force lifetime

`PhysicsStepListener::OnStep` receives the actual collision-step dt, first/last-step flags, and PhysicsSystem pointer. It runs once per collision step. Body and constraint mutexes are already held: it permits reads/writes, but not adding/removing bodies or constraints. Different listeners can run simultaneously; they must operate on disjoint owned bodies/constraints or provide their own synchronization.[^2]

The update dependency graph places step listeners before `JobApplyGravity` and active-constraint determination; collision work waits for those stages, followed by velocity solving, integration, CCD, and position solving. **Do not describe `OnStep` as a post-contact correction hook.** The code also clears accumulated forces/torques only during the **last** collision step of the enclosing Update. Repeatedly adding a fresh force every listener invocation therefore accumulates it across substeps unless the integration explicitly manages that lifetime.[^3]

Jolt linear velocity is world-space **COM** velocity in m/s; angular velocity is world-space rad/s. Direct `Body` setters need correct activation discipline. The locking `BodyInterface` setters activate a sleeping body for nonzero velocity and use clamped setters. The NoLock interface selects the same operations without recursively acquiring body locks. Default maximum angular velocity is approximately **47.12 rad/s**, and maximum linear velocity is **500 m/s**; preserving the old servo requires explicitly auditing these limits rather than accepting clipping silently.[^4][^5][^6]

**Inference for feedback:** retain the existing 30 Hz NN publication/feedback contract independently of physics step rate. Publish immutable target snapshots to the physics owner, then sample a completed Jolt state for feedback. Never feed a partially written 22-body pose or substitute target-only/extrapolated presentation for realized physical state. The existing component-pose readback must continue to represent the completed physical pose. Preserve the local source's exact correction denominator and strength semantics initially; changing them is a control-law change, not merely a backend substitution.

**Inference for force variants:** Jolt `AddForce` is force in N and `AddTorque` is torque in N·m, not UE's acceleration-change overload. Translational acceleration requires `F = m a`; desired angular acceleration requires world inertia multiplication before torque submission, with explicit treatment of gyroscopic integration and limits. An impulse must not be re-applied at every collision step. A force-reset scheme must preserve unrelated gameplay forces rather than clearing all incoming impacts.

**Local gravity distinction:** `FManualFollowerSubstepBody` contains targets and two strengths, with no cancel-gravity flag. Its automatic direct-velocity hook therefore must not inherit the cancellation policy of `ApplyBodyWorldMagnetization` or HalfSim `ApplyOneStepBody`, which exposes an explicit boolean and subtracts gravity only when requested. These public paths need separately recorded semantics. Comments or journal descriptions cannot substitute for executed code.

### Ragdoll structure and all eight HalfSim methods

`RagdollSettings::mParts` is one-to-one with its physics skeleton. Every part supplies body creation settings and an optional parent constraint; extra non-parent constraints have a separate list. A Prophecy adapter can therefore represent the **22 physics bodies** without pretending they are the complete render skeleton. The 25 NN bones and additional render bones still need explicit maps. `Ragdoll::SetPose` teleports bodies without activation; `GetPose` returns body world transforms. The class batches body insertion and removes constraints before body removal.[^7][^8]

The PoweredRig sample uses a loaded humanoid asset and adjusts its animation root to the current ragdoll root. It offers Position or PositionAndVelocity motors and computes a sample pose error. This verifies articulated motor capability; it does not demonstrate an externally commanded Prophecy pelvis, its current all-body servo, foot/capsule rules, or NN recurrence.[^9]

`Ragdoll::DriveToPoseUsingMotors` dispatches only SwingTwist and Hinge constraints, skips a root without a parent constraint, and asserts for other constraint subtypes. A SixDOF articulation or world-target implementation needs its own motor dispatch; the helper is not a generic drive implementation for every Jolt joint.[^8]

The current local enum in `Source/GameAnimationSample3/Public/ProphecyHalfSimDriveComponent.h` exposes eight modes. They all remain part of the eventual API compatibility surface, even when a mode intentionally lacks pelvis support. The following is a **capability mapping / research judgment**, not a claim that gains or dynamics match:

| Existing mode | Viable Jolt mechanism | Compatibility constraint |
|---|---|---|
| `NativeWorld` | Per-body SixDOF motor attached to a world reference, or an explicitly specified world force/torque controller | Requires world translation and orientation support on every selected body; angular-only PoweredRig is insufficient. |
| `NativeLocal` | Relative parent-frame drive without root support | Preserve intentional unsupported-pelvis behavior; must determine exact UE local-target semantics. |
| `NativeLocalPelvis` | Relative drives plus an independent world pelvis drive | Root support must remain independently controllable. |
| `JointMotors` | Motors on the authored anatomical constraints | Preserve the existing free-angular configuration and lack of pelvis support. |
| `JointMotorsPelvis` | Anatomical motors plus a world pelvis drive | Counts/strength settings must distinguish the two sets. |
| `WorldForcePD` | Existing implicit-PD equations with m/inertia conversion into Jolt force/torque | Uses different gain semantics from motors already in current code; retain that distinction. |
| `Passive` | Same articulation with all active drives disabled | Bodies, collisions and constraints remain active. |
| `WorldOneStep` | Existing one-step acceleration law with explicit gravity-cancellation behavior | Distinct from full-Sim direct SetV/SetW; align force lifetime with physics step policy. |

The local `Configure` implementation frees all three angular limits before configuring HalfSim drives, toggles joint motor states, and retains per-body settings/cancel-gravity flags. **Do not reconstruct restrictive PHAT angular limits during these modes merely because Jolt supports them.** `WorldForcePD` derives animation component transforms from animation locals, explicitly avoiding a physics-blended pose; that separation must survive the port.

For a world drive, Jolt's `BodyInterface::CreateConstraint` can use `Body::sFixedToWorld` for one missing/invalid body endpoint. A SixDOF constraint can keep all axes free and enable motors with position/orientation targets. **Inference:** this permits world physical-animation drives without manufacturing a hidden skeleton or a colliding target body. Its cost and behavior need measurement. The official SixDOF sample demonstrates a motor-driven dynamic body against a static reference and independently selectable motor states.[^5][^10]

### Constraint frames, motors, and missing Chaos semantics

SixDOF exposes separate translation/rotation axes, free/fixed/limited states, cone/pyramid swing limits, and per-axis motors. Its translation targets/velocity use body-1 constraint space, while target angular velocity uses **body-2 constraint space**. Orientation has a body-space setter with `R2 = R1 * target`. Soft limit settings exist for translation only; **soft angular limits are not supported there**.[^11]

SwingTwist is specialized for humanoid rotation with coincident positional anchors, twist-axis and plane-axis frames, separate swing/twist motors, and radian limits. Its orientation conversion is based on both body-to-constraint rotations; simply copying UE `Swing1`/`Swing2` numbers and a bone quaternion does not establish the correct frame. `SetTargetOrientationBS` describes body-relative orientation; it is not a world quaternion setter.[^13]

Motor states differ materially: Position uses a position spring with damping toward zero velocity, while PositionAndVelocity damps the error to an explicit target velocity. MotorSettings separately limits force and torque, with unlimited defaults. SpringSettings offers frequency/damping-ratio, physical stiffness/damping, and (new in 5.6) mass-normalized stiffness/damping using effective constraint mass/inertia. **Inference:** import each existing parameter with declared units and mode, then calibrate by measured pose/contact response; numerical equality of two differently defined stiffness fields is not evidence of equivalence.[^14][^15]

Constraint local positions in `EConstraintSpace::LocalToBodyCOM` are relative to COM, requiring the shape COM offset to be subtracted from origin-local anchors. `ResetWarmStart` exists for real discontinuities; using it every frame weakens effective constraint support. When a shape's COM changes, the owner must notify all attached constraints through `NotifyShapeChanged`. A disabled constraint still has processing overhead. Breakability can be implemented by inspecting solved impulse and disabling/removing the constraint; an impulse is not a force threshold unless divided by the appropriate dt.[^16]

The inspected public Jolt settings do **not** establish one-to-one implementations of UE `bParentDominates`, Chaos shock propagation, Chaos runtime mass conditioning, projection tolerances/iteration settings, or MACD. Jolt has Baumgarte correction, velocity/position iterations, constraint priority, and an optional ragdoll stabilization authoring operation. These are different mechanisms. **Do not claim support by copying the old numeric field into a roughly similar Jolt field or leave a functional Blueprint option as a silent no-op.** Retain a capability/status record and identify a measured replacement or explicit unresolved incompatibility.

In particular, `RagdollSettings::Stabilize` redistributes masses and alters inertia to reduce parent/child ratios. **Inference:** it is not a lossless import step or proof of Chaos mass-conditioning equivalence. Auto-calling it would change a supposedly exact PHAT benchmark. Existing NN forearm/PHAT length mismatch is a geometry constraint already recorded in the project journal; a new solver cannot satisfy mutually incompatible hard geometry and pose targets by itself.[^8]

### Geometry, units, COM and skeletal transforms

Jolt uses right-handed coordinates, defaults to Y-up, uses column-vector matrix multiplication, and works best in SI units. Other up axes are supported with correct gravity and relevant shape/character settings. Double precision is available for world positions, while much internal math and broadphase remain float. Determinism requires the same initial state and ordered mutation inputs; cross-platform determinism additionally requires matching source/defines and its compile option. These are library guarantees under conditions, not a guarantee for the NN/Blueprint/render pipeline.[^17]

**Derived conversion rules:** for a chosen orthogonal UE→Jolt basis matrix `B` and distance scale `s = 0.01`, use `pJ = s B pUE`, `vJ = s B vUE`, `RJ = B RUE B^T`, `mJ = mUE`, `IJ = s² B IUE B^T`. Angular velocity and torque are axial vectors: under a reflection (`det(B) = -1`), `ωJ = det(B) B ωUE` and `τJ = s² det(B) B τUE`. Force uses `FJ = s B FUE` when the input is kg·cm/s². These formulas are mathematical derivations, conditional on the existing data's actual units; UE acceleration-mode calls require the additional mass/inertia conversion already noted.

These formulas deliberately do not prescribe an unverified global Y flip. The adapter must choose and document `B`, reconcile UE's rotation/multiplication conventions with Jolt's matrices, and validate positive/negative rotations around every axis, quaternion round trips, off-center impulse torque and COM readback. The trained model's existing `MirrorYBasis` transform belongs to a separate boundary and must not be applied a second time merely because the solver changed. Capsule-local Y and world-up selection are also independent choices.

Keep separate transforms for **bone**, **body origin**, **shape-local frame**, **COM**, **constraint frame**, and **render component**. The current full-Sim source builds `BodyFromBone * InterpolatedTarget`; that offset is evidence that body and bone are not interchangeable. In Jolt, input position is body/shape origin; internal integration uses `pCOM = pOrigin + R cShape`. `MoveKinematic` calculates the desired COM from target origin and orientation before computing velocity.[^18]

**Derived velocity conversion:** `v(point) = vCOM + ω × (point − pCOM)`, hence `vCOM = vOrigin − ω × (pOrigin − pCOM)`. Apply the matching world-space COM offset; do not reinterpret an origin velocity as COM velocity. The inverse readback must recover body origin before reconstructing the bone transform. These are critical for feedback and impact speed on rotating off-center limbs.

Jolt capsules are aligned with local Y and take **half the cylindrical section**, excluding sphere caps. Settings allow cylinder half-height zero and create a sphere in that case; direct CapsuleShape construction expects positive cylindrical half-height. UE capsule half-height and PHAT sphyl length must be interpreted using their respective definitions before conversion.[^19]

`RotatedTranslatedShape` places/rotates a child relative to body shape space. `OffsetCenterOfMassShape` shifts COM independently of geometry and adjusts mass properties. These are distinct operations. A PHAT body containing multiple primitives needs a compound shape or equivalent consistent local shape collection, plus authored mass/inertia rather than accidental density-derived replacements. Preserve shared immutable shape data where valid; scale must be validated per shape subtype instead of assumed universally supported.[^20][^21][^22]

### Collision filtering, contacts and CCD

#### Dynamic concave geometry: boat, sword and cut fragments

**Dynamic MeshShape is supported with important restrictions; it is not categorically forbidden.** The 5.6 header explicitly permits dynamic or kinematic mesh bodies provided they never need to collide with another MeshShape or HeightFieldShape. `MeshShape::GetMassProperties` returns invalid/default properties because arbitrary triangle surfaces do not establish a solid volume. Use `EOverrideMassProperties::MassAndInertiaProvided` and supply **both mass and inertia**; `CalculateInertia` still calls the mesh's unsupported mass-property calculation and is not sufficient. The official DynamicMeshTest creates a dynamic torus this way and collides it with boxes.[^42][^43][^44][^48]

**Mesh–mesh and mesh–heightfield pairs are unsupported in the stock narrow phase.** The mesh and heightfield implementations register convex↔mesh/heightfield handlers, including reversed shape casts; they do not register the missing concave pairs. The default dispatch handler asserts and returns no collision result. A collision filter can prevent hitting that unsupported code, but cannot supply the omitted physical response. HeightFieldShape is documented as static-only and does not define valid dynamic mass properties; do not extrapolate MeshShape's explicit exception to heightfields.[^43][^45][^46][^47]

Mesh triangles are single-sided for simulation; selected query APIs can request backfaces. MeshShape's built-in submerged-volume operation is explicitly unsupported and its volume getter returns zero. **Inference for the boat:** preserving existing buoyancy forces/point sampling on an appropriate body remains viable, but simply selecting a dynamic triangle mesh and calling Jolt's generic submerged-volume buoyancy routine is not a verified replacement.[^42]

**Inference for gameplay geometry:** a freely moving sword, boat or sliced fragment that must hit a triangle-mesh world, terrain heightfield, or another concave moving object needs supported simulation geometry, such as suitable convex shapes or convex-child compounds, or a separately verified custom collision implementation. A render mesh can remain concave and richly detailed; it need not be the simulation collider. A dynamic mesh is a valid special case only when its allowed contact pairs and supplied mass/inertia meet the restrictions. Runtime cut topology must regenerate the simulation collider and its identity/mass metadata where needed; visual mesh slicing alone does not establish a collidable Jolt fragment.

GroupFilterTable permits cross-group collision and uses a subgroup bit table for self-collision within a group. Same-group/same-subgroup bodies do not collide; same group with different filter instances also does not collide. **Inference:** use globally unique agent group IDs and a shared authored self-collision table per compatible rig; do not reuse one group ID across all crowd agents. Copy the actual PHAT disabled-pair policy, not just parent-child exclusions.[^23]

`RagdollSettings::DisableParentChildCollisions` can also suppress pairs that overlap in a supplied pose. That is a convenience, not proof it matches production collision rules; automatic overlap suppression risks removing intended collisions. Broad-phase/object-layer filters should reject broad categories early. The contact listener's validation stage is deliberately late and comparatively expensive for rejecting most unwanted pairs.[^7][^24]

Contact callbacks can run concurrently, with bodies locked. Use no-lock **read** access and do not mutate physics state or call Blueprint/UObject/render work from them. `OnContactRemoved` must not access bodies at all: they may already be destroyed or concurrently changing. Cache stable metadata or enqueue IDs. Added-contact velocities are pre-solve; the true solved impulse is not available there. LinearCast can cause both added and persisted callbacks for the same pair/subshape in one collision step.[^24]

**Inference for blood/hits:** record a plain-data event containing generation-safe body/agent/bone identities, subshape IDs, point, normal, relative point velocity, contact stage and physics step/time; consume after the solver on the game thread. Preserve normal direction when canonicalizing pair order. Use a deduplication/attack-contact policy rather than treating every persisted/CCD callback as a new strike. Estimated impulse must remain marked as estimated if it substitutes for existing impulse-based behavior.

LinearCast can stop movement at the first collision and delay the bounce to the next step; it also has documented callback nuances. Its rotational blind spot means contact-free center translation is insufficient proof of safe sword sweep. **Inference:** retaining/adding a rotationally sampled weapon sweep or another explicitly verified angular-hit mechanism may be necessary. The exact choice depends on the project's sword hit contract; turning on LinearCast alone is not the acceptance test.[^12]

Default PhysicsSettings include 10 velocity iterations, 2 position iterations, 2 cm penetration slop and speculative-contact distance, and linear-cast thresholds based on inner radius. Friction requires at least 2 velocity iterations. Body/constraint iteration overrides take the maximum over the island. **Inference:** an expensive override on one agent in a contact pile can expand the work of the whole connected island. Defaults are research inputs, not tuned Prophecy values; thin objects and hand-contact expectations especially need explicit scale/tolerance checks.[^25][^6][^16]

### Switching, ownership and lifetime

Changing Dynamic↔Kinematic does not zero velocities in the Body implementation, but entering Kinematic clears force and torque. Entering Static clears linear/angular velocity too. A static body that may later become movable needs motion properties provisioned via `mAllowDynamicOrKinematic`. Disabling sleeping does not itself wake an already sleeping body.[^18][^6]

**Inference:** a mode transition needs an explicit pose, COM velocity, angular velocity, activation, gravity, collision and drive snapshot. SetMotionType alone does not preserve Prophecy mode semantics. It must not reinitialize NN state or attack phase. Runtime PHAT replacement must preserve matching bones as the current local wrapper does, rebuild identity/constraint maps, and avoid stale callbacks/shape handles.

Jolt construction/initialization is not Unreal object lifetime management. HelloWorld shows allocator/factory/type registration, temp allocator/job system creation, physics initialization, body activation, stepping, and reverse cleanup. Body interfaces manage body destruction; `Ragdoll` removal must precede its destruction. **Inference:** world-owned PhysicsSystems with module-owned library globals must handle PIE's multiple worlds and repeated startup/shutdown; unloading the module while Jolt objects, jobs or callbacks survive is invalid.[^7][^26]

### Performance, capacity, precision and build constraints

Jolt permits a custom JobSystem, but its job graph changes while jobs run. Jobs/barriers have reference-lifetime requirements. `WaitForJobs` should execute its own Jolt jobs, not arbitrary jobs that touch physics; engine-wrapper jobs may still need joining after the barrier is done. **Inference:** a UE task-system integration must preserve these rules. An initial bounded dedicated pool is a legitimate comparison option, but hardware_concurrency-minus-one from a standalone sample is not proof it is appropriate inside UE with NN/render workers.[^27][^26]

The fixed TempAllocator aborts on exhaustion and incorrect LIFO freeing. `TempAllocatorImplWithMallocFallback` exists, making a resilient initial allocator possible. Capacity failures are not benign: Update's bitfield distinguishes manifold-cache, body-pair-cache and contact-constraint exhaustion, each capable of ignoring contacts. Track all three and fail benchmark validity if any occur. Capacity estimates need the environment and dense worst-case piles, not just 2,200 agent bodies.[^28][^30]

The 5.6 official `PerformanceTest` documents **160 motor-active ragdolls / 3,680 bodies**, as either 16 piles or one pile. It provides thread counts, discrete/LinearCast modes, no-sleep, per-frame CSV, repeated trials, state validation and final-state hashes. **Inference:** these controls are useful methodology, but this fixture is 23 bodies per rig and is not Prophecy's exact 22-body continuous-NN-target workload. The existing project's headless benchmark should retain its accepted topology, stimulus, error metrics and environment when comparing the new backend.[^29]

The 5.6 release reports scene-dependent speed/memory improvements, a changed friction model, and a fix preventing kinematic contacts/constraints from unnecessarily combining islands. It also adds GPU compute/hair infrastructure, not a demonstrated GPU rigid-body crowd solver. **Inference:** do not advertise GPU acceleration for this migration or use release percentages as a predicted improvement. The kinematic-island fix does make old-version performance assumptions worth rechecking.[^1]

CMake defaults must be reviewed: static MSVC runtime, LTO, CPU ISA options, debug renderer/profiler in Release, and new GPU-compute backends are enabled by default in relevant configurations. Profiling/debug-render support has runtime cost even if no drawing occurs. A rigid-body-only UE build can disable unused compute backends. Record exact compiler, CRT, ISA, precision, determinism, profiling and library/link flags for every comparison. Jolt headers require `Jolt/Jolt.h` first; RTTI/exceptions are not required by Jolt.[^31][^32]

Jolt exposes `VerifyJoltVersionID()` for ABI compatibility. Registration compares the client version and feature defines, including precision, determinism, debug/profile modes, object-layer width and allocator/object-stream options, and aborts on mismatch. This is a concrete defense against a Development/Shipping or prebuilt-library mismatch. It does not replace checking UE's compiler/CRT compatibility.[^33][^34]

Allocator hooks include normal, realloc, free, aligned allocation and aligned free, with stated alignment constraints. **Inference:** a UE memory adapter must implement the full contract consistently before type registration and retain it until all Jolt allocations are freed; mixing DLL heaps or replacing allocators while live objects exist would violate ownership assumptions.[^35]

### Adversarial compatibility check: what could invalidate a thin adapter

**The strongest unresolved gap is actual solved contact impulse.** The complete 5.6 ContactListener exposes validate/added/persisted/removed, with added contacts explicitly before solving. The inspected PhysicsSystem public interface exposes contact presence, not a public post-solve manifold-impulse getter/callback. `EstimateCollisionResponse` is a separately callable estimate; its own contract says simultaneous contacts involving more than two bodies make it inaccurate. A constrained limb or crowd contact cannot therefore be advertised as producing an equivalent UE `NormalImpulse` through that estimate. If an existing gameplay threshold really requires solved contact impulse, its exact compatibility needs a verified extension/instrumentation or a consciously changed contract. Subtracting body velocities before/after Update does not isolate one contact from joints, gravity, drives and other contacts.[^24][^36][^37]

**World drives are possible, but force and velocity control are observably different.** Jolt applies gravity and accumulated force, then damping, then clamps velocities. Its contact restitution computation also explicitly compensates the component of gravity/accumulated force into the contact normal. A direct velocity change is not represented in that force accounting. Identical free-flight acceleration does not establish identical bounce or pile behavior for two controller implementations.[^38][^39]

**Gravity cancellation has a fractional-strength edge case.** The locally read `ApplyOneStepBody` subtracts gravity from its acceleration **before** multiplying by LinearScale, and only runs that branch when LinearScale is positive. Thus for cancellation enabled and scale `s` between zero and one, ideal unconstrained residual gravity is `(1 − s)g`; scale zero leaves normal gravity. Replacing that path with `SetGravityFactor(0)` whenever the boolean is true silently changes behavior. This does not apply automatically to the separate full-Sim SetV/SetW callback, which has no cancel-gravity flag. Damping/contact effects remain solver-dependent even after retaining the explicit algebra.

**PHAT freedom and soft limits are not universally importable by a field mapper.** SixDOF's orientation target setter clamps the requested target to the configured swing/twist limits. Its motor rotation error is a quaternion-based small-angle approximation, unlike the current explicit axis-angle direct-velocity rule. Turning off the motor still allows configured joint friction, and positional/anatomical limits remain active. Stock SixDOF cannot encode soft angular limits; custom Jolt `Constraint` subclasses are an extensibility route, but their correctness/performance is new work. No evidence here proves all enabled Chaos projection, parent-dominance, mass-conditioning or shock-propagation settings can be preserved through the existing stock constraint classes.[^11][^16][^40]

**Zero drive strength can preserve collision without a solver fork**, provided it means no drive contribution and the body remains Dynamic with the intended layer/filter and authored constraints. Making the body Kinematic, a sensor, removing it, disabling collision, or clearing anatomical constraints is a different gameplay state. Motor Off can leave intentional joint friction; an adapter must distinguish drive strength from friction/structural limits.[^4][^6][^40]

**The root capsule must remain an explicit mover and query contract.** A Jolt CharacterVirtual is not a rigid body or a broadphase member; regular casts do not see it without its optional inner-body representation. It requires its own update/state handling. Consequently, substituting CharacterVirtual just because its shape is a capsule is not a fidelity argument. Equally, an independent Chaos capsule does not automatically collide with Jolt-owned limbs: bridge or rerouted queries must preserve kinematic-capsule/physical-limb interactions and avoid two solvers owning the same dynamic response. The latter is an integration inference from independent world ownership, not a claim that Jolt itself supplies a Chaos bridge.[^41]

**Compatibility judgment:** public Jolt APIs support the essential body/velocity/force/constraint operations without a UE engine fork. They do not establish complete gameplay equivalence through a thin field-for-field wrapper. True impulse reporting, soft angular/Chaos-specific constraint behavior, and cross-world capsule queries are specific points capable of expanding the adapter. Their actual relevance depends on which production properties and Blueprint outputs are used; none should be silently discarded.

### Remaining gaps that need explicit prototype evidence

- Exact full-Sim contact behavior after translating the existing SetV/SetW correction, including damping, gravity integration, angular caps, constraint warm starting, and output readback.
- Exact local-drive semantics of UPhysicalAnimationComponent and a measured equivalent for NativeLocal/NativeLocalPelvis.
- PHAT import of authored inertia orientation, all primitive scales, constraint reference frames, collision-disable table and any enabled unsupported soft angular/projection/mass-conditioning fields.
- Sword rotation-only tunneling, impact-event deduplication, hit strength/impulse semantics, and strength-zero physical response.
- Real 100-agent throughput including target publication, solver, body-to-bone conversion, pose presentation and NN feedback, separately from a solver-only run.
- Frame scheduling at 60/30/5 render FPS and repeated mode/PHAT transitions without stale target/feedback or destroyed-body events.
- Whether double precision is needed for this map's operating extent; the choice should follow actual coordinates and accuracy requirements.


## Feature compatibility inventory

### Feature coverage matrix

| Feature | Confirmed source / artifact | Rendering or gameplay logic to preserve | Physics integration needed |
|---|---|---|---|
| Persistent particle stains | `Source/GameAnimationSample3/Private/ProphecyBloodStainRenderer.cpp:25,65,89,127,137,184` | Preallocated procedural triangle buffer, ring capacity, material, batched mesh updates, position/normal/radius inputs | Supply equivalent collision/export payload; preserve `SimulationPositionOffset`; `FBasicParticleData.Velocity` is interpreted as the stain normal |
| Static/Nanite texture paint | `ProphecyBloodTexturePaintManager.cpp:246,564,612,1325` in the same directory | Per-component/material-slot MID + RT storage and brush queue | Preserve UE component identity, exact collision triangle/UV mapping, material slot, world point; Jolt `SubShapeID` is not a UE `FaceIndex` |
| Skeletal texture paint | `ProphecyBloodTexturePaintManager.cpp:667,782,930,1477` | LOD0 reference triangle/UV cache; bone-based approximate projection; 48-pixel brush cap | Bone/body/component mapping and collision-time pose consistency; validate CPU render data survives cooking |
| Screen-space fluid and floor grid | `ProphecyBloodFluidPostProcessController.cpp:88,135,200`; `ProphecyFoliageDecalGridComponent.cpp:194,206` | Stencil 42, postprocess materials/MIDs, floor tile merging/decal rendering | Correct blocking-hit bit and point/normal for floor grid; Niagara presentation timing |
| Sword equipment and grip | `ProphecySwordComponent.cpp:89,170,226,241,246,284` | Existing `A_Sword`, calibrated grip, exact training mesh, socket attachment, inventory/Blueprint nodes | Jolt body/constraint, CCD policy, velocities, owner-only pair suppression, lifecycle and mode rebind |
| Sword cutting | `Docs/AgentSwordBlueprint.md:15,17,47,50`; `ProphecyBladeSweepBlueprintLibrary.cpp:16` | Original Blueprint cutting graph and blade-depth sample math | All Blueprint trace/contact/constraint/velocity calls need inventory and routing; physical cut constraints must share the sword/victim solver |
| Impact velocity | `PhysicsHitVelocityLibrary.cpp:84,136,155` | Blueprint result shape; translational/rotational spring math | COM/inertia and event-phase semantics differ; store true pre-solve states rather than subtracting an invented Jolt impulse |
| Potence rope/noose | `ProphecyPhysicsConstraintBlueprintLibrary.cpp:165,212,267,302,349,409`; `ProphecyRetractableSkeletalMeshComponent.cpp:45` | One skeletal rope, retracting visual bones, full-length dynamic articulation, welded noose | 28-body state, kinematic root, 27 dynamic links, constraints, collision retirement, wake, compound body mass/COM handling |
| Boat | `ProphecyPhysicsConstraintBlueprintLibrary.cpp:494`; `Saved/Profiling/BoatBuoyancy/BP_Boat_EventGraph.txt` | Existing water-level spring and wave math; render mask | Force/torque/velocity read-write adapters; current BP wiring audit; rider floor/base/force transfer |
| Environment | `Source/ProphecyEditor/Private/ProphecyExportSimCollision.cpp:151,205,237,287,347,419` | Authored static/instance/landscape collision choice and IDs | Cook Jolt-native primitives/convex/mesh/heightfields plus provenance, hole/material/filter/instance data; existing v1 export is insufficient |
| Agent root capsule | `ProphecyAgent.cpp:2524,2910,2999`; `Config/DefaultEngine.ini:163-173` | Accepted mover, swept location, depenetration/slide, measured actual root | Query authority and root-vs-limb filter matrix; no automatic Jolt visibility to ordinary UE sweeps |
| Double-reach test actors | `ProphecyDoubleReachBallTest.cpp:23,212,243` | Experimental reach targets/animation | Physics balls and bounds use primitive simulation and velocity APIs; feature usage must be classified in manifest |

All unqualified `.cpp` paths in the matrix live under `Source/GameAnimationSample3/Private/`.

### Blood and Niagara

**B1 — Persistent stains are predominantly presentation, with narrow input contracts.** `AProphecyBloodStainRenderer` creates a collision-disabled `UProceduralMeshComponent` (`:32`), writes existing buffer entries rather than spawning a component per stain, and updates the mesh in a batch (`:107`). `ReceiveParticleData_Implementation` forwards to `AddBloodParticleData`; each particle becomes `Position + SimulationPositionOffset`, `Velocity` used as the world normal, and a radius derived from `Size` (`:89-95`). This implementation does not query physics. A Jolt port should preserve its data convention even though Niagara's field is named velocity. The renderer's triangles are world-position presentation, not an attachment mechanism for a moving limb; the texture-paint manager is the separate skin-following persistent mechanism.

**B2 — The actual collision producers remain partly opaque.** `ProphecyWireBloodStainCommandlet.cpp:17,64,171-284` targets `/Game/_mygame/blood2/A_DecalManager`, finds its `ReceiveParticleData` event, and inserts `AddBloodParticleDataToWorld` while retaining the existing execution chain. This is authoring-tool source, not proof it is the currently executing asset graph. `Saved/ProphecyInspectBloodAssets.json` names `NS_bloodsplat`, `NS_bloodrender`, and `A_DecalManager`, but many attempted Niagara property reads failed; it does **not** establish each emitter's CPU/GPU target or collision mode. A future read-only asset manifest must capture those modes, trace channels, export conditions/payloads, local-space mode, persistent IDs, event handlers, and data interfaces.

**B3 — UE CPU Niagara queries are still UE world traces.** Installed `UE/Plugins/FX/Niagara/Source/Niagara/Private/NiagaraCollision.cpp:47,144-170` uses `UWorld::AsyncLineTraceByChannel` and `LineTraceSingleByChannel`. `NiagaraDataInterfaceCollisionQuery.cpp:33-34` exposes synchronous/asynchronous CPU query functions; GPU functions separately query depth/distance fields/async GPU traces. Therefore a project-side Jolt scene will not become visible to stock CPU Niagara traces merely because Jolt bodies are simulated. An adapter, a custom CPU collision data interface, or synchronized UE query proxies is required for those emitters that actually depend on this path. GPU render-based collision may continue to see UE-rendered geometry if its transforms and rendering representations remain correct; it does not become Jolt narrow-phase collision. Epic's collision-module documentation distinguishes the CPU ray and GPU scene depth/distance-field routes.[^90]

**B4 — GPU collision events and GPU particle export are different mechanisms.** Epic's event-handler page says Niagara emitter events work with CPU simulation.[^91] Installed 5.7.4 `NiagaraDataInterfaceExport.cpp:44,120-148,264-280` nevertheless has **both CPU export and GPU readback** to game-thread callbacks, proving that GPU-to-Blueprint export is supported independently of the event-handler restriction. At `:34-40`, the default per-particle GPU export readback cap is 1,000 entries; this is an engine default, not a verified current project override. Export is deferred through `FNiagaraWorldManager::EnqueueGlobalDeferredCallback`, and GPU export additionally waits for readback. Preserve callback/world lifetime and monitor queue overflow or dropped data. Do not treat a returned particle location as a same-frame skeletal hit unless a collision-time identity/pose reference exists.

Epic marks Niagara GPU ray-traced collision experimental, requires supported DX12/hardware ray tracing, and documents a one-frame delay.[^92] That route is an optional existing rendering dependency to inventory, not an automatic replacement for reliable sword hit detection.

**B5 — Static blood UV lookup has an engine data dependency.** `TryPaintFromHit` requires a `UMeshComponent` (`:246`), resolves a material slot (`:564`), then calls `UGameplayStatics::FindCollisionUV` (`:627`). Installed `UE/Source/Runtime/Engine/Private/GameplayStatics.cpp:1449-1473` reads `Hit.Component->GetBodySetup()`, transforms **`Hit.Location`** into component space, and passes `Hit.FaceIndex` to `UBodySetup::CalcUVAtLocation`. `UE/.../Private/PhysicsEngine/BodySetup.cpp:1238` indexes `UVInfo.IndexBuffer[FaceIndex*3]`, reads vertex UVs and calculates barycentrics. `bSupportUVFromHitResults=True` is saved at `Config/DefaultEngine.ini:118`, and Epic documents this requirement.[^93]

Inference: a fabricated `FHitResult` with the correct point but arbitrary Jolt subshape number can paint the wrong UV or fail. The cook must retain a source-triangle identifier and distinguish collision-triangle index, render-triangle index, material slot, and Jolt subshape identity. Pinned Jolt 5.6.0 `MeshShapeSettings` explicitly reorders triangles; `mPerTriangleUserData`/`GetTriangleUserData` can retain the original index (about 25% extra mesh memory), and mesh sanitization removes duplicate/degenerate triangles.[^94] The original index must refer to the exact triangle stream corresponding to UE UV data, not just any mesh's LOD0. A direct UV-result adapter can avoid pretending every Jolt result is a native UE collision hit, while retaining the existing brush/MID/RT code. For contact-driven painting, Jolt's manifold reduction may combine coplanar contacts while retaining only one subshape pair; that pair is not guaranteed to identify a separate exact source triangle for every manifold point.[^98] An explicit collision-source refinement query may be needed for UV accuracy.

**B6 — Skeletal projection is approximate and tied to a bone pose.** At `ProphecyBloodTexturePaintManager.cpp:710-726`, the code uses `Hit.BoneName` to select triangle candidates and transforms the hit through the **currently published bone world transform** back into reference space. It finds the nearest reference triangle and interpolates UVs; no exact skinned-triangle physics mesh is created. Cache construction (`:782`) reads LOD0 indices, positions, skin weights, section bone maps, and UVs, keyed by asset path/UV channel/LOD0 (`:930`). Missing CPU-readable data produces a rejection. Current bone pose and impact timing must therefore agree after Jolt readback; a delayed callback may require saved bone-local point or collision-time transform. Updating skeletal presentation only after blood queries would give plausible but misplaced stains. The existing 48 RT pixel skeletal stamp cap (`:1477`) limits island bleed, and does not solve geometric approximation.

**B7 — Nanite rendering does not define the collision mesh.** Epic 5.7 documents that fallback mesh / selected collision LOD provides complex per-poly collision.[^95] Preserve the collision source chosen by the asset and its UV correspondence. A Jolt mesh built from visual Nanite triangles would change both collision cost and hit position relative to the existing behavior. Existing journal risks remain: real hero Nanite validation, landscape and unique ISM masks, blood normal layering, packaged profiling. `MakeStateKey` (`:502`) uses component unique ID + material slot, **no instance index**; ISM inherits static-mesh component behavior but unique per-instance staining is not implemented by that key.

**B8 — The screen-space and floor-grid effects need little solver work.** `ProphecyBloodFluidPostProcessController.cpp:88` tags matching Niagara components for stencil rendering; `:135-220` builds blendables and pushes material parameters. `ProphecyFoliageDecalGridComponent.cpp:194` requires `bBlockingHit`, selects point and normal from the hit, then delegates to a world-space grid. These do not need a Jolt rewrite; provide equivalent hit metadata and retain UE materials/decal rendering.

### Sword, hit responses, and constraints

**S1 — Equipment is a real rigid attachment and an existing Blueprint actor.** `ProphecySwordComponent.cpp:89` spawns the existing `/Game/_mygame/sword/A_Sword`, creates/reuses its typed decal manager, initializes per-instance debug/freeze/gravity fields before BeginPlay, makes its named static-mesh component the root, and optionally uses the exact calibrated `Sword_GL01_Training` mesh. The code specifies a mass override, gravity, CCD, and solver iterations (16 position / 8 velocity), then creates a six-axis-locked `UPhysicsConstraintComponent`. Retain those behavioral inputs; iteration counts are solver-specific and must be validated rather than numerically equated.

`Bind` (`:170`) binds to the actual pose mesh's hand body, derives constraint frames from the authored grip rather than a deflected sword, includes scale in the blade frame, adds a tick prerequisite, and wakes bodies. The non-simulated variant disables collision and attaches to the socket; this is intentionally collision-free. `SetSimulated` (`:226`) restores carried velocities; `Drop` (`:246`) clears only owner suppressions, removes the grip, enables simulation/collision/gravity, and preserves linear/angular momentum. `TickComponent` (`:284`) runs after physics and estimates carried velocity from successive component transforms. All need matching Jolt/UE ownership and timing, including rebind after agent mode switches.

**S2 — Owner suppression is more than a collision channel.** `ProphecySwordComponent.cpp:17-72` stores solver + Chaos particle unique IDs, queues commands directly to the Chaos broadphase ignore manager, and includes skeletal bodies and primitive/capsule bodies. `Docs/AgentSwordBlueprint.md:17` explains why: self-cutting can create competing constraints. Jolt's layer filters handle broad categories, while `CollisionGroup`/`GroupFilterTable` support same-group subgroup exclusions.[^96] Preserve separate ownership of hold exclusions and victim-cutting exclusions; dropping a sword must not globally enable a pair still disabled for another live constraint. Shared subgroup tables require care: editing a shared filter for one character can affect all instances using it. Lifetime/generation mapping must prevent released bodies or a reused ID being mistaken for the same sword/owner.

**S3 — Cutting needs its own manifest.** `ProphecyBladeSweepBlueprintLibrary.cpp:16` only produces deterministic depth samples between previous/current blade depths; it is math, not the actual scene sweep. The cutting graph remains in `A_Sword`. Existing docs confirm victim constraints and retained Niagara behavior, but its complete nodes, dynamic constraints, shape queries, trace complexity/channels, attached wound FX, and body writes are not fully represented in native source. For full parity those graph operations must reach the same solver as sword and target. A Chaos `UPhysicsConstraintComponent` cannot exert a Jolt joint between two Jolt bodies without an explicit adapter. A fast-rotating sword also needs angular-motion coverage beyond assuming a linear CCD setting is equivalent; the detailed Jolt solver research covers that separately.

**S4 — Current pre-impact velocity API cannot be mechanically mapped.** `PhysicsHitVelocityLibrary.cpp:84` reads final linear/angular velocity, mass, inertia tensor, COM and body transform; computes `NormalImpulseOnSword / Mass`, converts `r × impulse` through the inertia frame, and subtracts these from final velocities. It reconstructs pre-impact point velocity using `v + ω × r`. That is already an assumption based on the supplied impulse, especially with multiple contacts/constraints. The springs (`:136,155`) are independent math using explicit or world delta time.

Epic documents that `OnComponentHit` gets zero `NormalImpulse` for swept-component blocking hits, but a physics impulse for simulating bodies.[^97] Jolt's `OnContactAdded` is **before** contact resolution, can execute on multiple worker threads while bodies are locked, and does not expose a solved impulse there. Added/persisted callbacks permit read-only capture of the bodies' velocities at that callback phase; removed callbacks cannot safely read bodies. Sleeping removes contact reports, and CCD can generate multiple kinds of callback for one pair in a collision step.[^98] Therefore queue stable POD events and deliver gameplay/Blueprint delegates on the game thread, with explicit begin/persist/end/sleep semantics and duplicate handling. Preserve pre-solve point velocity directly for sword logic. Do not feed an estimated impulse into an API whose callers expect an exact normal impulse. Jolt's `EstimateCollisionResponse` is useful for effect intensity but is explicitly approximate for simultaneous interactions involving more than two bodies.[^99]

**S5 — Snapshot preservation does not provide a solved `NormalImpulse`.** The current `UPhysicsHitVelocityLibrary::RetrieveVelAngVel` must have a backend-aware implementation or its callers must consume the captured point velocities directly; keeping its name/signature alone does not make the subtraction algorithm valid. Pinned 5.6.0 `CollisionEstimationResult` contains estimated per-contact normal impulses in `mContactImpulse`, separate tangent friction impulses `mFrictionImpulse1/2`, an angular friction impulse, and predicted velocities.[^99] None is a post-solver contact report. A body's observed pre/post velocity difference also includes other contacts, joints, gravity, external forces and controller writes, so it cannot generally recover one hit's solved normal impulse. If an existing cutting, sound, or damage node requires a solved contact impulse, it needs a separately validated solver-level extraction mechanism or an explicitly agreed gameplay contract change; that requirement is currently unresolved. Record provenance (`sweep`, `pre-solve state`, `estimated response`, or `measured solved contact`) instead of publishing all as an undifferentiated Unreal hit. Speculative Jolt contacts can have negative penetration and produce no velocity change; `Added` alone is not evidence of a damaging impact.[^98]

### Rope and welded noose

**R1 — Retraction preserves the articulation topology.** `ProphecyPhysicsConstraintBlueprintLibrary.cpp:212` caches the PHAT, root `joint`, 27 segment bodies `joint1`...`joint27`, and their parent constraints; it selects `SkipAllBones` so skeletal prephysics will not reset the controlled root. `:165` sets per-particle Chaos solver overrides to 12 position, 2 velocity, 24 projection iterations. `UpdatePotenceRopePhysics` (`:409`) moves the kinematic root through the fixed wood anchor while leaving a full-length constrained chain. Consumed bodies remain dynamic with their mass/constraints but match no collision channels (`:267`); restoring filtering does not recreate their body. Wake occurs on changed retraction input. Do not replace this with removing bodies or shortening joints at segment boundaries: those changes violate the accepted topology and can change tip continuity.

`ProphecyRetractableSkeletalMeshComponent.cpp:45` modifies editable component-space transforms immediately before final render publication, after animation/physics blending; consumed visuals collapse toward the anchor and scale along local Z while bodies are untouched. A Jolt skeletal output path must preserve this hook/order. `ProphecyPotenceRopeVisualComponent.cpp` still exists as an older duplicate poseable-mesh implementation; the journal says the current `A_Potence` uses the single retractable component. Do not infer the old class is production merely because the source exists; asset references settle this.

**R2 — The noose is welded, not held by a compliant fixed joint.** `WeldNooseToRopeEnd` (`:349`) breaks/disables the old constraint and `PerformPotenceNooseWeld` (`:302`) attaches the noose to the terminal bone with welding enabled, waiting for physics state if needed. This is a compound rigid-body relationship; a Jolt fixed joint may have measurable compliance and would not automatically preserve the accepted behavior. Preserve component identity and collision child IDs even if both are represented in one Jolt body, plus world pose, mass, inertia and COM when constructing the compound. Jolt 5.6.0 mutable compounds require controlled mutation and broadphase/cache notification; cached subshape identity also needs revision handling. If the compound COM is adjusted, notify both `BodyInterface::NotifyShapeChanged` and affected constraints through `Constraint::NotifyShapeChanged`. Concurrent queries require shape cloning/replacement or a suitable synchronized mutation boundary; taking a body lock alone does not make concurrent shape traversal safe.[^100][^104][^16] Prefer creating the accepted compound at initial body setup when possible; this is an inference from the one-time weld behavior, not a request to change the asset.

### Boat and legacy character interaction

**W1 — Native wave generation is portable math followed by physics I/O.** `ApplyBoatWaveForces` (`ProphecyPhysicsConstraintBlueprintLibrary.cpp:494-691`) computes three deterministic spatial wave components, sums four virtual-corner forces/torques, applies drift and linear/angular damping, and adds yaw angular acceleration. It reads registration/simulation state, mass, world time, COM, rotation and velocities, then calls `AddForce`, `AddTorqueInRadians` in torque mode and acceleration-change mode. Preserve units (cm, seconds, kg, radians), torque versus angular acceleration semantics, and update cadence. Jolt 5.6.0 has point force/impulse, torque and point-velocity APIs, but linear velocity is explicitly COM velocity; adapters must account for the offset from the Unreal component origin and convert force/torque units consistently.[^104] This is not full hydrostatic buoyancy and does not automatically wire a Blueprint.

**W2 — A retained Blueprint graph shows additional boat controls.** `Saved/Profiling/BoatBuoyancy/BP_Boat_EventGraph.txt` (filesystem timestamp 9 August 2026; 59 nodes) includes Tick -> angular spring -> additive `Set Physics Angular Velocity in Radians` -> linear spring -> additive linear-velocity writes -> `Apply Gentle Boat Wave Forces`; the gate uses boat Z and a `water level` variable. This historical graph demonstrates why wrapping only the native wave function is incomplete. A fresh read-only asset inventory must confirm current links, per-instance settings and functions. Journal wording that the helper is not automatically wired does not imply the Blueprint asset has no manually connected call.

**W3 — Riders require engine-side behavior too.** `Source/ProphecyEditor/Private/ProphecyBoatBuoyancyAutomationTest.cpp:39,203,256,581,686` tests `BP_Boat` with a 90-kg rigid cube and the actual `/Game/_mygame/SandboxCharacter_CMC`; it records sustained movement-base contact. Installed `UE/Source/Runtime/Engine/Private/Components/CharacterMovementComponent.cpp:11570` calls `BaseComp->IsAnySimulatingPhysics()` before applying downward force through `AddForceAtLocation`; `:7697` also handles impact physics forces. A UE query-only representation of a Jolt boat can let the rider find a floor while losing rider load/push forces if these APIs still report no Chaos simulation. Matching actor transforms alone does not prove rider parity. The water cutout material is a separate rendering concern; the journal says moving boats need updated origin/world-to-local parameters.

### Environment, root collision, and inventory gaps

**E1 — Reuse exporter knowledge, not its reduced schema as the final Jolt cook.** `ProphecyExportSimCollision.cpp` already discovers static and instanced meshes, configured simple/complex collision, convex bodies and landscapes. However `FExportedCollisionObject` (`:28`) only retains labels/IDs/class/component/collision-source, vertices and indices. JSON output (`:419`) contains no UVs, source face mapping, physical materials, collision response masks, bone data or dynamic mass properties. It tessellates analytic spheres/capsules, flattens instance transforms into world-space triangle streams, and the landscape path explicitly omits hole/material masks (`:403`). The journal's 701-object/4,158,798-triangle/~600-MB cache is useful prior environment evidence, not a production physics artifact that preserves all gameplay.

Pinned Jolt 5.6.0 mesh construction accepts material assignments and preserved triangle user data, but changes triangle ordering and removes degenerates.[^94] Heightfields support explicit gaps and surface materials; the local export's missing hole masks are a converter gap, not a Jolt limitation.[^101] Preserve negative/nonuniform transforms, triangle winding/backface policy, exact collision-LOD choice, landscape holes, instance identity and runtime creation/removal (including PCG-generated instances). World-space duplicated triangles also discard shape sharing; repeated static assets can share collision shapes once their source and scale are identified. Dynamic concave geometry support and shape restrictions are covered by the core Jolt research and must be considered for boat/sword/cut fragments. Specifically, the pinned mesh header permits a dynamic/kinematic mesh only with explicit mass and inertia and without mesh/heightfield counterparts; it does not make arbitrary concave-versus-concave props supported. Heightfields are not dynamic bodies.[^42][^44][^45]

The cache includes **water quads**, houses/tents, hay, fence-generated instances and mountain geometry (`ProjectJournal.md:198-204`). The complex-export command explicitly bypasses configured collision selection to export underlying triangles (`ProphecyExportSimCollision.cpp:240,259-274,564`). Those triangles were useful to the standalone viewer/navigation, but some are not intended as blocking rigid-body surfaces in Unreal. In particular, `WaterBodyCollision` is configured **QueryOnly/overlap** (`Config/DefaultEngine.ini:163`); converting every exported water triangle into a Jolt static solid would create an unintended floor. A production cook must restore each source component's collision enabled mode, response matrix, simple/complex policy, physical material, source face/UV provenance, stable asset/component/instance key, and streaming lifetime. The existing exported `id`/label/component strings are useful provenance hints but do not encode the complete rebuild/cooking/streaming contract. The `.navbin` navigation artifact remains a planner artifact; it cannot replace collision against contact bodies, slopes, holes, triggers, water, and dynamic props.

**E2 — Root sweeps are implicit engine queries.** `AProphecyAgent::SetManagedRootLowPoint` (`ProphecyAgent.cpp:2910`) calls swept `SetActorLocation`, applies horizontal depenetration of `Hit.PenetrationDepth + 0.5 cm`, then a projected slide sweep. It records whether the blocking component is `WorldStatic` and returns the actual low point to the accepted mover. The shared mover algorithm compiles from `StandaloneSim/sim_core/src/locomotion.cpp` through `ProphecySharedLocomotion.cpp`; porting a physics backend does not require replacing this mover with a new character controller. If Jolt dynamic bodies are absent from the UE query scene, these sweeps will miss them unless query routing or synchronized proxies exist. Combining Jolt and UE query results must preserve closest blocking hit, starting penetration, filtering, ignore-self and component identity; avoid duplicate hits when an object has two representations. Jolt exposes ray, shape cast, overlap and shape collection queries, but those APIs do not themselves install UE `SetActorLocation`/Blueprint compatibility.[^102]

**E3 — The collision-channel manifest is broader than the two agent channels.** `Config/DefaultEngine.ini:164-173` declares `Traversable`, `slided_skel`, `sword_piking`, `sword`, `NiagaraWound`, `sword_only`, `houses`, `ProphecyAgentCapsule`, `ProphecyAgentLimb`, and `floor`; `:163` has a `WaterBodyCollision` query/overlap profile. Retain query channels separately from object channels and derive the combined response of both objects, not simply a broadphase group label. `ProphecyAgent.cpp:2524` and the HalfSim path have different native collision setup, and Blueprint/runtime overrides may change both. Journal intent, local code defaults, and the actual live effective configuration must be recorded separately before choosing a migration baseline; do not silently correct them during the port.

The first matrix is the **journal's intended production contact policy**, recorded at `ProjectJournal.md:138-141`; it is not a claim that current runtime matches it. Its future acceptance gate must verify both participants' responses and physical/query outcomes:

| Intended production pair | Required result from journal |
|---|---|
| Kinematic capsule ↔ Kinematic capsule | Block |
| Kinematic capsule ↔ Physical limb | Block |
| Physical limb ↔ Physical limb | Block, subject to authored self/constraint exclusions |
| Physical capsule ↔ any agent capsule/limb | Ignore |
| Physical capsule ↔ static environment | Block |
| Physical limb ↔ world | Block |
| Kinematic skeletal mesh ↔ anything | No skeletal collision |

The second matrix is the **current native source setup and controlled-experiment gate**. These are source-side settings, not a live effective pair matrix; no Blueprint/current-instance manifest has been run:

| Current native branch/component | Source-side enabled mode and responses | Evidence / acceptance implication |
|---|---|---|
| `ApplyCollisionMode(Physical)` capsule | QueryAndPhysics; all Ignore except WorldStatic Block | `ProphecyAgent.cpp:2533-2537`; root support remains |
| `ApplyCollisionMode(Physical)` mesh | QueryAndPhysics; **all Ignore**; limb object channel | `:2539-2543`; comments explicitly retain bodies/constraints while disabling contacts for drive validation |
| `ApplyCollisionMode(Kinematic)` capsule | QueryAndPhysics; all Block except Visibility/Camera Ignore | `:2547-2552`; pair response still depends on counterpart |
| `ApplyCollisionMode(Kinematic)` mesh | NoCollision; stored response values all Block | `:2553-2554`; stored Block values do not create contacts |
| `EnterHalfSimulation` pose mesh | PhysicsBody object; QueryAndPhysics; all Ignore except WorldStatic, WorldDynamic, PhysicsBody, GameTrace9 Block; gravity true | `ProphecyAgentHalfSimulation.cpp:129-145`; differs from the Physical drive-validation branch |
| `EnterHalfSimulation` capsule | PhysicsBody explicitly Ignore; other responses inherited from setup/prior mode | `:135`; do not infer a complete capsule matrix from this one assignment |

`ProjectJournal.md:181` says skeletal ground contacts remain disabled in the focused controller experiment until explicitly restored. Current HalfSim source sets world contacts and gravity on, so that historical statement cannot override the observed source or prove the live state. The early port gate should reproduce the **selected, recorded experiment baseline**, while the separate later feature-parity gate should validate the **intended production matrix** once its restoration is authorized. This research has not restored contacts, altered profiles, or reconciled the difference. Record effective mesh/body filters, gravity, active mode, Blueprint overrides and call ordering before interpreting either benchmark.

**E4 — Explicit unresolved inventory.** Current complete `A_Sword` cutting graph, `A_Potence` component references, current `BP_Boat` function/instance overrides, all active Niagara emitter targets and collision data interfaces, destructible/cut-fragment behavior, Physics Asset runtime overrides, PCG lifetime/collision settings, landscape holes/materials, CMC/vehicle/Water plugin usage, overlap consumers, network authority and save/load requirements need a future manifest. Source existence and enabled plugins do not prove production use. Native experiment classes and old helper implementations should be labeled retained/experimental unless referenced by the authoritative maps/BPs. This is a bounded gap; it prevents claiming full functionality coverage from C++ grep alone.


## Evidence limits and completion criteria

### What the evidence establishes

A project plugin can access the needed runtime Physics Asset geometry and constraint descriptions on UE 5.7.4, link upstream Jolt, and publish simulation results through project-owned interfaces. Jolt's public rigid-body/controller APIs cover the central character use case. These findings justify a focused implementation prototype; they do not establish compile compatibility or eliminate the specific API gaps described above.

A complete migration means every **used** physics-dependent behavior has a Jolt implementation or an explicitly documented compatibility path, with one authoritative simulator per dynamic body. Unreal may retain rendering, materials, skeleton evaluation, asset authoring and necessary query representations. Keeping those engine services does not require simulating the same articulation twice. Conversely, leaving swords, boat loads, cutting constraints or stock trace consumers disconnected would not satisfy full functionality.

The scope includes retained experimental controls when they are actually used. It does not invent unfinished combat validation, world occlusion, new wound rules, blood normals, per-instance paint support or other features that the journals explicitly leave unimplemented.

### Remaining gaps ranked by impact

| Priority | Uncertainty | Evidence needed to close it |
|---|---|---|
| Critical | Current asset graph coverage | Read-only manifest of reachable Blueprint physics/query nodes, Niagara simulation/collision/export modes, PHAT settings and runtime overrides; historical exports cannot substitute. |
| Critical | Solved contact impulse | Identify every consumer of `NormalImpulse` and impact thresholds. Prove direct pre-solve velocity covers the actual requirement, or implement/validate a narrowly scoped solved-impulse observation path. An estimator is not equivalent. |
| Critical | Exact PHAT semantics | Export body shapes, reference/COM frames, mass/inertia, joint profiles, limits and disabled pairs. Determine whether any used soft angular or Chaos-specific behavior requires an extension or explicitly accepted alternative. |
| Critical | Total performance | Matched 100-agent measurements of solver plus target publication, synchronization, pose output, queries/proxies, events and rendering. No present source establishes the expected speedup. |
| High | Skeletal publication timing | One actual character must preserve rendered bones, NN feedback, sockets, fists, scale handling, sword and a stain on a moving limb at 60/30/5 render FPS. |
| High | World and root interaction | Correct closest-blocking/overlap/penetration semantics, mixed kinematic/dynamic agents, static geometry, water, landscapes, instances and streaming. |
| High | Weapon contact fidelity | Rotation-only sword sweeps, thin targets, self-suppression, victim constraints, repeat callbacks and dropped momentum. |
| High | Boat and rope completion | Rider floor/base and load transfer, additive velocity springs, compound noose COM/inertia and continuous retraction with retained dynamics. |
| High | Cooked/packaged state | Clean package without prior PIE, CPU mesh data needed for skin paint, versioned collision cache, fresh map load and actor/world teardown. |
| Open product criterion | Frame budget and acceptable response envelope | Keep 100 full agents as the known workload and the existing 30 Hz simulation contract. A final rendered FPS target, physics budget and acceptable tuning envelope must be recorded before declaring success; they are not supplied by public benchmarks. |

### Performance evidence has three distinct levels

1. **Open-loop numerical fixture:** both backends consume the exact same recorded moving targets and impulses. This isolates conversion, controller, contact and timing differences.
2. **Closed-loop gameplay:** physical feedback changes subsequent NN inputs. Compare preserved codec/deadband/cadence and accepted response; bit-identical long-run trajectories across different solvers are not a meaningful requirement.
3. **Rendered project workload:** test the real agents, swords, blood, world and retained compatibility overhead on the target laptop. A fast solver alone does not prove physics has stopped limiting the game.

The historical Jolt scaling paper uses 160 powered ragdolls / 3,680 bodies. Its PhysX/Bullet comparison is a separate convex-body scene, and it keeps the best repeats. It is not a Chaos benchmark or a forecast for Prophecy. The official current PerformanceTest is useful for methods and stress cases, while the project-specific fixture is the relevant comparison. [^84] [^29]

Unreal Insights can expose thread waits and custom scopes for target publication, Jolt stepping, pose reconstruction, proxy updates, event delivery and rendering. Report solver wall time, CPU work and total frame time separately; overlapping thread scopes cannot be added as independent elapsed costs. Record p50/p95/p99, repeated interleaved trials, valid/awake body and constraint counts, contact count, overflow/NaN status and full-trajectory errors. [^86]

Jolt's architecture evidence also highlights loading and concurrent queries as major integration concerns. Large-scale world registration and physics access can erase a raw solver win if they introduce avoidable waits. These are reasons to measure the complete dependency path, not reasons to copy a particular thread architecture before profiling. [^85]

### Dependency and evidence maintenance

Jolt's MIT license permits reuse subject to retaining its notice, and donor integration code has its own provenance. A dependency record should retain exact source SHA, license, compiler/CRT, ISA, precision, determinism, library configuration and converter schema. Cooked shape formats can change between versions; 5.6's API-change record already contains serialization and contact-estimate changes. Upgrades therefore require recooking and regression evidence, not merely changing a header version. [^88] [^89]

The following source catalogue is the factual foundation for the separate migration plan. Unresolved items above are concrete prototype or asset-inventory questions; they are not hidden assumptions of completed compatibility.

## Sources

All web sources were accessed **9 September 2026**. Jolt implementation links are pinned to release commit `e77f175595e64cb44218cc9d9d56fc365ad0e36a`; UnrealJolt and the alternative plugin have their own immutable SHAs. Publication dates are retained where available. Undated API/source entries inherit the stated release/commit, not an inferred publication date.

Installed Epic source references are private local evidence for **UE 5.7.4, CL 51494982** and require access to that engine installation. Project paths in the body are relative to the declared workspace unless explicitly rooted; unqualified feature `.cpp` names are in `Source/GameAnimationSample3/Private`. Source line numbers refer to the inspected working state.

### Jolt core

[^1]: Jorrit Rouwe / Jolt Physics. [Release 5.6.0](https://github.com/jrouwe/JoltPhysics/releases/tag/v5.6.0), published 2026-07-11; latest metadata also read from GitHub API `/repos/jrouwe/JoltPhysics/releases/latest` and tag ref API. Release/version, friction, kinematic islands, new motors, scene-dependent optimization limits. Version 5.6.0; accessed 2026-09-09.

[^2]: Jorrit Rouwe / Jolt Physics. [PhysicsStepListener.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/PhysicsStepListener.h). Step dt, ownership, synchronization, permitted operations. Version 5.6.0; accessed 2026-09-09.

[^3]: Jorrit Rouwe / Jolt Physics. [PhysicsSystem.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/PhysicsSystem.cpp). Update job dependencies, force clearing at last collision step. Version 5.6.0; accessed 2026-09-09.

[^4]: Jorrit Rouwe / Jolt Physics. [Body.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Body/Body.h). Direct COM velocity/force/torque units, activation, point velocity. Version 5.6.0; accessed 2026-09-09.

[^5]: Jorrit Rouwe / Jolt Physics. [BodyInterface.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Body/BodyInterface.cpp). Clamped velocity setters, activation, fixed-world endpoint construction. Version 5.6.0; accessed 2026-09-09.

[^6]: Jorrit Rouwe / Jolt Physics. [BodyCreationSettings.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Body/BodyCreationSettings.h). Origin vs COM, initial motion support, damping/caps, mass and iteration overrides. Version 5.6.0; accessed 2026-09-09.

[^7]: Jorrit Rouwe / Jolt Physics. [Ragdoll.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Ragdoll/Ragdoll.h). Articulation API, parts/skeleton mapping, optional self-collision filtering. Version 5.6.0; accessed 2026-09-09.

[^8]: Jorrit Rouwe / Jolt Physics. [Ragdoll.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Ragdoll/Ragdoll.cpp). Motor subtype dispatch, lifecycle, stabilization, pose operations. Version 5.6.0; accessed 2026-09-09.

[^9]: Jorrit Rouwe / Jolt Physics. [PoweredRigTest.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Samples/Tests/Rig/PoweredRigTest.cpp). Actual sample root policy and motors. Version 5.6.0; accessed 2026-09-09.

[^10]: Jorrit Rouwe / Jolt Physics. [SixDOFConstraintTest.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Samples/Tests/Constraints/SixDOFConstraintTest.cpp). World reference motor example and force limits. Version 5.6.0; accessed 2026-09-09.

[^11]: Jorrit Rouwe / Jolt Physics. [SixDOFConstraint.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Constraints/SixDOFConstraint.h). DOF/limit/motor target spaces; absent soft angular limits. Version 5.6.0; accessed 2026-09-09.

[^12]: Jorrit Rouwe / Jolt Physics. [MotionQuality.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Body/MotionQuality.h). LinearCast translation/rotation limitations. Version 5.6.0; accessed 2026-09-09.

[^13]: Jorrit Rouwe / Jolt Physics. [SwingTwistConstraint.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Constraints/SwingTwistConstraint.h). Swing/twist frames and targets. Version 5.6.0; accessed 2026-09-09.

[^14]: Jorrit Rouwe / Jolt Physics. [MotorSettings.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Constraints/MotorSettings.h). Position/velocity modes and force/torque limits. Version 5.6.0; accessed 2026-09-09.

[^15]: Jorrit Rouwe / Jolt Physics. [SpringSettings.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Constraints/SpringSettings.h). Physical vs normalized springs and units. Version 5.6.0; accessed 2026-09-09.

[^16]: Jorrit Rouwe / Jolt Physics. [Constraint.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Constraints/Constraint.h). COM-relative anchors, priority, warm start, shape-change notifications and breakage. Version 5.6.0; accessed 2026-09-09.

[^17]: Jorrit Rouwe / Jolt Physics. [Architecture of Jolt Physics 5.6.0](https://jrouwe.github.io/JoltPhysicsDocs/5.6.0/), sections Conventions and Limits, Big Worlds, Deterministic Simulation. Coordinate/precision/determinism conventions. Version 5.6.0; accessed 2026-09-09.

[^18]: Jorrit Rouwe / Jolt Physics. [Body.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Body/Body.cpp). Mode transitions, COM-target conversion and sleep. Version 5.6.0; accessed 2026-09-09.

[^19]: Jorrit Rouwe / Jolt Physics. [CapsuleShape.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/Shape/CapsuleShape.h). Y-axis and cylindrical half-height definition. Version 5.6.0; accessed 2026-09-09.

[^20]: Jorrit Rouwe / Jolt Physics. [RotatedTranslatedShape.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/Shape/RotatedTranslatedShape.h). Shape frame wrapper. Version 5.6.0; accessed 2026-09-09.

[^21]: Jorrit Rouwe / Jolt Physics. [OffsetCenterOfMassShape.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/Shape/OffsetCenterOfMassShape.h). Independent COM adjustment. Version 5.6.0; accessed 2026-09-09.

[^22]: Jorrit Rouwe / Jolt Physics. [ScaledShape.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/Shape/ScaledShape.h). Scaling wrapper and shape validation. Version 5.6.0; accessed 2026-09-09.

[^23]: Jorrit Rouwe / Jolt Physics. [GroupFilterTable.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/GroupFilterTable.h). Group/subgroup rules and explicit pair table. Version 5.6.0; accessed 2026-09-09.

[^24]: Jorrit Rouwe / Jolt Physics. [ContactListener.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/ContactListener.h). Callback concurrency, lifetime, pre-solve impact data and CCD duplication. Version 5.6.0; accessed 2026-09-09.

[^25]: Jorrit Rouwe / Jolt Physics. [PhysicsSettings.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/PhysicsSettings.h). Solver/tolerance defaults, listener batching and island splitter. Version 5.6.0; accessed 2026-09-09.

[^26]: Jorrit Rouwe / Jolt Physics. [HelloWorld.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/HelloWorld/HelloWorld.cpp). Library lifecycle and setup; sample values are illustrative. Version 5.6.0; accessed 2026-09-09.

[^27]: Jorrit Rouwe / Jolt Physics. [JobSystem.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Core/JobSystem.h). Dynamic job graph/barrier/refcount contract and engine integration cautions. Version 5.6.0; accessed 2026-09-09.

[^28]: Jorrit Rouwe / Jolt Physics. [TempAllocator.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Core/TempAllocator.h). Fixed allocator failure and malloc fallback. Version 5.6.0; accessed 2026-09-09.

[^29]: Jorrit Rouwe / Jolt Physics. [PerformanceTest.md](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Docs/PerformanceTest.md). Exact official fixture and methodology controls. Version 5.6.0; accessed 2026-09-09.

[^30]: Jorrit Rouwe / Jolt Physics. [EPhysicsUpdateError.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/EPhysicsUpdateError.h). Capacity failures and ignored contacts. Version 5.6.0; accessed 2026-09-09.

[^31]: Jorrit Rouwe / Jolt Physics. [Build/CMakeLists.txt](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Build/CMakeLists.txt). Actual 5.6 build defaults. Version 5.6.0; accessed 2026-09-09.

[^32]: Jorrit Rouwe / Jolt Physics. [Build/README.md](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Build/README.md). Header ordering, configurations, defines. Version 5.6.0; accessed 2026-09-09.

[^33]: Jorrit Rouwe / Jolt Physics. [RegisterTypes.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/RegisterTypes.h). ABI version verification API. Version 5.6.0; accessed 2026-09-09.

[^34]: Jorrit Rouwe / Jolt Physics. [RegisterTypes.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/RegisterTypes.cpp). Mismatch diagnostics and required initialization state. Version 5.6.0; accessed 2026-09-09.

[^35]: Jorrit Rouwe / Jolt Physics. [Memory.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Core/Memory.h). Allocator API and alignment contract. Version 5.6.0; accessed 2026-09-09.

[^36]: Jorrit Rouwe / Jolt Physics. [EstimateCollisionResponse.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/EstimateCollisionResponse.h). Estimates and explicit multi-body-contact accuracy limitation. Version 5.6.0; accessed 2026-09-09.

[^37]: Jorrit Rouwe / Jolt Physics. [PhysicsSystem.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/PhysicsSystem.h). Public contact-presence/query/step surface; no observed solved contact impulse retrieval surface. Version 5.6.0; accessed 2026-09-09.

[^38]: Jorrit Rouwe / Jolt Physics. [MotionProperties.inl](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Body/MotionProperties.inl). Force/gravity/damping/clamp order and inertia application. Version 5.6.0; accessed 2026-09-09.

[^39]: Jorrit Rouwe / Jolt Physics. [ContactConstraintManager.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Constraints/ContactConstraintManager.cpp). Restitution's accumulated-force/gravity compensation. Version 5.6.0; accessed 2026-09-09.

[^40]: Jorrit Rouwe / Jolt Physics. [SixDOFConstraint.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Constraints/SixDOFConstraint.cpp). Target clamping, motor-error approximation, motor-off friction/structural constraints. Version 5.6.0; accessed 2026-09-09.

[^41]: Jorrit Rouwe / Jolt Physics. [CharacterVirtual.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Character/CharacterVirtual.h). Virtual-character broadphase visibility and inner-body requirements. Version 5.6.0; accessed 2026-09-09.

[^42]: Jorrit Rouwe / Jolt Physics. [MeshShape.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/Shape/MeshShape.h). Explicit moving-mesh exception, unsupported concave pairs, single-sided simulation, absent submerged-volume support. Version 5.6.0; accessed 2026-09-09.

[^43]: Jorrit Rouwe / Jolt Physics. [MeshShape.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/Shape/MeshShape.cpp). Invalid intrinsic mass/inertia, override example, convex-pair registrations. Version 5.6.0; accessed 2026-09-09.

[^44]: Jorrit Rouwe / Jolt Physics. [BodyCreationSettings.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Body/BodyCreationSettings.cpp). MassAndInertiaProvided vs CalculateInertia behavior. Version 5.6.0; accessed 2026-09-09.

[^45]: Jorrit Rouwe / Jolt Physics. [HeightFieldShape.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/Shape/HeightFieldShape.h). Static-only documented shape contract. Version 5.6.0; accessed 2026-09-09.

[^46]: Jorrit Rouwe / Jolt Physics. [HeightFieldShape.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/Shape/HeightFieldShape.cpp). Default mass properties and convex-pair registrations. Version 5.6.0; accessed 2026-09-09.

[^47]: Jorrit Rouwe / Jolt Physics. [CollisionDispatch.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/CollisionDispatch.cpp). Unsupported-pair default handlers assert and return without a hit. Version 5.6.0; accessed 2026-09-09.

[^48]: Jorrit Rouwe / Jolt Physics. [DynamicMeshTest.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Samples/Tests/General/DynamicMeshTest.cpp). Actual dynamic torus mesh with explicit mass/inertia and box contacts. Version 5.6.0; accessed 2026-09-09.

### Unreal integration and UE source

[^49]: Yadhu-S. [Pinned repository tree / commit](https://github.com/Yadhu-S/UnrealJolt/tree/50e64573548ea829943604138735eee091ea0784), 23 August 2026. GitHub REST `commits/master` and recursive tree verified SHA/date/gitlink on 9 September 2026. Accessed 2026-09-09.

[^50]: Yadhu-S. [README](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/README.md), pinned commit. Requirement, scope, features, landscape packaging. Accessed 2026-09-09.

[^51]: Yadhu-S. [UnrealJolt.uplugin](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/UnrealJolt.uplugin), lines 1–29. Descriptor/modules. Accessed 2026-09-09.

[^52]: Yadhu-S. [JoltSkeletalMeshComponent.cpp](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/Source/UnrealJolt/Private/JoltSkeletalMeshComponent.cpp#L14), lines 14–127, 162–173, 251–255. Single body, first shape, disposal, actor pose. Accessed 2026-09-09.

[^53]: Yadhu-S. [JoltSubsystem.cpp](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/Source/UnrealJolt/Private/JoltSubsystem.cpp), relevant ranges: 43–127 lifecycle; 244–442 initialization/tick/interpolation; 557–725 static/complex meshes; 751–873 primitive shapes; 1242–1249 removal; 1289–1388 queries; 1412–1488 landscapes; 1798–1821 velocities; 2070–2077 torque. Accessed 2026-09-09.

[^54]: Yadhu-S. [Helpers.h](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/Source/UnrealJolt/Helpers.h), lines 7–101 conversions; 135–145 data paths; 196–242 ray collector. Accessed 2026-09-09.

[^55]: Yadhu-S. [UnrealJoltLibrary.Build.cs](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/Source/ThirdParty/UnrealJoltLibrary/UnrealJoltLibrary.Build.cs), full script. CMake/ABI/build/platform settings and UE4CMake attribution. Accessed 2026-09-09.

[^56]: Yadhu-S. [JoltSubsystem.h](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/Source/UnrealJolt/Public/JoltSubsystem.h), custom query/Blueprint APIs, base subsystem, public backend access, pointer maps. Accessed 2026-09-09.

[^57]: Yadhu-S. [JoltContactListener.cpp](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/Source/UnrealJolt/Private/JoltContactListener.cpp), contact estimates/queue/persisted filter/removed TODO; [contact header](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/Source/UnrealJolt/Public/JoltContactListener.h). Accessed 2026-09-09.

[^58]: Yadhu-S. [.gitmodules](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/.gitmodules), SSH dependency URL. Accessed 2026-09-09.

[^59]: Yadhu-S. [MIT LICENSE](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/LICENSE), copyright 2025. Accessed 2026-09-09.

[^60]: Yadhu-S. [Unreal Engine 5 plugin that adds jolt, discussion #1738](https://github.com/jrouwe/JoltPhysics/discussions/1738), 24 August 2025; author's 10 September 2025 reply on no engine source modification and own-project workload. Historical context, not current performance evidence. Accessed 2026-09-09.

[^61]: Yadhu-S. [How to use this correctly, discussion #13](https://github.com/Yadhu-S/UnrealJolt/discussions/13), author replies 14 and 16 July 2026. Authoritative scope of separate physics, minimal UE API integration, shape extraction. Accessed 2026-09-09.

[^62]: Yadhu-S. [JoltPhysicsComponent.cpp](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/Source/UnrealJolt/Private/JoltPhysicsComponent.cpp), creation and `EndPlay`; [header](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/Source/UnrealJolt/Public/JoltPhysicsComponent.h), authoring and Blueprint properties. Accessed 2026-09-09.

[^63]: Yadhu-S. [JoltWorker.cpp](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/Source/UnrealJolt/Private/JoltWorker.cpp), lines 6–58 pool, teardown, synchronous step callbacks. Accessed 2026-09-09.

[^64]: Yadhu-S. [Runtime module build](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/Source/UnrealJolt/UnrealJolt.Build.cs), dependencies and `FPSemantics`. Accessed 2026-09-09.

[^65]: Yadhu-S. [JoltDataAsset.cpp](https://github.com/Yadhu-S/UnrealJolt/blob/50e64573548ea829943604138735eee091ea0784/Source/UnrealJolt/Private/JoltDataAsset.cpp#L14), shape/material state serialization. Accessed 2026-09-09.

[^66]: Jorrit Rouwe. [Jolt Shape.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/Shape/Shape.h#L367), pinned plugin dependency, binary shape version and external-child/material serialization contract. Accessed 2026-09-09.

[^67]: BastienVdW. [Pinned repository tree](https://github.com/BastienVdW/JoltPhysics/tree/74ad1d7f911796e0ec8f197be0622eb77470fdd1), commit 8 September 2026. GitHub REST metadata/tree verified on 9 September 2026. Accessed 2026-09-09.

[^68]: BastienVdW. [README](https://github.com/BastienVdW/JoltPhysics/blob/74ad1d7f911796e0ec8f197be0622eb77470fdd1/README.md), feature and license declarations. Accessed 2026-09-09.

[^69]: BastienVdW. [JoltPhysics.Build.cs](https://github.com/BastienVdW/JoltPhysics/blob/74ad1d7f911796e0ec8f197be0622eb77470fdd1/Source/JoltPhysics/JoltPhysics.Build.cs), source compilation, shared exports, commented compile flags. Accessed 2026-09-09.

[^70]: BastienVdW. [JPRPhysicsSubsystem.cpp](https://github.com/BastienVdW/JoltPhysics/blob/74ad1d7f911796e0ec8f197be0622eb77470fdd1/Source/JoltPhysicsRuntime/Private/System/JPRPhysicsSubsystem.cpp), tick 97–104, globals 114–162, stepping 166–194, fixed constraints 306 onwards. Accessed 2026-09-09.

[^71]: BastienVdW. [CharacterVirtual object](https://github.com/BastienVdW/JoltPhysics/blob/74ad1d7f911796e0ec8f197be0622eb77470fdd1/Source/JoltPhysicsRuntime/Classes/Physics/Character/JPRPhysicsCharacterVirtualObject.cpp), native character construction/update reference. Accessed 2026-09-09.

[^72]: Epic Games. [Third-Party Libraries, UE5.7](https://dev.epicgames.com/documentation/en-us/unreal-engine/integrating-third-party-libraries-into-unreal-engine?application_version=5.7). Retrieved 9 September 2026. Accessed 2026-09-09.

[^73]: Epic Games. [Live Coding, UE5.7](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-live-coding-to-recompile-unreal-engine-applications-at-runtime?application_version=5.7). Retrieved 9 September 2026. Accessed 2026-09-09.

[^74]: [Build.version](<C:/Program Files/Epic Games/UE_5.7/Engine/Build/Build.version>) and `C:/ProgramData/Epic/UnrealEngineLauncher/LauncherInstalled.dat`. Accessed 2026-09-09.

[^75]: [SkeletalMeshComponent.h](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Classes/Components/SkeletalMeshComponent.h:1844>), physics virtuals at 1844, 1871–1872, 1962–1965; pose hooks at 2037, 2076; nonvirtual physics setters 2198–2253. Accessed 2026-09-09.

[^76]: [SkeletalMeshComponentPhysics.cpp](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Private/SkeletalMeshComponentPhysics.cpp:1252>) for body setters; [SkeletalMeshComponent.cpp](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Private/Components/SkeletalMeshComponent.cpp:3766>) for simulation-state scan. Accessed 2026-09-09.

[^77]: [PrimitiveComponent.h](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Classes/Components/PrimitiveComponent.h:1749>) and [PrimitiveComponentPhysics.cpp](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Private/PrimitiveComponentPhysics.cpp:409>), velocity getters; angular implementation at 477. Accessed 2026-09-09.

[^78]: [ModuleRules.cs](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Programs/UnrealBuildTool/Configuration/ModuleRules.cs:777>), `FPSemantics` property exists. Accessed 2026-09-09.

[^79]: [PhysicalAnimationComponent.cpp](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Private/PhysicsEngine/PhysicalAnimationComponent.cpp:259>), targets and constraints 259–434, Chaos actor release 484–491. Accessed 2026-09-09.

[^80]: [WorldSubsystem.cpp](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Private/Subsystems/WorldSubsystem.cpp:39>), default supported world types; [WorldSubsystem.h](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Public/Subsystems/WorldSubsystem.h:61>), support/lifetime methods. Accessed 2026-09-09.

[^81]: [PhysicsInterfaceDeclaresCore.h](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/PhysicsCore/Public/PhysicsInterfaceDeclaresCore.h:76>), Chaos actor alias; [BodyInstance.h](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Classes/PhysicsEngine/BodyInstance.h:681>), physics actor handles. Accessed 2026-09-09.

[^82]: [SkinnedMeshComponent.h](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Classes/Components/SkinnedMeshComponent.h:1636>), editable component-space transform accessor; [SkeletalMeshComponent.h](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Classes/Components/SkeletalMeshComponent.h:2548>), parallel animation state/completion and internal blend path. Accessed 2026-09-09.

[^83]: [PhysicsAsset.h](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Classes/PhysicsEngine/PhysicsAsset.h:204>), runtime arrays; [PhysicsAsset.cpp](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Private/PhysicsEngine/PhysicsAsset.cpp:147>), collision-disable serialization; [BodySetup.h](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Classes/PhysicsEngine/BodySetup.h:136>), runtime geometry, materials, UV/face data and mesh creation; [BodySetup.cpp](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Private/PhysicsEngine/BodySetup.cpp:823>), cooked data serialization; [ConvexElem.h](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Classes/PhysicsEngine/ConvexElem.h:35>), UPROPERTY vertices/indices/transform; [AggregateGeom.h](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Classes/PhysicsEngine/AggregateGeom.h:28>), complete shape family list. Accessed 2026-09-09.

### Additional primary evidence

[^84]: Jorrit Rouwe. [Jolt Physics Multicore Scaling](https://jrouwe.nl/jolt/JoltPhysicsMulticoreScaling.pdf). 2022; updated 2023-03-10. Accessed 2026-09-09. Historical fixture and benchmark methodology.

[^85]: Jorrit Rouwe / Guerrilla. [Architecting Jolt Physics for Horizon Forbidden West](https://jrouwe.nl/architectingjolt/ArchitectingJoltPhysics_Rouwe_Jorrit_Notes.pdf). GDC 2022. Accessed 2026-09-09. Synchronization, streaming and query architecture.

[^86]: Epic Games. [Unreal Insights](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-insights-in-unreal-engine?application_version=5.7). UE 5.7 documentation. Accessed 2026-09-09. Process/thread timing and trace instrumentation.

[^87]: Epic Games. [Coordinate System and Spaces](https://dev.epicgames.com/documentation/en-us/unreal-engine/coordinate-system-and-spaces-in-unreal-engine?application_version=5.7). UE 5.7 documentation. Accessed 2026-09-09. UE coordinate conventions.

[^88]: Jorrit Rouwe / Jolt Physics. [MIT License](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/LICENSE). Copyright 2021 Jorrit Rouwe. Version 5.6.0; accessed 2026-09-09.

[^89]: Jorrit Rouwe / Jolt Physics. [Breaking API Changes](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Docs/APIChanges.md). Version 5.6.0; accessed 2026-09-09. Friction API and cooked binary changes.

### Feature evidence

[^90]: Epic Games, [Particle Update Group Reference — Collision](https://dev.epicgames.com/documentation/unreal-engine/particle-update-group-reference-for-niagara-effects-in-unreal-engine?lang=en-US), default 5.8 documentation; CPU ray versus GPU render-data routes, independently confirmed in local 5.7.4 source. Accessed 2026-09-09.

[^91]: Epic Games, [Events and Event Handlers Overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/events-and-event-handlers-in-niagara-effects-for-unreal-engine), default 5.8 documentation; event-handler restrictions, distinct from export/readback. Accessed 2026-09-09.

[^92]: Epic Games, [GPU Raytracing Collisions](https://dev.epicgames.com/documentation/en-us/unreal-engine/gpu-raytracing-collisions-in-niagara-for-unreal-engine?application_version=5.7), UE 5.7; experimental status, hardware requirement and one-frame latency. Accessed 2026-09-09.

[^93]: Epic Games, [UGameplayStatics::FindCollisionUV](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UGameplayStatics/FindCollisionUV), default 5.8 API page; enabled-support requirement, checked against installed 5.7.4 function implementation. Accessed 2026-09-09.

[^94]: Jorrit Rouwe / Jolt Physics, [MeshShape.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/Shape/MeshShape.h), pinned 5.6.0; triangle reordering/sanitization/winding, materials, original-index storage and memory cost, dynamic-mesh restrictions. Accessed 2026-09-09.

[^95]: Epic Games, [Nanite Technical Details — Fallback Mesh](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-technical-details?application_version=5.7), UE 5.7; fallback/selected LOD complex collision. Accessed 2026-09-09.

[^96]: Jorrit Rouwe / Jolt Physics, [GroupFilterTable.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/GroupFilterTable.h), pinned 5.6.0; per-group subgroup exclusions and enable/disable semantics. Accessed 2026-09-09.

[^97]: Epic Games, [On Component Hit](https://dev.epicgames.com/documentation/en-us/unreal-engine/BlueprintAPI/Collision/OnComponentHit), default 5.8 Blueprint API; simulation hit-notification requirement, normal orientation and swept-hit zero impulse. Accessed 2026-09-09.

[^98]: Jorrit Rouwe / Jolt Physics, [ContactListener.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/ContactListener.h), pinned 5.6.0; worker/locking restrictions, pre-solve callbacks, sleep/removal, speculative contacts, manifold reduction, callback repetition and subshape lifetime. Accessed 2026-09-09.

[^99]: Jorrit Rouwe / Jolt Physics, [EstimateCollisionResponse.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/EstimateCollisionResponse.h), pinned 5.6.0; limited two-body impulse estimate and separate normal/friction/angular-friction result fields; not a solved-contact event. Accessed 2026-09-09.

[^100]: Jorrit Rouwe / Jolt Physics, [MutableCompoundShape.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/Shape/MutableCompoundShape.h), pinned 5.6.0; compound body, COM, child IDs, concurrent query/mutation hazards, body and constraint `NotifyShapeChanged`. Accessed 2026-09-09.

[^101]: Jorrit Rouwe / Jolt Physics, [HeightFieldShape.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/Shape/HeightFieldShape.h), pinned 5.6.0; sample/material data, static-only heightfield, explicit no-collision gap constants. Accessed 2026-09-09.

[^102]: Jorrit Rouwe / Jolt Physics, [NarrowPhaseQuery.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Collision/NarrowPhaseQuery.h), pinned 5.6.0; query families, filter levels and hit-base offsets. Accessed 2026-09-09.

[^103]: Epic Games, [UCharacterMovementComponent](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/UCharacterMovementComponent), default 5.8 API; movement-base velocity and physics interaction. Specific force behavior above is verified in installed 5.7.4 source. Accessed 2026-09-09.

[^104]: Jorrit Rouwe / Jolt Physics, [BodyInterface.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Body/BodyInterface.h), pinned 5.6.0; shape replacement/notification, COM velocity, point velocity/forces/impulses, torque and body lifecycle. Accessed 2026-09-09.
