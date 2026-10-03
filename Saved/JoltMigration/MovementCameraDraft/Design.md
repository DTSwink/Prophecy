# Movement-only camera hierarchy draft

This patch removes an unused view subtree from capsule transform propagation in explicit native movement-only benchmark fixtures. It preserves every capsule collision query, root update, NN step, physical-feedback sample, rig body/joint, skeletal bone and query receiver. It does not change production defaults, remove camera objects, merge movement operations or claim a measured speedup.

## Exact source finding

The partial actual-NN report [nn_jolt_partial_100_20260909_1346.json](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_partial_100_20260909_1346.json>) records `manager_visual_roots=0.957205555 ms` over 210 completed validation rows. Its 211 world samples include a failed query-validation frame and are not performance acceptance.

[UpdateVisualRoots](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp:3854>) has no normal-path pose-store reads or skeleton retargeting. Each world frame it interpolates roots/yaw and calls the real capsule mover for every agent. Rebase work and an extra `PublishAgentPose` occur only after a blocking movement correction. The successful two-agent real-NN smoke has exactly 60 publication calls across 30 NN steps and 60 world frames: no extra correction publication occurred in that run. The 100-agent partial artifact lacks per-frame publication counts, so it cannot establish that run's correction rate.

[SetManagedRootLowPoint](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyAgent.cpp:3125>) performs a rotation update, a swept translation, optional depenetration/slide and final low-point read. Its boolean return means the primary sweep blocked, not generic movement success. The normal 100-agent workload therefore makes 100 rotation calls and 100 primary translation calls per world frame, with conditional extra movement on collisions. Its floor queries and correction semantics remain unchanged.

UE5.7 already avoids a zero-translation, unchanged-rotation MoveComponent in `Engine/Source/Runtime/Engine/Private/Components/PrimitiveComponent.cpp:3075-3087`. Combining rotation and translation would change which rotation the sweep sees (`InitialRotationQuat` at line3146) and transform/callback ordering. Scoped movement deferral also changes when transforms/overlaps are published. Neither is proposed as an exact-behavior optimization here.

The existing movement-only fixture disables SpringArm and Camera ticks at [PrepareManualAgent](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkManual.cpp:120>) but leaves `Capsule -> SpringArm -> Camera` attached. `USceneComponent::UpdateChildTransforms` (`Engine/Source/Runtime/Engine/Private/Components/SceneComponent.cpp:2882-2923`) still visits and updates attached children regardless of tick enablement. Removing that subtree eliminates two scene-component descendants per changed-root propagation. Stationary roots already benefiting from the engine early-out do not gain two updates per frame, and blocked multi-move frames can propagate more than once. Actual time saved remains to be measured.

## Why this fixture's cameras stay unused

- The native [Agent constructor](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyAgent.cpp:1334>) creates/attaches SpringArm and Camera. A source-wide scan finds no later native Agent camera reattachment or repositioning; Agent Tick performs physics/pose/input work and does not manipulate that subtree.
- These actors are spawned as exact native AProphecyAgent shells, with automatic AI/player possession disabled. The patch additionally refuses possessed actors and any actor currently used as a player-controller view target.
- The actual-NN fixture publishes explicit world-space movement/facing input. It does not derive movement from the unused camera heading. Camera-heading behavior in unrelated Blueprint/player input is outside this patch.
- Actual-NN adoption calls `ConfigureSimpleLocomotionTest`, but collects the prepared agents. Manager line1441 marks this as placed-agent use; [InitializeSimpleTestPlayerView](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp:4040>) refuses that case without PlayerAgent. The fixture does not assign PlayerAgent. This guard prevents later automatic player-camera adoption in the tested path.

## Patch and recorded proof

`MovementCamera.patch` touches three existing benchmark files only; `BaselineHashes.json` records their exact source bytes. It passed `git apply --check` when written. Root owns promotion, build and execution.

After the existing movement-only tick disable, the patch calls `SpringArm->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform)`. Camera remains attached to SpringArm. Both native objects remain registered and owned by the fixture actor, and normal actor destruction cleans them up. No global setting or new default gameplay policy is introduced.

For each actor, setup records actual before/after parent paths, full before/after world transforms, component identities, whether the camera world transforms were preserved, and whether actor/inherited/PhysicalMesh transforms stayed unchanged. Failed setup becomes a fixture error. This setup and JSON recording occur before timed samples.

Existing before/after audits include:

- `movement_camera_detachments`: all captured per-actor evidence.
- `movement_camera_subtrees_detached`: expected Count in a movement-only manual fixture.
- `movement_camera_components_retained_in_detached_subtrees`: expected Count times2.

SaveCase rejects a mismatch between current registered, detached, tick-disabled subtrees and the setup records. A 100-agent run must therefore report 100 detached subtrees and 200 retained camera components. These audits run outside world timing. The top-level movement-only scope text explicitly names the detached subtree, avoiding a hidden workload change.

The same common PrepareManualAgent path applies to synthetic Jolt, actual-NN Jolt and matched ManualCrowd fixtures. Non-movement-only runs retain their original hierarchy. Interactive production camera activation/restoration is not implemented by this benchmark patch; production support would need an explicit per-agent optional-view lifecycle after player selection.

## Validation required

Compile, then run matched actual-NN smoke and 100-agent measurements with identical query padding, GT placement, phase/batch, model and cadence flags. Require actual parent evidence, 100/200 final counts, preserved world transforms, no active view target detachment, full 22/21/88 checks, retained capsule floor collision, 30 Hz full CPU NN and 60 Hz physics/presentation. Compare manager_visual_roots and full world distributions. Existing query and callback gates remain mandatory. No benchmark, policy mutation or active source edit was performed by this subtask.
