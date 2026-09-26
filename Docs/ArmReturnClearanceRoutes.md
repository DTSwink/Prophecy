# Reverted experiment: clearance-dependent arm return

**Reverted2026-09-26 at the user’s request.** The straight-path blending and its diagnostic CVar/test are removed. The evidence below is historical, not the current behavior. See [Arm Return Reference](ArmReturnReference.md) for the replacement per-attack reference choice.

# Arm return: smoother, more direct clear paths

The previous neutral-return and NN-handoff routes always interpolated elliptical radius/angle. This added an unnecessary sideways curve even when the direct hand segment cleared the body, noticeable after pike.

`ProphecySlashReturnMath.h::FrontPath` now continuously approaches the direct segment as clearance increases. It measures the whole chord against the existing torso exclusion ellipse, then uses a quintic transition over a5cm normalized clearance band. The transition has zero first and second derivative at either end. It does not switch abruptly between an arc and a straight line.

Route blending occurs in elliptical radius/angle space. Whenever the straight-route weight is nonzero, both candidate radii clear the existing1.08 margin; blending therefore preserves that margin. Across-the-back shortcuts stay excluded. Blocked segments keep the previous front arc exactly. Destination projection, initial-distance speed, conservative speed bound, rotation winding, sword clearance, connected elbow solve, hold/blend clock and retirement remain unchanged. The same rule is used by neutralward movement, the transfer to NN and blade-winding selection, for both arms and every eligible attack. No additional inference, timer or work outside active returns.

## Validation2026-09-26

- Final Live Coding build27.39s loaded13:49UTC. Nine SlashReturn/HandRecovery tests passed13:49:49UTC. New ClearDirectPath test checks exact straight routing with clearance, left/right symmetry, unchanged blocked/front winding, speed bounds, exclusion radius, and matching one-sided numerical tangents at both clearance-band boundaries.
- Current pike setup: two360-tick captures with only editor comparison variable changed. All captured target positions match exactly before first return at119. Right-hand torso-relative rendered path detour from its start/end chord falls3.158→2.381cm, path length62.084→61.584cm. Maximum frame displacement1.758→1.742cm and maximum velocity change1.605→1.546cm/tick; no added peak in these measurements. Sampled swept sword clearance1.624→1.628 (≥1 is clear).
- Seven-direction isolated kinematic regression, all six slashes plus pike,720 ticks. Actor ticks were disabled only after all agents switched to kinematic, and requests were explicitly issued every90 frames; no saved Blueprint changes. Minimum sampled post-four-tick blade clearances all≥1.00067. SlashLU begins with a pre-existing overlap0.850203: a late comparison enabling the old route at486 retains identical prefix through487 and exactly the same initial minimum, with post-four-tick clearance1.000672(old)/1.000677(new). No claim of universally collision-free motion or perfectly smooth NN outputs.
- Owned diagnostic sessions ended; `Prophecy.SlashReturn.Audit=0`, `Prophecy.SlashReturn.ClearPathShortcut=1` (final/default). User node settings/Blueprint/assets unchanged. Include this live patch in the next authorized normal build.

Evidence: `Saved/Diagnostics/PikeReturn/{legacy,smooth,summary,smooth_variants,latelegacy_variants}.json` plus per-variant clearance reports. Scripts: `CapturePikeReturn.py`, `AnalyzePikeReturn.py`, `CheckReturnVariantClearance.py`. The editor-only `Prophecy.SlashReturn.ClearPathShortcut=0` comparison restores the previous all-curved path; there is no new gameplay toggle.
