# Print NN Modifiers

Call **Print NN Modifiers** with the agent (Self by default). One call draws the
current report for one tick; calling it on Tick keeps the display current. Pausing
the game (including the editor Pause button) keeps the last report visible until
the next unpaused tick. Each
row has a distinct color derived from its feature name. Repeated calls for the
same agent replace the screen snapshot. The **Report** output contains all rows;
the return value is the row count, including context rows. The overlay uses
columns at normal Print String font size with an opaque color and black shadow.
Long lines end in an ellipsis; the Report pin retains the complete text. Text
is never scaled down to fit a column.

The snapshot reads the last accepted policy/presentation state. If called before
the manager updates this frame, it describes the preceding publication. It does
not run inference, sample physical bodies, advance springs, consume blend clocks
or modify configuration. No diagnostic tick/draw callback remains after expiry.

## Reading the report

- **INPUT / HISTORY**: conditioning, root control and recurrent feedback.
- **POSE**: correction to the decoded pose. **POSE+HISTORY** also affects a
  subsequent prediction. Full/half ownership is respected for attack entry
  hand/core inertia: half mounts do not feed the moving real carrier into the ghost.
- **PRESENT**: interpolation or pose correction after policy publication.
- **PHYSICS**: drives, joint allowances and physical motion; contact/external-force
  effects can return through physical feedback.
- **CONSTRAINT**: a currently eligible limit. It may do nothing while the pose
  is inside its permitted range; presence is not proof of a nonzero correction.
- **STATE / CLOCK / CODEC / GATE**: ownership, timing, normal decoding or an
  enabled gate. These are distinguished from a currently moving spring.

The readback covers FK return (including NN weight, easing, coefficient, hold,
trimmed deadline and final interpolation tail), retained FK momentum, attack motion
inertia, entry core/hands/pelvis/feet, general pelvis/attack-hand inertia,
lower tempering and recovery, gait blending, pin controls, ghost loco/ghost
displacement, drag handoff/poles/root freeze, half mount/compensation, manual armed
pose, authored animation layers, wrist freedom/forearm return, wrist/leg clamp
tightening, calf return, knee soft IK, gaze/equipment/root conditioning, physical
feedback tolerances/drives/damping, fingers and simulation mode blending.

Several older controls are intentionally bypassed in the current upper locomotion
pipeline. Merely configuring them does not make them appear as active modifiers.
The node does not retrospectively identify arbitrary Blueprint/AnimGraph writes,
previous impulses/teleports already baked into history, or changes inside checkpoint
weights. Exact raw-output-versus-final-pose attribution still requires a trace.

## Cleanup and backup

Before this work, the saved source, PoseAgent Blueprint, TestNN map, docs and
custom attack fixture were pushed as `9b4c03f` on `codex/standalone-sim`.

Removed the superseded upper recovery helpers `MixHandRecoveryUpper`,
`TemperCoreLocalState`, `CarryCoreArm`, `BuildHandRecoveryUpperInput` and
`HandInertiaCarrier`, plus the two tests that only exercised those removed
algorithms. They remained after FK Return replaced that path and had no runtime
callers. The still-used attack hand inertia helpers remain. Valid optional
features, saved Blueprint identities and retained Live Coding layouts remain.

## Validation (October 4)

Pause persistence follow-up loaded at 13:46:03 UTC. All three modifier tests
passed at 13:46:18 UTC, including game pause, editor pause, retained text across
paused frames, resumed expiry and callback cleanup.

Live Coding loaded the new runtime/editor patches at 13:36:11 UTC. The reflected
node exists and the current PoseAgent Blueprint compiles with status 3,
`native_properties=0`, `pin_types=0`. No Blueprint or map was explicitly saved.
The normal Development Editor DLL still needs rebuilding before a cold launch.

All 11 focused modifier/FK return/clock/motion-handoff tests passed at 13:39:10
UTC, including distinct colors, one-tick expiry, callback cleanup and repeated
readback without consuming pending finger/FK blend ticks. An earlier test run
overlapped an owned replay and failed the global screen-count assertions; the
isolated rerun passed. Test and replay sessions must run sequentially.

The complete 260-game-tick replay called the new node twice per tick and checked
identical repeated reports. All captured values matched the pre-change replay
exactly: 23-bone future/presented/body/target transforms and velocities, root
windows, ghost readback, phase state and 40 native attack input/output records.
Coverage includes locomotion, slashLU full/half and FK return. This is parity for
the current mostly Kinematic setup, not a broad physical/contact stress test.

The user's debug-profile graph changed during the build; those edits were kept.
The post-verification graph and replay-start graph are byte-identical. There was
no diagnostic node insertion or gameplay tuning change. The owned replay ended
and trace controls returned to -1/0. Screen lifetime was tested programmatically;
no claim of a captured viewport visual review is made.

Receipts: `Saved/Diagnostics/NNModifiers20261004/verification.json`,
`before-observe-comparison.json`, `before.json`, `observe.json`, native traces and
graph audits. Scripts remain alongside them.
