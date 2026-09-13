# Locomotion controls and NN input debug mesh

2026-09-13. Installed in the normal Editor build (`BuildLocomotionInstall.log`). Unreal reopened on testNN; verification completed with PIE stopped and no dirty assets.

All nodes target a **Prophecy Agent**, so settings can differ between agents and change during play.

## Locomotion clamp leeway

- `Set Locomotion Foot Clamp(Enabled, Leeway Cm)`: caps thigh-to-foot distance at the total rest leg length plus leeway. It does not force the leg straight.
- `Set Locomotion Calf Clamp(Enabled, Leeway Cm)`: keeps knee-to-foot distance within rest calf length ± leeway. Zero is exact; one permits one centimetre in either direction.
- `Set Locomotion Hand Clamp(Enabled, Leeway Cm)`: caps elbow-to-hand distance at rest forearm length plus leeway.
- `Set Locomotion Forearm Clamp(Enabled, Leeway Cm)`: keeps elbow-to-hand distance within rest forearm length **± leeway**. Zero is exact; one permits 1 cm of shortening or stretching. It acts on both arms and supersedes the one-sided Hand Clamp while enabled. Disabling restores the existing Hand Clamp setting. This new option defaults off.

Disabled preserves the decoded positions. Negative or nonfinite leeway returns false without changing the setting. Until a node is called, the agent inherits the manager's existing controls. These overrides use rest length directly; the manager's old length multipliers apply only when no override has been set.

Foot/calf controls also apply to the locomotion legs during half attacks. Full attacks retain their separate `Set Attack Foot Clamp` and `Set Attack Calf Clamp` controls. Locomotion hand controls are separate from `Set Attack Hand Clamp`. Calf and attack-hand leeway also carry through render interpolation, so interpolation does not silently restore an exact clamp.

## Attack hand clamp

`Set Attack Hand Clamp(Enabled, Leeway Cm)` controls both hands in full and half attacks, independently per agent. Default is enabled with zero leeway, preserving the existing reference-animation wrist attachment.

- Enabled, 0: exact skeleton rest offset from the forearm.
- Enabled, 1: allows up to 1 cm of positional deviation from that attachment, leaving positions inside the band untouched.
- Disabled: preserves raw attack hand positions and disables the corresponding interpolation correction.

Hand rotations, forearms, raw attack NN recurrence and locomotion clamp settings are unchanged. Changes apply on the next attack pose update. Negative/nonfinite leeway returns false without modifying the setting. The same rule is used for the published pose and both interpolation modes.

These are geometric reach controls, not floor collision or foot pinning. They do not alter the locomotion model's recurrent state.

Forearm Clamp applies to locomotion arms, with the same band enforced after both interpolation modes and on physical-animation targets. Full and half attack arms retain their separate Attack Hand Clamp. Forearm Clamp moves the hand endpoint to bound segment length; it does not change the elbow's location or physical joint limits. Outside the band it retains the elbow-to-hand direction. Inside the band it leaves the prediction untouched. The existing hand-based forearm rotation reconstruction remains in use.

## Root window

`Get Locomotion Root Window` returns success plus arrays `World Roots` (transforms in Unreal world centimetres) and `Time Offsets Seconds`:

| Index | Sample | Time offset at 30 Hz |
|---|---|---|
| 0 | Previous root | −1/30 s |
| 1 | Current input root | 0 |
| 2–9 | Eight future roots | +1/30 through +8/30 s |

The window belongs to the **last encoded locomotion input**, with future positions decoded from its actual normalized/clamped features. It does not predict a new trajectory when queried, and it does not use a drawing/debug cache. Rotation follows the agent root convention. Root position is the ground-level carrier position, not the pelvis or capsule centre. Returns false before the first policy input. If inference is paused, it remains the last input window. During an attack, this still reports the background locomotion policy; Slash's ghost has its own fixed frame.

## Previous-input pose mesh

Call `Set Show NN Previous Pose Debug Mesh(Enabled, Prefer Attack)` and use the returned poseable mesh with `Set Material`. The same reference is available as the read-only Blueprint variable `NN Previous Pose Debug Mesh`.

- `Prefer Attack = true`: displays the previous encoded Slash pose while attacking, otherwise previous locomotion inputs.
- `Prefer Attack = false`: always displays the previous locomotion lower/upper inputs, including while a half attack runs separately.
- Disable destroys the component and removes the agent from the debug update list. Enable again returns a new component, so assign its material again.

The renderer reads input tensors before inference mutates history. It reconstructs the encoded control bones without presentation clamps; bones without NN channels are reconstructed through the usual skeleton decoder. For half attacks, the attack view includes the **ghost lower body** in its fixed attack frame, not the live locomotion legs. This is not the previous rendered/interpolated physical pose and not the existing orange target mesh.

The component is transient, unticked, has no animation instance, collision, navigation influence, or shadows. Pose reconstruction and skeletal refresh run only for explicitly enabled agents. Nothing is spawned by default, and no additional inference runs for debugging.

## Attack handoff investigation

With all clamps disabled, the reproduction captured abrupt movements including about 21 cm at a half-attack exit. This measurement includes the first locomotion prediction and is not by itself proof of an encoding error.

Two coordinate inconsistencies were found in the integration:

1. Root catch-up already computed its displacement in heading coordinates, then rotated it into the skeleton basis a second time before rebasing upper-body history. With the training root basis, this can convert horizontal displacement into a vertical hand displacement. Lower-body history did not apply that extra rotation. The same argument error existed in blocked-root reconciliation.
2. Attack publication encoded upper-body history in the published carrier, while its lower-body state and pelvis baseline had already been rebased to the next carrier. Upper history now receives the same carrier change, including for half attacks.

`Prophecy.NN.Handoff.CarrierCoordinates` checks point preservation and agreement between upper/lower rebases for translations and several yaw angles. `Tools/NN/TestProphecyLocomotionControls.py` exercises the new Blueprint surface and records full/half, natural/interrupted handoffs with all clamps off. The normal build and CarrierCoordinates automation passed. Four full/half, natural/interrupted exits passed numerical checks: explicit Stop preserved all 25 published bone positions exactly; previous and current pelvis, both feet and both hand histories reconstructed the outgoing world poses with a maximum error of 0.0000324102 cm (0.000324102 mm). This establishes coordinate/history continuity, not a visual judgement of recovery speed. The first learned locomotion output can still move a hand about 15.5 cm per 30 Hz step in this fixture. That motion is produced by the network after receiving the preserved pose; no recovery blend or model retuning was added.


## Verification evidence

- `Saved/Diagnostics/SlashContacts/BuildLocomotionInstall.log`: successful normal build/link.
- `Prophecy.NN.Handoff.CarrierCoordinates`: passed.
- `LocomotionHandoff.json`, `HandoffInputs.jsonl`, `HandoffInputValidation.json`: four exits; actual input histories compared against outgoing world poses by `Tools/NN/AnalyzeProphecyHandoffInputs.py`.
- `InputDebugClamps.json`: 0 cm and 1 cm runtime calf, total-leg and forearm reach assertions passed; material assignment verified.
- `nn_inputs.jsonl`, `InputDebugValidation.json`: 605 previous-input control-bone comparisons; maximum component-position error below 0.000001 cm. Root-window positions matched encoded inputs within 0.000008 cm and all yaw quaternions matched. Produced by `Tools/NN/AnalyzeProphecyInputDebug.py`.
- Debug enable/disable/re-enable, no component tick, accessible Blueprint reference and array ordering/finite values passed in `Tools/NN/TestProphecyLocomotionControls.py`.

All scene tests used transient PIE actors. Saved Blueprint/map wiring was not edited.
