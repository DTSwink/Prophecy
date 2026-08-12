# Physics backend decision — 100 Physical agents

Reference workload: 100 authored UEFN agents, 22 bodies and 21 joints each,
pelvis + joint-torque drive, MACD, four-step foot roll, 30 Hz. Current UE 5.7
median is 29.894 ms total and 12.663 ms in the Chaos solver. The 33.333 ms
budget is met, but only with 3.44 ms median headroom.

## Chaos

There is no newly identified Chaos switch worth enabling now. The exact project
benchmark remains more trustworthy than generic forum advice:

| Candidate | Evidence | Decision |
|---|---|---|
| Task push + Partial Jacobi | Measured 5.0% less Chaos CPU together | Still the only CVar candidate; contact behavior must be validated before retaining it. |
| Lower solver iterations | Epic confirms lower counts cost less in isolation; the exact 100-agent test was slower/inconsistent | Do not retain. |
| Async physics | Moves work away from the waiting thread; exact test used 0.9% more solver CPU | Not a capacity gain. |
| Sleep tuning | Helps bodies that come to rest; continuously driven agents remain awake | Useful for corpses, not active Physical agents. |
| Disable CCD | Legitimate global optimization only when no system uses CCD; MACD is separate | Requires a project-wide CCD-use audit, so it was not changed. |
| Linear joint solver and contact manifolds | Epic documents these as the cheaper paths | UE 5.7 already uses them; no new gain. |
| Simpler shapes | Recommended generally | Already done: 18 capsules + 4 boxes, no convex or triangle limb collision. |

The legitimate untested gains are structural:

1. Prune unnecessary **intra-agent** collision pairs in the Physics Asset while
   keeping limb-to-world and limb-to-other-agent collisions. This reduces
   broadphase/contact work without reducing the 22 sampled bodies. It needs an
   explicit collision-behavior test before any asset change.
2. A lower-body Physics Asset LOD would be the largest remaining UE 5.7 lever,
   but it removes true simulated transforms for omitted limbs and therefore does
   not preserve the current NN input contract.
3. UE 5.8 adds graph-colored parallel constraint batches through
   `p.Chaos.Solver.PartitionManager.Partitioning` and better intra-island
   parallelism. This directly targets articulated/contact-heavy workloads, but
   Epic publishes no capacity gain for our case. Test only in a separate 5.8
   copy before considering an upgrade.

Forum reports support collision pruning, primitive bodies, sleeping settled
ragdolls, and the linear solver. Their quoted ragdoll counts are mostly UE
5.0–5.2 and are not used as performance evidence for UE 5.7.

## Box3D

### Raw capacity evidence

Box3D's official `rain` benchmark is materially relevant: it uses articulated
humans with 14 dynamic capsule bodies, 13 limited revolute/spherical joints,
joint springs, contacts, and four solver substeps at 60 Hz. It is not a loose-box
benchmark.

Release build measured locally on the project's i5-12450H:

| Active ragdolls | 1 worker median | 4 workers median |
|---:|---:|---:|
| 90 | 5.483 ms | 1.948 ms |
| 120 | 8.079 ms | 2.618 ms |
| 240 | 12.362 ms | 4.412 ms |
| 270 | 12.839 ms | 4.407 ms |

These are Box3D core step times, not Unreal frame times. The test is lighter per
agent than Prophecy (14/13 versus 22/21), its pose target is not changed by the
NN every tick, and integration/skeletal-pose publication is absent. Therefore it
does **not** prove an exact Prophecy frame time. It does show enough raw margin
that 100 agents are likely feasible inside 33.333 ms; an exact 22-body prototype
is required to confirm the final number.

Box3D's published Ryzen 7950X `rain` result is 2434.57 ms for 400 progressive
steps on one worker and 444.147 ms on eight workers. Community loose-body tests
also report large gains, but they are not used to predict ragdoll cost.

### Physical-animation compatibility

The Box3D core can implement the required behavior:

- spherical joints provide cone/twist limits and a target-rotation spring;
- spring force/torque limits mean limbs physically travel toward targets rather
  than teleporting;
- forces, torques, contacts, hit events, capsules, triangle meshes, heightfields,
  filtering, CCD, fixed stepping, and deterministic multithreading are present;
- the official source includes an articulated human sample using these joints.

It is **not compatible with the current Unreal workflow as a drop-in backend**.
The available Box3DUnreal plugin is early development and supports static-mesh
bodies. It has no SkeletalMesh/PhysicsAsset import, Physical Animation
component, authored joint API, complete Blueprint character API, Chaos↔Box3D
interaction, or replication. Its README explicitly says Box3D bodies simulate
independently while Chaos sees the mesh as static.

A migration would require custom code for:

1. Physics Asset body/shape/joint conversion to Box3D.
2. Per-joint NN target rotations, pelvis drive, and state switching.
3. Reading every Box3D body transform back into the Unreal skeleton each tick.
4. Copying relevant static world collision into Box3D.
5. Moving every interacting dynamic object to Box3D or writing an explicit
   cross-engine interaction layer; the two solvers do not collide automatically.
6. Hit events, queries, debugging, save/replay, and later networking integration.

## Decision

Do not migrate the production agent yet. Box3D is a credible performance backend
and is likely capable of the 100-agent budget, but the present UE integration
does not support our character architecture. The next decision-grade step would
be an isolated exact 100 × 22-body/21-joint Box3D benchmark followed by one
SkeletalMesh pose-sync prototype. Neither is wired into Prophecy by this
research.

Sources:

- Epic physics settings and solver controls:
  https://dev.epicgames.com/documentation/en-us/unreal-engine/physics-settings-in-the-unreal-engine-project-settings
- Epic Physics Asset solver settings:
  https://dev.epicgames.com/documentation/en-us/unreal-engine/BlueprintAPI/Utilities/Struct/MakePhysicsAssetSolverSettings
- Epic Physics Asset collision controls:
  https://dev.epicgames.com/documentation/unreal-engine/physics-asset-editor-in-unreal-engine---tools-and-profiles
- Epic UE 5.8 release notes (parallel constraint solver):
  https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes
- Box3D announcement and Unreal integration caveats:
  https://box2d.org/posts/2026/06/announcing-box3d/
- Box3D simulation, joints, threading, and determinism:
  https://box2d.org/documentation3d/md_simulation.html
- Box3D source and official benchmarks:
  https://github.com/erincatto/box3d
  https://box2d.org/files/benchmarks_3d.html
- Box3DUnreal features and limitations:
  https://github.com/alattanzio/Box3DUnreal
- Box3DUnreal author's firsthand report:
  https://www.reddit.com/r/UnrealEngine5/comments/1vdhc3d/i_replaced_almost_my_entire_unreal_engine_physics/
- Community Box3D comparison and corrected measurement discussion:
  https://www.reddit.com/r/godot/comments/1v2m9g4/box3d_extension_for_godot_16000_physics_bodies_at/
