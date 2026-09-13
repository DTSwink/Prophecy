# Runtime physical joint limits

On a **Prophecy Agent** reference (Self inside its Blueprint), use **Set Physical Joint Angular Limits**:

- **Child Bone**: `hand_r` selects its wrist connection to `lowerarm_r`; `foot_r` selects its connection to `calf_r`.
- **Swing 1 / Swing 2 / Twist Motion**: Free, Limited or Locked, using Unreal's normal PHAT angular axes.
- **Swing 1 / Swing 2 / Twist Limit Degrees**: symmetric angular limits, in degrees. Each number must be finite and between 0 and 180, even for a Free/Locked axis where the number is inactive.
- **Return Value / Out Error**: success or the reason the request could not be applied. Invalid requests leave the rig unchanged.

**Limited 0°** maps to a locked native axis, and **Limited 180°** maps to an unrestricted native axis. This lets you limit just one axis to 1° while leaving the other two at 180°. The requested UE profile values are retained. Other Limited angles must remain between 0.5 and 179.5 degrees because of Jolt's internal thresholds; values strictly between 0 and 0.5, or between 179.5 and 180, still reject the request. Always check the node's result when changing ranges.

Example: `hand_r`, Swing 1 Limited 20, Swing 2 Limited 15, Twist Limited 30 changes only that wrist. Use **Reset Physical Joint Angular Limits** with `hand_r` to restore its PHAT default angular settings. The asset itself is never edited.

These nodes update the initialized physical mesh's runtime constraints in Chaos or Jolt. They retain bodies, joint anchors, authored frame offsets and physical-animation strengths. Jolt updates its existing native joint in place and wakes affected bodies when the ranges change. No new per-frame polling is added.

Selection follows the skeleton hierarchy and actual PHAT endpoints, regardless of endpoint order or joint name. If PHAT skips skeleton bones, the nearest ancestor with a direct constraint to the requested child is selected. Missing joints, root bones without a parent joint, and duplicate connections to the same parent are rejected. This is a single-joint operation, not a descendants operation.

Jolt continues using hard limits. These nodes do not change linear limits, soft-limit stiffness/damping, or the joint's angular frame offset. Existing global **Set Use Authored Angular Limits** overrides these angular settings for all joints. Treat changes as runtime instance settings; a new rig/Physics Asset initialization can restore authored defaults.

For a Prophecy Agent possessed by a PlayerController, eligible limited swing cones also constrain outward velocity while approaching the boundary from inside. NPCs and Free/Locked swing joints retain stock Jolt constraints, with no extra speculative solver callbacks. Possession and runtime range changes update this selection automatically; no extra polling is added. Authored ranges remain intact and no damping is added. Diagnosis and numerical evidence: [Wrist limit snapping](JoltWristLimitSnapping.md).

Use **Set Jolt Joint Limit Prediction Enabled** on the agent to toggle that extra correction at runtime:

- **Enabled = false**: remove the extra predictive swing correction, leaving stock Jolt hard limits active with the same angles and PHAT frames.
- **Enabled = true**: restore it for this player's eligible Limited swing joints. Default is true.

**Is Jolt Joint Limit Prediction Enabled** reads the requested setting. It does not mean the agent currently has an eligible joint: Jolt, player possession and Limited swing are still required. The setting applies to the whole agent and persists across backend changes, possession, and rig recreation on that agent. It can be set in BeginPlay before Jolt admission. It does not change magnetization, physical feedback, simulation mode, or the angular-limit values, and adds no per-frame polling. For the wrist experiment, leave the 170-degree limit nodes connected and call this new node with false.
