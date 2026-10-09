# Separate FK return controls

- **Set Attack FK Return Values** changes only Return Time, Inertia and Easing. It preserves the attack's current bone weights, momentum hold/decay, world/local space and spine-angle time. If no override exists, these are taken from the imported lab profile.
- **Set Attack FK Return Inertia Profile** changes only Bone Inertia, Inertia Hold, Inertia Decay, World Inertia and Spine Angle Time. It preserves Return Time, Inertia and Easing. These pins are visible rather than hidden behind Advanced Display.
- **Set Attack FK Return Twist Inertia** changes only Remove Twist (0–1), symmetrically for both upperarms. Zero retains the original inertia; one removes its axial twist while preserving swing. Other profile setters preserve this field, except the legacy combined override which replaces the complete profile. The imported slashLD profile uses .98; other families default to zero.

All accept Agent and Attack. Attack None updates the respective fields for all families while preserving each family's other settings. Their execution order does not matter. Changes apply at the next attack end; the existing Set Attack FK Return node still independently controls enable, NN takeover shape and per-attack hold/trim.

The former combined native function remains compatible with existing Blueprint wiring, named **Set Attack FK Return Combined (Legacy)**, and is hidden from the new-node menu. Replace the earlier combined node with **Set Attack FK Return Values** to adjust only the three main controls. Keeping the legacy node connected still applies all its old hidden overrides.

The setters resolve and merge profiles only when executed. There is no additional per-tick lookup, inference, allocation or blending. Reset snapshots retain the merged profiles through the existing mechanism.

Focused test `Prophecy.NN.FKReturn.SeparateSetters` covers imported defaults, independent updates, call order, all-family preservation, input rejection and reset restoration. Existing `LifecycleAndCurve` checks compatibility of the combined API.
