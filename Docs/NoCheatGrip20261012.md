# Causal lab mode and drawing grip correction — October12

User authorized a “no cheat” lab checkbox and a fix for the drawing constraint
conflict. No S pursuit/slide-entry fix, tuning change or Blueprint rewiring.

## Lab

Added optional, persistent `noCheat` setting, shared by D/S. Default off retains
the reference behavior. `online.js` records a chronological60Hz simulation,
using existing FK, body, pole, head, curve and return helpers. Input reads are
restricted to each current tick (plus static authoring references). Future gait
and eventual successful arrival are unavailable. Native-style initial duration,
four-tick filtered moving-target refits, deadline pursuit, rolling sliding guides
and60Hz held-arm return replace the future-informed preparation path. Known
authored profile targets can still be evaluated ahead. Entry incoming velocity
uses the observed preceding gait tick; native can also derive it from its already
available NN interpolation state. No runtime solver is added to rendering.

Head/return/gait clocks stay independent of reach/slide curves. Changing a curve
recalculates this simulation; it cannot reuse a future-informed source plan.
Both sequence orders, right-panel body preview, persistence and snapshots use
the selected mode. Off-path frames match the pre-change implementation exactly
for idle/walk/run × D/S. Causal tests modify future input and timeline length:
observed-prefix poses remain identical, later output changes, every dynamic
input access is audited, and six saved-fixture actions complete. Isolated browser
test passes mode switching without seeking, unchanged tuning, both-action mode,
curve bypass during playback, worker edit, disk/reload and restoring original mode.

Scope: recorded kinematic gait, not Jolt, online NN feedback/recurrence, crowd
contact, or multi-agent scheduler phase. Lab-only holster stabilization remains
explicit. This is not a claim of complete Unreal pose parity or a fix for S jitter.

Refresh validation exposed an existing asset-fingerprint mismatch: saved/live
state `38eac96…` matched the pushed holster, while the authorized rigid placement
on disk hashed `934a8e7…`. Added only these known predecessor hashes to setup
metadata and startup compatibility; transforms/meshes/tuning unchanged. Original
snapshot mismatch validation remains. User informed before the compatibility edit.

## Unreal

The temporary fixed joint's drawing FrameB formerly came from the actual sword
body at grip. That retained acquisition/physics-publication error as its rest
relationship, opposing the authored wrist target throughout sliding. FrameB now
comes from `GripLocal()` and the component-to-native-body origin, as S reach
already did. FrameA remains the wrist socket in the hand body. Both use the same
authored grip; scale update, one-joint reuse, release and cancellation paths stay
unchanged. No new fields, controllers, per-tick work, speed/drive changes or damping.

Fresh before/after captures:1000 absolute ticks each, all3agents, current unsaved
Blueprint/tuning retained. For NPC C_2, physical/target/future data are exactly
identical until first D grip190 (C_3 until199); possessed agent's entire captured
prefix remains identical. First release command is unchanged:

| Measurement | Before | After |
| --- | ---: | ---: |
| C_2 wrist error at release208 |9.476°|0.149°|
| C_2 physical step209 (command2.962°) |14.927°|2.995°|
| C_3 wrist error at release217 |6.511°|0.239°|
| C_3 physical step218 (command3.381°) |11.826°|3.300°|
| C_2 first post-grip step191 (command2.593°) |16.179°|6.128°|

Across4 C_2 and5 C_3 D releases, final sliding wrist error ≤0.504°; physical
rotation-step excess above command in the release windows ≤0.261°. No transferred
release kick hidden at acquisition: first-grip error/step also decrease, though
there is still a transient before tracking settles. Later cycles can differ
because physical feedback changes. Current possessed agent still stalls in S;
the change does not address its unreachable approach. Separate500-tick kinematic
capture completed without errors. This confirms the diagnosed constraint conflict
on these fixtures, not perfect motion in every setting or removal of command-side
return steps.

Live Coding implementation-only build succeeded116.00s without a restart.
Post-patch full Blueprint graph and asset hashes match the immediate pre-build
checkpoint; user's already-dirty PoseAgent/TestNN were left unsaved. Editor25964
subsequently closed externally during final checks at22:54. Ran the now-needed
normal build successfully in83.49s; normal DLLs are current. Editor left closed,
no cold-launch verification requested/performed. No push.

Evidence: `Saved/Diagnostics/NoCheatGrip20261012/`: before/after/kinematic captures,
`grip-comparison.json`, `compare.py`, preservation/postflight, build, numerical/UI
receipts and screenshot. Production probes reused `Tools/SwordHolster/ProbeHeadFps.py`.
