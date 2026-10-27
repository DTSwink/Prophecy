# Foot IK shared surface solver

Bodyflip consumes this lab's source directly. Keep foot-placement changes in
`surface.js` / `footik.js`, not a second implementation in Bodyflip.

`surface.js` exports API version 1:

- `createFeet({names, parents, terrain, settings, metrics?})` returns
  `{step, metrics, events}`. Call `step` in chronological order at 120 Hz.
- `step({baseline, terrainPose, source, sourceLegs, stance, untilPlant, time,
  frame?, normal, surfaceQ, height, velocity, terrainWeight?, enabled?,
  wallExpired?, steep?})` returns `{pose, feet, supports}`. Poses use world
  metres and `{points, q, axes}`. `untilPlant` is seconds for each foot.
- `terrain.surfaces` contains finite rectangles with `normal`, `bounds`,
  `local`, `world`, `closest` and `project`; `terrain.pick(point)` returns
  `{surface, point, distance}`. A pin releases immediately if its surface ID
  is absent from the current `terrain.surfaces` list.
- `stableLeg`, `gaitIntent`, `bodyRotation`, and `settings` provide the shared
  rig, contact-intent, body alignment and default settings rules.

Foot IK's own `prepare()` calls this same `createFeet().step()`. Its existing
root simulation, course and UI remain owned here. Bodyflip supplies its editable
platforms and upright capsule trajectory. Its adapter compensates capsule
clearance through the mesh pelvis, applies the shared body alignment, caches
corrections at 120 Hz and relinquishes feet to the jump planner during support,
push and flight. Landing starts from the current pose and resumes the actual NN.
This shares inclined locomotion, not the prototype's wall traction/root physics.

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
