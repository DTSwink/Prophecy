# Unreal tip alignment and grip stabilization — October 13

The later mesh/native separation diagnosis below is now fixed; see
[the synchronization follow-up](SwordPhysicsPresentation20261013.md) for
implementation, measured results and the remaining native hand-grip residual.

## Requested behavior

Port the accepted lab capture → tip alignment → slide behavior without changing
the lab. Add grip-only holster rotation stabilization and a return duration to
the existing **Set Sword Holster Profile** node. The class viewport owns the
neutral holster mount.

## Implementation decisions

- Capture S at the first full sword-rotation tolerance pass. Body readiness and
  distance to the old hand target no longer gate capture.
- Attach with KeepWorldTransform. Freeze the current axial shrink during tip
  alignment. The alignment trajectory lives in the holster's rotation frame,
  in centimeters, and aims the actual blade tip at the entrance.
- Use the accepted lab's constrained rotation and conservative shared duration:
  max(rotation / angular speed, (tip distance + lever × radians) / linear speed).
  The time clock is 60 unpaused authored ticks. Curves do not retime alignment.
- **Corrected after the user's ownership report:** the holster-local trajectory
  owns the sword after attachment. Solve the arm toward its captured grip, but
  never feed the solved hand back into the sword path or gate tip arrival on arm
  reach. The rendered sword and native kinematic body use this same path.
  Start sliding when that path reaches the entrance, with the existing curve,
  time-based rotation correction, and return. The lab is unchanged; its alignment
  still contains the solved-hand dependency and is not an ownership oracle.
- Continue the body toward its clear pose under its angular bound during
  alignment. Slide from the actual body pose reached at entry, avoiding a jump
  to an endpoint it had not reached.
- At capture, update the existing temporary hand/sword joint's two frames from
  the current physical poses. Capture the same actual grip for arm authoring,
  preserving the current hand and sword world poses. Do not add another joint.
  Drawing retains its existing authored grip. The native physics target override
  covers alignment as well as sliding; sheathing destroys the joint at 100%.
- Add `GripHolsterStabilizationPercent` (default 0) and
  `HolsterReturnDuration` (default .25 authored seconds) to the existing basic
  profile node. No lab stabilization setting is imported implicitly.
- At grip capture, hold the current world rotation by the chosen percentage;
  translation continues following the pelvis. D captures at its grip, S at
  attachment. After slide completion, reduce stabilization to zero over the
  configured duration, then restore the exact original relative rotation and
  rotation-inheritance flag.
- Restore the mount on cancellation/removal and before a simulation-mode switch
  can capture it. No editor template is written by runtime stabilization.
- Game-world reference capture reads the class component template's local mount,
  preventing old placed-instance overrides from becoming the runtime neutral.
  Construction/editor reference capture remains read-only.
- An explicit, guarded editor command refreshes only existing basic profile
  nodes that lack the new pins. It does not save or replace wiring/defaults.

## Verification status

The ownership/captured-grip correction is loaded by implementation-only Live
Coding. No restart, Blueprint/tuning change, or lab motion change. Evidence is
under `Saved/Diagnostics/TipAlignPort20261013/`.

- The native `Prophecy.SwordHolster.TipAlignment` test passes, including arbitrary
  captured grips at three shrink scales, no capture-pose jump, and independence
  from an unreachable solved hand. Six lab path math cases still match within
  1e-13cm / .000036deg; this does not claim full-motion parity.
- Saved moving setup: Sim and Kinematic each complete two S→D pairs for all three
  agents. The formerly blocked C_3 now starts S sliding at64 and finishes S152
  in Sim. Twelve S alignments across these runs have the correct parent, zero
  joint-handle changes during alignment, exact planned alignment duration, and
  slide-entry tip error <5e-13cm. Local path residual <6e-7cm. Joints are absent
  at release and poses remain finite.
- Direct native readback at S capture: grip anchor error ≤.000002412cm and zero
  measured rotation error across the three agents. Current poses are captured,
  not snapped to the nominal authored grip.
- **Remaining issue, explicitly reported to the user:** during sliding, native
  versus rendered sword error reaches9.044cm /7.482deg; native grip error briefly
  reaches4.027cm /21.521deg near entry. The geometry path is sampled against an
  upcoming predicted pelvis for physics and the actual holster for display;
  attached kinematic publication deliberately does not overwrite the component.
  This is not solved by correct component parenting or the captured joint.
  No motor-strength, physics-iteration, or presentation patch was added to hide
  it. Do not claim the physical grip is perfect or complete runtime parity.
- First compile failed on local variable shadowing; corrected compile/reload
  succeeded. A later diagnostic-only patch adds grip/native/render errors to the
  existing on-demand report, with no recurring work. The initial owned capture
  overlapped queued Automation and was ended by Automation; it is retained as
  partial evidence and was replaced by the complete runs above.

The user's attachment complaint was correct about behavior: the root component
was attached in all 248 alignment samples across three agents, but both render
and physics paths overwrote its transform from the solved hand. Earlier
arm-length diagnoses and path-math parity did not validate ownership. The
source-only correction was paused when the user requested an explanation;
implementation resumed only after the user confirmed the grip behavior and said
"go". Capture/path-independence regressions were then added. No lab edits.

The earlier reset patch is loaded and passed interruption plus five repeated
resets across three agents (local position residual <1e-12cm); the earlier
"awaiting reset retest" status is superseded. Normal DLLs remain stale after
implementation-only Live Coding patches; build before a future cold launch.

The pre-edit source, asset bytes, and lab settings are backed up in `before/`.
`Tools/SwordHolster/export_tip_alignment.cjs` reads the accepted lab and exports
six idle/walk/run alignment paths for the native numerical test. Live tests must
also check attachment, completion, stabilization/return and interruption cleanup.
