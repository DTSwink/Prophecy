# Attack fist controls

On a **Prophecy Agent**, under **NN Attack → Fists**:

- **Closed Fist Animation**: `/Game/_mygame/closed_fist`, sampled at time zero.
- **Enable Attack Fists**: on by default. Off leaves the existing finger animation alone.
- **Default Attack Fist Settings**: left/right levels **1**, closing start **0.4 seconds**, opening end **1 second**.
- **Attack Fist Settings**: a Name → Prophecy Attack Fist Settings map. Keys match `Trigger NN Attack`, for example `jabL`, `jabR`, `hookL`, `slashR`. Missing entries use the defaults.

## Blueprint nodes

1. `Make Prophecy Attack Fist Settings`: set **Left Closed Level**, **Right Closed Level**, **Closing Start Seconds**, **Opening End Seconds**.
2. `Set Attack Fist Settings`: Target = your agent; Attack = the attack name; Settings = the struct above. This stores that attack's override on this agent.
3. Use your existing `Trigger NN Attack`. No extra Tick, Timeline, animation node, or hand-closing call is necessary.

Alternatively, edit the map/defaults directly in Blueprint Class Defaults or on an instance. `Get Attack Fist Settings` resolves the override/default. `Get Fist Closed Levels` reads the current interpolated levels.

### Persistent manual control

`Set Fist Closed Levels` → **Left**, **Right**, **Blend Seconds** (default 0.4 seconds).
Call once: the selected levels persist. Both start at **0**. For example, Left 0 / Right 1 / Blend Seconds 0.4 closes only the right fist and holds it. Use 0 seconds for an immediate change, or both levels 0 to open both hands.

The manual node takes hand control even during an attack, without stopping the body attack. The next successfully triggered attack temporarily uses its per-attack levels, then blends back to the saved manual levels. No Tick or Timeline is necessary.

## Exact behavior

- **0**: the mesh's reference A-pose local finger transforms, not a sampled idle animation.
- **1**: the authored closed-fist deformation, including the finger translations edited in Unreal, converted into the fitted mesh's bone coordinate frames.
- Between them: linear translation/scale interpolation and shortest-path quaternion spherical interpolation.
- Only the finger and metacarpal bones are changed. Wrists, arms, root, NN recurrent state, and attack targeting are untouched.
- The closing duration is measured from a successful attack trigger to its requested levels. The end duration starts when the attack completes, is stopped, or aborts, and returns to the persistent manual levels (default 0). Both hands use these durations but have independent target levels.
- Durations are **seconds**, not speed multipliers. Zero duration is instantaneous. Levels clamp to 0–1; durations clamp to nonnegative values. The setter rejects non-finite inputs.
- Settings are captured on each successful trigger. Changing a map entry affects the next trigger, not the attack already underway.
- Retriggering/chaining begins from the currently interpolated levels, including a partially opened fist. It does not reset to the open pose.
- Timing uses world/game time, so repeated pose evaluations at the same time do not advance closing, and game pause/time dilation are respected.
- Full and half attacks use the same fist lifecycle. The finger layer is applied after the NN/overlay pose, before the mesh's existing physics blending.

The clip was authored on the raw Blender-axis validation rig, while the keeper uses native UEFN bone axes. Their joint positions match but many finger axes differ by 90–160 degrees. Copying local tracks is incorrect. The runtime preserves skin deformation using `TargetBindCS * inverse(SourceBindCS) * SourceClosedCS`, then rebuilds local finger transforms relative to the converted parent. The mesh's own reference skeleton is authoritative, not the shared Skeleton asset's stock joint positions. This conversion is not a general proportion-changing retargeter.

## Implementation

`ProphecyAttackFistTypes.h` contains Blueprint settings. `ProphecyAttackFists.cpp` owns lifecycle interpolation and immutable animation-worker snapshots. The NN animation proxy applies those snapshots without changing its live native allocation layout. The existing Slash runtime reports successful starts and stops. No new animation Blueprint or extra mesh is created.

Snapshot storage uses a lazy, process-lifetime allocation so its lock outlives animation-proxy destruction during reload/shutdown. After the Live Coding cleanup crash, the startup DLL was rebuilt successfully with Unreal closed before the authorized reopen; the new nodes are included in that base build.

Engine references: [local pose blending](https://dev.epicgames.com/documentation/unreal-engine/blending-animations-in-unreal-engine?application_version=5.7); UE 5.7 `UAnimSequence::GetBoneTransform` and `FQuat::Slerp`.

## Verification status

The corrected `TestFistDeformation.py` audit passed 12 open/closed/held/reopened checks across Kinematic, Half Sim and Sim. It compares 38 rendered finger bones using skin-space probes against the actual source animation editor pose, rather than comparing incompatible local tracks. Maximum probe error: **0.00005766 cm**. Persistent levels and independent partial levels also passed. Report: `Saved/AttackFists/deformation_audit.json`. The user visually confirmed the final fist works.

In manual Sim, a reference-local animation proxy supplies the finger layer while physics continues owning body bones; no NN target mesh or duplicate character is created. Natural attack-completion timing was not proven by the older lifecycle harness (its timeout is not a passing test). No map, source pose or skeleton was modified by these tests.
