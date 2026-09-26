# Slash train parity — seed 2026092223

Reference: `latest_predictive_pin_x5_20260924_refresh2/seed_2026092223/complete/variant_viewer.html`, checkpoint step184064 SHA `e0759ba5039db0db26f5dd17d58e74b72f1dc092f9f7bf6f54e4a622677f7d7b`.

## Comparison setup

`Set Slash Train Starting Pose` is a development-only, event-driven diagnostic node. It loads the two initial conditioning poses from `Tools/NN/Fixtures/SlashTrain2026092223.json`, maps them into the current mesh carrier, and replaces the pose buffers and both recurrent history frames. It requires an initialized, idle, kinematic agent. Only the first request of `codex slash train` calls it.

The node also matches the viewer's stationary reference frame for the next30 full attacks. This is an explicit diagnostic condition, not a change to ordinary gameplay. Histories are still encoded from Unreal's published poses at each entry; targets, Armed/Hit, inference, completion and normal pose publication still run locally. No future poses or expected outputs are injected. The actual root can still return to its locally selected balancing point; the comparison's NN carrier stays stationary, matching training. The selected shared native model temporarily uses the reference coordinate frame for this agent's inference only and is restored before publication. Other agents/checkpoints retain their normal frame. The override expires on the30th attack ending or world teardown and is compiled out of Shipping.

The user authorized zero attack trims for this comparison. A zero-valued `Set Trim Attack` runs at the entry of the comparison function, after the ordinary tick setup, to prevent that setup from reintroducing early endings. The existing regular trim node is preserved. Both existing input-history frames are restored, rather than duplicating a frozen pose. The user's attack-start pelvis-inertia disable and kick-checkpoint override disable remain in the graph.

## Complete comparison controls

Use these conditions for this saved viewer (seed2026092223, complete variant), rather than treating every gameplay blend as a mismatch:

| Control | Required for the raw comparison |
|---|---|
| Set Attack Checkpoint | Predictive Pin x5 Refresh2, step184064. |
| Set Kick Checkpoint Override | False; no historical good.pt kicks. |
| Set Simulation Mode | Kinematic; physics/collisions are not in this viewer rollout. |
| Set Slash Train Starting Pose | Once before the first request. Loads both actual initial history frames AND temporarily fixes the reference carrier for30 full attacks. Does not duplicate one frame. |
| Set Attack Initialization Mode | Dynamic. Static deliberately duplicates the current frame and cannot reproduce this saved dynamic-history rollout. |
| Set Trim Attack | All16 values0; the train function already applies this after the ordinary trim setter. |
| Trigger NN Attack | Full attack, Half Attack=false, no victim; target sampled once using the extracted target arrays/transplantation rule. No Get Valid Attack Target/extra-reach clamp in this path. |
| On NN Attack Ended | Immediate next request, already wired. No locomotion prediction, delay, Stop/retrigger or pose-changing event code between requests. |
| Set Attack Start Pelvis Inertia | Enabled=false; both translation and rotation channels bypassed. |
| Set Hand Inertia Enabled | False for hand_l and hand_r, or Attack LinearFollow/AngularFollow all1. This is separate from locomotion hand tempering. The existing hand-inertia graph chains are disconnected in the inspected Blueprint. |
| Set Attack Foot Clamp | Enabled=false; disables extra Unreal hip-to-foot reach clipping. |
| Set Attack Calf Clamp | Enabled=false; disables extra Unreal knee-to-ankle length clipping. Does not remove the checkpoint's own floor-safe±5cm band. |
| Set Attack Hand Clamp | Enabled=false; exposes the native wrist position, including the trained forearm-distance rules. |
| Set Special Forearm Roll Correction | False only for raw rotation matching. User requested default/current gameplay setting stay true. |
| Set Special Calf Roll Correction | False only for raw rotation matching. User requested default/current gameplay setting stay true. |
| Magic cube/root forcing | Keep user's comparison disabled influence; no extra external pose/root velocity edits during capture. Normal preserve-world root return can still run; the seeded comparison carrier stays fixed. |
| Agent speed / manager NN rate | Multiplier1 (special entry already resets it); NNUpdateHz30. Compare policy frames or matched60Hz interpolation phases, not elapsed browser wall time. |
| Set NN Interpolation Mode | **Attack Viewer** selects linear positions/plain shortest-path Slerp, matching the original viewer's interpolation. Current retains our existing angle-weighted rotation interpolation; HermiteSlerp also changes positions. The default and existing Blueprint selection are unchanged; choose Attack Viewer explicitly for presentation comparison. |

The checkpoint's learned pinning, cone correction, floor-safe calf-distance band, forearm-distance band and wrist limits must remain: they exist in training too. `Set Attack Foot Pinning Iterations` controls the older checkpoint's frozen Walk proposal. This184064 model has no such proposal; its learned pin pass uses the same fixed4 iterations as training. Walk pin smoothing/bounds/transfer/height veto and Run pin boost do not govern these full attack predictions.

Locomotion lower-body/kick/hand/FK-core tempering, regional Walk/Run recovery, foot-rotation recovery override, arm return-to-idle, upper-body exit inertia and recovery leg reconstruction are not settings to zero indiscriminately. In this immediately chained full-attack test, new attack entry cancels recovery before another locomotion pose is generated. They matter if a locomotion gap is reintroduced, and after the final attack (outside the comparison).

`Set Kick Foot Joint Leeway` and `Set Physical Foot Target Clamp Leeway` are separate physical-following controls, not the native calf-distance band. The former also supplies the outgoing length-recovery duration and can suppress extra presentation clamps while active; with attack clamps already off, neither needs retuning to compare these kinematic attack endpoints. Joint limits, magnetisation, damping, tolerances, material, collision sweeps and solver substeps cannot make simulated Jolt motion numerically identical to this kinematic rollout.

## Calf length versus calf roll

The native attack contract genuinely permits rest calf length±5cm, with floor clearance, for all attacks on this checkpoint—not just kicks. Final449-frame capture: both knee-to-ankle distances span approximately37.5633–47.5634cm (rest42.5633cm). Maximum difference from viewer calf lengths is0.003807mm left /0.004353mm right. There is no remaining material calf-length mismatch in that comparison. The removed extension-only Blueprint correction was an older real incompatibility: it discarded valid compression; it is not the current native band.

Calf roll only changes orientation about the segment. Separately, Unreal retains authored unit calf mesh scale during attacks; the legacy locomotion `ExtendCalfToFoot` stretching is bypassed. Viewer bone segments and Unreal skin/mesh shape are different visual representations, so a visible mesh gap/stretch must not be equated with a different knee/ankle trajectory. There is no new attack mesh-scaling knob in this work, and previous position/rotation metrics do not certify skin deformation.

## Independent reference checks

`Tools/NN/ValidateCurrentSlashChain.py --staging Saved/SlashTrain2223 --seed 2026092223` reproduces all449 predicted25-bone positions in the saved viewer rollout exactly (maximum difference0). Its input and output arrays are stored in `Saved/SlashTrain2223/chain_audit.json`.

The isolated native runtime audit, with the reference carrier geometry, passes: maximum teacher-input position error0.001382mm;449-step recurrent error0.051202mm; all Armed/Hit latches match. This checks the native transition implementation. It does not certify the gameplay entry, handoff or presentation path.

## Handoff mismatch and correction

Polling on the next Blueprint tick allowed one locomotion prediction between attacks. At the first handoff it changed the pelvis by2.14cm and the left hand by10.9247cm; the next attack's first prediction differed by8.2586cm. The unused `On NN Attack Ended` event now calls the train immediately, guarded by possession and Index>0. The function's Index>=30 guard terminates the chain. The original tick-after30 caller still starts the first request. This uses real Unreal completion, not recorded viewer deadlines, Stop/retrigger, or forced phase latches. A new attack cancels recovery and suppresses the secondary Special Ended callback through the existing cancellation mechanism.

Preserve-world root rebasing remains fixed separately; see [SlashTrainFootHandoff](SlashTrainFootHandoff.md). With the end-event chain, the two handoff history frames remain continuous within0.000033cm.

## Reference-frame difference

The viewer's initial root height is0.000353031471604481m; the exported gameplay canonical carrier is essentially at height0. Lower hybrid inputs and the upper network use absolute target/pelvis height, while foot geometry uses the root-local ground. Matching pose alone therefore does not give identical conditioning. A controlled isolated native audit flattened only that reference height: recurrent error increased from0.0512mm to1.3895mm, and teacher-input error from0.00138mm to0.3372mm. Merely offsetting the starting bones/target also changes the root-local floor constraint and did not resolve the drift. The explicit comparison carrier addresses both consistently. Ordinary gameplay framing is unchanged.

## Roll controls

- **Set Special Forearm Roll Correction**: Agent, Enabled=true. Both forearms in attack, parry and dodge; disabling exposes checkpoint roll.
- **Set Special Calf Roll Correction**: Agent, Enabled=true. Both calves in full attacks; defense/locomotion lower-body behavior is unchanged.

These affect presentation rotations at the next policy pose, not endpoint positions, hand/foot rotations, leg reconstruction, raw attack state, weights or timers. Per-agent settings default enabled; no false setters are wired into the user's Blueprint. Temporary diagnostic sessions disable either/both and world cleanup clears their overrides.

Four complete449-step runs cover both off, forearms off only, calves off only, and a fresh default-enabled world afterward. Each disabled family matches its raw decoded rotations within0.00008degrees; the other family retains its correction. Published endpoints match native output within0.000025cm. The enabled/default replay keeps all30 completion lengths and phase latches, with raw trajectory error0.277222mm. Calf-roll changes can produce tiny subsequent pose-codec rounding differences at the next entry; the controls do not directly overwrite NN state.

An additional expiry run completes the449-step train, then triggers an ordinary jabL: all11 subsequent native steps use the original gameplay reference frame, confirming that the diagnostic frame is removed. All owned PIE sessions ended, trace counters disabled, roll defaults enabled. Final native Live Coding build62.37s loaded20:52:56UTC; Blueprint library-default repair preserved values/wiring and compiled status3. Blueprint remains unsaved; new native changes must be included in the next authorized normal editor build before a fresh launch.

## Live numerical evidence

Final raw comparison `Saved/Diagnostics/SlashTrainParity-rawverified-verified.json`: all30 attacks, all449 policy steps, every Armed/Hit value and attack duration match. Across all25 bones: maximum position error **0.283269mm**, RMS **0.127505mm**, maximum rotation error **0.033433degrees**. These are measured close agreement, not bitwise identity. The isolated native runtime and live pose/quaternion encoding are separate numerical paths; do not claim zero residual error.

`Tools/NN/CompareLiveSlashTrain.py` performs one initial world alignment, then compares every frame without realigning at boundaries. It explicitly reports missing trace writes and refuses to certify incomplete captures. The earlier rawframe capture lost two diagnostic writes during concurrent file inspection; its apparent single37.9-degree rotation error was an indexing artifact. The final449-step capture is complete.

`Saved/Diagnostics/CaptureSlashTrainParity.py` captures actual Blueprint gameplay, native inputs/outputs and authored/mesh targets. The presentation audit checks raw native output against published world endpoints. Intentionally enabled forearm/calf corrections remain visual differences from the viewer.

The raw60Hz target audit covers898 samples: previous/future/interpolated positions stay within0.28314mm. Current Unreal rotation interpolation uses the polar factor of a matrix lerp (`BlendAuthoredRotation`), while this viewer now uses quaternion Slerp. Near a180-degree raw forearm-roll change, that produces an additional0.30875-degree midpoint difference at tick727. Comparing against Unreal's actual interpolation rule instead gives0.033445degrees maximum. This is a known interpolation difference, not another NN or handoff mismatch. Preserve the user's request to keep local Unreal rules; do not silently change global interpolation for this comparison. These tests do not certify simulated Jolt motion or the browser's wall-clock playback phase.

## Duplicate viewer with Unreal interpolation

User requested a separate viewer rather than changing Unreal. Created sibling `variant_viewer_unreal_interpolation.html` under the184064/seed2026092223/complete folder, served at `http://127.0.0.1:8795/latest_predictive_pin_x5_20260924_refresh2/seed_2026092223/complete/variant_viewer_unreal_interpolation.html`. Defaults to **Unreal · Current**, with an **Original viewer · Slerp** dropdown for comparison at the same frame/camera. The original page and motion binaries are unchanged; no Unreal or Blueprint changes.

The60Hz motion binaries already contain baked Slerp midpoints. Unreal mode therefore interpolates from even frames (the original45130Hz keys), not between the baked60Hz samples. Even-frame positions and matrices match `rollout.npz` exactly. Translation remains linear. Rotation ports the current Unreal normalized-quaternion hemisphere choice, float angle/atan2 weighting and normalized Slerp; it does not add forearm/calf roll corrections or any other gameplay processing. Frame numbering, playback rate, targets and attack markers stay unchanged.

Rebuild using `Tools/NN/BuildUnrealInterpolationViewer.py <original viewer path>`. Creation/hash receipt: `Saved/Diagnostics/UnrealInterpolationViewer.json`. Headless browser validation confirms all451 keys unchanged, altered fractional rotation interpolation, working selector/playback, no page errors, original page unmodified, and rendered3D output (`UnrealInterpolationViewer.png`). Validation report: `Saved/Diagnostics/UnrealInterpolationViewer-validation.json`. Existing checkpoint/seed navigation still opens its original destination pages; the duplicate applies to the selected184064/2223 train only.
