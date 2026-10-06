# Body and held sword collision during NN attacks

**Set Own Sword Collision Enabled** (category `Prophecy | Agent | Sword`) is the
manual owner-only control. Pass the agent and **Enabled = false** to suppress
contact between their held sword and their own physical bodies. Other agents,
world contact, sword channel responses, body-body self-collision, grip and
velocities retain their existing rules. True restores the normal attack-phase
owner behavior below; it does not bypass the attack's owner-suppression phase, and the
gripping-hand and gripping-forearm exclusions remain. It is enabled by default and can be configured
before equip. The preference survives attack Hit/end, rebind and future equips;
drop removes the released sword's exclusions. Agent/controller EndPlay and world
cleanup clear preference state. The control uses existing Jolt and Chaos pair
exclusion paths, with no added ticking, body recreation or inference. It does not
change independent Blueprint damage/cutting trace logic. The existing **Set Sword
Collision Enabled** is the separate global held-sword collision toggle.

The attack phase automatically controls the held sword's collision:

| Phase | Slash / pike | Punch / kick / headbutt |
| --- | --- | --- |
| Attack starts | Suppress sword-owner pairs only; external channels stay active | Ignore all channels |
| First Armed output | Restore normal sword-owner pairs | Remain suppressed until Hit |
| First Hit output | Keep Armed-based sword-owner state | Restore original responses and normal owner pairs |
| Attack finished, stopped, replaced or interrupted | Restore normal owner pairs | Restore original responses and normal owner pairs |

For slash/pike, Armed is latched for collision for the rest of the attack. For melee (punch/kick/headbutt), the first learned Hit output above 0.5 restores collision immediately, including the remaining recovery animation; Armed alone does not. These are NN outputs, not physical Event Hit callbacks. Once restored, a later low NN output does not suppress collision again. Full and half attacks share the rule. Active Trigger updates do not restart the gate: same weapon/melee class retains its collision latch; changing between classes applies the new rule to the preserved Armed/Hit phase, retaining original responses/body/grip. Stop followed by a fresh Trigger resets the gate. Dropping restores the released sword's original responses.

Since October 6, slash/pike preparation no longer disables sword contact with
opponents or the world. It suppresses only the owner's pairs until **Armed**.
Punch/kick/headbutt behavior remains unchanged: all sword channels and owner
contact remain suppressed until the first NN **Hit** output. The explicit global
**Set Sword Collision Enabled=false** still overrides either attack family.
The gripping hand and its parent forearm stay excluded for the
entire held lifetime, including after Hit/end, owner-collision re-enabling, and
grip/backend refresh. Dropping removes these held exclusions and restores normal
collision eligibility. This applies to simulated and attached swords on Jolt and
Chaos, using the configured hand socket to choose the arm. Phase state is latched,
including equipment/rebinding after Armed/Hit; it does not switch off
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

Implementation: `ProphecySwordAttackCollision` in `ProphecySwordComponent.cpp`, attack start/exit through `NotifySwordAttackState`, Armed transition and first latched HitFrame in `ProphecyNNSlashRuntime.inl`. Owner changes update existing Jolt/Chaos pair exclusions, including welded sword subshapes. Melee and explicit global disable still update the existing body's channel profile and UE receiver. Bodies, grip constraints, mass and velocities remain intact. Kinematic PHAT/sword defense-stop queries accept weapon preparation, while retaining the melee/global-disable gate. Neural conditioning boxes are unchanged.

No added Tick callback, timer, actor scan or locomotion polling. Changes run on attack/equip/drop/backend events and the existing Armed/first-Hit transitions.

Focused engine test: `Prophecy.Jolt.Sword.AttackCollisionPhases`.

October 2 held-forearm change: Jolt simulated/attached fixtures now assert two
held exclusions (hand and forearm), retention across Hit/re-enable/refresh, and
complete removal on drop. These assertions passed in the 21:03:44 UTC run, but
the test as a whole failed two pre-attack channel checks: its asymmetric UE-only
response setup had not initialized the native Jolt response. The fixture now
initializes both copies explicitly; that correction compiled and loaded at
21:05:39 UTC. A complete rerun was deferred because user Play was active and was
preserved. Do not report the whole test passed yet. The gameplay fix loaded at
21:03:11 UTC and a separate owned TestNN replay reduced tick-200 hand error from
25.845 to 0.288 degrees. No asset/settings edits; include source in the next normal
editor build before cold launch. [Diagnosis and replay](HandPhysical200Diagnosis.md).

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
