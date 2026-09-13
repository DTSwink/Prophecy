# Foot pinning debug and locomotion threshold

All nodes target a Prophecy Agent and can be called at runtime.

1. Call **Set Foot Pinning Debug Enabled(true)** on agents you want to inspect.
2. Use **Get Locomotion Foot Pinning**, or **Get Attack Foot Pinning**.
3. Split the returned Sample pin (or use Break Prophecy Foot Pinning Sample).

Every Vector2D pair uses **X = left foot, Y = right foot**:

- **Raw Network Output:** original neural outputs/logits. These are not probabilities.
- **Raw Pinning:** decoded 0–1 weights before near-ground forcing.
- **Effective Pinning:** the 0–1 weights supplied to the foot projection.
- **Sample Time Seconds:** game time of the completed policy step, not the current interpolated render frame.
- **Applies To Visible Feet:** distinguishes the visible policy from a background or ghost policy.
- **Walk Policy:** locomotion's walk/run selection. The frozen attack stage is a walk-policy baseline.

The getter returns false before capture, when capture is disabled, or when inference is disabled. Attack reads also return false outside an active attack with a generated pose. Turning capture off discards the samples. Repeated getters read cached data; they do not run neural networks or sample meshes. Capture is sparse and opt-in: no per-agent debug samples, extra inference, tracing, or sigmoid computation during normal gameplay. Enabled agents copy values already calculated during inference; the frozen attack diagnostic decodes two cached logits using the same binary selection rule. No performance benchmark was run.

## Attack stages and half attacks

**Get Attack Foot Pinning** defaults to the learned attack stage. **Frozen Stage = true** reads its frozen lower-policy baseline instead. This intermediate stage does not directly control the final visible feet. Both stages have different logit mappings from run locomotion; do not compare raw logits as percentages.

Half-attack samples describe the attack's ghost lower body, so Applies To Visible Feet is false. Read locomotion pinning for the visible feet during half attacks. During full attacks, background locomotion still updates, but its sample is marked as not applying to the visible feet.

## Threshold control

**Set Locomotion Foot Pinning Threshold(Threshold Cm = 2, Fade Range Cm = 0.5)** changes this agent's run-policy near-ground rule on its next policy step:

- A foot qualifies for forced pinning below Threshold Cm.
- Full forced pinning applies below max(0, Threshold Cm − Fade Range Cm), fading to zero at Threshold Cm.
- A zero threshold disables the forced-pin contribution; the NN's decoded pinning and ground penetration correction remain active.
- Zero fade range gives a hard height cutoff. Negative or nonfinite inputs return false without changing the setting.

Defaults preserve the exported contract: full pin below 1.5 cm, fading out at 2 cm. Until called, the node inherits contract settings. The rule still chooses the sole qualifying foot, or the more strongly predicted contact when both qualify. This does not change the legacy walk policy or attack-stage pinning.

## Backward-turn diagnosis, current testNN setup

Captured BP_ProphecyManualPoseAgent (handle 0), matching the user's tick debug 80–110, without changing its Blueprint. At tick 89 the right foot's soft pin is 2.29%, but its predicted sole is only 0.235 cm above the floor; the left sole is 2.731 cm high. The near-ground rule therefore forces the right to 100%, moving its target 17.696 cm from the unprojected prediction. At tick 91 the forced foot switches to the left (28.66% to 100%, 17.967 cm correction).

Replaying the captured inputs through the original checkpoint and training projection matches Unreal's four-iteration foot positions within 0.00002092 cm over ticks 80–110. Four versus training's sixty integration iterations differs by at most 0.084735 cm on these same inputs. The published foot position matches decoded Unreal targets within 0.00001348 cm. This identifies the inherited near-ground rule as the source of the large corrections in this window; it is not a whole-trajectory proof for all model inputs.

Evidence: Saved/Diagnostics/BackwardTurn/{scene.json,inputs.jsonl,analysis.json}; capture/replay: Tools/NN/CaptureProphecyBackwardTurn.py and AnalyzeProphecyBackwardTurn.py. The debug-node and threshold runtime check is Tools/NN/TestProphecyFootPinningNodes.py.
