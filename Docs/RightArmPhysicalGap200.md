# Right simulated arm separation — September 29

Current-setup investigation only. No gameplay code, Blueprint, collision preferences, or assets were changed persistently. Owned diagnostic PIE runs ended themselves; no build or full suite.

There are two distinct discrepancies.

## During slashR, ticks 173–178

Right hand error peaks at 15.379 cm at176 (14.642 at175). The NN's presented elbow-to-hand geometry is incompatible with the fixed physical wrist offset. In target forearm coordinates the hand is (-17.35, 0, 0) cm at174/176, and (-8.13, -3.65, -0.56) cm at175. The physical wrist stays near (-22.35, 0, 0) cm. The midpoint chord severely shortens the displayed segment while the forearm rotates 67.46 degrees per displayed tick at175–176. Forearm tracking rotation error reaches48.1 degrees at176. Error is already down to2.112 cm at180.

Self-collision, sword-collision and angular-limit controls did not remove that peak. This confirms a target/physical geometry mismatch; the complete contribution of velocity caps versus other solver dynamics to the angular lag has not been isolated. A grip-break comparison returned false, so it is not evidence of a successful grip ablation.

## During recovery, ticks 199–207

The elbow (lowerarm_r origin) separates3.811 cm at200 and5.026 cm at202, returning to0.272 cm at210. Right-arm/torso self-contact is causal: disabling only the pairs between upperarm_r/lowerarm_r/hand_r and pelvis/spine_01–05 reduces elbow error to0.582 cm at200 and0.548 cm at202. Disabling all self-collision produces the same result. At202 the hand error also reduces2.500→1.645 cm. NN elbow/hand position differences between this comparison and baseline are only0.092/0.177 cm at202, much smaller than the physical elbow improvement.

Sword collision and authored angular-limit comparisons leave the elbow peak essentially unchanged. Drives stay linear/angular1 and damping0 across upper exit189 and the recovery window. Feedback tolerance changes at exit from1000/1000 to5 cm/35 degrees; that is not drive weakening. Current cone is radius60/strength1,000,000/damping20, hold0.5/blend0.5; wrist limit5/recoil50/damping10. A directional arm cone does not guarantee clearance for the entire bent arm's collision shapes.

The later gap is physics rejecting the NN arm's overlap with the torso. The earlier gap needs coherent NN forearm/hand geometry, analogous in category (but not identical implementation) to the calf/ankle mismatch. Neither should be described as a drive-strength fade. No proposed fix implemented.

Evidence: `Saved/Diagnostics/CaptureArm200.py`; `Saved/Diagnostics/Knee202/arm200_{baseline,no_self,no_arm_torso,no_sword_collision,no_limits,no_grip}.json`. Successful captures245 ticks; initial sword-ablation attempts stopped safely at164 on Python reflection/enum errors, then the completed comparison used reflected `SetSwordCollisionEnabled`.
