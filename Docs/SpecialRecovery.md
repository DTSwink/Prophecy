# Shared special recovery

Specials are attack (full/half), active parry and active dodge. A queued defense
waiting for Armed is not yet a special and leaves locomotion controls available.

All three exit paths now share regional Walk/Run recovery, lower-body tempering,
spine-local hand tempering and hand source recovery, FK-core tempering, and the
upper-body inertia configuration. Defense exits select the regular profile;
kick limb roles are selected only by the agent's own kickL/kickR. The attacking
opponent's family must not select a defender's kick profile.

Entering any special cancels the previous locomotion recovery motion and clocks,
while preserving configured settings. Exiting to locomotion restores those
settings before the shared Blueprint event. This includes the regular lower-body
profile even when no kick override exists. Interrupted special-to-special changes
do not start a locomotion recovery.

**Special Ended** is exposed through the optional `ProphecySpecialRecoveryEvents`
Blueprint interface, avoiding a reflected layout change to the live base agent.
Its outputs are Special (Attacking/Parrying/Dodging), Attack (None for defenses),
Half Attack, and Returning To Locomotion. Existing Attack Ended remains attack-only.
Use the Returning To Locomotion pin to gate recovery commands. Event setters can
configure the current handoff before its first locomotion evaluation.

The existing nodes keep their names and pins for compatibility, including the
ones named Set Attack To Locomotion Blend, Set Attack To Locomotion Hand Blend,
Set Attack Upper Body Inertia and the camera fade duration. Their regular profiles
now cover all specials. The possessed-player camera follow and fade compensate
defense root recentering as they do attack recentering.

Intentional restrictions remain: kick leeway/self-balancing/kick recovery profiles
remain kick-only; right-arm sword wraparound remains slash-only, excluding pike.
Physical profile, clamp, damping, magnetisation and tolerance snapshot blends are
already mode-independent and can be called from the shared event.

Hold/blend times remain 60 unpaused game ticks per authored second. Normal/finished
returns retain no timer, extra inference or reconstruction. The interface is
dispatched only at an exit and needs no component or polling.

Validation completed September 23, 2026:

- Live Coding build succeeded; all 33 focused tests passed at 13:43:43 UTC,
  including `Prophecy.NN.SpecialRecovery.AllExitsAndRetirement`. The new test
  covers shared profile restoration, independent channels, interruptions and
  retirement for all three special states.
- The pose Blueprint now implements Special Ended. Its existing attack-ended
  recovery chain was transferred to Special Ended through a Returning To
  Locomotion branch, preserving downstream nodes, values and links. Original
  Attack Ended remains present and disconnected. The graph was exported before
  migration to `Saved/Diagnostics/BeforeSpecialRecovery-20260923-154632.txt`.
  Blueprint status3, zero stale native/pin types; no explicit asset save.
- Owned kinematic PIE exercised natural parry/dodge endings and explicit stops:
  all four became active, returned to locomotion, and remained there for 71
  captured return ticks with finite head transforms. Final checkpoint weights
  were Walk1/Run0. Inertia was enabled on transient test agents. Evidence:
  `Saved/Diagnostics/SpecialRecoveryLive-20260923-154645.json`.
- A separate unchanged-scene 600-frame capture completed six attack exits with
  finite pose transforms and no runtime errors. This is a bounded regression
  check, not a guarantee of visual perfection for every pose/profile. Evidence:
  `Saved/Diagnostics/CalfRoll-20260923-154715.json` and
  `Saved/Diagnostics/SpecialRecoverySummary.json`.

Owned Play sessions ended; Unreal remains open. The upper-body inertia node is
still opt-in and is not automatically connected by this event migration. Include
the live changes in the next authorized normal editor build before reopening.
