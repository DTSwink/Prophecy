# COM rotation and simulated playback plan

Requested October 29, 2026. Work remains contained to Bodyflip Lab; preserve the
live scene, playback, existing tuning and all unrelated work. Use offline frame
audits and bounded single-thread tests, without desktop control.

## Completion criteria

- Flip and twist controls specify target angular velocity in degrees/second.
  Rotation continues until the command changes or real landing takes over; a
  jump or hand push must not reset orientation or its velocity target.
- Body rotation preserves the mass-weighted COM. The physical rig and motion
  planner share segment mass/COM/inertia definitions. A tucked pose spins faster
  than an extended pose at the same reference velocity target.
- Entry/changes remain smooth and deterministic when scrubbing, looping,
  refreshing, or extending the trim. Existing poses and attacks still work.
- Foot/hand support respects limb reach and joint limits under rotation. A
  conflicting two-hand pin can release one hand continuously; no stretched arms,
  teleports or silently cancelled spin.
- Simulated mode drives the same targets through real Jolt dynamics, with only
  the pelvis position servo and angular limb tracking. Test joint constraints,
  contact, stability and tracking against the kinematic reference.
- Inspect full representative motions, not only transition instants. Preserve
  existing landing, momentum, trim, pose and attack regressions.

## Work sequence

1. [x] Audit current flip scheduling, pivots, mass model, hand takeover and Jolt
   servo. Capture the current scene read-only and establish baseline failures.
2. [x] Implement shared mass/inertia definitions and continuous COM-centred
   angular-velocity planning. Update control labels/units in their current places
   and migrate saved angle commands without modifying saved scene files.
3. [x] Carry spin through foot and hand events, resolve rotational support
   conflicts and implement safe one-hand release from a paired pin.
4. [x] Repair simulated tracking/contact issues identified by comparison with
   the same kinematic targets. Run real Jolt in bounded offline tests.
5. [x] Exercise positive/negative/zero rates, all axes and twist, tucked/open
   poses, sequential and overlapping events, hand/foot/sloped contacts, landing,
   attacks, reverse seeking and trim extension. Inspect complete frame sheets
   and investigate any discontinuities or constraint violations.
6. [x] Run focused regressions, verify served scripts, confirm live scene remains
   intact, update the current journal/README and report results and limitations.

## Findings and evidence

- Shared 45 kg mass properties match Jolt (COM error 2.2 nm; inertia error 2.2e-8 kg m²).
- Old markers used a finite angle and pelvis pivot. New v2 fields are degrees/s;
  blank inherits, zero brakes to rest. Legacy nonzero angles migrate once by
  their former duration. Spin persists through support and hand-push release.
- Basic spin suite: all 12 axes, signs, constant rates, COM preservation,
  migration, reverse seeking, marker inheritance and inertia ratio pass.
- Dynamic baseline had >1 m target errors during recovery. Joint-compatible
  linear velocities, a common constrained target and continuous release/landing
  handoffs reduce the saved motion's final peak error to 1.53 cm (including contact).
  Pelvis error is 5.3 mm; maximum attachment error 7.8 mm.
- Paired support now releases a hand before its reach/joint limits are exceeded;
  losing both contacts ends the drive instead of producing a phantom push.
- Real Jolt: 33 cases / 12,490 steps, plus 9 updated contact cases / 3,024 steps.
  All attacks, foot/hand, inherited turns, paired release, slopes/wall and speeds
  to 3,600 deg/s. Extreme-speed error stays below 1.3 cm with adaptive substeps;
  worst attack self-contact transient is 8.2 cm. No sustained divergence.
- COM/pins: 310 hand checks pass. Six paired-turn cases retain compatible pins,
  release one or both when required, never push after loss, and seek identically.
- Actual saved scene was extended through 3.4 s using its seeded NN. Prefix stays
  unchanged. Reviewed whole collider sheets for both modes, paired release/fall
  and the sweep kick. Visible target geometry stays clear of the floor.
- Browser globals loaded from the existing service in a JS VM (no UI): all new
  dependencies served fresh, persistent turn runs, live state remains identical.
- Cost: saved audit 7.3 s including 2.1 s Jolt for 3.4 s playback. Maximal 32-action
  overlap 5.5 s isolated / 10.8 s after corpus; bounded but still expensive.
- Completed: all 16 final regression suites pass (regressions.json), including
  161 spin checks, 310 hand COM checks, 64 editor checks, 321 clips/17 attacks,
  hand recovery, buildup, travel, paired bounce, trim and release contact.
  Also passed: 106 posed-body landing checks, 93 space/attack checks and browser
  global loading from the existing service. Syntax checked all changed modules.
- Current README and ProjectJournal updated. Live saved scene/playback remains
  identical to the starting snapshot. No desktop, Unreal, service restart or push.
  No further required work remains.
