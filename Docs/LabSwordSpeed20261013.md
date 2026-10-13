# Independent attached sword speeds — October13

## Follow-up: cap hand motion relative to the holster

User saw about350cm/s and explicitly selected the holster frame for the limit.
Recorded live setup reproduced354.973cm/s world and283.008cm/s relative to the
holster against a230cm/s limit. The previous independent tip/rotation paths made
the hand swing around the tip, adding travel that the translation clock ignored.

The alignment now translates the grip from its captured location to the location
that puts the tip at the mouth with the chosen final rotation. Rotation occurs
about the grip, with an independent angular clock. Both limits apply in the
holster frame. The tip can curve during this short approach; final tip position,
rotation tolerance, authoritative holster attachment and exact capture stay intact.
No synchronized slowdown, future gait lookup, new settings, or native edits.

The counter now explicitly measures actual hand motion in the holster frame.
Current setup alignment84→85: maximum integer hand speed145.734cm/s;
1/32tick samples148.663cm/s and381.450deg/s, below230/600 limits.
Six current-profile idle/walk/run × planner cases also pass actual fractional
hand limits.36 broader alignment/sequence cases pass target caps, tip arrival
and ownership; unreachable arms still show their tracking error. This does not
guarantee a speed cap on a physically unreachable arm dragged by its shoulder.
Nine independent speed cases, displaced-arm ownership, causal audit and isolated
UI counter/frame/scrub/playback/sequence/worker/persistence checks pass.
The body-schedule fixture initially had no interior alignment samples because
alignment became shorter; it now uses60deg/s to exercise52 interior samples
across12 cases, preserving the original schedule assertion.

Saved settings/Blueprints/Unreal unchanged. Lab-only; refresh required.
Evidence/backups: `Saved/Diagnostics/HandAttractionSpeed20261013/`.

## Previous tip-speed implementation (superseded above)

User requested translation and rotation at their respective maximum speeds,
without shared-duration calculations. This change is limited to the lab's
attached Align tip phase in `tipalign.js`.

Tip translation follows the existing straight holster-local path at Max reach
speed. Sword rotation follows the existing quaternion path at Max reach rotation
speed. Each stops at its own target. The phase finishes on the first simulation
tick after both arrive. Fractional durations preserve the specified speed rather
than stretching either path to an integer or shared duration. Curves do not
affect either clock. Sword origin/hand motion additionally reflects rotation
about the moving tip; it no longer has a combined wrist-travel budget.

No targets, controls, saved settings, sliding rules, or Unreal code changed.
Unreal retains its previous coupled alignment timing and is not yet equivalent
to this timing change. No build, editor restart, asset save, or push.

Verification:

- `test_tip_speeds.cjs`: nine combinations of zero/short/long tip travel and
  zero/small/large rotation, sampled at 1/32 tick. Independent progress matches
  230cm/s and 600deg/s until each arrives.
- `test_tipalign.cjs`:36 planner/motion/curve/shrink combinations plus sequence
  checks pass.15 cases contain unreachable hands; tip arrival error<2e-13cm.
- `test_sword_owner.cjs`:100cm displaced arm cannot change sword path/timing.
- `test_attach_body_schedule.cjs`:12 cases preserve the reach body schedule.
- `test_online.cjs`: causal/future-input audit passes.
- Six drawing trajectories exactly match the pre-change version; saved state
  bytes unchanged. Current saved S: attachment84 unchanged, slide90→87,
  seated119→116, full return191→190.

Backups and receipt: `Saved/Diagnostics/LabSwordSpeed20261013/`.
Refresh the lab to load the change.
