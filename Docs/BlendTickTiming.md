# Blend duration contract

User-approved convention, 2026-09-19: one duration unit labelled "second" means
60 unpaused game-world ticks, independently of FPS and time dilation. This is
deliberately a tick-count contract, not a promise of identical physics at different
FPS. At30FPS, a60-tick blend takes2 real seconds; at120FPS it takes0.5 real seconds.
Apply this convention to newly added authored blend/fade durations too, including
camera fades. Do not use DeltaSeconds or elapsed wall time for those durations.

Covered features:
- Locomotion Walk-to-Run and Run-to-Walk checkpoint transitions.
- Post-attack pure-Run hold and return to Walk.
- Lower-body tempering hold and return of all four controls to1.
- Possessed player's full-attack camera offset fade: default1 means60 completed
  unpaused PostPhysics game ticks, zero snaps immediately; the component stops
  ticking when the fade finishes. No NPC camera fade and no permanent fade clock.
- Kick self-balancing pelvis-target hold and fade to the normal feet midpoint.
  Starts on kick return to locomotion; uses the shared bounded clock and cancels
  on a new attack, active defense or reset. Both0 disables with no active timer.
- Magnetization and feedback-tolerance blends, including conditional profiles,
  single/Below/All variants, and returns to saved snapshots.

The NN still runs at its existing frequency. A policy evaluation samples the
timer using the game ticks since its previous evaluation; calling it twice in
one game frame adds no time. It does not pretend that each30Hz NN step is one
60Hz game tick. Pose changes remain visible at the existing policy/presentation
cadence; no extra inference is introduced just to publish a blend endpoint.

No permanent clock: the shared callback exists only while timers are active.
Bounded timers retire from that callback at their deadline even if their consumer
is temporarily suspended; one final unread result is retained until consumed or
cancelled. Conditional-profile clocks stop when all their cells finish. Existing
physical property updaters likewise unregister when empty. Zero-duration bypasses,
single-checkpoint holds, and post-completion pose/IK/inference bypasses are retained.

Scope excludes Jolt stepping, root integration, pelvis bounds, attack/defense
termination rules, animation playback, and ordinary Blueprint Tick logic.

Validation: Live Coding build loaded without restart, 2026-09-19. Six focused tests
passed: SixtyTickClock (30/60/120FPS deltas, dilation ignored, duplicate reads,
hold/blend endpoints, deferred completion and callback retirement), ReturnTimeline,
PolicyBlend.AttackRecovery, PolicyBlend.DirectionalTiming, PhysicalBlends.RuntimeAndBatch,
and PhysicalContext.SelectionAndAttacks (including active blend transfer to an
attack override at tick15 and completion at tick60). The profile-transfer test was
updated from its obsolete single-update quarter-second assumption and rerun at
12:59UTC. No scene/Blueprint edits or whole-simulation FPS comparison were performed.
