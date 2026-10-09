# Half-attack reach and pair-specific defense contacts

October 8, 2026. Runtime rules apply when NN Dodge/Parry actually activates (after its existing Armed gate), and are released by the existing defense-stop/reset/teardown paths. The existing post-Hit and maximum-duration settings are unchanged.

## Contacts

- **Dodge:** suppress contacts between this dodger's bodies and its attacker's attacking bodies. Other agents, the world, and the attacker's non-attacking bodies retain their normal collision rules.
- **Parry:** protect the parrier's Blueprint `trunk` list plus `upperarm_l/r`, `lowerarm_l/r`, and `hand_l/r` against its attacker's attacking bodies. Those protected bodies have zero inverse-mass and inverse-inertia scale in that contact's Jolt solver settings. The attacking side retains its normal scales. Actual mass, drives, gravity and other contacts are unchanged; joints can still transmit forces from other, unprotected contacts.
- The current Blueprint trunk list is `spine_01` through `spine_05`, `clavicle_r/l`, `neck_01/02`, `head`, and `pelvis`. It is read once at defense entry; only bodies actually present in the PHAT rig are bound. The same list is the native-agent fallback when there is no Blueprint property.
- Attacking-body membership uses the existing shared attack-role mapping: slashes and sword pike include the sword **and hand_r**; punches use their hand and forearm, without adding a held sword. Welded swords retain their logical identity.
- Rules have independent owners and generation-checked handles. Existing sword/self/joint exclusions are reference counted, not overwritten. Rig/sword identity changes rebind through the existing physical update; no additional physics step, sweep or NN inference is introduced. The ordinary contact listener remains the normal path when no parry protection is active.

## Blueprint controls

**Visualize Defense Input Ghost**: call on the defender each Tick to draw the actual
filtered previous/current attacker pelvis and single trained collider. Supports
both Parry and Dodge, including half attacks, alongside the complete accepted
defender pose (upper body and legs).
[Node pins, colors and input-coordinate contract](DefenseInputGhost.md).

**Set Half Attack Minimum Reach**: `Agent`, `Distance Cm = 30`. Clamp the half-attack shared NN target away from the real predicted pelvis in the world horizontal plane before inverse-mount reach conversion. Preserve target world height. At exactly zero horizontal separation, use the agent's forward direction. Zero disables the clamp. Full attacks retain their original targets. Both half-attack models receive the resulting compensated target. Existing spine/position compensation remains separately controlled.

**Set Defense Half Attack Horizontal Velocity**: `Agent`, `Remove = false`. Configures that defender's Dodge and Parry perception. When observing a half attack, remove the attacker's horizontal pelvis displacement from its two conditioning samples and subtract the same displacement from the attack collider's perceived motion. Current positions, rotations, vertical motion, target, actual attack and collision geometry stay unchanged. Synthetic spear input is bypassed; a sword `pike` is not the synthetic spear feature.

**Visualize Ghost Attack**: the red target now uses the shared lower/upper target actually consumed by the accepted native half-attack prediction, including minimum reach and inverse mounting. Its pose and marker still share the supplied drawing offset. Both ghost models now use that same target. Preview predictions cache their corresponding target and do not publish a marker until accepted.

**Get NN Attack Target** uses that same accepted cache for Effective World Target (clamped real target) and Ghost World Target (shared attack-policy target). Requested World Target stays the gameplay request. A retarget between policy steps can therefore change Requested before the other two pins reflect the next accepted prediction.

## Verification

Native checks are available through `Prophecy.Defense.VerifyCombatMath` and `Prophecy.Jolt.VerifyScopedContacts`, which avoid entering global Unreal automation mode. Their registered automation equivalents are `Prophecy.NN.Defense.CombatMath` and `Prophecy.Jolt.Contacts.ScopedDefense`. Event-only live rule tracing is opt-in via `Prophecy.DefenseContacts.Audit 1`.

Eight distinct native tests passed, including all existing HalfAttack checks and the new ContactLifetime check. Final contact fixtures pass 318 assertions across both body orders, suppression ownership, unrelated pairs, zero direct linear/angular reaction, removal from a persistent contact and endpoint deletion. The 87 math assertions cover horizontal-only clamping, coordinate-frame covariance, target height, exact bypass and spear exclusion. At the time of that upper-only implementation, four checkpoint families retained bit-identical lower predictions with reach/clamping enabled; the later shared-target fix intentionally supersedes that isolation contract.

Owned live tests on the current scene ran through absolute tick257 for Parry, Dodge, the optional filter, and a temporary slashL. The actual Blueprint trunk list plus arms bound16 PHAT bodies (neck_02 is absent as a separate collider), producing32 parry pairs against the two attack bodies. Dodge bound23 bodies including its held sword, producing46 pairs. Filter traces contain exactly zero horizontal pelvis displacement in7 Parry samples and1 Dodge sample. These checks verify the installed paths and contact mechanics; they do not rate the resulting learned defense motion. Receipts: `Saved/Diagnostics/DefenseCombatRules20261008/`.


## Root alternative for half-attack velocity removal (October 8)

**Set Defense Half Attack Horizontal Velocity** now also has **Use Root Velocity**, default false. **Remove** remains the master switch. Unchecked retains the exact pelvis-based filter; checked subtracts the attacker root's horizontal displacement over the same two published policy samples from both perceived pelvis and attack-collider displacement. Thus pelvis motion relative to the root remains visible, while root translation is removed once from both channels. Current positions, rotations, vertical motion, physics and NN recurrent state are unchanged. Both Parry and Dodge use it; full attacks and synthetic spear bypass it. Root samples are already stored by the attacker; no new history, actor scan or inference. Disabled entries are removed and the filter exits before any arithmetic.
