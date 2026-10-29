# Throw controls — native port

October29 initial port of the approved Throw Lab checkpoint `a193d263`.
Normal Editor build and all four `Prophecy.Throws` tests pass. The native DLLs
are current; the main project was not opened interactively.
The exact saved setup is in `Labs/ThrowLab/approved/2026-10-29/`.

## Blueprint surface

Search **Lab Throw** under **Prophecy / Throw**:

- **Begin Lab Throw** starts charging. Call **Release Lab Throw** on trigger-up.
  Small Throw derives its percentage from the charge frames actually played.
  Big Throw reaches its armed marker before beginning its complete throw.
- **Play Lab Throw** plays a chosen throw immediately. Its advanced percentage
  input defaults to `-1`, meaning the lab's saved percentage (currently Small37%).
  Big Throw remains100%.
- Both action nodes return **Released**, **Completed**, **Cancelled**, and
  **Failed** execution pins. Release fires once; no Blueprint Tick is needed to
  find the fractional release marker.
- **Cancel Lab Throw** stops the action. **Get Lab Throw State** reads the
  current phase/frame, charge, held hand/weapon frame, object kind and launch data.

Provide the agent and an absolute world target. The profile's saved Aim setting
determines whether that target is used. Current Big aims; current Small does not.
There are no Blueprint pins for hand/forearm edits, grips, timing, slowdown,
body effort, clavicle recovery, Half or Aim. These mirror the approved lab.

The physical struct provides an additional launch-velocity multiplier, world
velocity rotation and optional axial twist in degrees/frame. Multiplier1 and no
override preserve the lab's existing amplitude and twist. Velocity output uses
UE cm/second; angular output uses world radians/second. Reflection reverses the
angular-vector sign, preserving the lab's visible spin direction.

## Integration boundary

The native action supplies the authored pose to the existing pose publication
path and writes the accepted lower/upper pose back into NN recurrence. It does
not add or change any Blueprint nodes, wires, map actors or asset defaults.
The existing game object logic must attach the selected object while held and
consume the Released event to launch it. The weapon transform identifies the
**lab geometry frame**; original asset pivots/binds must be reconciled before
using it directly as a mesh-component transform (especially the bomb).

This first port does **not** yet own projectile spawning, hand attachment,
Jolt admission/substep release, impact behavior, or the lab's aerodynamic forces.
The exact fractional release transform/velocity and remaining tick fraction are
available for that integration. Do not describe the physical flight as ported
or verified merely because pose/launch-data parity passes.

Throw publication runs every game frame, preserving odd-frame rotation keys;
the existing NN inference cadence stays intact. The shared presentation alpha
selects that exact authored frame while the throw owns the pose.
Timing is one authored frame per unpaused game-world tick. FPS, hitches and time
dilation do not buy additional frames. Active state/callbacks retire on completion,
cancellation and world cleanup. The profile is loaded once on first use.
Conflicting attacks, animation layers, reaching, get-up and sword actions are
rejected at start instead of being silently interrupted. Runtime interruptions,
long armed holds, locomotion transitions and actual physical scene behavior still
need an in-game integration pass. User tuning and current Play must be preserved.

## Data and verification

`node Tools/Throws/export.mjs` explicitly imports the approved snapshot and
current lab algorithm/data into `Content/ThrowLab/Profile.json`, and creates an
independent JS reference under `Saved/Diagnostics/ThrowPort20261029/reference.json`.
It does not write the live lab state. Exported JSON is staged as a runtime UFS
dependency. Updating the mirrored preset requires a deliberate re-export.

`Tools/Throws/verify_axes.py` compares all raw joints/frames to the SDK conversion
used by UE5.7's FBX importer: Z-up, -Y forward, then Y reflection. Maximum position
error1.32e-13cm and quaternion error2.23e-16. Source FBXs remain untouched.

Native automation group: **Prophecy.Throws**. All four tests pass:1392 poses across
18 cases, max position error1.92e-11m, quaternion error6.67e-16 and launch velocity/
twist error2.10e-14. It covers the independent lab
pose/launch comparison, control-node reflection, causal charge prefix, game-tick
timing, one release per action and callback retirement. A first parity failure
exposed use of UE's float PI constant; double precision fixed it without changing
the test tolerances. Reflection inspection reports status3/native_properties0/
pin_types0/wiring_preserved1. PoseAgent/TestNN file hashes remain unchanged.
This is not a visual or physical Play validation.

Evidence: `Saved/Diagnostics/ThrowPort20261029/` (`build3.log`, `automation3.log`,
`report/index.json`, `axes.json`, and before/after asset hashes). Run isolated
automation with `-nullrhi -nocef -unattended -DisablePlugins=Fab` and the empty
`/Engine/Maps/Entry` map. The first attempt hit a restored Fab browser tab's
startup assertion before tests; excluding Fab for that diagnostic process fixed
startup without editing project plugins or user settings.
