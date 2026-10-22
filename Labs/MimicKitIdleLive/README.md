# Live idle push test

Open http://127.0.0.1:8850/ after running `./Labs/MimicKitIdleLive/start.ps1`
from the project root. The server starts paused and binds only to localhost.
Choose a body, world direction and kick strength, resume, then apply an impulse.
Clicking a body also selects it. Reset restores the idle starting pose.

Uses a frozen copy of locomotion checkpoint 0122776 from
`20261022_104557_uefn_locomotion_pelvis_velocity5_1024`, with its saved observation
normalization, action scaling, policy and phase head. Provenance and SHA256 are
in `Saved/MimicKitIdleLive/checkpoint.json`. Training and Unreal are untouched.
The pinned source and assets are in that directory's `source` folder.

The policy receives the actual physical observations and the idle gait command,
with selectable unarmed/drawn equipment and autoregressive predicted phase.
One local CPU agent runs the configured native MuJoCo profile: 240 Hz physics,
30 Hz deterministic policy, original gains and torque limits. The actor reacts
freely; no pose pinning, automatic failure resets, AE, reward or learning loop.
CPU native physics is not guaranteed bit-identical to GPU training trajectories.

Strength is an instantaneous velocity change in m/s at the selected body's COM
along the selected world direction. The generalized impulse is computed from
MuJoCo's mass matrix and body COM Jacobian, accounting for connected limbs.
Thus a 1 m/s kick starts with the same directional speed change on a hand or
pelvis, although the required impulse and subsequent motion differ. Contacts
and motors subsequently respond normally. It does not teleport any pose.
Reference: https://mujoco.readthedocs.io/en/3.10.0/APIreference/APIfunctions.html

Pause cancels the browser's simulation timer; the server has no background
physics loop. Rendering is also event-driven while paused. Hiding or leaving
the tab pauses it. Model data stays in memory so resuming is immediate.
The server can be closed entirely to release that memory.

Verification receipts live in `Saved/MimicKitIdleLive/verification.json`.
They check pause tick stability, both idle stances, and equal requested speed
changes across different body masses. `smoke.log` contains a 90-tick idle/kick
smoke check. No cloud GPU or paid service is used by this viewer.
