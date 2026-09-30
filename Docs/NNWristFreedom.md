# Set NN Wrist Freedom

Blueprint node on the existing wrist library, targeting a Prophecy Agent:

- **Free Position**: bypass the fixed anatomical hand attachment for both NN hands, including locomotion decoding, full/half attack ghosts, defense, publication, interpolation, and final kinematic rendering.
- **Free Rotation**: bypass **Set Left Hand Constraint** in every mode. This also bypasses its native attack correction and clears a pending wrist-angle clamp reduction. Existing per-mode angle settings remain stored and resume when this pin becomes false.

Neither pin changes physical joint limits. Inertia, manual posing, arm-cone recoil and constraints built into the trained checkpoint remain separate motion controls. This is a binary bypass, not a return of length leeway bands or blending leeway.

Without calling the node, the previous behavior remains: fixed NN hand attachment and the configured left-wrist constraint. The node's input defaults are Free Position=true and Free Rotation=false. Use false/true to free only rotation, or true/true to bypass both clamps. Changes affect subsequent NN publications.

The overrides use sparse per-agent storage and world cleanup. There is no new ticking, inference, pose capture, or physical-joint work. Existing pose snapshot layouts are retained; zero attachment offsets identify a publication whose positional repair is bypassed.

Validation (September30): Live Coding compiled and loaded at13:11:49UTC. Four focused automation tests passed (AttackWrist Math/Modes/AllCheckpoints and PhysicalTargets.FixedForearms), covering independent flags, angular bypass/restoration, and free/fixed publication. A260-frame owned PIE check toggled fixed, free position, both free, then restored; all poses remained finite. Free-position length deviation reached4.695cm, confirming release; restored attachment error from frame216 onward was6.61e-12cm. Capture: `Saved/Diagnostics/NNWristFreedom20260930/Smoke.json`. PIE ended cleanly.

The left-hand constraint also supports [angular leeway, per-attack selection and a global enable switch](LeftHandAngularLeeway.md). Free Rotation and the global-disable switch are independent; either bypass wins.
