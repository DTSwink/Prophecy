# Query-tree padding experiment — source-only draft

Read against installed Epic UE 5.7 source on 2026-09-09. No engine/project source edits, builds, editor launches, setting changes or performance runs were performed by this subtask. The actual-NN timing supplied by the parent is diagnostic evidence for where to investigate; this note does not turn a failed-frame value into an accepted mean or assert a speedup.

## Deliverable and promotion boundary

- `Launcher.apply-patch.txt`: isolated patch to `Tools/NN/RunSterilePhysicsBenchmark.ps1`.
- `Report.apply-patch.txt`: isolated patch to `Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmark.cpp`.
- Launcher active baseline SHA256: `D55D1FEC0E3E1F662BB19D3708D8BBBCFFDCEEB8B3A373048E2D9448CA6C9927`.
- Native benchmark active baseline SHA256: `4EE9E5082470E182C69B4650F17DAFDEDF31243F0AFC0BB9186E31F2526B208B`.

Both patches were applied to strings in memory with every hunk required to match exactly once. The resulting PowerShell parsed with zero AST errors. Four isolated argument-builder cases passed: neither option, CSV only, padding only, padding plus CSV. None included or executed `Start-Process`. The builder emits exactly one quoted `ExecCmds` argument, preserves CSV's original commands/frame count, and formats numeric padding using invariant culture. Active hashes were unchanged after checks. Native changes remain uncompiled until the parent builds them.

`-QueryTreePaddingCm 5`, `20`, or `40` is an explicit launcher experiment for JoltLive/JoltCrowd/NNJoltCrowd. Omitting the argument does not set the CVar, even though the optional numeric parameter's displayed default is 5. Values must be finite and within 0–1000 cm. The launcher also passes a separate `PhysicsBenchQueryTreePaddingCm` provenance argument; native code does not set the CVar. Native measurement-start and case-end checks refuse an explicit request if the runtime CVar is absent or differs. Before/after audit objects and the final report independently read actual settings. Existing audits also count native skeletal actor spatial bucket/inner indices outside the timed world interval.

The CVar is process-global to Chaos dynamic trees, including relevant capsule/tree work. It is not a Jolt solver setting or a private per-character setting. No production default or ini is changed. Baseline and treatments should use the same compiled binary, processor-placement option, priority, modes, sample/warmup counts and rendering configuration. Retain all existing current-pose, controlled-scene-query, capsule and blood correctness gates. Record query/world costs; do not report a reinsert count that was not measured.

## Source contract: existing fat nodes preserve current exact bounds

All engine-relative paths below are under `C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/`.

| Source | Verified behavior |
| --- | --- |
| `Experimental/Chaos/Private/Chaos/AABBTree.cpp:28–35` | `p.aabbtree.DynamicTreeBoundingBoxPadding` defaults to 5 cm; leaf capacity defaults to 8; dynamic leaf enlargement defaults to 0.1. The CVar's stated purpose is amortizing updates through extra dynamic-tree bounds. |
| `Experimental/Chaos/Public/Chaos/AABBTree.h:224–235` | A dynamic leaf's aggregate bounds additionally grow by the leaf extents times `DynamicTreeLeafEnlargePercent * 0.5` on each side. Therefore 5 cm is not the only source of containment margin. |
| `.../AABBTree.h:1390–1393,1458–1459,1651–1654,1754–1757` | Dynamic node insertion/refitting thickens node bounds by the padding CVar. Changing the variable does not proactively resize every existing node. |
| `.../AABBTree.h:1938–1979,2005–2009` | When the new exact actor AABB remains inside the padded dynamic leaf node, update replaces constituent bounds and returns without remove/reinsert. Escaping the node removes and reinserts. |
| `.../AABBTree.h:469–483` | The leaf update stores the new exact element bounds and payload, and marks the leaf dirty. It does not replace exact element bounds with the padded node bounds. |
| `.../AABBTree.h:386–416` | Leaf overlap/raycast/sweep traversal tests individual exact element bounds before visiting actual shape geometry. Larger parent bounds may visit extra leaves, but do not enlarge shape geometry or make exact body bounds stale. |

Nonnegative additional padding is conservative for the broadphase. Geometric query coverage and the narrowphase remain based on the current body/shape state; all 22 updates and queries continue. The added candidate traversal may cost more, and tie ordering among geometrically equal candidates is not an identity guarantee. The experiment must pass actual functional queries. It should not assume every extra cm translates into a proportional improvement.

The observed 3.33 cm/frame root travel makes repeated containment exits a plausible explanation for part of the moving-NN cost, especially with limbs, but actual nodes group up to eight elements and have the percentage margin above. No reinsertion rate has been measured. The query-update phase also contains validation, body writes, exact shape bounds and solver-pending updates, so its entire duration is not removable tree reinsertion work.

## Bucket verification and actual runtime provenance

| Source | Verified behavior |
| --- | --- |
| `Experimental/Chaos/Private/Chaos/PBDRigidsEvolution.cpp:37–51` | Defaults: query-only isolation 0; static/dynamic split 1; dynamic-tree use 1; dirty dynamic tree 1; overlapping-leaf caching 1. |
| `Experimental/Chaos/Public/Chaos/PBDRigidsEvolution.h:38–69` | Default broadphase type is Tree (1). |
| `Experimental/Chaos/Private/Chaos/PBDRigidsEvolution.cpp:78–110` | Dynamic and DynamicQueryOnly inner buckets use a dynamic tree when that CVar is enabled. Other buckets need not use the same update route. |
| `PhysicsCore/Private/ChaosEngineInterface.cpp:2423–2495` | Nonstatic actors use a dynamic particle even when kinematic. With normal split=1/isolation=0 they get the Dynamic inner index at actor creation. |
| `Experimental/Chaos/Public/Chaos/SpatialAccelerationCollection.h:19–24` | Inner indices: Default=0, Dynamic=1, DefaultQueryOnly=2, DynamicQueryOnly=3. |
| `Experimental/Chaos/Public/PhysicsProxy/SingleParticlePhysicsProxy.h:289` | The external handle exposes read-only `SpatialIdx()`. `Chaos/GeometryParticlesfwd.h:58–67` exposes the actual `Bucket` and `InnerIdx` members. |

The bridge retains the native PHAT actors created while the mesh was dynamic; QueryOnly handoff does not itself demonstrate recreation/migration to a query-only bucket. Do not infer isolation from the current component collision mode or add an isolation toggle as if it necessarily moves existing actors. The draft reads native indices into `skeletal_actor_spatial_buckets` so the actual 2200-body distribution can be inspected, alongside actual runtime CVar values. Source/defaults and no discovered local config overrides are not substitutes for those runtime fields.

`UnrealEngine.cpp:2248` queues startup ExecCmds. `Launch/Private/LaunchEngineLoop.cpp:6078` executes them through `UEngine::TickDeferredCommands` (implementation at `UnrealEngine.cpp:2472–2495`). Thus the setting is deferred rather than guaranteed before every actor is created. Existing warmup is retained. Native boundary validation proves the requested value was active by sampling, but is deliberately labelled a CVar snapshot rather than a measurement of every existing node's margin. Older leaves adopt the new padding when inserted/refitted; account for that startup transient when interpreting the experiment.

## Current query publication has no duplicate 2200-body parent update

The active `ProphecyJoltQueryPose.cpp` uses exact cached actors, bone indices, geometry and scale checks. It writes each actor's X/R, updates per-shape bounds, and makes one scene acceleration update call for the mesh. It cleared retained V/W/kinematic targets at initialization; it does not repeat that clearance every frame.

The active character handoff selects `KinematicBonesUpdateType=SkipAllBones`. `Engine/Private/SkeletalMeshComponentPhysics.cpp:1697–1740` calls the skeletal kinematic-update route on component/parent movement, but `Engine/Private/PhysicsEngine/PhysAnim.cpp:538–561` returns early for SkipAllBones except a teleport of a simulating mesh. The retained bridge receiver is nonsimulating QueryOnly. Consequently ordinary parent capsule travel does not trigger another complete native PHAT query-body update through that route. Component transform propagation, bounds/overlap work and the capsule's own update can still occur and remain distinct work.

The following apparent duplication cannot simply be deleted:

- `PhysicsProxy/SingleParticlePhysicsProxy.h:1178–1191`: X/R setters do not themselves update shape bounds.
- `Chaos/ParticleHandle.h:2866–2879`: `UpdateShapeBounds()` updates each shape's world bounds.
- `PhysicsCore/Public/SQVisitor.h:219–259`: multi-shape rays/sweeps use these per-shape bounds before geometry intersection.
- `PhysicsCore/Private/ChaosScene.cpp:236–277`: the scene's public batch API computes the aggregate actor geometry AABB, updates the external acceleration structure, then queues solver-side mirror updates for each actor.
- `Experimental/Chaos/Private/Chaos/Framework/PhysicsSolverBase.cpp:354–367`: solver-pending updates retain operation/index/handle/timestamp keyed by native identity.

Per-shape bounds and aggregate actor bounds serve different consumers. The public scene API has no observed precomputed-AABB overload. Manual containment caching outside the tree cannot replace the scene call because it would omit exact constituent/payload and pending-mirror updates. `AABBTree.h:1867–1885` provides `NeedUpdateElement`, but the engine uses it to prune internal pending data (`PBDRigidsEvolution.cpp:625–636`); it is not a reason to skip the required GT scene update.

## Existing statistics and proof boundary

`PhysicsCore/Private/ChaosScene.cpp:455–476,516–539` collects structural/dirty statistics. Existing `ChaosPhysics` CSV fields include dirty elements, dirty-grid overflow, too-large elements and nonempty cells. Optional `AABBTreeExpensiveStats` adds maximum leaves/depth/leaf size/global payload size and its own traversal cost. Neither is a per-frame dynamic remove/reinsert counter. `AABBTree.h:1897` has a commented-out `AABBTreeUpdateElement` CSV timer; this draft does not enable it or patch the engine. No expensive stats category is enabled by default.

The useful result is therefore a same-binary comparison with verified runtime settings, actual bucket placement, retained full correctness coverage and measured query/world CPU changes. Any attribution specifically to fewer reinserts remains an inference unless independent native instrumentation later supplies counts.
