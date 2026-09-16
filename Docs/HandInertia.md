# Hand inertia

Per-agent and per-hand. Controls apply to the authored IK target in Kinematic, Half Sim and Sim; physics still acts on the resulting targets normally.

1. **Set Hand Inertia Checkpoint**: Agent, Hand Bone (`hand_l` or `hand_r`), Checkpoint (`Walk`, `Run`, `Attack`), Linear Follow and Angular Follow.
2. Right-click either vector pin and **Split Struct Pin** to access X, Y and Z separately.
3. **Set Hand Inertia Enabled**: choose the same agent/hand and enable it. Each hand is disabled by default; all six values default to 1 for every checkpoint.
4. **Get Hand Inertia Checkpoint** reads stored values and the hand's enabled flag.

Values must be finite and between 0 and 1. **1** follows the ordinary NN target; **0** retains world velocity, subject to arm reach. Intermediate values blend velocity toward the target. The linear/angular velocity corrections are decomposed along the current root's X/Y/Z axes, weighted separately, then transformed back to world space. Thus the control directions rotate with the root while zero-follow preserves the pelvis feature's world-momentum behavior. These are angular-velocity axes, not hand-local axes or Euler angles. Angular follow uses quaternion increments.

Walk/Run values blend linearly using the actual policy WalkWeight, including forced-walk selection and transition timing. Momentum is shared across the transition, rather than resetting when a checkpoint changes. Attack uses the Attack set for full and half attacks: all current attack families use the shared attack checkpoint. An all-one effective set bypasses inertia and IK even if enabled. Retuning parameters doesn't itself enable the hand.

The upper NN predicts first, then inertia filters the hand target. A fixed-length shoulder/elbow/wrist solve clamps unreachable endpoints and transports the bend frame through hand rotation. The shoulder stays at its torso attachment; the upper-arm orientation changes to reach the filtered hand. Forearm orientation uses the normal hand-derived decoder. Corrected hand and upper-arm channels are written back to upper state; attacks also update their ghost recurrence with the proper full/half mount conversion. The accepted reachable wrist is stored, preventing an unreachable hidden target from accumulating.

Disabled/all-one paths skip extra pose decoding, integration and IK. There are no ticking components, timers, extra NN evaluations or debug captures. Sparse per-agent state is removed at EndPlay; only eligibility checks remain when disabled. Existing presentation clamp settings still apply afterward.

Validation scope requested by user: compilation plus the small `Prophecy.NN.HandInertia.ControlsAndIK` automation check. Extensive gameplay testing is left to the user; no cost benchmark or long PIE run.

Validation 2026-09-14: Live Coding build/patch succeeded without restarting Unreal; new Blueprint library loaded. The single Prophecy.NN.HandInertia.ControlsAndIK test passed (blend/default bypass, world momentum with root-local axes, eight fixed-length IK cases). No PIE or performance test was run. Existing unsaved BP edits remained unsaved. Evidence: Saved/Diagnostics/BuildHandInertia.log and HandInertiaAutomation.log.
