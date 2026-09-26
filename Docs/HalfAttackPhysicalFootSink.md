# Half-attack physical foot dip — September 26, 2026

The original investigation below identified the cause without changing normal behavior. The subsequent user request approved matching physical ankle allowances to the calf-clamp nodes, with half attacks using locomotion settings. The correction is described next.

## Coherent attack/locomotion controls

- Locomotion and half attacks use the enabled **Set Locomotion Calf Clamp** allowance for symmetric physical ankle travel and as a minimum foot-drive target allowance.
- Full attacks use the enabled **Set Attack Calf Clamp** allowance by the same rule.
- Disabled or unconfigured calf clamps supply zero extra joint travel in either mode; disabling a pose clamp does not grant unlimited physical joint travel.
- **Set Physical Foot Target Clamp Leeway** stays a separate drive-target control. Its profile now follows the owner of the legs too: Locomotion during half attacks, Attack during full attacks. A large target allowance does not open the joint.
- **Set Kick Foot Joint Leeway** remains additional extension: compression equals the selected calf allowance, extension is the larger of that allowance and the active kick allowance. Its existing finite return remains.
- Mode switches and live calf-clamp/snapshot changes are read by the existing target publication. The native rig/value cache avoids rebuilding unchanged ankle constraints. No new tick, inference, pose copy or retained-object layout change.
- Parry/dodge physical range policy is unchanged.

The current scene's locomotion calf setting is 2 cm, attack calf clamp is disabled, attack drive-target allowance is 1000 cm, and kick extension allowance is 7 cm. Thus half attacks retain ±2 cm; enabling the attack calf clamp at 5 cm gives full attacks ±5 cm. The 1000 cm target setting remains independent. No Blueprint values were edited.

The temporary `Prophecy.PhysicalFoot.HalfLocomotionLeeway` diagnostic branch was removed from the implementation; half-attack support is now normal runtime behavior, including packaged builds.

### Correction validation

Live Coding succeeded and reload completed **2026-09-26 21:57:47 UTC**. Four focused native tests passed **21:58:15 UTC**: `Prophecy.Physics.FootTargetLeeway`, `Prophecy.Joints.KickFootLeeway`, `Prophecy.Joints.CalfReturnLocomotionTarget`, `Prophecy.Jolt.RigWorld.FootExtension`.

The final 450-frame physical replay (`fixed.json`) matches the original baseline's entire captured first 119 frames exactly. At the first half attack, the former left/right entry dips are absent: minimum foot heights over frames 120–132 are 0.005622/0.000034 mm above their pre-attack means. This agrees with the prior controlled diagnosis.

A separate 110-frame physical run (`matrix.json`) verifies full→half→full, live attack-calf changes 5→3→disabled→0, stopping, kick entry/return, and entering/exiting a half attack during the ongoing lower recovery. The actual current Blueprint lower-end callback sets locomotion calf allowance to **20 cm** and blends it to **2 cm** over 60 ticks. The measured half/recovery ankle allowance follows that existing curve (19.985167 cm on its first tick); the test intentionally preserves it. Full attacks read 5/3/0 cm as configured, and the kick reports 5 cm calf allowance plus 7 cm extension, followed by its existing return. Initial test analysis incorrectly assumed recovery always stayed at 2 cm; correcting the expectation to the current Blueprint's documented 20→2 blend makes all 12 checkpoints pass without changing runtime or Blueprint code.

Scripts: `Saved/Diagnostics/VerifyCoherentFootLeeway.py`, `TestCoherentFootLeeway.py`, `AnalyzeCoherentFootLeeway.py`. Results: `Saved/Diagnostics/AttackFootSink/coherent-summary.json` and the `fixed`/`matrix` captures and drive logs. Temporary settings existed only on owned Play instances. Play ended and tracing was reset. No Blueprint edit/save, restart, commit or push.

## Finding

The current `/Game/testNN` stationary half-attack sequence reproduces a small physical foot dip at attack entry. The locomotion calf allowance is **2 cm**. `ProphecyPhysicalFootTarget::LocomotionCalfLeeway` returns it only when the whole-agent activity is Locomotion, so a half attack makes it return zero even though the lower body still belongs to locomotion.

`UProphecyJoltCharacterComponent::PublishAuthoredTargets` passes this result into `ProphecyKickFootLeeway::Synchronize`. That changes both ankle joints from symmetric **±2 cm** travel to locked during the half attack, then restores the allowance on completion. This physical transition remained after the upper/lower special-end split.

## Causal comparison

`Saved/Diagnostics/InvestigateAttackFootSink.py` captures the current scene with physical simulation and normal actor ticking. It does not inject attacks; the Blueprint starts its normal half `slashL` at captured frame 120. Two 450-frame runs were made:

- `baseline`: unchanged ankle policy throughout.
- `late`: identical lead-up, then enable `Prophecy.PhysicalFoot.HalfLocomotionLeeway 1` after frame 119, immediately before attack entry. This diagnostic preserves the locomotion allowance only during half attacks.

Captured pelvis/calf/foot physical positions matched exactly through frame 119 (maximum difference **0 cm**). Both foot authored targets also matched exactly on frame 120. The physical drive trace shows no target displacement from the authored foot during this interval in either run: the current attack-specific target-clamp allowance is 1000 cm, so changing the locomotion allowance affects the ankle joint, not the effective drive target clamp.

| Foot | Baseline maximum entry dip, frames 120–132 | Preserved ankle allowance |
| --- | ---: | ---: |
| Left | 1.603689 mm | No dip; minimum height 0.005622 mm above pre-attack mean |
| Right | 0.636137 mm | No dip; minimum height 0.000034 mm above pre-attack mean |

Pre-attack means use frames 100–119. Baseline left foot also rises again on completion. Evidence is in `Saved/Diagnostics/AttackFootSink/baseline.json`, `late.json`, their `*-drive.log` files and `summary.json`; analysis is `Saved/Diagnostics/AnalyzeAttackFootSink.py`.

These measurements are physical foot-bone heights, not collider/floor penetration depth. They establish the cause of this attack-entry dip without changing ground contact settings (world penetration slop remained 2 cm). They do not establish every possible cause of sinking during full attacks or moving attacks.

## Original investigation conclusion (superseded by the correction above)

The locomotion calf/ankle allowance should remain active while an attack is half-body, matching the lower-body ownership contract. Full attacks, parries and dodges should retain their existing special behavior. The diagnostic verifies this correction for the observed stationary half-attack dip; normal behavior remains unchanged while the diagnostic is zero (its default).

The separately configured physical-foot target clamp also selects the whole-agent attack profile for half attacks. That did not move the targets in this capture, so it is not the measured cause and was not changed.

Both diagnostic Play sessions ended. `Prophecy.PhysicalFoot.TraceFrames=0` and `Prophecy.PhysicalFoot.HalfLocomotionLeeway=0` were restored.
