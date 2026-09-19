# Held sword collision during NN attacks

The attack phase automatically controls the held sword's collision:

| Phase | Slash / pike | Punch / kick / headbutt |
| --- | --- | --- |
| Attack starts | Ignore all channels | Ignore all channels |
| First Armed output | Restore original responses | Remain suppressed until Hit |
| First Hit output | Keep Armed-based state | Restore original responses |
| Attack finished, stopped, replaced or interrupted | Restore original responses | Restore original responses |

For slash/pike, Armed is latched for collision for the rest of the attack. For melee (punch/kick/headbutt), the first learned Hit output above 0.5 restores collision immediately, including the remaining recovery animation; Armed alone does not. These are NN outputs, not physical Event Hit callbacks. Once restored, a later low NN output does not suppress collision again. Full and half attacks share the rule. Starting a replacement attack resets the gate. Dropping restores the released sword's original responses.

The existing owner-body exclusions are separate: an attacking sword still ignores its wielder as before. Re-enabled collision retains the original channel responses rather than forcing BlockAll. Equipping or rebinding a held sword during an attack reapplies the current phase.

Implementation: `ProphecySwordAttackCollision` in `ProphecySwordComponent.cpp`, attack start/exit through `NotifySwordAttackState`, Armed transition and first latched HitFrame in `ProphecyNNSlashRuntime.inl`. Jolt updates the existing body's collision profile (including welded sword subshapes); the UE query/Chaos receiver uses the same response container. Bodies, grip constraints, mass and velocities remain intact. Kinematic PHAT/sword defense-stop queries respect the gate. Neural conditioning boxes are unchanged.

No added Tick callback, timer, actor scan or locomotion polling. Changes run on attack/equip/drop/backend events and the existing Armed/first-Hit transitions.

Focused engine test: `Prophecy.Jolt.Sword.AttackCollisionPhases`.

2026-09-19: melee Hit restoration installed through Live Coding without restart (137.52 s). The focused test passed at 09:45:11 UTC, checking saved UE/native Jolt responses for simulated and attached swords, repeated/latched Hit, weapon Hit-before-Armed, replacement/cancel/drop, unchanged body/joint counts, and kinematic melee restoration. No Blueprint/map changes or scene rollout.
