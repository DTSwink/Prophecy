# Foot IK shared surface solver

Bodyflip consumes this lab's source directly. Keep foot-placement changes in
`surface.js` / `footik.js`, not a second implementation in Bodyflip.

October30 F82/F123-131: host slide-arms.js now uses a continuous wall-gradient
search at all correction sizes and retains history before clearance entry.
Entry acceleration limiting fades as contact settles. Shared API unchanged.

October30 F145 yaw-stop hand-velocity easing is also host-only in slide-arms.js;
existing constrained arm solve and wall clearance retain contact. No root or
shared solver/API change.

October30 release smoothing is host-only in slide-arms.js; bounded angular
acceleration during release and minimal wall-safe repair. Shared API unchanged.

October30: torso avoidance/front routing was removed at user request after a
F105.5 velocity hitch. Only the independent continuous shoulder-gradient fix
for the F138 wall-bracing hand kick remains in host slide-arms.js. Torso crossing
is unresolved again. Shared surface.js/API1/dependencies remain unchanged.

October29 slide continuity and inward guards are REVERTED after visible loss of
limb motion and wall bracing. Exact accepted wall-clearance arms and prior host
surface restored; shared createFeet/API1/dependencies unchanged. No broad
self-clearance, extra joint inertia or side-plane restriction is active.
app.js mouse scrubbing still preserves Play/Pause; trim behavior is unchanged.
Release-arm torso crossing remains an unresolved issue, not a completed fix.

October29 self-clearance experiment is reverted at user request: motion visibly
stuck. The two new helper dependencies are removed from the active host/hashes.
Exact previous wall-only arm correction remains; shared API1 is unchanged.

October29 arm wall clearance remains host-only: final slide arm capsules and
hand boxes are constrained against the active wall after pose blending, with
joint limits and temporal continuity. Contact receipts use the actual nearest
hand-box surface. Shared createFeet, dependencies and API1 are unchanged.

October29 signed Fall speed: sanitizer retains negative slideSpeed and the
standalone root host can enter before the apex. Initial ascent is retained
until descending or accelerating above the entry threshold; later ascent
exits normally. Snapshot includes previous vertical velocity and the slide's
descending latch. Shared createFeet and API1 are unchanged.

October29 hand-continuity fix is confined to host-only `slide-arms.js`: full
palm-target residual, accepted elbow-pole continuation, damped reach fitting
and a shared three-joint response/rate bound replace wall-distance-only
acceptance and independent joint caps. Heading speed continuously increases
response to avoid turning-contact lag. Inner arm FK
retains the same constraint arithmetic. No shared input, dependency or API change.

October29 heading-aware Slide remains host-only. The slide host receives the
controller's current/future heading and adapts pelvis orientation, legs and
hand contacts continuously. `slide-arms.js` is loaded only by `createSlidePose`
and included in Foot IK's browser/worker fingerprints. It is not a Bodyflip
dependency. Speed-based downward gaze applies to all slide headings. The
shared `createFeet`, dependency bundle and API1 remain unchanged.

October29 follow-up remains host-only: Slide entry removes outward normal
rebound once. `slideLegBlend` supplies independent leg timing, default twice
`slideBlend`; the corridor predicts the longer duration and body schedule.
`slidePelvisBlend` independently times pelvis position/orientation, with its
schedule included in leg planning. Shared foot placement and API1 are unchanged.

October29 slide entry audit is host-only. `slide-joints.js` supplies the bounded
swing/twist and hinge blend; `slide-entry.js` plans the leg corridor while
preserving pelvis placement. It supersedes the large temporary body-clearance
envelope. Both helpers are included in Foot IK's browser/worker fingerprints.
Soft bracing-arm reach/release and host pelvis-withdrawal easing also stay in
`simulate`/`createSlidePose`. `createFeet`, Bodyflip, shared bundles and API1 are
unchanged. Only the Foot IK slide host loads these helpers.

October29 preparation performance is host-only. The Foot IK worker returns
lossless gzip-JSON pose batches (`frameEncoding`, `frameBatches`) alongside the
existing policy replies. Its viewer appends these directly instead of solving
twice. Bounded generation/session restore and API1 are unchanged. The worker
reuses an evicted same-version Node peer after resetting its entire simulation.
Slide-only chain FK and reused shoe geometry do not change shared `createFeet`.
Generic vector arithmetic retains operation order and typed-array behavior.

October 28 bounded generation is host-only. Foot IK's `simulate()` can yield
completed-frame checkpoints and `surface-coupling.js` retains its generator for
trim extensions. `createFeet().step()` and shared API 1 are unchanged. Short
surface seed metadata provides total duration/reference height; root heading
and travel helpers continue analytically beyond that seed. Bodyflip requires
no protocol change. The Foot IK server uses API 7/generation protocol 1.

October28 slide prototype is Foot IK host-only: `simulate()` owns the
ballistic root during Slide and a separate procedural slide pose. October29
entry is descending-only; upward velocity exits Slide and resumes native NN
inference with rebased current/history seeds. `createFeet().step()` and
Bodyflip behavior are unchanged. Settings are opt-in (`slideEnabled`, `slideSpeed`,
`slideBlend`); defaults do not activate slide in either host. Sliding soles/palm
are visual contacts, not root supports or material pins. The Foot IK coupling
adapter stops policy calls while Slide is active. Its host-only slide-joints.js
helper supplies Jolt-frame arm/ankle limits; it is resolved lazily inside slide
creation and is not part of Bodyflip's shared bundle. Shared dependencies and
API version remain unchanged. Foot IK's browser/worker fingerprints include it.

Slide contact compliance remains host-only: three tangent particles add bounded
friction/recovery to the feet/palm pose, with no reaction force on the ballistic
root. The joint helper now exposes feasibleSwivel for the hip as well as the
shoulder. No change to createFeet, host inputs, shared bundles or settings.
Latest slide tuning slows spring recovery with stiffness-matched damping and
prefers calf-relative relaxed feet with heel/toe/edge wall contact. The shared
locomotion foot-placement solver is unaffected.
Host-only `slideFriction` and `slideRecovery` percentages default to100; the
slide-pose contact particles consume them. They do not change shared feet or
apply forces to either host's root.
Host-only `slideShift` (cm, default20) and `slideShiftSpeed` (m/s, default10)
control both feet; `slideHandShift` / `slideHandShiftSpeed` independently control
the bracing hand. Old shared values initialize both pairs, then persist apart.
They move targets along projected world up, proportional to total root speed
and capped by both the requested shift and each limb's joint reach. Each pair
owns its damped offset and carrier velocity; zero disables only that pair.
Shared `createFeet` and API1 are unchanged; `slideTargetShift` is a pure
host-side diagnostic helper, not a required Bodyflip input.

`surface.js` exports API version 1:

- `createFeet({names, parents, terrain, settings, metrics?})` returns
  `{step, metrics, events, reset}`. Call `step` in chronological order at 120 Hz.
  Optional `reset()` clears contact/transition history for a host mode change;
  Foot IK uses it on Slide entry/exit. Existing callers need no change.
- `step({baseline, terrainPose, source, sourceLegs, stance, untilPlant, time,
  frame?, normal, surfaceQ, height, velocity, terrainWeight?, enabled?,
  wallExpired?, steep?, allowPins?, pelvisShift?})` returns `{pose, feet, supports}`. Poses use world
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

October28 optional pelvisShift is a world-space translation of the hip anchors
and upper body before leg IK. Baseline/terrainPose still supply the original
feet, so held contacts are not translated. Omission preserves the host's old
behavior. Foot IK blends Pelvis min/max cm using actual total root speed and
the configured Min/Max m/s pair, then ramps the result from zero at Minimum
gravity incline to full at90°. Its smoothed surface normal gives the direction.
Old saves inherit the existing amount at both speed endpoints; Bodyflip does
not opt in.
API1 and dependency lists are unchanged.

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
