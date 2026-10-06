# Third attack stall and isolated motion inertia - October 5, 2026

**Fixed:** motion inertia now smooths the final visible/physical upper pose after NN feedback is committed. Existing node pins and defaults are unchanged.


Original TestNN/PoseAgent setup: simulated actor, Attack184064 checkpoint;
sequence hookL, pike, overL. The optional Set Attack Motion Inertia is enabled with
response .03, Armed+1 tick, full upper body, core-throughout false, After Hit false.

The third overL stalls because this inertia changes the upper recurrent history
seen by subsequent NN steps. It is not an Armed-block flag, stopped inference,
paused world, or the new ticks-since-attack counter. The filter does not directly
rewrite Armed: its filtered upper pose is encoded back into Slash.State+172 in
ProphecyNNSlashRuntime.inl, affecting the following raw Armed predictions.

## Controlled evidence

Three owned 750-game-tick replays used the same live graph without saving/editing
assets or permanent settings. Raw native traces include the Armed request at
output433, latch431, and Hit request434/latch432.

| Replay | Change to third attack | Result |
| --- | --- | --- |
| Baseline | None | overL still active/unarmed at policy216; raw Armed peaks .5724289 at policy11, below checkpoint threshold .6, and settles near .2929 |
| Late disable | Disable motion inertia after capture tick500, already stalled | Still unarmed at policy216; final raw Armed .2927794; modifier readback confirms filter removed |
| Start disable | Disable only motion inertia after tick320 / overL policy1, before its first traced prediction | Arms at policy9 (raw .9686592), Hits at14 (raw .9811680), last active policy19, back to locomotion at capture tick358 |

The start-disable run has exactly identical native input/output arrays for all32
records through the first overL prediction, including both preceding attacks.
The late-disable prefix also matches baseline exactly before intervention.
Disabling at start prevents the stall, while disabling after the recurrent state
has settled does not recover it. This demonstrates a filter/history interaction
for this setup; it is not proof that every unfiltered attack always succeeds.

Baseline inference continues for215 traced overL steps; there is slight residual
motion rather than a literal frozen pose. No ArmedBlock modifier is active.
The contract is `Content/locomotion/NN/Attack184064/prophecy_slash_runtime.json`,
gate_threshold .6. Changing that threshold or forcing Armed was not tested or
applied. The FK idle-return system never starts during the stalled attack.

## Initial investigation outcome

Investigation only. User Blueprint remains unsaved as before, settings unchanged;
owned Play sessions ended and trace CVars restored. Potential remedies are to
disable/reduce this filter for affected wind-ups, or separate visual smoothing
from NN recurrence. Neither is silently applied: the latter changes the accepted
attack-motion-inertia design and needs its own implementation/validation.

Scripts and raw evidence: `Saved/Diagnostics/ThirdAttack20261005/`:
`capture.py`, `control.py`, `control-start.py`, corresponding capture/native files,
`graph.txt`, and `segments.json`. Captures are local diagnostic data.

## Implemented fix and live comparisons

Removed motion-inertia filtering/re-encoding from the attack ghost recurrence.
The same parent-local spring now runs once at the end of accepted attack pose
publication, after all older entry controls and NN-state writes. Its source
cache isolates previous-pose reads by legacy hand inertia and arm-cone feedback.
The visible cache remains the filtered output for interpolation, physics,
defenders and FK return. Forearm convention runs before this final spring.
No extra NN inference, gate override, timeout, or attack-specific exception.
The source cache is sparse, reserved at attack entry, and released when the
window ends (or retained while waiting for After Hit). Explicit cancel/reset/end
and world cleanup clear it. Root relocation carries its world history too.

Ten complete owned physical captures with Attack184064:

- Current overL off/on: start121, Armed136, Hit146, final active157, 18 native
  predictions in both. Maximum input difference2.54e-6, output3.40e-6.
- Isolated problematic slashL off/on: start59 (observed60), Armed70, Hit86,
  final active97. All19 native input/output arrays are bit-identical.
  At the brake tick71 the displayed right-hand travel is2.936 ->5.620 cm/tick;
  peak displacement-vector change over ticks68–76 is13.066 ->9.557 cm (26.9%
  less abrupt). Physical hand3.156 ->5.886, peak13.387 ->9.876 cm (26.2% less).
  Release steps73/75 have vector changes3.180/5.530 cm, below the original
  brake. This is still learned braking, not constant hand speed or the exact
  old recurrent trajectory; the old filter's stronger change included changing
  the NN's predictions themselves.
- The paired half-at-Armed slashL runs also have bit-identical complete native
  input/output arrays, unchanged gates/end and the same brake reduction.
- After Hit enabled: complete slashL and initial return, finite poses; preserves
  all native attack input/output arrays against the off control.
- Enabled from startup: 750 ticks,17 consecutive completed attacks, including
  third overL. Every completed attack reaches Armed and Hit; all recorded
  displayed/future/physical transforms are finite.

This prevents the filter's own recurrent feedback trap. Other modifiers,
physical interactions and subsequent attack initialization can still alter
inputs; it cannot guarantee all possible NN rollouts will reach Armed.

Receipts: `Saved/Diagnostics/MotionIsolated20261005/` (`capture.py`, `batch.py`,
`analysis.json`, paired pose/native traces). User gameplay settings and graphs
were not edited. The user's current Enabled=false setting is retained. A first
fixture capture hit a Python stop-function argument error; it was corrected
and rerun to completion before drawing conclusions.

Normal Development Editor build succeeded, including the final pure-half-entry
seed guard (no spring step before the first actual prediction). Seven focused
headless MotionInertia tests passed: Window, Geometry, Lifecycle, Cost, AfterHit,
SourceIsolation and ReturnHandoff. The new isolation check verifies raw world
history versus filtered display, pelvis exclusion, explicit root translation,
release and cleanup. Full normal-build receipts and automation report are in
the same diagnostic directory. The rebuild also required qualifying one
`ProphecyDefense::FGeometry` test variable in concurrently updated defense tests;
no defense behavior was changed by this task.

Cold-launched TestNN Blueprint verification: status3, native_properties0, pin_types0, wiring_preserved1. Two additional direct-half-entry slashL captures also complete with identical gate/end timing and bit-identical native input/output arrays. Editor left open on TestNN; owned Play sessions ended, trace restored, Enabled=false retained.
