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

## Ghost Loco Inertia

`Ghost Loco Inertia` (`SetGhostLocoInertia`) is a separate opt-in setting, configured
before the attack. Pins: **Enabled=false**, **Duration Ticks=12**, **Multiplier=1**.
Multipliers above 1 are supported. It requires an active Ghost Loco Drag branch;
it does not enable drag or create ghost legs on its own.

At ghost entry it captures the last encoded locomotion window's **Root+1 − Root**
in world centimeters (array entries 2 minus 1; entry 0 is the previous root).
The multiplier scales that one total displacement. Each accepted attack prediction
adds the elapsed fraction to both ghost ankles. For example, a 10 cm root vector
with multiplier 2 over 10 ticks adds 20 cm total, 2 cm per tick. Prediction and
presentation retain their existing cadence. There is no velocity fade and the
vector is not recaptured as the character turns. Duration 0 applies the whole
amount at the first accepted prediction.

The existing two-bone solver reconnects each shifted leg to its unchanged hip,
preserving segment lengths, foot orientation and local toe transform. Unreachable
ankles are limited to the leg's reach shell. Only the accepted ghost leg channels
feed back; subsequent NN predictions can respond through the shared pelvis.
Consequently the final foot difference from an unmodified rollout need not equal
the injected displacement: the NN continues to move the feet and reach limits
still apply. Real drag legs and pelvis inertia keep their existing processing.
The existing `Read/Draw Ghost Loco Drag` automatically includes the correction.

Ticks are unpaused game ticks, independent of frame delta and agent time dilation,
using the existing blend clock. Half mode pauses the pending displacement and
resumes it if the same attack returns to full. End/kick replacement/reset/removal
discard the remainder, so it cannot leak into return-to-idle or another attack.
Disabling cancels immediately; other setting changes latch at the next attack.
Root lookup and allocation happen at entry only; the prediction path uses fixed
scratch, two leg solves and only two leg-channel writes, with no extra inference.

October 4 validation: Live Coding loaded October 3 23:45:09 UTC (October 4 local).
All five GhostLocoInertia/GhostLocoDrag/SixtyTickClock tests passed. Three final
160-tick owned physical runs compare default-off, explicit-off and enabled
(duration6, multiplier2). Default-off and explicit-off captures/native traces
match exactly. Enabled prefix before the first affected prediction matches too.
Each foot received world displacement (-25.982976,20.876837,0) cm in fractions
1/6,2/6,2/6,1/6 across four policy predictions: total error below0.0000075cm,
then exactly zero extra displacement. All recorded poses remained finite through
half transition and attack end. This establishes the additive ghost feedback,
not a claim of improved combat motion. Receipts/scripts:
`Saved/Diagnostics/GhostLocoInertia20261004/verification.json`.

The user edited the movement/debug branch during compilation, so the initial
pre-build capture is not a valid comparison to the final scene. Final tests set
`bool debug 3` only on owned PIE actors through SetBoolPropertyByName; editor
settings and the user's new graph remain intact. Early captures without attacks
and failed instance-editor-property attempts are not acceptance runs.

Live Coding archived existing library CDO references, causing a Play compile
prompt. User dismissed it after computer-control initialization failed. Existing
`Prophecy.Editor.RepairLibraryDefaults` repaired59 references and proved all other
values/wiring unchanged. Run this repair before PIE after reflected library reloads
when those archived references remain. Final BP status3, native_properties0 and
pin_types0; BP saved, map not saved. New node is available but not wired/enabled.
Owned Play ended, trace restored-1/0. Normal Development Editor DLL rebuild is
still required before any cold launch; do not reopen against the older DLL.

Validation and current Blueprint wiring are recorded in `Saved/Diagnostics/GhostLocoDrag20261003/` and the project journal.

October 3 acceptance: normal Development Editor build and six focused tests passed. In the matched second pike, Armed-to-Hit physical sword transverse deviation was 14.3944 cm with ordinary drag and 5.9828 cm with ghost drag. Primary native outputs matched the drag-disabled attack exactly. Visible feet still used drag, though the changed pelvis advanced the right-foot release by two game ticks. Existing pelvis entry inertia remained active. The user confirmed the result and FK return. No FK-return algorithm or settings were changed for this feature.
