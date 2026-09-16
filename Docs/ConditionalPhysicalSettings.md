# Conditional magnetization and feedback

The existing **Set Body Magnetization Below**, **Set Physical Feedback Tolerance Below**, **Blend Body Magnetization Below**, and **Blend Physical Feedback Tolerance Below** nodes, plus their four single-bone counterparts (Set Body Magnetization, Set Physical Feedback Tolerance, Blend Body Magnetization, Blend Physical Feedback Tolerance), now have two additional selectors:

- **Locomotion:** Both, Walk, Run.
- **Equipment:** Both, Drawn, Sheathed.

Both enums default to Both, including old serialized nodes with no pins for these arguments. Existing execution wires and numeric arguments retain their names. Self-collision is explicitly excluded from this refactor. Native physical test-pawn controls and one-shot force/impulse operations are separate APIs.

Call the nodes to configure values, rather than only while their conditions match. For example, configure upperarm_r with Both/Both = 1, then Run/Drawn = 0.3. The latter changes only running with a sword in hand. Actual published Walk/Run checkpoint proportions mix numeric settings while policies blend; this follows checkpoint selection, including speed-based Walk overrides. Drawn means actual held equipment, matching the NN sword input; Sheathed also includes no held sword.

Calls write the selected combinations. Last call wins where selections overlap. Both/Both overwrites all four combinations for the selected bones. Unselected combinations keep their prior values; the first conditional call initializes them from the current settings. Descendant and Include Parent semantics are unchanged: magnetization includes PHAT bodies, whereas feedback affects only recurrently controlled bones. Disabled magnetization contributes zero strength while blending with an enabled checkpoint.

Full and half attacks override per-body magnetization to **enabled, linear 1 / angular 1**, and feedback tolerance to **1000 cm / 1000 degrees**, as explicitly requested. This preserves simulation membership, per-body gravity settings, global magnetization controls, and other unrelated properties. The locomotion configurations return after the attack. Changes made during an attack update the stored locomotion settings while the attack override remains in effect. This applies to unarmed attacks too, through the existing shared attack lifecycle.

Timed Below nodes retain smoothstep interpolation. Each selected combination has its own start and target, progressing in game time with actor time dilation. Changing checkpoint/equipment does not restart a timer. Attack entry transfers any active legacy timeline, preserving its original elapsed time and curve; the timer progresses behind the attack override. Cancel nodes freeze the stored values, and single-bone setters with Both/Both, or the All setters, overwrite their selected bones universally.

No new ticking component or subsystem is added. Ordinary Both/Both locomotion calls remain on the old implementation without allocating a policy. Conditional settings use weak per-agent storage, request-time hierarchy traversal, cached context and changed-value publication. The existing agent update and pre-feedback sampling update configured agents. Attack-only snapshots are removed on return to locomotion when no conditional settings or timelines remain. EndPlay clears the agent's storage. The pre-existing body/feedback getters expose the currently applied values.

Validation scope: one small native selection/timeline/attack test, followed by a short PIE startup check. No performance benchmark or extensive gameplay testing.

Validated 2026-09-14: normal Editor build succeeded; SelectionAndAttacks native regression passed, including reflected Both/Both defaults and preservation of active timed blends through attacks. Current saved scene passed 120 frames of PIE and clean shutdown without Blueprint errors/assertions. Unreal remains open on testNN with no dirty assets; no saved Blueprint/map modifications.

Single-bone extension validated 2026-09-14: normal build, extended native selection/timeline/default regression and 120-frame current-scene PIE all passed. No saved graph changes; Unreal remains open.
