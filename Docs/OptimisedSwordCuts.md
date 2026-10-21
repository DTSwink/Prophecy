# Optimised sword cuts — installed and tested, October21

## Current head-entry correction — October21, 17:09 UTC

The user's current head-pike placement exposed an admission error absent from
the earlier open-side fixture. Optimised recentered the accepted wound onto the
blade centreline, creating 6.221056cm of transverse error. The hard joint then
tilted the blade upward to close it. Admission now preserves the accepted pike
contact's transverse offset, with the axial origin still at the hilt plane.
No recurring correction, extra physics work, layout or Blueprint changes.

Exact current-scene legacy/broken/fixed captures have ten identical pre-solve
samples, head admission at0.166667s. First post-contact angle relative to legacy
falls from4.750977deg to0.019213deg; the upward kick is absent. Later trajectories
need not be identical because Optimised retains its own friction and hard-stop
behavior. Blade stain reaches1.0; current fixture has a4.945mm transient hilt
overshoot, rather than the earlier fixture's0.432mm. Forced withdrawal at0.3333s
clears cut and wound effect at0.35s. No saved scene/launch tuning changed by tests.

Implementation-only Live Coding: one compile action,119.98s, loaded17:09:35UTC;
normal DLLs still stale before next cold launch. Small evidence lives in
Saved/Diagnostics/SwordOptimised/head-current-{old,opt,fixed,cleanup}.json and
head-entry-comparison.json. TestOptimisedCuts.py supports --legacy to compare
the current scene through a transient PIE-only mode change.

`/Game/_mygame/sword/A_Sword` is saved with **Optimised=true**, instance editable
under Sword|Cuts. Select it before Play; changing modes during an active cut is
not supported. False returns to the preserved original post-hit Blueprint path.
Accepted-hit conditions, dimensions, tuning and the rest of sword Tick remain
authored. All3,976 original pins were compared with the pre-install graph:
nine intended connection changes, zero unexpected changes. explosionVFX's saved
SHA256 is unchanged. Editor21708 is open there, outside Play, no dirty packages.

## Behavior

- Accepted-hit setup calls **Start Optimised Sword Cut**. Native admission reads
  the existing cut record once and installs a hilt-frame physical joint. The
  old `handle cuts f` exits immediately in this mode.
- Pike: locked transverse/angular axes, blade Z travel, hard hilt stop. Slash:
  locked thickness plane and swings, free cutting twist/X and Y/Z travel; the
  accepted signed cut type (-1/+1) chooses the entering edge. Far-edge stop is
  the full blade width, not an arbitrary symmetric joint radius.
- Friction uses user-confirmed **velocity cut dampings**, selected by matter0/1/2.
  Parameters set on admission; existing native body reads calculate point
  velocity. Direction crossings turn the motor off during withdrawal and back
  on during penetration. User explicitly confirmed easier withdrawal.
- **Matter0 only:** five distinct game frames after impact, cap maximum depth
  at current penetration. Withdrawal stays open. Uses the shared physics
  boundary and frame counter, not a separate timer or wall time.
- Active cuts inspect native relative travel after the shared solve. Beyond
  tip/entering edge +0.05cm, retire joint, broadcast OnConstraintBroken, remove
  cut record, restore authored collision policy and destroy shared wound NS
  when the last flesh cut ends. Destroyed/broken endpoints queue cleanup outside
  registry iteration. Other active flesh cuts retain their effects/collisions.
- Existing Blueprint admission still creates wound NS for flesh. Pike staining
  calls existing Stain Blade only on new maximum penetration (1/1024 threshold
  or full depth). Slashes do not stain the blade.

This removes old Blueprint depth/friction/cleanup polling. Physics still checks
active joint travel; it is not a zero-work automatic distance break. No feature
processing remains after its cut state has been retired.

## First impact and joint accuracy

Old slash restore doubled velocity after Cancel Hit Reaction. Optimised skips
that duplicate; false retains original wiring. At~1000cm/s, one frame travels
~17cm versus5.56cm blade width. User approved **one-time far-edge correction at
accepted slash admission**: retract width overshoot, retain velocity, then hand
motion to the joint. No recurring post-step pose writer was added.

Stock slash constraints developed centimetres of plane error. `FSlashJoint`
solves thickness-plane and two locked-swing rows together in a3x3 block at the
wound, inside existing iterations. Twist remains free; stock SixDOF retains
travel limits/motors. Only Optimised slash bindings select this wrapper.
No extra global iterations, mass changes or global filters.

The existing explicitly enabled coupled pike solver now fully corrects its
hard axial stop within normal position iterations, matching its other hard
rows. This also applies to other joints already using that pike wrapper;
ordinary unmarked joints are unchanged. Fractional axial correction allowed
7.18cm past hilt in the flesh test; final error0.04323cm (0.432mm). Contacts still
solve afterward; arbitrary loads are not guaranteed exactly zero joint error.

## Verification

Owned temporary Play captures only; saved scene/launch tuning untouched:

- **Wall slash:** accepted0.05 game seconds; corrected far edge2.779678cm.
  Final test stays within width; locked plane reads0.000cm at audit precision.
  Free twist lets the blade rotate out, releasing at0.116667s.
- **Falling cube pike**, transient velocity(1000,0,0): accepted0.233333s;
  frame5 cap0.316667s/min50.107cm. Largest later cap undershoot0.001304cm.
  Withdrawal motor turns off; natural ejection clears cut at0.683333s.
- **Head pike**, temporary approach from unobstructed side: type0/matter2/head
  at0.05s; wound NS present. Blade stain starts0.37538 next frame, reaches1.0.
  Hilt error below0.5mm. Forced withdrawal at1s clears cut/joint/NS at1.05s.
  Matter2 keeps initial hilt stop; no frame5 cap.
- Early flesh captures hit intervening blocks; attempts to disable their actor
  collision invalidated a standalone shared-step registration and stopped that
  diagnostic world. These runs are excluded. Final fixture changes only sword
  pose/velocity; collision policies and shared registration stay intact.
- Standalone `SlashJointLab` includes production header:1/100 constraints,
  static/dynamic victims, free twist/plane/swing assertions pass. Complete
  physics-step cost in final run~0.45–0.73ms for100 coupled cuts, ~8–11us for
  one. These small CPU fixtures are not Unreal FPS measurements or comparisons
  against the old Blueprint handler. Pike spin/wall regression fixture also
  rerun after hard-stop change; contacts remain active.

## Build/save state and source

User authorized save/normal build/restart for retained cut state. Completed:
12-action build found2 compile API issues;7-action retry passed93.94s. Reopened
editor and verified saved assets. Subsequent implementation-only Live Coding
patches loaded; final plugin patch33.21s, reload16:52:35UTC. New slash class did
not change existing retained layouts. **Normal DLLs stale: incremental build
required before next cold launch.** No restart solely to tidy this state.
No commit/push performed.

- Runtime: `Source/GameAnimationSample3/Private/ProphecyJoltConstraintRuntime.cpp`
  and `ProphecyOptimisedSwordCut.inl`; node in existing narrow constraint library.
- Physics: `Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltSlashJoint.h`,
  existing PikeJoint and native world wrapper/motor/reaction integration.
- Editor command `Prophecy.Sword.InstallOptimised` in
  `Source/ProphecyEditor/Private/ProphecySwordOptimisedSetup.cpp`.
- Tools: `Tools/SwordHolster/InstallOptimisedCuts.py`, `TestOptimisedCuts.py`,
  `FinalizeOptimisedCuts.py`; standalone `Tools/Jolt/PikeJointLab`.
- Evidence: `Saved/Diagnostics/SwordOptimised/final-state.json`,
  `graph-verification.json`, `validation.json`, `wall-final.json`,
  `cube-hard-stop.json`, `flesh-hard-stop.json`, lab CSVs. Earlier captures are
  historical failures/comparisons, not final validation. Original saved A_Sword
  backup retained there. No heavy visual captures generated.
