# Runtime locomotion limb clamps

Use `Get Actor of Class`, choose **Prophecy NN Locomotion Manager**, then drag from its Return Value to create these variable Set nodes. Cache the valid manager reference for repeated use. In the manual agent, run this after `Ensure Standalone NN Manager` during initialization (or once the manager exists during play).

Do not use `Get World Subsystem → Get Manager` in testNN: that subsystem is only created for locomotion-named maps or the explicit locomotion command-line mode. Manual agents create their manager directly, so the subsystem lookup returns None even while the NN is running.

| Enable node | Length node | Meaning |
| --- | --- | --- |
| Set Clamp Hand | Set Hand Clamp Length Multiplier | Maximum hand distance from elbow, relative to authored forearm length. |
| Set Clamp Foot | Set Foot Clamp Length Multiplier | Maximum foot distance from thigh, relative to total authored leg length. |
| Set Clamp Calf | Set Calf Clamp Length Multiplier | Places foot at the specified authored calf-length multiple from the knee, including extending it when closer. |

The manager reads these settings on each pose publication; changes work during play and affect all its agents, both sides. Multiplier `1` means authored length, `1.1` means 10% longer, `0.9` means 10% shorter. Use the enable checkbox to disable a clamp. Matching Get nodes read the current settings.

Hand defaults remain enabled at `1.0`, preserving the previous hard-coded limit. Foot/calf settings and saved overrides are unchanged. These are pose controls, not PHAT joint limits. Physical animation receives the resulting target pose.

As of 2026-09-12, **full-body Slash attacks also apply Clamp Foot and Clamp Calf** to their decoded pose, before the existing visible-pose/locomotion feedback encoding. Previously the attack replaced the already-clamped locomotion legs, bypassing both controls. Half attacks retain the clamped locomotion legs. Raw Slash model outputs/history are unchanged; hand correction remains separate.

When Clamp Calf is active with a positive multiplier, interpolation preserves the published calf-to-foot offset and carries the toes with the foot. This applies to the kinematic mesh, physical-animation targets and individual NN foot/toe transform reads. Use **Clamp Calf = true**, **Calf Clamp Length Multiplier = 1** to keep feet attached at authored calf length. Clamp Foot alone bounds hip-to-foot reach and does not fix calf length.

For the **unclamped original Slash/training pose**, set **Clamp Foot = false AND Clamp Calf = false** on the owning manager. Disabling only Clamp Foot leaves the separate calf-length correction active. These switches already work at runtime for full attacks. They are global to that manager, as for locomotion.

Foot pinning runs in the source NN transition before these optional presentation clamps. A fixed calf length can move the foot away from its pinned endpoint, including below the floor: the current hook scene measured **2.35 cm** left-foot penetration with Clamp Calf on. Both clamps off restored raw foot targets within **0.0002 mm** of their source-decoded position; the actual kinematic mesh's contact-geometry variation was below **0.8 mm** over40s. Strict source parity permits the variable calf-to-foot distance present in training. See `Docs/SlashFootContactsAndCamera.md` for the matched tests and their limits.

Validated in the user's current testNN attack chain over 50 seconds: generated endpoint gap is effectively zero; largest measured gap in the actual kinematic mesh was **0.00559 cm (0.056 mm)**. Five PhysicalTargets tests passed. Details: `Docs/AttackFootClampFix.md`.
