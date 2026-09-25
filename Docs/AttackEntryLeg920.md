# Right-leg extension at attack entry, tick 920

## Diagnosis

2026-09-25 current kinematic setup: overR starts919. Right target knee bend919=29.41444 degrees,920=0.05688,921=0.05736,922=3.97153,923=36.85414. PhysicalMesh reproduces extension (920=0.09733degrees); future NN pose at920 still has29.51306degrees bend.

Attack-start pelvis inertia moves the hip beyond the authored ankle reach. At920 it moves the pelvis by(2.5001575,5.7891179,0.18855771)cm and the hip by(2.55421313,5.87168403,0.03605408)cm. Corrected hip to original ankle82.84149615cm exceeds segment sum81.34249171cm by1.49900444cm. ProphecyAttackStartInertiaMath.h::MoveHip projects the ankle to L1+L2-0.00001cm, effectively straightening the knee. As the correction decays the knee can bend again.

Controlled initial diagnosis: replay prefix850–920 position differences exactly0cm. Disable only attack-entry pelvis inertia on920 and reread without advancing: knee0.056877 ->29.513062degrees. This establishes the correction as the cause, not a different rollout.

The last locomotion effective right pin at919/920 is0.313569. At921 the locomotion getter says right0 and applies_to_visible_feet=false. These cached locomotion samples must not be interpreted as the visible attack pin state.

## Implemented correction

User requested locomotion-only knee smoothing, with an exception while attack-start pelvis inertia applies. The ordinary presentation pass now skips special publications (attack/parry/dodge), and skips an active inertia correction before the first special publication. The shared inertia Apply function runs configured knee smoothing once AFTER moving the pelvis/hips. It also handles an active zero-offset correction, then stops the exception when inertia retires/cancels. Existing clamp/recovery passes remain unchanged.

Same Set Knee Pop Smoothing enable/zone and stable thigh-local bend reference. No new Blueprint node/settings, clock, inference or retained episode state. Disabled smoothing keeps the guard and skips bone processing; inactive inertia returns before postprocessing. Physical and component-space animation readers share the correction. General locomotion reconstruction and per-tick pinning are unchanged.

Editor-only Prophecy.KneeSmoothing.SpecialOrder:0=legacy all-mode pre-inertia smoothing,1=final/default. Non-editor always uses final behavior. Left at1 after all diagnostics.

## Validation

Live Coding build105.84s loaded2026-09-24 22:17:32UTC. All11 KneePopSmoothing/RecoveryCalfLength/Presentation/WalkPinning tests pass22:17:52UTC. Added checks cover shared normal-special bypass, locomotion resumption, exactly one post-inertia pass, segment lengths, pelvis/foot rotation, component/world parity and retired-entry bypass. Existing accepted knee/per-tick pin tests retained.

Controlled replay kept0 until reading tick920, then switched1 and reread on that same tick. Captured850–920 target/previous/future position prefix matches baseline exactly (max0cm). Right knee0.056877 ->15.439631degrees; foot shifts0.735753cm toward hip (Z+0.545559cm). Pelvis transform and both foot rotations unchanged; segment lengths unchanged within floating-point tolerance. Following right target bends921/922=15.571026/15.882514degrees;923=36.854140. This fixes the near-zero extension lock, not a claim of uniform angular velocity throughout the attack.

Normal replay with final behavior from startup completes1050ticks with201 captured samples850–1050, all finite. PhysicalMesh knee bends920/921/922=15.45183/15.55509/15.87123degrees, matching the targets. No additional scene retuning, Blueprint graph edits, explicit saves or restart. Owned PIE sessions ended, trace disabled, callbacks removed. Pose BP inspection status3/zero stale native or pin types/wiring preserved. Include this Live Coding patch in the next authorized normal build.

Evidence in Saved/Diagnostics:
- Leg920-capture.json, Leg920-nn.jsonl, Leg920-metrics.json (baseline).
- Leg920InertiaOff-same-frame.json, Leg920InertiaOff-capture.json, CheckLeg920Inertia.py (cause).
- Leg920Fixed-same-frame.json, Leg920Fixed-capture.json, Leg920Fixed-verification.json, VerifyLeg920Fixed.py (identical-prefix order switch).
- Leg920Default-capture.json, Leg920Default-verification.json (normal final replay).
