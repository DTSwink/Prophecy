# Attack-entry hand inertia

Blueprint node: **Set Attack Start Hand Inertia**, category **Prophecy → Agent → Hands**. Configure before triggering an attack. Disabled until explicitly configured.

| Pin | Default | Meaning |
| --- | ---: | --- |
| Enabled | false | Enable for subsequent new attacks; false cancels immediately. |
| Hold Out Time | 0.1 s | Keep full configured inertia influence before fading. This preserves motion, not a frozen hand pose. |
| Blend Time | 0.3 s | Smoothly fade influence back to the attack output. |
| Reference Alpha | 1 | 0 = locomotion root local (published root position and yaw), 1 = spine_05 local; intermediate values blend root position/heading toward spine position/rotation. |
| Response Time | 0.25 s | Critically damped spring softness; larger values retain more inertia. Zero bypasses. |
| Momentum Scale | 1 | Scale incoming reference-local linear/angular velocity. Zero removes incoming momentum but retains spring lag. |
| Alpha | 1 | Overall influence, clamped0–1. Zero disables completely. |
| Left Hand / Right Hand | true / true | Select either or both hands. |
| Last Attack Tick Threshold | 0 | Start only when the existing **Get Ticks Since Last Attack** count is strictly greater than this value. |

The gate captures the count at accepted attack entry **before** the full-attack
reset to zero, then uses that captured value when initializing hand inertia.
For threshold25:25 skips,26 enables. Default0 skips a zero-count immediate chain.
It checks once per new attack, before pose sampling or clock creation. Raising or
lowering the threshold later applies to the next attack; it never switches an
ongoing effect on/off. The counter's existing full/half/lower-release/reset and
manual seed behavior is unchanged. The modifier debug report includes the captured
entry count when this effect is active.

Hold/blend use the shared60-unpaused-tick authored-second clock. Settings latch when a new attack starts; repeated setter calls do not restart an active window. Retriggering/retargeting an existing attack or switching half/full does not restart it. Disabling or setting Alpha0 cancels immediately. New attacks capture fresh entry motion; an upper attack end, replacement non-attack special, reset, actor removal, or world cleanup cancels the entry state. Lower-end events during a full→half switch leave it running.

The enabled entry reads the existing NN pose snapshot once. Wrist positions and orientations are spring-filtered in the selected root-to-spine reference. At Reference Alpha 0, the reference is the locomotion root's published world position and yaw, matching the existing root-local hand controls; it is neither the pelvis bone nor absolute world space. Entry velocity uses the previous and current root frames, so root movement is removed from measured hand momentum and then carried by the reference. At 1, motion is measured relative to spine_05 and the target follows that reference. Intermediate values blend those moving references. Full and half attack publication supplies the current root, including repeat publications. Both connected arm chains are reconstructed around those targets, retaining bounded reach and elbow guidance. Unreachable targets discard outward velocity instead of accumulating an invisible runaway target.

The correction runs on the accepted attack NN pose before its existing publication/history update. Physical meshes follow normal targets. Full attacks feed accepted arm channels into attack recurrence. Half attacks keep the existing independent ghost policy and publish the corrected real upper pose/history. No extra checkpoint inference, physics impulses, persistent full-pose history or mesh-only offset.

When attack forearm stretch is enabled, the arm solver blends from the captured
entry forearm length to the predicted length using the same influence as hand
inertia. Full influence retains entry length; zero influence restores the
predicted length. This prevents an immediately shorter forearm from making a
held wrist unreachable and forcing the elbow straight. Fixed-length arms keep
their existing behavior. The existing physical wrist allowance and inertia
timing remain unchanged; no additional timer or inference is needed.

Full-attack feedback can change Armed/Hit timing: this influences the checkpoint's actual motion rather than applying a cosmetic offset over an unchanged attack.

Disabled or completed instances have no entry sampling, active clock, spring/IK math or extra inference. Hooks are cheap sparse-state guards; configured idle agents do not continuously sample hands. New state lives in separate maps rather than resizing retained Live Coding allocations.

This is separate from **Set Attack Upper Body Inertia**, which runs after upper special completion, and from pelvis/foot attack-entry inertia.

**October 1 corrected request:** zero selects locomotion root local instead of pelvis local. The user corrected the preceding request for absolute world space; that intermediate implementation is superseded. The default 1 retains spine-local behavior. Existing values below 1 intentionally have different semantics; no saved Blueprint values or wiring are migrated. Response 0 still disables the entire entry effect regardless of Hold, Enabled, Momentum or reference selection.

**Current root-local verification:** Live Coding compiled in **196.43 seconds** and
finished loading at **21:51:32 UTC**. Both focused `HandReference` and `HandLifecycle`
tests passed at **21:52:09 UTC**. Coverage verifies removal of common root/body
velocity, root/spine reference endpoints and midpoint, moving-root hand carrying,
independent spine movement at a fixed root, fixed arm attachments, a nonidentity
component carrier, and the existing lifecycle. Pose BP compiled with status 3;
36 archived library defaults were repaired, all other values/wiring preserved,
no explicit save. No stale agent properties/pin types found. User Play was not
stopped; verification ran after it ended. No gameplay capture, full suite,
normal-DLL rebuild or push. Script: `Saved/Diagnostics/VerifyAttackStartHandsRoot.py`.

**Superseded absolute-world implementation:** Live Coding compiled successfully in 158.16 seconds and finished loading at
**21:39:05 UTC**. The two focused `Prophecy.NN.AttackEntry.HandReference` and
`HandLifecycle` tests passed at **21:39:49 UTC**. Updated coverage verifies world
linear/angular velocity, spine-relative velocity, intermediate reference rotation,
stationary world wrists versus spine-carried wrists under body movement with a
nonidentity component carrier, fixed forearm lengths, and the existing lifecycle.
The pose Blueprint compiled with status 3; 60 archived library defaults were
repaired after Live Coding, preserving all other pin values/wiring and leaving the
asset unsaved. No stale agent properties or pin types were found. No gameplay
capture, full suite, editor restart, normal-DLL rebuild or push for this change.

The following September29 evidence predates the root-local endpoint change and used the former pelvis-to-spine mapping. Native patch loaded at18:57:23 UTC. Two focused tests passed18:57:58: `Prophecy.NN.AttackEntry.HandReference` and `HandLifecycle`. They covered reference endpoints/midpoint and rigid body covariance, reference-local velocity, zero momentum versus disabled inertia, selected-hand ownership, arm connection, repeated publication/setters, hold/blend timing (including exact default tick24 retirement), zero alpha, reset and cleanup. The reflected Blueprint function was also verified through a null-agent validation call.

Owned current-setup physical replays: disabled and Alpha0 produce exactly identical NN positions across210 ticks. Enabled reference0.5, response0.25, momentum1 stays finite and leaves pre-attack NN motion identical. Default hold0.1/blend0.3 starts at151, switches full→half at173 while the window is still running, hits183 and completes195 (baseline half165/hit175/end187). A stronger hold0.35/blend0.35 comparison remains finite but delays Armed to193/Hit201 and was bounded at210. These are behavior checks, not unchanged attack-timing claims. Source scripts/data: `Saved/Diagnostics/CaptureAttackStartHands.py`, `AnalyzeAttackStartHands.py`, `Knee202/entry_hands_*.json`. All capture configuration is temporary; no user Blueprint settings or assets saved.

Final check confirms Alpha0 matches **every raw NN transform**, including both future/presented rotations and scales, exactly. Additional240-tick owned replay forces full→half at155 and half→full at161 during the default window: both setters succeed, all captured poses remain finite, later normal half transition177/Hit187/end199 completes. All five owned replays ended, no trace/full suite/restart/explicit asset save, node left unconfigured in the user's Blueprint.
