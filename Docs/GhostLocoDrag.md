# Ghost Loco Drag

`Set Ghost Loco Drag` opts a full non-kick attack into two lower-body histories. Configure it before the attack. It starts only when at least one foot enters under Loco Drag; changing the setting affects the next attack. Default is disabled.

The attack upper network does not receive leg channels directly. Its 217-value input contains upper history, attack/target/phase information, and previous/current/next pelvis transforms. Dragged legs influence it indirectly by changing the lower model's next pelvis prediction.

With this option enabled:

- The main attack history retains its own predicted legs instead of receiving Loco Drag leg feedback. It predicts the shared pelvis and runs the upper network once.
- A second lower-only prediction uses the accepted visible leg history and the same previous/current pelvis, target, labels and checkpoint. Its legs attach to the shared pelvis with the existing hip solve, then pass through the existing clamps, Loco Drag ownership/blending, pole correction and foot handoff.
- Accepted visible legs feed only the real leg history and the existing locomotion recurrence. They cannot overwrite the attack ghost legs. The extra leg branch continues until attack end so completed feet preserve their own history.
- The actual authored pelvis follows the ghost branch. This deliberately changes the pelvis trajectory compared with ordinary Loco Drag; substituting legs while retaining precisely the old pelvis trajectory would not change the upper network.

The existing pelvis inertia is retained. Native pelvis-target inertia, when enabled, runs once in the primary prediction. The second leg prediction does not advance it. Attack-start presentation inertia, physical pelvis following, and their current settings remain on their existing paths. Thus “shared pelvis” means the character's authored pelvis, followed by the same presentation/physical processing as before.

`Draw Ghost Loco Drag` draws cyan ghost legs each time it is called. Wire it to Tick for a continuous overlay; Enabled hides/shows it, World Offset separates it spatially, and Duration controls debug-line lifetime. It uses interpolated ghost legs attached to the actual presented pelvis, including presentation inertia. `Read Ghost Loco Drag` returns that same nine-bone world pose for diagnostics.

Half mode suspends the extra branch. A full attack returning from half retains its attack ghost and reseeds the real leg history from the two actual poses in the new carrier. Switching to a kick cancels the branch and restores its real leg history. Attack end, reset, agent removal and world cleanup retire the state. A direct half attack has no ghost-loco branch.

Implementation shares the existing checkpoint and batches only opted-in real leg predictions. It evaluates no extra upper network and creates no second model instance. Reusable game-thread scratch avoids per-step input/output allocation; disabled agents have no ghost state. The existing Run/Walk inference required by pending drag feet still operates normally.

Validation and current Blueprint wiring are recorded in `Saved/Diagnostics/GhostLocoDrag20261003/` and the project journal.

October 3 acceptance: normal Development Editor build and six focused tests passed. In the matched second pike, Armed-to-Hit physical sword transverse deviation was 14.3944 cm with ordinary drag and 5.9828 cm with ghost drag. Primary native outputs matched the drag-disabled attack exactly. Visible feet still used drag, though the changed pelvis advanced the right-foot release by two game ticks. Existing pelvis entry inertia remained active. The user confirmed the result and FK return. No FK-return algorithm or settings were changed for this feature.
