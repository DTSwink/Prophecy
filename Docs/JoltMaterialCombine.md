# Unreal material combining in Jolt

The bridge applies the captured body physical material's effective friction and restitution combine modes to Jolt contacts. This covers character rig bodies, standalone bodies and imported static components/ISM/HISM instances. Each material's override wins over its corresponding project default at capture time.

When two effective modes differ, the higher-priority mode wins, exactly as in Chaos: **Maximum > Multiply > Minimum > Average**. Friction and restitution resolve independently. For example, foot restitution 0 with a Minimum override against floor restitution 0.3 with Average produces 0. If the floor instead specifies Maximum, the result is 0.3.

The implementation uses Chaos's numeric `ChooseCombineMode` and `CombineHelper`, with compile-time checks of UE enum values. It stores both modes in four bits of the existing Jolt **body** user-data field at creation. Shape/triangle query provenance is separate and unchanged. Jolt's existing two combine callbacks are replaced; no additional contact listener, tick, scan, material lookup, allocation, lock or body-registry search is added. Workers read only native body numbers. This is a small arithmetic change, not a measured guarantee of literally zero CPU cost. Exceptionally large coefficients are saturated only if the combined result cannot fit Jolt's float representation.

Settings are captured when bodies enter Jolt. Changes made before Play or before re-enabling a character/body apply on creation. The explicit character override nodes below can now change selected bodies at runtime. Automatic propagation from the standard component override node or edits to a shared material asset is still separate work. Existing body-level material scope remains: per-triangle material selection and a separate static-friction coefficient are not implemented. Contact generation, restitution threshold, shape geometry, drive forces, simulation timing and solver iteration counts are unchanged.

## Runtime per-bone overrides

On **Prophecy Agent**, after `Is Jolt Physical Animation Enabled` is true:

- **Set Jolt Bodies Physical Material Override**: `Body Bones` is an array of PHAT body bone names, such as `foot_l`, `foot_r`; `Material` is the physical material to copy. It updates only those native bodies' friction, restitution and effective combine modes. Return Value reports success; Out Error explains a rejected request.
- **Reset Jolt Bodies Physical Material Override**: pass the same array to restore each selected body's own original values captured on Jolt admission. Passing None to the setter also resets. Repeated overrides never overwrite the original reset values.

For frictionless walking feet, make a physical material with **Friction 0**, **Override Friction Combine Mode enabled**, **Friction Combine Mode Minimum**, and the restitution settings you want. Set it on `foot_l`/`foot_r` when walking; reset those feet when ragdolling. A contacting material with a higher-priority combine mode can still win (notably Maximum). The setter copies restitution too, so configure that deliberately.

Names must identify real PHAT bodies; helper bones such as `ball_l` without their own collider are rejected. Empty arrays are rejected rather than interpreted as the whole skeleton. Duplicate names are harmless. One invalid name or invalid material value rejects the entire request. The nodes require healthy active Jolt simulation; they do not start simulation or change backend/mode. Temporary overrides clear on Jolt rebind. After editing a material asset's values at runtime, call the setter again to copy the new values.

Changing a material updates native scalar values, discards the selected bodies' old contact caches and wakes touching bodies. Bodies, joints, transforms, velocities, masses and PHAT assets are retained. No per-frame polling or retained UObject material pointer is introduced. UE query receiver materials/SurfaceType are not changed by these Jolt contact overrides. The per-character reset cache is allocated on admission and freed on teardown.

The original foot/floor defaults have equal coefficients, so correct combining alone does not fix the previously reported grazing behavior. See `JoltFootFloorInvestigation.md` for those measurements.

Validation on 2026-09-11: the normal Editor build passed for both combine policy and runtime overrides. All three focused tests passed: the 32-contact imported combine matrix, runtime sleeping/sliding contacts with atomic rejection, and the real 22-body character's selected-foot override/reset/rebind checks. Blueprint reflection confirms both nodes are loaded. Evidence is in `Saved/Diagnostics/RuntimeBoneMaterials/` (`EditorBuild.log`, `Automation.log`, `result.json`, `reflection.json`). There were zero test errors and one existing transient test-world EndPlay cleanup warning. The earlier combine-only checkpoint passed twelve selected tests, including ISM override/project-default capture and existing body/rig/static ownership checks (`Saved/Diagnostics/MaterialCombine/`). No game assets were modified. No new packaged build or frame-time benchmark was performed.
