# Kinematic mode switch freezes magic cube (September 29)

The earlier same-mode setter optimization did not fix this rollout failure. The
failing motion is root movement, not a presentation-only bone jump.

## Measured failure

The current Blueprint requests Kinematic every tick but also requests Physical at
tick 5. When the sword controller returns to Chaos during the mode switches, the
generic physics-command and scene-discovery paths can automatically admit its
blade as an independent Jolt prop. That adapter is separate from the sword
controller's own adapter. The next controller bind fails because the blade has
another owner. Its fallback attaches the blade to the hand, invalidating the
independent dynamic adapter.

The shared world then stops at tick 6. The instrumented failure identifies
`A_Sword_C_0.ProphecyJoltBodyComponent_1`: source `sword`, parent `PhysicalMesh`,
follow parent none, attached false, kinematic false. The magic cube is an unrelated
client of the same stopped world, so it also stops despite continued velocity
commands.

In the failing 95-frame replay, cube Y stays -323.556 cm from tick 6 onward.
Root Y advances to -155.890 at tick 61. The Blueprint enables magic feedback after
`Ticks Since Last Attack > 60`, producing -2012.000 cm/s Y correction at tick 61.
The motion window consumes it and root Y reverses from -145.890 at tick 64 to
-160.890 at tick 65, reaching the configured 900 cm/s cap.

## Correction

Automatic prop admission must defer to the equipment controller for a held sword.
Both generic physics commands and dynamic scene discovery now check the holder's
actual held-sword identity before automatically creating an adapter. An existing
controller-owned Jolt adapter still receives commands normally; a held Chaos
blade keeps Chaos ownership. Dropping clears the owner and restores ordinary prop
admission. Attached nonsimulated scene colliders retain their existing path.

Failure diagnostics now identify the shared-step client and report binding changes
instead of an empty preparation error. No Blueprint edits, cube-follow shortcuts,
root-velocity overrides, or global error suppression.

Capture scripts: `Saved/Diagnostics/CaptureKin65.py`; results under
`Saved/Diagnostics/Knee202/kin65_*.json`.

## Validation

Final Live Coding loaded 20:14:08 UTC. The unchanged current Blueprint completed
the matched 95-frame `kin65_fixed` replay without a shared-step/sword ownership
error. At ticks 64/65/66 root Y is -145.890/-142.557/-139.224 cm: continuous
forward movement near 200 cm/s, instead of the previous backward 900 cm/s.
Cube Y at tick 65 is -142.558 cm (about 0.001 cm behind root); magic correction
Y is -0.01393 cm/s instead of -1952.003 cm/s. Cube still follows at tick 90.
The intermediate `kin65_after` replay with only the command-path guard still
failed; the scene-discovery guard is required too. Owned PIE ended; no full suite,
Blueprint modification, explicit asset save, or editor restart.
