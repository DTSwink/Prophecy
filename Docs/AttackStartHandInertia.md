# Attack-entry hand inertia

Blueprint node: **Set Attack Start Hand Inertia**, category **Prophecy → Agent → Hands**. Configure before triggering an attack. Disabled until explicitly configured.

| Pin | Default | Meaning |
| --- | ---: | --- |
| Enabled | false | Enable for subsequent new attacks; false cancels immediately. |
| Hold Out Time | 0.1 s | Keep full configured inertia influence before fading. This preserves motion, not a frozen hand pose. |
| Blend Time | 0.3 s | Smoothly fade influence back to the attack output. |
| Reference Alpha | 1 | 0 = pelvis, 1 = spine_05; intermediate values blend their world origins and shortest-path rotations. |
| Response Time | 0.25 s | Critically damped spring softness; larger values retain more inertia. Zero bypasses. |
| Momentum Scale | 1 | Scale incoming reference-local linear/angular velocity. Zero removes incoming momentum but retains spring lag. |
| Alpha | 1 | Overall influence, clamped0–1. Zero disables completely. |
| Left Hand / Right Hand | true / true | Select either or both hands. |

Hold/blend use the shared60-unpaused-tick authored-second clock. Settings latch when a new attack starts; repeated setter calls do not restart an active window. Retriggering/retargeting an existing attack or switching half/full does not restart it. Disabling or setting Alpha0 cancels immediately. New attacks capture fresh entry motion; an upper attack end, replacement non-attack special, reset, actor removal, or world cleanup cancels the entry state. Lower-end events during a full→half switch leave it running.

The enabled entry reads the existing NN pose snapshot once. Wrist positions and orientations are spring-filtered in the blended anatomical reference, so body translation/rotation is carried with that reference instead of becoming unwanted world-space hand lag. Both connected arm chains are reconstructed around those targets, retaining bounded reach and elbow guidance. Unreachable targets discard outward velocity instead of accumulating an invisible runaway target.

The correction runs on the accepted attack NN pose before its existing publication/history update. Physical meshes follow normal targets. Full attacks feed accepted arm channels into attack recurrence. Half attacks keep the existing independent ghost policy and publish the corrected real upper pose/history. No extra checkpoint inference, physics impulses, persistent full-pose history or mesh-only offset.

Full-attack feedback can change Armed/Hit timing: this influences the checkpoint's actual motion rather than applying a cosmetic offset over an unchanged attack.

Disabled or completed instances have no entry sampling, active clock, spring/IK math or extra inference. Hooks are cheap sparse-state guards; configured idle agents do not continuously sample hands. New state lives in separate maps rather than resizing retained Live Coding allocations.

This is separate from **Set Attack Upper Body Inertia**, which runs after upper special completion, and from pelvis/foot attack-entry inertia.

Native patch loaded September29 at18:57:23 UTC. Two focused tests passed18:57:58: `Prophecy.NN.AttackEntry.HandReference` and `HandLifecycle`. They cover reference endpoints/midpoint and rigid body covariance, reference-local velocity, zero momentum versus disabled inertia, selected-hand ownership, arm connection, repeated publication/setters, hold/blend timing (including exact default tick24 retirement), zero alpha, reset and cleanup. The reflected Blueprint function was also verified through a null-agent validation call.

Owned current-setup physical replays: disabled and Alpha0 produce exactly identical NN positions across210 ticks. Enabled reference0.5, response0.25, momentum1 stays finite and leaves pre-attack NN motion identical. Default hold0.1/blend0.3 starts at151, switches full→half at173 while the window is still running, hits183 and completes195 (baseline half165/hit175/end187). A stronger hold0.35/blend0.35 comparison remains finite but delays Armed to193/Hit201 and was bounded at210. These are behavior checks, not unchanged attack-timing claims. Source scripts/data: `Saved/Diagnostics/CaptureAttackStartHands.py`, `AnalyzeAttackStartHands.py`, `Knee202/entry_hands_*.json`. All capture configuration is temporary; no user Blueprint settings or assets saved.

Final check confirms Alpha0 matches **every raw NN transform**, including both future/presented rotations and scales, exactly. Additional240-tick owned replay forces full→half at155 and half→full at161 during the default window: both setters succeed, all captured poses remain finite, later normal half transition177/Hit187/end199 completes. All five owned replays ended, no trace/full suite/restart/explicit asset save, node left unconfigured in the user's Blueprint.
