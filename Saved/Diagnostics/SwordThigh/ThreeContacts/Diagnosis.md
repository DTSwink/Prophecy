# Current contact diagnosis — 13 September 2026

Read-only capture of the possessed BP_ProphecyManualPoseAgent, current saved testNN setup, ticks95–140. Physical Jolt, attached sword, attached inertia1, no attack. No gameplay/native implementation or settings were changed. Scripts only start/stop PIE and read state.

## Confirmed

- At115, lowerarm_r/thigh_r effective rig self-collision is enabled, with PhysicsBody blocking.54 sampled points lie inside BOTH UE query colliders. Thus this is actual collision-volume overlap, not just skin outside PHAT geometry. UE bone positions and native body positions agree (within printed0.0001cm); query bodies are the synchronized receiver geometry, not native contact-manifold telemetry.
- Sword centerline samples are inside thigh_l at110,115,120,125 (3/4/5/7 of41 points respectively). At125 there are also5 samples inside thigh_r. These samples establish penetration, not its exact native contact depth or missed-contact cause.
- At125, physical lowerarm-origin to hand-origin distance is43.136cm; at95 it is22.550cm. Historical scaled wrist anchor offset is22.349cm (Saved/Benchmarks/jolt_scope_rig_32channels_20260909_0819.json); using that historical offset estimates a22.647cm anchor gap at125. Exact current native anchor telemetry was not exposed to Python, so the historical-offset estimate must not be claimed as a current direct anchor measurement. Runtime wrist linear axes are all Locked. Physical and visual bone origins agree. This is real physical chain separation.
- Shoulder/elbow/wrist angular axes are Free in the current runtime constraint descriptors. Global linear and angular magnetization strengths are1 and magnetization enabled; absent arm overrides use native defaults1. Thigh overrides also use1. Each body's magnetization rewrites target-tracking velocity independently before Jolt's solve; there is no explicit arm-chain policy that preserves the wrist by preferentially rotating the upperarm.
- At125, hand angular speed is2475deg/s; forearm1297deg/s. Fast rotation makes sword rotational CCD coverage relevant.

## Implementation facts and diagnosis limits

The integration leaves Jolt PhysicsSettings at10 velocity iterations,2 position iterations and0.02m penetration slop. Rig-captured UE iteration values are not applied as Jolt overrides. The current wrist UE profile has projection enabled (linear alpha1); the hard-joint converter explicitly does not implement Chaos projection. Body inertia conditioning IS imported; do not confuse this with all Chaos per-joint stabilization features being implemented.

Jolt LinearCast handles translation and does not continuously sweep a long object's complete rotation (official docs: https://jrouwe.github.io/JoltPhysicsDocs/5.3.0/index.html#autotoc_md33; CCD section). Weld admission promotes the carrier hand to sword LinearCast quality. Therefore enabling CCD alone is not a complete answer to rotating blade penetration. Default slop documented at https://jrouwe.github.io/JoltPhysicsDocs/5.3.0/struct_physics_settings.html and confirmed in pinned local source.

Evidence points to competing full-strength per-body pose tracking, contact/joint convergence and coarse contact tolerance; rotational CCD can additionally miss sword sweeps. Individual contributions are not isolated because this pass intentionally changes no settings. A larger inertia factor only changes angular response; it does not tighten penetration tolerance or locked-joint convergence.

## Proposed order, not implemented

1. Record native contact depths/impulses and exact wrist/elbow anchors in the same115/125 scene; distinguish late/missed detection from detected contacts losing the solve.
2. Address fight-scale penetration tolerance and rotating-blade contact detection according to that evidence.
3. Make the arm's locked positional constraints converge under contact and pose drive, using targeted solver work first. If drives still overpower the chain, make drive effort yield within the constraint solve so the shoulder/elbow can move while the wrist stays connected. Do not hide separation by moving the rendered hand or blindly add more sword inertia.
4. Recheck all three errors together in the unchanged scene. No fixed improvement or performance result is claimed yet.
