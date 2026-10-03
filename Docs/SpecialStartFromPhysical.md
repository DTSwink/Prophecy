# Starting specials from the physical pose

October3 current setup: the user removed the node and chose NN-centered entry. Default remains false; no automatic simulation-mode override exists. Pelvis/core/hands/feet entry inertia use NN history. The physical checkpoint-seed feature below remains available only through an explicit enable call. [Checks and current contract](NNEntry20261003.md).

**Set Special Start From Physical** takes Agent and Enabled (default false). Call it before starting a special. The preference applies to newly started full attacks, half attacks, parries and dodges. Editing an ongoing attack, retargeting it or switching between full and half does not restart its history.

Previously, entry always encoded the published NN component pose and previous NN pose (or the saved Armed activation history for queued defenses). Physical feedback can influence those predictions, but that is not the same as starting from the actual physical skeleton.

With this option enabled and physics active, entry samples the completed physical pose once and encodes it in the special's existing carrier frame. Its previous recurrent pose is estimated one policy interval backward from current physical linear/angular velocities, accounting for rotation about the center of mass. Bones without a body inherit the closest body's motion. This estimate avoids mixing a physical current pose with unrelated NN history; it is not a recorded previous physical frame. The existing Static Attack Initialization option still overrides attack history to remove entry velocity.

Half attacks seed their independent ghost from the physical pose; their visible lower body remains owned by locomotion and existing upper mounting/compensation still applies. Queued parries/dodges sample when they actually activate. Root windows, targets and physical bodies are not teleported or reset by this option.

Attack display interpolation retains the already-published entry endpoint while the model/ghost use the physical seed. This prevents rewinding the first displayed attack interval when locomotion finishes a pending sample after the trigger. [Tick131 correction and replay](Foot131PhysicalEntryHandoff.md).

Kinematic agents and unavailable physical samples keep the existing NN entry. No added inference or per-tick sampling, history cache or pose processing. Disabled entries bypass sampling; configuration uses a sparse weak-agent set and world cleanup, without changing retained actor/manager layouts.

Validation: Live Coding compiled and loaded September 29 at 12:18:50 UTC; reflected Blueprint node verified. Focused `Prophecy.Jolt.Special.PhysicalStart` passed at 12:19:12 UTC, covering default bypass/no pose allocation, physical pose conversion across different root carriers, COM-aware velocity history, unchanged physical body/velocities, disable and kinematic fallback. Attack/parry/dodge entry call sites compiled; no gameplay rollout, full suite, Blueprint wiring or asset save.
