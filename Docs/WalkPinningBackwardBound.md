# Walk pinning line and circle bounds

`Set Walk Pinning Backward Bound`: Agent, Enabled, Distance Min Cm (20), Distance Max Cm (60), Root Index (0), Lerp Target (0). Off until called. Disable removes the configuration. Root Index selects **heading only** from the zero-based continuous root window:0 is current,1..8 are future samples. The projection origin always stays at the currently applied root (window0). It does not include the discrete previous-root entry. Invalid indices/nonfinite/reversed thresholds are rejected without changing existing settings.

Lerp Target blends that selected heading toward the mover's final locomotion target facing:0 preserves the selected root heading;1 uses the target directly, beyond the finite root-window horizon. Intermediate values interpolate the shortest horizontal angle, preserving a unit direction even for a180-degree turn. The target comes from the most recent resolved mover step (`GetLocomotionTarget`), not velocity or a future window sample. An unavailable target retains the selected heading. Values outside0..1/nonfinite are rejected without changing prior settings. This is per agent and affects backward bounds, their opposite-foot transfer and their debug arrows; circle bounds are unchanged. Zero removes the override and skips target lookup/angle math; disabled bounds skip the feature entirely. There is no extra timer or inference.

Validation2026-09-24: Live Coding succeeded104.27s, loaded18:45:52UTC. All seven WalkPinning tests passed18:47:47UTC, including new endpoint/intermediate/opposite/wraparound headings, missing-target fallback, per-agent settings and disabled cleanup. Existing Blueprint node refreshed with default0; old values/wiring preserved, compile status3 and zero stale types. No gameplay rollout or explicit asset save/restart. Include the live change in the next authorized normal build.

For horizontal normalized heading H from Root Index, signed backward distance is `dot(Root[0].Position - Foot, H)` in centimeters. Cap is1 at/below Min,0 at/above Max, linear between. Equal thresholds make a hard cutoff just beyond that distance. Negative thresholds are allowed. Height and sideways separation do not matter. Native window heading is local Unreal+Y (training+Z), consistent with the existing root trajectory debug arrows.

For each visible Walk foot, apply `min(smoothed pin, cap)` after temporal smoothing and before foot-roll pin projection. The foot is its current held NN ankle, converted from the actual fed-input root frame; an unconstrained future prediction must not conceal a planted foot left behind. The bound alone does not alter smoother history and never creates/increases a pin or transfers it to the other foot. The separately enabled transfer feature below can raise the opposite pin. Run and special checkpoint pin rules remain unchanged; existing reach guard and final clamps retain their later priority. The continuous root window is queried once per enabled agent evaluation, not per foot or hidden hand-source evaluation. Missing/unavailable windows bypass the cap.

## Optional backward pin transfer

`Set Walk Pinning Backward Transfer`: Agent, Enabled, Multiplier (1). Off until
called; disabling or setting multiplier0 removes its configuration. Requires an
enabled backward bound with a valid root window. A circle bound alone does not
drive this feature. Multiplier must be finite and nonnegative.

For each foot, compute `release = 1 - backward cap` from its geometric position:
zero before Min, one after Max. Raise the other foot to at least
`clamp(release * multiplier, 0, 1)`. Half released therefore requests50% at
multiplier1 or100% at multiplier2. A stronger existing receiving pin stays stronger.
The source foot need not have been selected by the NN hard gate.

Both transfers are computed simultaneously from geometry, with no mutual feedback.
As requested, the receiving foot's own backward/circle caps and later reach guard
still win. The former raw-value limit has been removed. Both feet beyond their
bounds can therefore still be unpinned. Transfer runs after temporal smoothing,
without modifying its history or adding another ramp. It is applied to the actual
Walk pin projection; Effective Pinning reports the resulting weight after normal
policy mixing and reach rejection. Auxiliary hand-source evaluations, pure Run
and active specials do not acquire this behavior.

No new timer, tick callback, inference or duplicate root-window query. Disabled
uses the prior bound path, with only a configuration/branch guard. World cleanup
removes weak-agent settings; agent reset retains this configuration.

Transfer validation2026-09-24: Live Coding build105.19s, loaded13:40:15UTC.
All7 WalkPinning tests passed13:40:58 (BackwardBound includes new transfer tests:
half release at multipliers1/2, mirrored directions, stronger existing pin,
receiving circle cap, simultaneous release/no feedback, both feet outside,
zero bypass, per-agent settings, invalid input and disabling). Existing raw-limit,
reach-guard, temporal smoothing and coordinate tests also pass. Node reflected;
pose Blueprint compiles status3 with zero stale types after26 archived library
defaults were repaired, preserving other values/wiring and leaving assets unsaved.
No node wired, gameplay rollout, restart or asset save. Include this Live Coding
patch in the next authorized normal editor build.

`Draw Walk Pinning Backward Bound`: Agent, Width Cm (100), Ground Offset Cm (2). One-frame arrows; call it from Blueprint Tick when desired. White marks the selected heading anchored at current root0, a green transverse arrow marks cap1, a red transverse arrow marks cap0, and green/yellow/red arrows span the fade interval. Gameplay and drawing share the same origin/heading resolver. Debug-only static-world downward traces put arrow endpoints on the ground; absent hits fall back to the agent root's ground plane. Disabled/unavailable configuration returns false and draws nothing. No automatic debug ticking or traces. The node is DevelopmentOnly and drawing is compiled out when debug drawing is unavailable.

Disabled gameplay adds no configuration/history, timer, root-window allocation/query, projection, debug drawing or NN evaluation beyond the configuration guard. Enabled has no independent tick callback. Settings are removed on world cleanup and remain configured across agent reset.

`Set Walk Pinning Circle Bound` has Agent, Enabled, Distance Min Cm (20), Distance Max Cm (60), Root Index (0). It caps by horizontal radius `length((Foot - Root).XY)` instead of the signed backward projection. Radii must be nonnegative and ordered. It uses the selected root position; heading does not affect a circle. Line and circle have independent settings/enable flags and root indices. If both are enabled, their minimum cap wins; one continuous-window lookup is shared. Disabling either does not disable the other.

`Draw Walk Pinning Circle Bound` takes Agent and Ground Offset Cm (2). It draws green inner, yellow midpoint and red outer circles, plus outward radial arrows, projected onto static ground. Like the line drawing it lasts one frame, requires explicit calls, is DevelopmentOnly, and performs no background work. The white arrow identifies the selected root heading but does not rotate/change the circular bound.

Validation: final Live Coding build passed60.52s and loaded10:57:25UTC (the preceding line-only build also passed94.67s). BackwardBound, CircleBound and Smoothing tests all passed10:58:08UTC. The native tests exercise distances/endpoints, lateral/height independence, yaw/translation invariance, selected future position+heading, upper-bound rather than multiplication semantics, hard-cut/negative thresholds, validation, disabled cleanup and unavailable debug windows.

Both setters and draw functions verified through the canonical reflected library. Pose Blueprint compiled status3 after47 archived library default references were repaired; other values/wiring preserved and zero stale agent types. No gameplay Play, debug screenshot, automatic wiring, asset save or restart. Include these live changes in the normal editor DLL before the next fresh launch.

## Lower-state coordinate correction (2026-09-24)

Later heading-index correction2026-09-24: the backward line previously moved its
origin to the selected future root. It now anchors at root0 and reads only the
heading from Root Index. Gameplay, opposite-foot transfer caps and debug arrows
share that reference. Circle-center selection stays unchanged. Root Index0 and
disabled behavior are unchanged; no new window query/timer/inference work.
Live build118.00s loaded17:19:55UTC; all seven WalkPinning tests passed17:20:41UTC,
including future-position invariance, future-heading rotation around root0,
root0 compatibility, transfer, circle and coordinate regressions. Pose Blueprint
status3/zero stale types after27 archived-default repairs, values/wiring preserved.
No gameplay rollout, graph wiring edit, asset save or restart. Fold into the next
authorized normal build. Earlier validation below describes the coordinate fix
and predates this corrected heading-only index contract.

The first implementation omitted `SeedRootRot` when converting the held lower-state foot to world space. Lower state is Z-up while native root trajectories are Y-up; this confused height with forward/backward distance. The root-window debug arrows were correct, but the runtime cap measured a different point. Both line and circle now rotate lower state into root-heading coordinates before world yaw and translation, consistent with `LowerTransformToHeading`.

Current unchanged Blueprint reproduction (20/60cm, root0, Walk) showed the left physical foot approximately47.26cm behind the root at2.5167s while Effective Pinning read1.0. Evidence: `Saved/Diagnostics/WalkBoundMismatch-before.json`. Physical/published positions are observational evidence, not an exact same-policy-step cap reference, because presentation, floor correction and clamps occur afterward.

Live Coding build succeeded25.41s and loaded11:13:31UTC, no reflected object changes. Four focused tests passed11:13:54UTC: CoordinateSpace, BackwardBound, CircleBound and Smoothing. The new test independently compares the production conversion against decoded component/world axes across multiple yaws and foot heights and verifies both cap types. The extra transform runs only for enabled bounds; no new ticking/inference, Blueprint changes or restart.

The corrected240-frame capture is `Saved/Diagnostics/WalkBoundMismatch.json`; analysis script `AnalyzeWalkBoundMismatch.py`. At0.5167s the foot's displayed distance was29.84cm with effective pin0.856707, falling to0.747503 at0.55s. Before correction, all51 observed positive-pin samples with displayed feet25–55cm behind had full pin; afterward37/40 were fractional (three full samples occur near entry). Do not expect exact agreement between the moving rendered foot/current root and the last completed30Hz policy's held-foot measurement. This verifies the observed cap now operates, not that downstream clamps/physics leave feet perfectly fixed. Only diagnostic-owned Play was ended; the user's graph/settings were preserved.
