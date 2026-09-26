# Left-hand bend constraint

`Set Left Hand Constraint` takes **Agent**, **Enabled=false**, **Mode=All** and **Max Bend Degrees=55**. Settings belong to each agent. Modes are Locomotion, Attack, Parry and Dodge; All updates all four. Call separately to retain different settings per mode.

Attack is always **55 degrees**, regardless of the angle pin, including full/half attacks and every checkpoint choice. Other modes accept finite angles from0 inclusive to180 exclusive. Invalid enabled settings are rejected without changing existing settings. Disabling All removes the agent's entry. No Blueprint node has been wired automatically.

The rule is the training `training/slashes2/slash2_wrist_neutral.py` `WristNeutral`: constrain anatomical left-hand +X to a cone around elbow→wrist, rotate only the excess bend via shortest swing, add no axial twist. Preserve all positions and the right hand. In-cone rotations pass through unchanged. A zero-length forearm passes through; exact antipodes use hand Y as the deterministic turn axis. This is a wrist bend constraint, not a forearm-roll lock.

For attacks it runs in the shared native decoder after candidate upper FK, before output. Both decoded hand rotation and recurrent upper hand rotation receive the same correction; no second FK, network execution, new history or phase restart. Settings are passed per inference lane, including half-attack ghosts. Existing constraints baked into a model remain when this optional override is disabled; already in-band rotations receive no further change.

Locomotion (Walk and Run), dodge and parry use their chosen limit on published pose endpoints, after existing pose/clamp/tempering work. The published local hand transform is rebuilt when changed. These non-attack limits affect visible/physical targets, not those checkpoints' recurrent buffers. Half attacks select the attack rule, not the locomotion rule. Existing interpolation remains unchanged between endpoints.

All modes are off by default. Disabled paths perform only configuration/branch checks: no wrist math, pose copies, extra FK, inference, timers or per-frame allocations. Weak per-agent entries are removed when disabled or their world is cleaned up. No actor/model persistent layout change.

## Validation2026-09-26

- Live Coding succeeded60.77s, loaded11:27:35UTC. Reflected node callable; no restart or asset save.
- `Prophecy.NN.AttackWrist.Math`, `.AllCheckpoints`, `.Modes` passed11:28:05UTC.
- All four installed attack models:20-step sequences each, actual out-of-cone correction exercised, only the left-hand rotation/output-state fields change on identical input; disabled versus original output bit-identical; emitted hand inside55-degree cone.
- Mode tests cover disabled defaults, independent agent/mode settings, All, attack55 despite supplied12/30, invalid-input atomicity, disable/removal, variable0/30/55/70/150-degree UE pose constraints and unchanged hand position.
- `Tools/NN/ValidateAttackWrist.py` compares260 native samples against the actual training implementation. Maximum rotation-basis coefficient error5.96e-7. Includes in-band, zero-length and antipodal cases. Evidence `Saved/Diagnostics/AttackWristMath.csv` and `AttackWristMath-oracle.json`.
- Initial model fixture used only already-valid wrists and failed its coverage assertion; reversed initial wrist history added to exercise the correction, without changing implementation to fit the test.
- No scene-play visual certification. Fold Live Coding changes into the next authorized normal editor build before a fresh launch.
