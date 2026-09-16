# Per-limb Jolt collision

Configure a live agent once using **Set Jolt Limb Collision Channel** and **Set Jolt Limb Collision Response**. `Bone Name` selects an exact PHAT body. **Include Children** also selects its descendant PHAT bodies; for example, `thigh_r` includes the right calf and foot. Calls return success and an error message.

To suppress leg–leg contacts:

1. For `thigh_r` and `thigh_l`, enable **Include Children** and set **Object Channel = ProphecyAgentLeg**.
2. For the same selections, set **Channel = ProphecyAgentLeg**, **Response = Ignore**.
3. Apply this configuration to each participating agent.

Other collision responses retain their captured values. A body on the normal limb channel can still block the legs. These are standard object-channel filters, so the selected response also applies to any enabled self-contact pair using that channel; the PHAT self-collision pair table itself is unchanged. Overlap suppresses blocking but does not implement overlap notifications.

The settings apply in locomotion. Full/half attacks, parry and dodge use the original native filters captured before the first override. Locomotion reapplies the configured settings automatically, including after a rig is recreated. Changes made during combat are remembered for locomotion. The native filter change occurs before the next physics step; setting nodes apply immediately when called at the normal gameplay boundary.

**Get Modified Limb Collision Bones** returns the tracked bodies, including suspended overrides. **Get Jolt Limb Collision Response** reads the actual native object channel/response and whether this body is tracked and currently using its locomotion override. **Reset Jolt Limb Collision** restores the captured settings and removes the selected bodies from the list; `pelvis` with Include Children selects the whole rig.

These nodes affect Jolt simulation filters. They do not edit PHAT assets or the Chaos query receiver's channel settings. Ordinary whole-mesh filter changes do not silently erase a configured limb override. No new tick, polling of bones, or body rebuild is introduced. Unconfigured agents only pass the empty-state guard; configured agents perform filter updates on configuration, mode, rig, or whole-mesh filter changes.

`ProphecyAgentLeg` uses the previously unused `ECC_GameTraceChannel11`, default Block. The editor-only `Prophecy.Collision.ReloadChannels` command reloads channel configuration outside PIE so the new name can be used without restarting.

Validation (2026-09-16): Live Coding build/install succeeded. Actual testNN PIE read native filters for a three-body right-leg selection, unaffected hand/third agent, invalid-bone atomic rejection, active slash, live NN parry/dodge, return to locomotion and reset/list cleanup; all passed, shared Jolt world healthy (71 steps). `Saved/Diagnostics/LimbCollisionLifecycle.json`. Python glue predates the live-added class/channel, so the script invokes the Blueprint functions through reflection and uses the existing Vehicle channel for its generic filter checks; the new Leg channel's loaded configuration/name was separately verified. No asset edits or saves and no performance benchmark.
