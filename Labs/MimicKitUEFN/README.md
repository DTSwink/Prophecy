# UEFN compound humanoid

**Current wrist correction:** wrists are now articulated with their PHAT frames
and limits.15 bodies/23 colliders remain; actions34, coupled ball profiles10.
User approved the stock neck motor settings for added wrist axes: velocity
gain10 and50Nm torque cap. Both wrists were included in the26-clip+5% audit;
only their limits needed further expansion. Retargets regenerated from original
recordings; nonwrist/root channels unchanged. See the current wrist section of
`Docs/MimicKitUEFNBodyMatching.md`. Fixed-wrist/28-action text below is historical.

**Current limit update (October15):** user authorized expanding the original PHAT
to contain all26 accepted retargeted gait clips plus5% angular room. Eight retained
profiles changed; ankle twist is now limited rather than locked (zero locked-ball
rows). Current source is `Saved/MimicKitUEFN/source-rig.json`; the historical
Robotics export below is preserved but no longer matches the saved PHAT hash.
See `Docs/MimicKitUEFNBodyMatching.md` for exact values, backups and verification.
`fit_motion_limits.py` prepares a read-only plan; `apply_motion_limits_unreal.py`
applies it with backup/change checks; `verify_motion_limits.py` independently
checks unchanged geometry/motions and the exact Jolt limit classifications.
Earlier original-limit/unchanged-Unreal statements below describe the baseline.

Separate model and interactive comparison, built October 15, 2026. The original
MimicKit humanoid, Unreal assets and active training are unchanged.

Open `http://127.0.0.1:8842/` while the local server is running. Cyan is the source
PHAT; orange is the independently loaded generated model. Toggle either layer,
separate them, orbit/pan/zoom, inspect one body, or move a retained joint within
its PHAT bounds. The original humanoid is a third optional layer. Joint sliders
are kinematic previews, not a simulation or a training rollout.

## Model

- `humanoid_uefn.xml`: MimicKit-compatible names/hierarchy, 15 bodies and 28
  action dimensions. Original motors/gains/torque budgets retained. Each of the
  23 PHAT colliders occurs exactly once as an existing body's shape.
- `limits.json`: source hashes, explicit ownership, reference constraint frames,
  true twist/swing profiles, hinge offsets and geometry validation data.
- `humanoid_uefn_physics.xml`: direct MuJoCo ball-joint counterpart for independent
  tests. This mirrors Newton's existing three-hinge-to-ball import convention.
- `runtime.py`: required coupled PHAT limit adapter. Stock Newton converts the
  triples to unrestricted ball joints; **loading the XML alone is insufficient**.
  In a new model's engine, call `install_limits(solver.mj_model, solver.mjw_model)`
  immediately after solver construction and before simulation/CUDA graph capture.
  Four elbow/knee hinges use native limits; eight balls use the exact PHAT
  twist/elliptical-swing equations, including two locked ankle-twist rows.

The adapter reuses the earlier independently tested coordinate/Jacobian/row
implementation in `../PhysicalRecoveryLab/phat_constraints.py`. Reference offsets
account for the PHAT rest pose being offset from a constraint's centre. A pinned,
in-process hook inserts rows before friction/contact categories; no installed
library files are edited and unregistered models retain upstream behavior.
Supported versions are MuJoCo Warp 3.5.0.2 (current Newton) and 3.6.0 (old fixture).
Unknown versions or ambiguous joint mappings fail instead of silently dropping
limits. This is not full Jolt dynamics parity.

## Compound ownership

| Existing body | PHAT colliders | Retained joint profile |
|---|---|---|
| pelvis | pelvis, spine_01, spine_02 | floating root |
| torso | spine_03, spine_04, spine_05, both clavicles | spine_03 |
| head | neck_01, neck_02, head | neck_01 |
| upper arms | corresponding upperarm | corresponding shoulder |
| lower arms | corresponding lowerarm | corresponding elbow |
| hands | corresponding hand | existing fixed wrist |
| thighs | corresponding thigh | corresponding hip |
| shins | corresponding calf | corresponding knee |
| feet | corresponding foot | corresponding ankle |

Torso and head anchors follow the existing model's abdomen/base-of-neck joint
roles. No summed spine/neck limit was invented. Omitted joints are fixed within
their owners; their independent motion and limits cannot exist without adding
joints. Whole source colliders are kept, not stretched to fill an invented shape.

Mass/COM/effective Jolt inertia are aggregated with the parallel-axis theorem:
total 78.2545296 kg, no duplicated mass. Body-pair collision exclusions are mapped
through the grouping and therefore become coarser; a compound body cannot retain
independent dynamics/self-collision between its own members. Friction/controller
settings otherwise remain those of the original training XML. Angular-stop
regularization uses the former PHAT adapter profile instead of vanilla's zero
boundary stiffness (`solimplimit=.9 .95 .001 .5 2`, `solreflimit=.02 1`).

Coordinates use metres and a proper +90-degree Z rotation: UE forward -Y becomes
MimicKit +X. No reflection, scale fitting, floor snapping or pose fitting is used.
The source export's mesh and PHAT file hashes match the current saved assets.

## Validation / reproduce

From the project root with the existing `Saved/Robotics/env/Scripts/python.exe`:

```powershell
& Saved/Robotics/env/Scripts/python.exe Labs/MimicKitUEFN/build.py
& Saved/Robotics/env/Scripts/python.exe Labs/MimicKitUEFN/test_model.py
```

`test_newton.py` checks the exact current Newton 1.0.0 / MuJoCo 3.5.0 /
MuJoCo Warp 3.5.0.2 environment on CPU. No second GPU job is needed.
Receipts live under `Saved/MimicKitUEFN/`. Checks cover collider transforms/sizes,
mass, unchanged names/action dimensions, 30 nonzero FK poses, 3,600 cases against
the actual project Jolt DLL, and a two-second constraint-only CPU test.

The first full-rig limit test exposed the vanilla asset's soft boundary setting;
the final new asset uses the original PHAT adapter's regularization as above.
The resulting swing boundary has small iterative-solver penetration (reported
numerically), not a promise of bitwise Jolt impulse response. No trained recovery,
GPU throughput or checkpoint-transfer claim is made by these asset tests.

Run the viewer locally with Python's static server, bound only to localhost:

```powershell
python -m http.server 8842 --bind 127.0.0.1 --directory Labs/MimicKitUEFN
```

Three.js 0.160.1 and its OrbitControls are vendored for offline viewing. No
telemetry, remote data requests or per-frame network traffic.
