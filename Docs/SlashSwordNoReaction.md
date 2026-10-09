# Automatic slash sword no reaction

`Set Slash Sword No Reaction` takes Agent/self, Enabled (default false), and Strength (default 1).
Call once to configure; it is event-driven, with no additional tick or physics pass.

Strength 0 keeps normal response; 1 removes sword reaction completely. Values between apply a contact inverse-mass and inverse-inertia factor of `1 - Strength`. For example, 0.5 uses half the normal inverse mass/inertia in that contact. The solver also recalculates the contact impulse, so this does not promise exactly half the resulting velocity/displacement. Actual body mass, inertia and joint settings are unchanged. Finite values clamp to 0–1; nonfinite values are rejected. The setting survives attack boundaries and can be changed while active.

- Normal reaction during wind-up.
- No reaction from the first accepted Armed event through the slash's end.
- Normal reaction while the assigned attack victim is actively dodging or parrying.
- If no Victim was supplied to Trigger NN Attack, any active defense against this attacker blocks the automatic effect.
- Queued defenses waiting for their start delay do not count as active defense.
- Pikes and melee attacks are excluded; collision cooldown after attack end does not extend this effect.
- Existing `Set Sword No Reaction = true` remains an unconditional manual override. Leave it false to use the automatic conditions.
- Disabling automatic mode removes its contribution immediately. Preferences survive equip/drop; dropped swords retain normal response.

Reuses the existing Jolt logical-sword response toggle, including welded swords. It does not change collision enablement, direct hand response, NN poses, or inference. Defense updates visit only opted-in agents on transitions; the backend avoids updates when its state is unchanged.

Implementation: SwordComponent sidecar and existing attack phase / defense binding / victim assignment transitions. Native automation `Prophecy.Sword.SlashNoReactionGate` covers all six slash families, wind-up, Armed latch, defense start/stop, manual override, excluded families, assigned/unassigned victim, repeated enable and disable. Existing `Prophecy.Jolt.Contacts.SwordNoReaction` covers native independent/welded body response.

Fractional version verified October 9, 2026: normal incremental DLL build succeeded and TestNN reopened (PID8216). Blueprint and Python expose Enabled=false / Strength=1. All five focused native tests passed: SlashNoReactionGate, Jolt.Contacts.SwordNoReaction, Jolt.Contacts.SwordReactionStrength, Jolt.Contacts.ScopedDefense and NN.Defense.ContactLifetime. Tests include independent/welded swords in both body orders, intermediate reaction below the normal endpoint, exact zero-reaction endpoint, composition with scoped protection, and restoring the saved strength after defense/attack transitions. Blueprint status3/native_properties0/pin_types0; normalized graph and saved BP bytes unchanged. Save-before-close found no dirty packages. No Blueprint/map wiring or tuning edits, no gameplay replay. This version is present in normal DLLs, not only a Live Coding patch. Receipts: `Saved/Diagnostics/FractionalSlashSword20261009/`; original boolean-node checks: `Saved/Diagnostics/SlashSwordNoReaction20261009/`.
