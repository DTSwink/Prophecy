# Blend and tempering idle audit — September 23, 2026

Scope: authored transition/hold features and their extra pose/inference work,
not the baseline NN/physics simulation. Normal still has inexpensive branch or
lookup checks. A configured, intentionally non-normal continuous control must
continue doing its requested work.

| Feature | Completion/disabled path |
|---|---|
| Shared 60-tick clock | Finite clocks remove themselves from Active at their limit; unread final time is retained without ticking. Last active clock removes the world tick callback. Consume cannot double-advance. |
| Lower-body tempering, XY/Z, pelvis/feet and kick roles | Identity removes current settings, per-foot sidecars and return timelines. The manager skips tempering and leg reconstruction; ordinary policy correction remains. |
| FK-core tempering | Identity removes current values and stops its clock. Manager skips extra core decode/arm transport when no other hand/core control is active. |
| Hand tempering and recovery | Identity removes tempering values; completed recovery removes active source requests and clocks. Extra Walk/Run upper-checkpoint evaluation is guarded by HasRecovery and active source needs. |
| Ordinary Walk/Run and regional attack recovery | Finished transitions stop their clocks and remove regional Active state. Normal weights no longer request both checkpoints. Configurations remain for the next transition. |
| Physical magnetisation/tolerance blends | Last completed or cancelled entry removes its active agent and world tick delegate. Zero duration applies immediately. |
| Contextual physical profiles and damping/snapshot restores | Running=false stops the profile clock. Unchanged context returns before cell iteration/publication. Completed universal entries are removed. Deliberately different walk/run/equipment profiles retain a context check and update only on a context change. Stored snapshots are never scanned by the update path. |
| Clamp snapshot blends | Last entry removes Active and the tick delegate. Snapshots/configuration can remain without ticking. |
| Authored angular-limit return | Completed/failed/destroyed entries are removed; empty Active unregisters tick and cleanup delegates. |
| Kick foot-joint leeway return | Only returning entries request a callback; zero completion removes the temporary constraint allowance and callback. Holding an active kick allowance has no return timer. |
| Kick self-balancing exception | Finite shared clock; zero weight cancels and removes return state. |
| Attack camera offset/root-snap compensation | Fade completion/zero duration/unpossession stops the component tick and removes prerequisites. Only the possessed agent can activate it. |
| Slash right-arm neutral return | Finite return removes active state/clock; route, blade clearance and arm reconstruction are behind the active gate. |
| Continuous hand/pelvis inertia | All-one/disabled controls bypass spring/reconstruction. Configured values remain for future use; fixed inactive checks remain. |
| New attack upper-body inertia | Opt-in finite return; no separate tick, timer or extra inference. Active gate controls core work, and completion/special/reset removes motion/clock. |

The audit found one interruption gap: dodge admission cancelled leg recovery but
did not cancel hand recovery or slash arm return. Dodge now cancels those and the
new upper-body inertia immediately, as parry does. Queued, unarmed defense still
permits locomotion and does not cancel it prematurely.

No dormant interpolation loop or extra checkpoint inference was found after
normal completion. This is a source and lifecycle-test audit, not an assertion
of literally zero CPU instructions or a measured whole-game performance benchmark.

Follow-up: attack, parry and dodge now share entry cancellation and exit recovery.
The shared lifecycle test verifies regular profile restoration and complete
retirement for all three. The expanded suite passed all 33 tests at 13:43:43 UTC;
live natural/stopped defense episodes and six scene attack exits also completed.
The event uses no component or polling; key snapshots for defense callbacks are
allocated only while those defenses are active. See [SpecialRecovery](SpecialRecovery.md).

All 32 focused tests passed September 23 at 13:24:53 UTC, covering clocks,
tempering, policy/hand/slash recovery, physical profiles, clamps, damping,
angular-limit return, kick leeway/balance and camera fading. An older knee test
initially failed two assertions that still demanded an immediate branch flip;
those assertions now check the accepted unchanged-source branch-preservation
contract. No production leg-solving mathematics was changed. New tests also
check upper-body initial velocity, actual outgoing endpoint preservation across
root recentering, repeated publication, cancellation and cache retirement.
