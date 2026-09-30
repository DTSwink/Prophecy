# Original GT target loop

`BP_ProphecyManualPoseAgent` → **codex GT slash** uses the user's existing possessed-agent, tick > 29 caller.

- **Attack**: any of the 16 supported attack names; default `slashR`.
- **Cool Out Seconds**: delay after actual NN attack completion; default 1 second. Negative values act as zero. Zero starts the next attack on the first function call after completion. The clock uses game seconds and pauses with the game.
- **Show Target**: draw a cyan sphere at the sampled original target, including during cooldown. Default true; false skips drawing.

Before every attack, **Prepare GT Attack From Idle** sets both previous/current lower and upper NN history frames to frame 0 of `M_Neutral_Stand_Idle_Loop`, clears mover momentum and the root window, and publishes that pose at the current agent carrier. The selected attack's original saved GT target is transformed from its source frame-0 root to that same carrier. **Trigger NN Attack** then runs a full attack with the current checkpoint and tuning. It does not play recorded attack poses or change weights.

Each repeat seeds the pose again at the agent's current world position and facing; it does not teleport the agent back to the first loop's world origin. Existing graph logic can still change attack tuning or half/full ownership. The seed requires an initialized Kinematic agent with no active attack, defense or animation layer. Invalid attack names/setup stop the loop and print the error once; reset `Codex GT Failed` to false to retry, or restart PIE.

`Tools/NN/ExportGTAttackIdleFixture.py` reads the original `final_gt_attack_dataset_npz` target metadata and the authored neutral idle, generating `Tools/NN/Fixtures/GTAttackIdle.json`. It records all source hashes and validates target-coordinate round trips. Both seed frames are identical, giving zero initial skeletal velocity. The shared debug seeding implementation retains the older slash-train fixture path and framing behavior for its existing node.

Loop timing, target storage and debug drawing are ordinary nodes in the Blueprint function. There is no additional native tick, timer, or inference. Fixture parsing and history replacement occur only at attack entry when this function is used. Live/disk Blueprint and affected source backups are under `Saved/Diagnostics/GTAttackIdle20260930/Before`.

Validation/status (September30): native changes loaded14:44:09UTC; the30-node Blueprint function compiled successfully (status3), preserved its caller and is not yet explicitly saved. Source idle arm values agree with the established idle seed within5.04e-8; all16 target coordinate round trips passed. A temporary owned Kinematic PIE run started attacks at30/138/246 and observed ends77/185, respecting the1-second cooldown with finite poses; PIE ended14:47:36UTC. Reports are in `Saved/Diagnostics/GTAttackIdle20260930`. The authored current setup is Physical and enables starting specials from physical; the existing seed rejects that mode. The user subsequently accepted the setup ('all good') and moved on. No automatic authored mode change has been made; do not resume this earlier mode question without a new request.
