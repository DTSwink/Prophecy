# Combat contact investigation — 2026-09-17

Follow-up: visible hand/head penetration was subsequently reproduced and an optional collision-substep node installed. See [JoltCollisionSubsteps.md](JoltCollisionSubsteps.md). The earlier findings below describe the initial investigation.

## Changes installed

**Combat return and the registered magic cube.** Attack and defense return already moved the root to the flat feet midpoint, but did not reset the registered cube. The handoff now places the cube at the resulting root XY (retaining its collider height), clears its linear/angular velocity in both the UE command path and native Jolt body, and clears the stale first linear magic term. Angular magic and independent magic set 2 are preserved. Unregistered agents are unaffected. No extra per-frame cube work. Bounds corrections during ordinary locomotion still shift the cube by the same correction, preserving their previous behavior.

Normal completion, cancellation and defense return use this handoff. Attack inference failure exits now use the same stop function instead of bypassing cleanup. Direct mode replacement with `bReturnToLocomotion=false` does not recenter/reset.

**Set Locomotion Auto Run Speed Threshold / Get Locomotion Auto Run Speed Threshold.** Per-agent, default **100000 cm/s**. Above the threshold, the run checkpoint wins over walk intent and the existing low-speed walk override. At/below it, existing selection applies. Speed is the planar distance from root0 to root1 divided by the NN timestep, from the final input window after smoothing, magic and speed limiting. A teleport does not count as velocity. This selects the checkpoint; it does not change the user's mover speed/input. Existing directional blend times apply. Negative/nonfinite thresholds are rejected. Configuration uses sparse weak-agent storage; no tick, timer or extra NN evaluation outside the existing blend rules.

## Hook/head investigation

The editor was already in the requested sword setup (possessed pawn X=500, `bool debug 1=false`). For a disposable hook capture, the possessed pawn was temporarily placed at X=0 opposite the other combat agent. Five full hook attacks alternated left/right, targeting the defender's current physical head, with Dodge queued through the existing Armed gate. This was a controlled reproduction attempt, not an untouched replay of the Blueprint's random sequence.

Both meshes were physical Jolt bodies. With hit notifications enabled on both, **39 cross-agent PhysicalMesh callbacks per side** were recorded, including attack-time contacts. The hit bridge is therefore operational; this does not establish that every fast contact is detected. The nearest sampled hand/head **body origins** were 19.30 cm apart, which is not a collider separation measurement. This capture did **not** establish a complete missed hook/head crossing. Self-collision callbacks were counted separately.

Evidence: `Saved/Diagnostics/HooksAttacks.json`, `capture_hooks.py`. The earlier `Hooks.json` contains only idle contacts and is not attack evidence. Notifications are opt-in; enabling them does not improve collision detection.

## Sword/static cube investigation

Repeated 211-frame captures used the possessed pawn at X=500 and `bool debug 1=false`. Native mode was **Discrete**. The sword component's `Use CCD` flag is true, but the agent's explicit Discrete override also covers its welded carrier: the component flag alone is misleading here.

The reported frame-90 jump was **not reproduced**. During ticks80–110 the largest sword rotation change was 0.42 degrees/frame, and sword-origin translation stayed below 0.06 cm/frame. A different, reproducible large rotation occurred during startup:

| Temporary test | Largest startup sword rotation/frame | Tick80–110 maximum |
|---|---:|---:|
| Current 60 Hz collision stepping | 61.61 degrees | 0.42 degrees |
| Same, obstacle moved away | 35.90 degrees | 0.028 degrees |
| 120 Hz collision stepping, Discrete | 59.97 degrees | 0.038 degrees |

The obstacle produces native contact impulses from approximately0.033–0.317 seconds. Removing it reduces the startup rotational spike but does not eliminate initial pose settling. Doubling collision frequency improves the later small jitter in this capture; it does **not** fix the startup jump. No performance measurement or general stability claim follows from this test.

The current held sword is welded to the hand. The hand's animation-following velocity drive still pulls toward its target each physics step; a blocked blade and an incompatible hand target can therefore produce abrupt corrections. This is a plausible mechanism to investigate for later contact jumps, not a proven diagnosis of the unreproduced tick90 event. Collision-free initialization and a short drive-strength ramp address startup settling; temporarily reducing the hand/arm angular magnetization is another controlled test for target/contact conflict. None of those behavior changes was applied automatically.

Evidence: `Saved/Diagnostics/SwordJump_baseline.json`, `SwordJump_cubeoff.json`, `SwordJump_discrete.json`, `SwordJump_discrete120.json`. The cube-off test moved the obstacle away temporarily; its authored transform was restored.

## Non-CCD options from official Jolt sources

- **More collision substeps** rerun detection and integration at smaller intervals. They can be enabled only during a relevant phase, but affect the shared world rather than just one agent. Extra solver iterations instead improve resolution of contacts already found; they do not fill gaps between collision-detection samples. Existing target interpolation must remain aligned with the chosen substep duration. [Jolt architecture](https://github.com/jrouwe/JoltPhysics/blob/master/Docs/Architecture.md), [official simulation loop](https://github.com/jrouwe/JoltPhysics/blob/master/HelloWorld/HelloWorld.cpp).
- **Speculative contact distance** creates contacts before overlap, but increasing it excessively causes false early contacts. Jolt's default is2cm. Penetration slop defaults to2cm and permits visible sinking; reducing it concerns resting/contact resolution rather than detecting a body that crossed completely between samples. Position-correction distance controls correction magnitude, not detection frequency. These are world settings in the current integration. [Jolt PhysicsSettings](https://jrouwe.github.io/JoltPhysicsDocs/5.3.0/struct_physics_settings.html).
- **Gameplay-only swept PHAT checks while Armed** are a separate option for reliable hit reporting without stopping the physical object. The existing kinematic-defense helper already supports authored PHAT/sword shapes and translation plus rotation sweeps. Reusing it selectively would require explicit victim/pair selection, deduplication and a separate event contract; a detected sweep has no solved physics impulse and should not be silently reported as one. This is a project-specific proposal, not a feature installed by this change.
- Jolt **LinearCast** uses the initial orientation for its cast and clips travel at contact. Thus it does not solve all long, rotating-sword crossings and can exhibit the stopping behavior the user dislikes. [Jolt MotionQuality](https://jrouwe.github.io/JoltPhysicsDocs/5.3.0/_motion_quality_8h.html).

Recommendation: trial an opt-in120Hz collision mode for physical response, or an Armed-only swept detector if the priority is hit registration. Neither is a guaranteed solution for an initially overlapping sword or a drive pulling it through an obstacle. No automatic quality setting, CCD change, collider enlargement or sweep event was installed.

## Validation and preserved state

- Live Coding installed the code without restarting Unreal (318.39s build, serial memory-limited compilation).
- Three focused automation tests passed: `Prophecy.NN.PolicyBlend.DirectionalTiming`, `Prophecy.Root.PelvisBounds.PlanarCircle`, `Prophecy.Root.PelvisBounds.CombatReturn`.
- Disposable physical-Jolt PIE smoke: default threshold100000; 300cm/s magic speed with walk intent and threshold100 selected `(walk=0, run=1)`; stopping an attack after deliberately introducing cube error produced exactly0cm XY error, zero first magic velocity, and preserved magic2 `(12,34,0)`. Cube height remained95cm. Evidence: `Saved/Diagnostics/CombatHandoffSmoke.json`.
- Python's cached class wrapper did not list the new functions after Live Coding; reflection `call_method` successfully exercised the installed UFunctions. No editor restart was needed.
- All test PIE sessions and settings changes were owned and cleaned up. No Blueprint/map save, permanent transform/collision edit, or Git push was performed.


## Sword follow-up, 2026-09-18

Fresh unchanged-scene capture (no hit-event opt-in, no CCD changes) retained the possessed agent's visible sword throughout 241 frames. Unreal viewport screenshot at tick89: `Saved/Screenshots/WindowsEditor/HighresScreenshot00017.png`. Windows computer-use screenshots failed with `SetIsBorderRequired`; the screenshot was obtained through Unreal HighResShot instead.

The authored mesh local tip estimate `(0,0,76.286438)` transformed with displayed sword scale/rotation/position lies approximately2.039cm beyond the cube's front plane at tick90 and1.9999cm at tick120. This is a visual blade-tip/plane measurement, not a separately sampled native whole-hull penetration depth. The cube is unrotated and the sampled tip is inside its X/Z extents at these frames.

A disposable second PIE changed only native world penetration slop from2cm to0.1cm at tick60 using the existing development ContactExperiment command. Tip depth fell to0.1253cm at tick90 and0.1035cm at tick120. This supports penetration allowance as the cause of the persistent shallow visual clipping. No CCD was enabled. This does not prove a fix for the user's reported later jump.

The exact tick90 jump still was not reproduced: baseline max sword rotation between ticks80–110 is0.4193degrees/frame and translation0.0508cm/frame. Largest rotation remains61.6106degrees at tick5. At tick5 the estimated tip is35.06cm past the cube front plane, consistent with severe startup overlap, though this estimate alone does not establish the entire native contact response mechanism. A smaller3.948degree motion occurred at tick68.

Evidence: `Saved/Diagnostics/SwordJump_current_observed.json` and `SwordJump_slop01_observed.json`, both241frames and no capture error. Baseline preserved; slop experiment ended with its disposable world. No Blueprint/map/source edits, no build or restart.
