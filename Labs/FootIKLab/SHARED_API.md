# Foot IK shared surface solver

Bodyflip consumes this lab's source directly. Keep foot-placement changes in
`surface.js` / `footik.js`, not a second implementation in Bodyflip.

`surface.js` exports API version 1:

- `createFeet({names, parents, terrain, settings, metrics?})` returns
  `{step, metrics, events}`. Call `step` in chronological order at 120 Hz.
- `step({baseline, terrainPose, source, sourceLegs, stance, untilPlant, time,
  frame?, normal, surfaceQ, height, velocity, terrainWeight?, enabled?,
  wallExpired?, steep?, allowPins?})` returns `{pose, feet, supports}`. Poses use world
  metres and `{points, q, axes}`. `untilPlant` is seconds for each foot.
- `terrain.surfaces` contains finite rectangles with `normal`, `bounds`,
  `local`, `world`, `closest` and `project`; `terrain.pick(point)` returns
  `{surface, point, distance}`. A pin releases if its surface ID
  disappears, unless another finite coplanar surface contains its material
  contact; in that case the pin transfers without moving the foot.
- `stableLeg`, `gaitIntent`, `bodyRotation`, and `settings` provide the shared
  rig, contact-intent, body alignment and default settings rules.

Foot IK's own `prepare()` calls this same `createFeet().step()`. Its existing
root simulation, course and UI remain owned here. Bodyflip supplies its editable
platforms and upright capsule trajectory. Its adapter compensates capsule
clearance through the mesh pelvis, applies the shared body alignment, caches
corrections at 120 Hz and relinquishes feet to the jump planner during support,
push and flight. Landing starts from the current pose and resumes the actual NN.
This shares inclined locomotion, not the prototype's wall traction/root physics.

October27 root/NN coupling: Foot IK's app now uses a separate host adapter in
`surface-coupling.js`, with `surface.js:simulate` yielding120Hz root contexts.
This lets its CPU worker run the actual recurrent NN at30Hz with measured root
history and a copied root-physics forecast. The synchronous `prepare` remains
available; all41 existing surface/platform checks pass unchanged. `createFeet`
and API1 acquire no new input or dependency. Bodyflip continues using its own
root/NN host; the new Python/Node coupling files are not shared-bundle dependencies.

October27 wall-frame correction supersedes nearest-feasible-knee selection.
Shared feet retain the source's stabilized signed hinge transformed with its
baseline thigh. They do not infer its sign from the tilted host pelvis or pick
the opposite knee bend to clear a plane. Free departure uses one position filter
without collision momentum. Material heel/toe/yaw pivots and API1 remain.
Four Walk/Run toward/parallel Bodyflip cases pass1368 checks; its root is unchanged.

Foot IK's standalone host places NN pelvis translation/lower articulation in
the ground frame, with Upright applied about the pelvis. It uses terrainWeight0
because that baseline already contains the surface adaptation. Bodyflip keeps
its own baseline/terrainPose adapter and weight contract. No new shared input,
dependency or user setting.

October27: optional `allowPins` defaults totrue. False cancels both material
pins and blocks acquisition; geometric shoe contacts/collision still work.
Foot IK computes this from total simulated root speed and the actual surface
incline. Bodyflip retains its existing pin policy unless its host opts in.
Empty surface lists release pins and return the free baseline pose safely.
Foot IK's standalone platform editor (`platforms.js`) is not a solver dependency.

The Bodyflip server's `/shared-foot-ik.js` bundles the current files on every
request: `recovery.js`, `support.js`, `terrain.js`, `footik.js`, `surface.js`.
They execute in an isolated CommonJS scope; they cannot replace Bodyflip's
similarly named globals. No build, copied bundle, Foot IK server, live-state
sharing or background watcher is involved. Refresh Bodyflip after a source edit.
Its diagnostics expose `flight.footIKSource` (SHA256 of the loaded sources).

Coordinate changes to this API or additions to the dependency list with
`Labs/BodyflipLab/foot-ik.js` and `shared_foot_ik.py`. UI slider changes in the
Foot IK app do not change Bodyflip settings; source/default changes do.

Planted yaw uses `footik.js:createPinYaw` in both solvers. Optional
`settings.footYawLimit` defaults to45 degrees. Retained contacts turn about
heel/toe support, transferring toward a ground-projected sole-centre pivot
near flat. A blocked turn can release the contact. Knee poles remain driven
by the NN leg. This adds no required host input or dependency; API stays1.

The extraction was checked against six full pre-change Walk/Run clips at
45 degrees toward/parallel and 90 degrees parallel: frames, metrics and events
remained byte-identical. Bodyflip integration tests are `verify-foot-ik.mjs`
and `verify-foot-ik-browser.cjs`; the latter intercepts all state writes.

October27 contact continuity: `supports` also includes geometric shoe contact
while the animation pin is acquiring/releasing. A support is not a promise of
a hard tangential lock; `feet[].contact` remains the material-pin receipt. Free
foot filtering smooths corrections relative to the NN ankle carrier, and reach
allowances retain source extension. Host inputs and API version are unchanged.
