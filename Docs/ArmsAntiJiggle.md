# Set Arms Anti Jiggle

Blueprint node in Prophecy > Physics. Agent defaults to Self; Left Arm and Right Arm both default false. Each call sets both choices. Enable before or during physical simulation; choices survive rig recreation/reset for that actor and clear when the world ends. Does not edit the Blueprint, NN output, arm masses, joint limits or solver iteration counts.

Each selected arm routes its existing upperarm/lowerarm/hand COM linear and angular magnetisation commands through three world-space Jolt SixDOF velocity motors. Finite limits are 3000 N and 500 Nm per motor axis, matching the successful October 9 trial. Gravity compensation remains outside the motor target. Zero-strength channels switch their motors off; unpublished targets retire their motor states. Local magnetisation's child targets continue to use the parent's commanded endpoint.

The welded sword is part of its hand's body. Selected arms use this control outside the attack window described below. Disabled arms retain direct velocity magnetisation. Disabling removes their constraints immediately without resetting pose or velocity. Choices are independent; changing one leaves the other arm's existing constraints intact.

Cost: three additional constraints/up to eighteen motor rows per enabled arm, plus sparse command routing. Both disabled adds no constraints or motors, and skips motor-specific target scans. This is not an overhead-free solver change; large-agent scaling remains unmeasured.

Original experiment and comparison: Saved/Diagnostics/SwordJiggleTrials20261009/Results.txt. Node verification: Saved/Diagnostics/ArmsAntiJiggle20261009/.

**Disable Arms Anti Jiggle For Duration** temporarily removes both arms' motors and restores their original independent selections on expiry. Duration Seconds defaults to0.1 (six ticks). One second means60 unpaused world ticks, independent of FPS, actor/world time dilation and physics substeps; positive fractions round upward to whole ticks. Repeating the node restarts the countdown while preserving the original selection. Zero restores immediately. An explicit `Set Arms Anti Jiggle` cancels the pending restoration and wins. Negative/nonfinite durations fail without changing state.

The timer survives rig recreation/reset for the same actor, while motors stay disabled, unless reset explicitly calls the normal setter. Actor destruction/world teardown cancel it. Already-disabled arms need no timer; when no holds remain, the shared world-tick callback is removed. Enabled motors are removed/restored only on transitions, with no extra physics query or inference.

**Automatic Armed-to-Hit suppression:** every attacking agent temporarily disables both arms' anti-jiggle from the latched Armed event until its NN Hit event, for every attack family. Hit is the attack network's output, not a physical collision. End/cancel/replacement also releases this gate. Left/right preferences are preserved, including changes made during the window. A timed disable and this attack gate must both finish before motors return; neither can prematurely override the other. No new tick, physics query or inference is added: the existing attack transitions change the gate, and agents with no configured arm motors skip the rig scan.
