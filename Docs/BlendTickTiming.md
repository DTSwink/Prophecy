# Project-wide golden rule: tick-based timing

Reaffirmed by the user on 2026-10-02 as a **general project-wide golden rule**, not
a rule limited to one recovery system: gameplay time progression is tick-based,
never wall-clock based. Hitches do not authorize extra progression or catch-up.
Apply this to every new feature/timing change; real-time exceptions require an
explicit user instruction.

User-approved convention, 2026-09-19: one duration unit labelled "second" means
60 unpaused game-world ticks, independently of FPS and time dilation. This is
deliberately a tick-count contract, not a promise of identical physics at different
FPS. At30FPS, a60-tick blend takes2 real seconds; at120FPS it takes0.5 real seconds.
At5FPS it takes12 real seconds. A .26-unit return requires16 ticks, approximately
3.2 real seconds at5FPS, regardless of the duration of an individual hitch.
Apply this convention to newly added authored blend/fade durations too, including
camera fades. Do not use DeltaSeconds or elapsed wall time for those durations.

Covered features:
- Attack FK return, its angular inertia decay, easing, and NN takeover coefficient:
  all sample one shared tick phase. Repeated publications/catch-up NN steps do not
  spend additional ticks. The initial October2 world-time version is superseded.
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

The NN scheduler now receives exactly 1/60 authored second per unpaused game tick.
At the default 30 Hz policy this is one evaluation every two game ticks, including
at 5 FPS or after a long hitch. Explicit per-agent locomotion rates are preserved;
attack frames use the shared cadence. Engine timestamps identify pose samples only.
Animation-layer playback and all layer fades consume their own shared tick clock.
Fist closing/opening and simulation-mode transitions also use this clock.
Legacy hand/target-pelvis inertia integrates the supplied fixed policy interval,
not differences between publication timestamps. The optional attack cone inherits
the fixed policy cadence. DoubleReach playback and smoothing spend at most one
1/60 interval per game frame.

The NN retains its configured policy interval. A policy evaluation samples the
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

The October 2 audit correction extends the earlier FK-only change to native NN
scheduling, animation layers, fists, mode fades and DoubleReach. Physics solver
stepping, external Sim Bridge delivery and Blueprint logic are unchanged; this
is not a claim of fully deterministic rigid-body physics across FPS. Diagnostic
watchdogs and profiling use elapsed real time intentionally: they measure or stop
the tools and do not advance gameplay.

FK return correction,2026-10-02: four focused tests passed after a normal DLL
build and fresh TestNN launch. The actual returning transforms match by tick at
5/30/60/120FPS; a20-second hitch consumes one tick, duplicate/catch-up reads add
none, and paused/zero-time ticks add none. Integer deadlines retire .1/.3/.7/1.0
duration pins exactly. See `Saved/FKReturn/tick-final-tests.log`.

Validation: Live Coding build loaded without restart, 2026-09-19. Six focused tests
passed: SixtyTickClock (30/60/120FPS deltas, dilation ignored, duplicate reads,
hold/blend endpoints, deferred completion and callback retirement), ReturnTimeline,
PolicyBlend.AttackRecovery, PolicyBlend.DirectionalTiming, PhysicalBlends.RuntimeAndBatch,
and PhysicalContext.SelectionAndAttacks (including active blend transfer to an
attack override at tick15 and completion at tick60). The profile-transfer test was
updated from its obsolete single-update quarter-second assumption and rerun at
12:59UTC. No scene/Blueprint edits or whole-simulation FPS comparison were performed.
