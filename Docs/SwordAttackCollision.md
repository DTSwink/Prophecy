# Body and held sword collision during NN attacks

The attack phase automatically controls the held sword's collision:

| Phase | Slash / pike | Punch / kick / headbutt |
| --- | --- | --- |
| Attack starts | Ignore all channels | Ignore all channels |
| First Armed output | Restore original responses | Remain suppressed until Hit |
| First Hit output | Keep Armed-based state | Restore original responses |
| Attack finished, stopped, replaced or interrupted | Restore original responses | Restore original responses |

For slash/pike, Armed is latched for collision for the rest of the attack. For melee (punch/kick/headbutt), the first learned Hit output above 0.5 restores collision immediately, including the remaining recovery animation; Armed alone does not. These are NN outputs, not physical Event Hit callbacks. Once restored, a later low NN output does not suppress collision again. Full and half attacks share the rule. Active Trigger updates do not restart the gate: same weapon/melee class retains its collision latch; changing between classes applies the new rule to the preserved Armed/Hit phase, retaining original responses/body/grip. Stop followed by a fresh Trigger resets the gate. Dropping restores the released sword's original responses.

Owner-body exclusions are separate: the sword ignores its wielder until the first
NN **Hit** output, then restores normal sword-owner contact during the remaining
attack animation. The gripping-hand exclusion remains. This is latched for every
attack family, including equipment/rebinding after Hit; it does not switch off
attack sweeps, special solver iterations or attack physical profiles. Stops,
interruptions and completion still restore normally if Hit never occurs. Re-enabled collision retains the original channel responses rather than forcing BlockAll. Equipping or rebinding a held sword during an attack reapplies the current phase.

Jolt body-body self-collision follows the same until-first-Hit lifetime, for every
full/half attack, including attacks without a sword. Armed does not restore it.
The attack temporarily masks the rig's collision filter; it does not overwrite
the configured master toggle, disabled-body/pair overlays or authored PHAT exclusions.
Blueprint changes to those settings during an attack remain stored, but cannot
re-enable self-collision before Hit. Hit/end removes only the attack mask, so a
globally disabled rig remains disabled and excluded pairs remain excluded.
Dropping a sword does not remove this body mask. Creating/rebinding a Jolt rig
during an attack reapplies the current phase before admission to simulation.
Other agents/environment keep their existing collision rules. PHAT sweeps check
the same native collision group, so they respect the body mask too.

The native mask is sparse rig-lifetime state, removed when its rig is destroyed.
Only phase/configuration events update the existing filter and invalidate affected
contact caches. No bodies/constraints are rebuilt; no per-tick or per-contact
lookup, timer, NN change, or new locomotion work is introduced. This body mask is
for the Jolt physical backend; kinematic presentation has no body self response.

Implementation: `ProphecySwordAttackCollision` in `ProphecySwordComponent.cpp`, attack start/exit through `NotifySwordAttackState`, Armed transition and first latched HitFrame in `ProphecyNNSlashRuntime.inl`. Jolt updates the existing body's collision profile (including welded sword subshapes); the UE query/Chaos receiver uses the same response container. Bodies, grip constraints, mass and velocities remain intact. Kinematic PHAT/sword defense-stop queries respect the gate. Neural conditioning boxes are unchanged.

No added Tick callback, timer, actor scan or locomotion polling. Changes run on attack/equip/drop/backend events and the existing Armed/first-Hit transitions.

Focused engine test: `Prophecy.Jolt.Sword.AttackCollisionPhases`.

September25 body-mask change: expanded phase tests cover body-pair suppression
through Armed, restoration at Hit/end and sword drop retaining body suppression.
`Prophecy.Jolt.Collision.SelfCollisionLayersAtomic` additionally checks runtime
edits/reset behind the mask, global-off preservation, native identity/target
retention and destruction/reuse cleanup. Live Coding compiled successfully
(final incremental build16.89s) and loaded17:13:35UTC. Both expanded tests passed
17:14:20UTC. They ran only after Play was already stopped; no user Play was
interrupted. No scene/BP settings changed or saved, no restart, no scene rollout.
Include in the next authorized normal editor build.

2026-09-19: melee Hit restoration installed through Live Coding without restart (137.52 s). The focused test passed at 09:45:11 UTC, checking saved UE/native Jolt responses for simulated and attached swords, repeated/latched Hit, weapon Hit-before-Armed, replacement/cancel/drop, unchanged body/joint counts, and kinematic melee restoration. No Blueprint/map changes or scene rollout.

September22 kick-profile/Hit validation: normal editor build succeeded (108.36s),
testNN reopened, both new nodes reflected, and all three existing recovery nodes
refreshed with other values/connections preserved. Pose Blueprint compiled and saved.
Six focused tests passed at19:14:49UTC: KickProfiles, AttackRecovery, ReturnTimeline,
SeparateReturns, SixtyTickClock, and Jolt Sword AttackCollisionPhases. The latter
checks native owner-pair restoration at Hit for simulated and attached swords,
retained attack context, repeated refresh, and stable body/joint counts. No scene
rollout. Evidence: `Saved/Diagnostics/KickProfilesValidation.txt`.
