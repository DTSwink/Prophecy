# Left wrist at 230 and attack leeway transitions

September 29, 2026. Current simulated `testNN` setup, Blueprint settings retained.

## Wrist cause and change

The first SlashR starts at 151, switches to half attack at 175, and ends at 197. Its exit upper-body inertia has no hold and a 0.5-second blend. The locomotion left-wrist constraint is enabled with a zero-degree bend limit; attacks use the existing baked 55-degree limit.

The final inertia sample could overwrite the wrist constraint applied earlier in publication. When inertia expired around 227, the unconstrained inertial wrist abruptly gave ownership back to the constrained locomotion wrist. This is an NN pose discontinuity: the physical wrist followed it closely, rather than creating the snap independently. Captured previous/future endpoints ruled out a stale previous-endpoint rewrite.

`ProphecyUpperBodyInertia::ApplyArms` now blends the solved left wrist toward its effective constrained orientation using the existing inertia return alpha, before storing the accepted arm pose. Position, reference-space selection, and the right-hand constraint policy retain their existing behavior.

## Leeway changes

`ProphecyClampEase` supplies independent NN foot, calf, hand, forearm and left-wrist channels, plus physical ankle and physical foot-target channels. Closing takes 0.25 authored seconds (15 unpaused ticks); opening is immediate. Re-enabling an unconstrained channel seeds from the actual outgoing pose. Very large physical target allowances likewise seed their reduction from used physical displacement, avoiding a delayed cliff near zero.

Blueprint values remain the requested destinations. During an existing Blueprint snapshot blend, changing the destination retains the active closing deadline and rebases the curve continuously; it does not restart the 15-tick window on every setter update. Exact repeated setters do not restart it either.

NN publication, attack/defense pose clamps, and presentation forearm/calf clamps use effective limits. Half attacks keep locomotion ownership of the lower channels. Physical ankle joint compression/extension and the physical foot drive share the effective calf allowance. The independent physical foot-target setting still does not grant extra ankle-joint freedom. Existing kick-specific length/range recovery keeps its authored return duration.

No extra checkpoint inference or retained Live Coding layout changes. Pose/body observation happens only when tightening needs a seed; the extra world callback exists only while a reduction is active. Stable channels use cached limits; unconfigured disabled channels create no active blend. Reset, agent removal, and world cleanup release the sidecars.

## Verification

Initial patched 270-tick matched replay: wrist rotation at 227/228 decreases from 7.904 to 2.510 degrees per displayed tick; physical wrist decreases from 7.597/7.415 to 2.515/2.515 degrees. This removes the isolated spike between surrounding roughly 2-degree steps. Captured NN positions/quaternions remain finite.

Five focused native tests cover reduction/opening/retargeting/retirement, physical foot policy, and existing arm inertia reference frames, velocity/reach, and spring retirement. An additional assertion covers per-tick destination updates retaining the closing deadline. No full suite, Blueprint edits, explicit asset save, or editor restart.

Raw captures and analysis: `Saved/Diagnostics/Knee202/wrist230_before.json`, `wrist230_after.json`, `wrist230_analysis.json`; scripts `CaptureWrist230.py`, `CaptureWrist230Ranges.py`, `AnalyzeWrist230.py`, and `TestWrist230Ease.py`.

Final Live Coding patch loaded 21:33:16 UTC. All five focused tests passed at 21:33:41. Final 270-tick simulated replay (`wrist230_final.json`) completed with finite NN samples and no logged errors; wrist step at 227/228 is 2.516 degrees, physical 2.521/2.522 degrees. NN hand travel at 227 is 4.940 cm versus baseline 5.434 cm.

Physical range trace (`wrist230_final_ranges.json`) confirms attack-entry calf allowance decreases monotonically from 2 cm at sample 152 to zero at 167, while the separate attack foot-target allowance opens immediately to the existing 1000 cm setting. At half-attack entry the Blueprint opens calf allowance to 20 cm, then restores its 2 cm baseline. Effective range closes monotonically: 17.1875 at 191, 10.5507 at 211, 3.2401 at 231, exactly 2 by 241 and through 270. Thus the existing Blueprint blend is honored without repeatedly stalling the extra closing window. The final capture checks both range transitions and the wrist in one rollout. Owned PIE ended and foot tracing returned to zero.
