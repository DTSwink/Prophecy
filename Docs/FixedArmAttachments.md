# Fixed hand attachment — September 30, 2026

By default, both wrists remain at their anatomical forearm offsets. The later [Set NN Wrist Freedom](NNWristFreedom.md) node can bypass this for NN output only; physical attachment remains locked. This applies to locomotion, full/half attacks and their ghost, parry/dodge, manual poses, hand tempering, neutral return, entry inertia, exit inertia, and intermediate presentation frames. For the current runtime contract the lengths are approximately 22.34915 cm left and 22.34924 cm right. Hand rotation remains independently authored.

Removed the attack and locomotion hand-clamp nodes, locomotion forearm-clamp node, parry/dodge hand and forearm clamp nodes, manager hand-clamp defaults/multiplier, snapshot fields, easing channels, clamp-profile entries, and inertia length blending/springs. `Blend Clamp To Snapshot` now offers Calf and Foot; `Blend All Clamps To Snapshot` covers the eight leg settings across four modes. The physical-profile debug row identifies arms as fixed length. Wrist angular controls and leg allowances retain their separate purposes.

The decoder builds fixed-length forearms, and publication carries the anatomical local offsets. Presentation places each wrist at its interpolated forearm's endpoint; interpolating wrist position independently would shorten an otherwise valid arm. The same correction feeds the authored targets read by physics. The final hand-chain solves use constant lengths independent of Alpha/Hold/Blend.

On physical rig/mode entry, wrist joints lock all three linear axes, disable linear breaking, and use the wrist origin and reference forearm endpoint as their anchors. Both Chaos entry and Jolt rig capture use this rule. Existing angular limits and drives remain independent. Physics can still exhibit finite solver error; there is no intentional translation range.

No extra checkpoint inference, all-bone solve, hand-leeway tick state, or hand-leeway blend callback was added. Fixed attachment is a bounded pair of endpoint transforms in the existing publication/presentation paths; joint setup runs only at mode/rig entry.

The current Blueprint's nine obsolete calls were removed with execution wires reconnected. Saved and live Blueprint copies plus the pre-change source are under `Saved/Diagnostics/FixedArms20260930/Before/`. Existing unrelated user changes were preserved. The old hand-leeway test scripts are replaced by `Tools/NN/TestProphecyFixedArms.py`, which owns its PIE session, records NN and physical wrist lengths, and can temporarily preview Physical mode before restoring the graph without saving.

Validation: normal Editor build succeeded in208.71s and Unreal reopened on testNN. Nine focused tests passed at12:49:15UTC (fixed attachment/interpolation, hand-chain continuity, entry lifecycle, three upper-inertia checks, and remaining leg clamp snapshots). The Alpha fixture now supplies a different fixed-length pose instead of shortening the wrist goal.

Two620-tick rollouts completed four full-to-half SlashR attacks, ending at187/349/443/543. Both NN forearm lengths stayed within7e-12cm of their contract through every sampled future/presented frame. The Physical preview stayed simulated for all620 samples; all temporary mode literals were restored and the Blueprint compiled successfully without saving.

Locked physical joints still have solver residual: maximum length errors0.329cm left and0.918cm right after tick20; startup right error1.485cm at2. The user explicitly said not to worry about this. No additional solver iterations, projection, plugin changes, or simulated-body teleport correction were introduced.

The current rollout also exposed startup Sim-to-Kinematic component-space blending shortening the rendered forearm by1.715cm at12, although NN readback was already exact. Final animation output now restores wrist-local reference translation after overlay and mode blends. This preserves hand rotations and finger-local poses. Final Live Coding patch loaded12:50:25UTC. A fresh620-tick current-setup replay passed the NN and rendered-kinematic wrist-length assertions, including the startup mode blends. The maximum rendered kinematic error was 2.98029867e-07cm; owned PIE ended12:51:47UTC.

Evidence: `Saved/Diagnostics/FixedArms20260930/Analysis.json`, `current_before_modefix.json`, `physical.json`, `BlueprintMigration.txt`, and the nine test results in the Unreal log.
