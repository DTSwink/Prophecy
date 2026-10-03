from pathlib import Path
text='''# Attack-start pelvis inertia

`Set Attack Start Pelvis Inertia` is per agent, disabled until configured. Pins: Agent, Enabled, Translation Window Frames (5), Translation Inertia (1), Rotation Window Frames (5), Rotation Inertia (1).

On a new full attack, latch the last two displayed world pelvis poses. Translation inertia 1 repeats their displacement on the first following game tick; rotation inertia 1 repeats their world angular increment (left multiplication, independent of root heading). Each channel's weight decreases linearly from its initial strength on frame 1 to zero on its last frame. A five-frame strength-1 channel therefore uses weights 1, .75, .5, .25, 0. The desired displacement is measured from the previously corrected pose to the current authored target, so there is no leftover position/rotation offset when the channel retires. Values between 0 and 1 interpolate momentum ownership; strengths greater than 1 extrapolate. Windows 0/1 or strength 0 bypass that channel. Settings are latched at entry; repeated setter calls affect the next entry.

These are unpaused game ticks, using the project's 60 Hz duration convention, not wall time or 30 Hz NN steps. Repeated pose readers and collision re-publications cannot spend extra frames. Target/type updates on an active attack do not restart inertia. Half attacks retain locomotion ownership of the pelvis; changing full to half cancels the entry. Ending/canceling an attack clears active correction. Initial-agent reset restores captured settings and clears motion; teardown removes settings and state.

The raw recurrent attack checkpoint, root/window, armed/hit latches and attack duration remain unchanged. The correction acts after ordinary pose interpolation/clamps and is shared by the displayed mesh, Jolt/manual physical targets, legacy Chaos world drives and single-bone target reads. Upper-body attachments follow the corrected pelvis rigidly. Legs transport their current authored bend frame, preserve segment lengths and keep reachable ankle targets; only unreachable endpoints move onto the new hip's reach shell. Foot rotations are retained. This optional entry correction does not replace the accepted locomotion knee-recovery solver.

When disabled or both channels bypass, the setting and history are removed: no sampling, extra inference, timer, allocations or chain math. Hot paths retain early guards. While configured, one pelvis-only sample per game tick retains the two world poses required for exact entry momentum; it does not copy the full pose. Active correction publishes once per tick; animation workers only read it under a lock. First-frame attacks before two displayed samples exist use the existing two policy poses divided by two as a seed.

## Validation

Pending current build and native checks. The helper is called from the existing externally linked RecoveryCalfLength test, to ensure Live Coding executes the new assertions rather than retaining an old anonymous test implementation.
'''
Path('Docs/AttackStartPelvisInertia.md').write_text(text,encoding='utf-8')
