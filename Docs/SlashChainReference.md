# 30-attack reference in testNN

Press Play in `/Game/testNN`. The orange **SlashChain30_Reference_Looping** is
saved at `(450, -385, 0)`, next to the existing manual agent. It plays
`/Game/_mygame/Tests/SlashChain30/AS_SlashChain30_Reference` indefinitely.
It is a recorded reference, **not another live NN**. One ordinary SkeletalMeshActor
plays a native animation; there is no Python tick, inference, physics, collision,
post-process animation Blueprint, or change to the existing agent.

455 authored frames at 30 Hz: **15.1667 seconds per loop**. The final pose is held
for the last sample interval, then playback resets to frame 0. No invented
transition is blended across the loop seam. Root motion is not extracted; the
recorded pelvis trajectory remains in the animation. Default orange material.

Authoritative handoff:
`C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260907_good_pt_continuous_random_30_hits_unreal_handoff/README_UNREAL.md`.
NPZ SHA-256: `e09a178140ca2b40701166cf9aeee4fdf409b409d6ae28a9ee9dbdb378d187ca`.
Checkpoint is accepted `good.pt`, step 265458, SHA-256
`6a76321d6e1525c9e6bcfcedcd0ce46676b03dd15dd277c2bd87f6c834239072`.

## Verified results

- Imported animation, all 455 × 25 world-space bones: maximum position error
  **0.01267 mm**, maximum angular error **0.01140°**.
- Live rendered mesh: **1,451 samples, two loop seams**, maximum position error
  **0.09981 mm** against Unreal's evaluated reference pose. Two live images inspected.
- Native NN versus independent Python **with the same four-step pinning**:
  453 self-fed steps, no pose reset between attacks; maximum world position error
  **0.09993 mm**, matrix-element error **0.000326**, identical Armed/Hit latches.
- Independently re-seeding each transition from the reference: native versus
  four-step Python maximum **0.001152 mm**, all latches identical.
- **All 30 learned Hit frames match the immutable saved rollout**, including
  headbutt frame 247. Its frame-246 early hit request must arm the attack before
  it can hit; the native latch rule now matches `advance_phase_latches` exactly.
- The earlier single-attack audit still passes (**0.003153 mm** against four-step Python).

**Not an exact live-NN match to the original 60-step rollout:** production's
previously accepted four-step frozen-Walk foot-pinning approximation remains
unchanged. Over this longer chain it produces a maximum **177.652 mm** world-joint
difference (right hand around frame 100) and one different Armed frame (98).
Python with that same approximation independently differs by **177.559 mm**.
Hit frames still all match. This accumulated approximation error is distinct
from the native port error; the reference animation itself is not approximated
this way. No weights, training/viewer code, or source rollout were changed.

## Reproduce

Use Stepper's `.tools/python310/python.exe` for the offline scripts:

1. `Tools/NN/PrepareProphecySlashChainAnimation.py` prepares lossless import tracks.
2. `Tools/NN/InstallProphecySlashChainReference.py` runs through the editor bridge
   outside PIE, only in clean `testNN`; creates/saves the new animation and map.
   Refuses to overwrite an already saved reference. Does not save dirty user BPs.
3. `Tools/NN/TestProphecySlashChainAnimation.py` checks all imported integer frames.
4. `Tools/NN/TestProphecySlashChainPlayback.py` runs in PIE, observes two loop seams
   and checks rendered bones. Its temporary camera is removed afterward.
5. `Tools/NN/PrepareProphecySlashChainAudit.py` creates the independent Python
   fixtures under `Saved/SlashChain`. Source poses are encoded into the source's
   exact stationary carrier; audit geometry is separate from production assets.
6. `Tools/NN/AuditProphecySlashChainUnreal.py` runs through the bridge outside PIE.
   It creates/destroys a transient manager and writes `Saved/SlashChain/summary.json`.

Map and animation are saved locally. Existing project ignore rules exclude these
content paths from Git; the reproducible importer/tests are source files.
