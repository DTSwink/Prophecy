# Runtime joint angular damping

- **Set Jolt Joint Angular Damping** — Agent, Child Bone, Damping, Return Value / Out Error. `hand_r` selects the hand's inbound PHAT joint to its parent, using the same parent-joint lookup as runtime joint limits. It does not modify the elbow or descendants.
- **Set Jolt All Joints Angular Damping** — Agent, Damping, Return Value / Out Error. Applies to all anatomical PHAT joints in that agent's rig, excluding sword grips/external joints.

Call after the character has a healthy live Jolt rig. These nodes operate on Jolt, not Chaos. Agent-node values now survive rig recreation within the same agent lifetime. Snapshots, single/Below/All blends and returns are described in [joint profile blends](JointProfileBlends.md).

**Damping = 0** is the current/default behavior: no added joint damping, native angular motors off. Positive values resist the child's angular velocity **relative to its parent**, equally along all three angular axes. Common rotation of both bodies is not body drag. The value is a mass-normalized rate in inverse seconds, not a 0–1 strength or damping ratio. For an isolated free axis, one step retains approximately `1 / (1 + Damping * dt)` of relative angular velocity. `6` is therefore noticeable damping; larger values resist faster. Real contacts, magnetisation and hard joint limits also affect motion.

Implementation uses stock SixDOF **PositionAndVelocity** motors with zero target velocity, zero stiffness, and MassNormalizedStiffnessAndDamping settings. Position-only mode ignores zero-stiffness damping in this Jolt version, so it is deliberately not used. There is no target-angle attraction, added spring, changed hard limit/frame, polling, Blueprint Tick controller or separate force pass. The native implicit constraint solver applies the reaction to both bodies. At zero, no added motor rows are solved. Same-value requests don't reset impulses or wake bodies; retuning clears only motor impulses, leaving limit/anchor warm starts intact.

Invalid/negative/nonfinite inputs and missing joints fail. All-joint requests visit anatomical inbound joints; a backend failure can stop the operation after earlier joints were updated. Existing authored body damping, magnetisation, physical materials and limits are untouched.

Minimal validation: compile/load plus `Prophecy.Jolt.Joints.AngularDamping` (default no-op, no spring attraction, analytic damping decay, same-value no-op, zero restoring undamped velocity). Extensive gameplay testing remains with the user.

Validated 2026-09-14: Live Coding build and module patches succeeded, reflected Blueprint library loaded, and the single native AngularDamping test passed. No editor restart or gameplay/performance run; existing unsaved Blueprint edits preserved.

Crash recovery 2026-09-14: subsequent PIE failed at subsystem CDO type validation after Live Coding re-instanced ProphecyJoltWorldSubsystem. Recovered with a normal Editor build and fresh process; current testNN then passed a 120-frame PIE-start/stop check. Do not Live-Code reflected changes to this existing subsystem again; use a normal build for this known reinstancing hazard. The earlier native test alone did not cover world creation.

## Automatic locomotion profile (2026-09-14)

Use **Set Jolt Joint Locomotion Damping** instead of the constant node when state-dependent damping is wanted. Pins: Agent, Child Bone, Walk Sheathed, Run Sheathed, Walk Drawn, Run Drawn, Out Error / Return Value. Same nonnegative rates and inbound-joint selection (lowerarm_r = right elbow). Drawn is the actual held-sword state used by the upper NN; Sheathed includes having no sword. The actual published Walk/Run checkpoint weights blend the selected pair, including speed-based checkpoint overrides.

**Set Jolt Joint Locomotion Damping Below** has the same four values, plus Parent
Bone and Include Parent. It selects inbound PHAT joints on descendant bones;
Include Parent also selects the named bone's inbound joint. For lowerarm_l,
false selects the wrist and true selects elbow plus wrist on the current PHAT.
Bones without anatomical joints are skipped. Return Value counts changed joints;
Out Error reports invalid values or unavailable joints. Selection runs only when
the node is called; the resulting profiles use the same snapshot and attack rules.

Full and half attacks, including unarmed attacks, force added damping to zero. Returning to locomotion restores the current blended equipment-specific value. Set all four values to zero to clear the profile. The constant single-joint node replaces this policy for that joint; the all-joints constant node replaces all anatomical joint policies on the agent. Constant and conditional values now share attack suppression and snapshot behavior.

Configuration requires a live rig and is applied immediately. Profiles survive rig recreation within the same agent lifetime and re-resolve the PHAT index for the new rig. EndPlay removes them. The shared physical-profile system now owns conditional values and timed blends; its timer retires when blends finish. Unchanged context skips joint iteration, and unchanged effective damping skips native commands. At zero, native motor rows remain off.
