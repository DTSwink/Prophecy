# Runtime physical materials on PhysicalMesh

**CURRENT STATUS: restored at the user's request (2026-09-19).** The user
identified the reported idle sliding as their own setup, and requested the runtime
fix back after comparison. It is not a confirmed regression in this material path.
Editor material assets and the Below damping node remain unchanged.

The standard **Set Physical Material Override** node on an agent's PhysicalMesh
now updates its live Jolt PHAT bodies as well as Unreal's receiver material.
Existing Blueprint calls work unchanged through the virtual override on
`UProphecyPhysicsSkeletalMeshComponent`. Editor and Chaos paths retain UE behavior.

The call copies friction, restitution and their effective combine modes into the
registered bodies. Project combine settings apply unless the material overrides
them. Existing native material updates invalidate changed contact caches and wake
touching sleepers; no bodies/joints are rebuilt and poses/velocities are retained.
There is no new tick callback, polling, or work between setter calls. Calling again
with the same asset refreshes changed coefficients; merely editing an asset's
fields is not polled.

Passing None re-resolves each body's normal UE material fallback, including when
the previous component override was already present at rig creation. Recreating
the rig while a component override is set captures that current override normally.
Only this PhysicalMesh's registered PHAT bodies are updated, not a separate sword
component. Partial rigs update their registered bodies.

The explicit per-bone `Set Jolt Bodies Physical Material Override` API remains
separate: its reset restores values captured at rig admission. The standard
whole-component setter replaces current per-bone Jolt material overrides, matching
its whole-mesh scope.

Regression coverage lives in `Prophecy.Jolt.Character.RuntimeBoneMaterials`:
standard Blueprint ProcessEvent dispatch, UE receiver consistency, every Jolt
body's coefficients/combine modes, repeated asset calls, rig recreation, and
clearing an override captured at admission. This checks backend state, not current
scene sliding/bouncing quality.
