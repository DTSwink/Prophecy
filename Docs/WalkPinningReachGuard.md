# Walk pinning reach guard

`Set Walk Pinning Reach Guard` takes **Agent**, **Enabled** and **Frames** (default 6).
It is off until explicitly enabled. Disabling removes its configuration and both
foot cooldowns. It does not change the existing pinning limit/tolerance settings.

After pinning and regional Run/Walk mixing, test the final hip-to-foot distance
against thigh length + calf length, including the signed calf length currently
returning after a kick. The boundary matches the leg solver's full-extension
margin (0.002 cm). If a selected pin reaches/exceeds it, reject that pin and use
the same blended foot prediction without its horizontal pin constraint. Preserve
the floor correction; do not choose the opposite foot or change knee guidance.

This operates on Walk feet, including a nonzero Walk contribution during policy
blends. Pure Run is unchanged. During mixed recovery a rejected foot loses the
whole blended pin, rather than leaving a residual Run pin. Hidden hand-source
policy evaluations cannot arm or restart the guard.

Each foot has an independent cooldown. `Frames` counts unpaused game ticks,
including the rejecting tick: 60 means one authored second regardless of frame
rate or agent speed multiplier. Zero rejects only the unsafe prediction and
retains no cooldown. During the cooldown even a safe requested pin is rejected;
repeated unsafe requests do not restart the countdown. At expiry the next
ordinary NN prediction can pin again, or start another cooldown if still unsafe.
This does not introduce additional inference between the existing policy steps.
Changing Frames affects the next rejection; disabling clears current cooldowns.
Initial-agent reset clears cooldowns while retaining the configured guard.

Disabled: no reach/floor-counterfactual calculations, retained cooldown or tick
callback. The policy path only checks whether a guard is configured. Enabled but
idle has no cooldown callback; the callback exists only while a foot is locked out
and is removed on expiry, disable, reset or world cleanup.

## Diagnosis motivating the guard

Intermediate scripts/BP checkpoint `c6be3ab88a86870b0058027c55c7d1069575e913`
was pushed to `origin/codex/standalone-sim` before this change.

Current kickR setup reproduced the user's left knee pops at frames 246 and 250.
The visible knee bend radius drops to 1.49/1.50 cm; the NN future is almost
straight (0.285 cm). At the corresponding 30 Hz predictions:

| Prediction time | Unpinned tempered hip–foot | Published hip–foot | Raw pin L/R |
| --- | ---: | ---: | --- |
| 4.0833 s | 78.01 cm | 81.19 cm (reach limit) | 0.8943 / 0.9301 |
| 4.1500 s | 78.21 cm | 81.23 cm (reach limit) | 0.9580 / 0.9956 |

The foot remains near the floor (lowest point 0.20/1.06 cm above it), so a simple
airborne height gate would not identify the reach conflict. Legacy Walk selects
the lower positive pin output and holds its horizontal foot position. The
connected solver consequently reaches full extension, then bends again when the
requested geometry becomes feasible. The knee branch itself is not reversed.

Isolated tolerance 0.1/0.2 tests, with fallback 0 and 1, remove those particular
extension events but move abrupt turns/extension events elsewhere. None was
applied to the saved Blueprint or accepted as a general fix. Evidence resides in
`Saved/Diagnostics/CalfAnkleConnection-left-knee-*.json`, matching
`FootVibration-nn-left-knee-*.jsonl` and `LeftKnee245-pinning-comparison.json`.

## Validation

Live Coding compiled four actions in 155.87 s. Reload raised recoverable RigVM
delegate/thread-access ensures while replacing reconstructed CDO references;
the editor temporarily stopped answering remote execution, then completed reload
at 21:39:18 UTC. It did not crash or restart. The initial crash report in chat
was corrected once completion was observed. No normal build/restart performed;
include these live changes in the next authorized normal Editor build.

The new function is reflected and callable on the canonical library CDO. The
pose Blueprint compiles status 3; archived library defaults were repaired with
other values and wiring preserved, without saving the asset. LiveAgentTypes
reports zero stale native properties/pins. All 27 focused native tests passed
at 21:41:03 UTC, including reach-boundary rejection, independent feet, repeated
evaluation without rearming, six game ticks at 30/60/120 FPS, pause-tick bypass,
zero frames, disable/reset timer removal and existing reconstruction/blend tests.

Two owned ten-second captures checked guard enabled with six frames and disabled.
Disabled reproduces the pre-change NN inputs/outputs and captured physical-mesh
transforms exactly (maximum difference zero). Enabled reports selected-left-pin
1 becoming effective 0 and removes the two full-extension events: visible knee
bend radius at frames 246/250 is 13.89/18.80 cm instead of 1.49/1.50 cm. This
veto deliberately releases the horizontal foot constraint; it does not smooth
that release or guarantee that all other knee motion is slow. For example, the
left thigh still turns 10.42 degrees at frame 245 as the pin is released.
No global reconstruction/pole/floor/tempering settings were changed.

Evidence: `WalkPinReach-verification.json`, `CalfAnkleConnection-left-knee-reach*.json`
and corresponding NN traces under `Saved/Diagnostics`. Both owned Play sessions
ended, tracing disabled and retained capture memory released. The feature remains
unwired/off in the user's Blueprint, ready to configure with the new node.
