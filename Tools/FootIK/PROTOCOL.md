# Native Foot IK boundary

`Content/FootIKLab/Runtime.js` is generated from the canonical lab sources by
`node Tools/FootIK/package-runtime.mjs`. It runs inside native in-process V8; Node and
esbuild are build tools only. The receipt lists every source hash and host seam.
The source transformations expose host factories, substitute live inputs,
bound retained history, and replace asynchronous policy orchestration with a
synchronous native callback. They do not replace constraint/pose arithmetic.

The bundle supplies matching V8 13.6 sin/cos through a tiny licensed fdlibm
WebAssembly module. Other operations use the verified V8 intrinsics. The earlier
isolated `ProphecyFootIKMath` module remains a diagnostic implementation for the
JSRT fallback tests. Source hashes and the redistributed V8/Sun notices are in
the receipt/package. Gameplay and Jolt compiler flags are unchanged.

`FProphecyFootIKRuntime` owns one optional VM. `Enable` receives an init command
and NN callback; `Step` accepts a tick command. `Disable` destroys the heap and
all solver history. The public owner must unregister its work/tick participation
and restore ordinary manager ownership. No disabled timer or worker is needed.

## Default exact planned course

`FProphecyFootIKPlanner` is the default integration path for reproducing the
accepted lab motion. `Prepare` receives a complete prepare command plus a
worker-only source initializer and NN callback. `FSource` produces the actual
NN course after model assets have been retained on the game thread. Warmup and
all initialization, IK, dynamics and inference run on one private serial worker
lane. The game thread only calls nonblocking `Poll`, reads `Frame(index120Hz)`,
and publishes the resulting pose/root.

`Prepare(InitJson, Source, NN, Horizon, Error)` accepts source-initializer and
NN callbacks; its shorter overload accepts an already supplied source.
`Extend(Horizon, Error)` preserves the existing solver and policy state.
`Cancel()` interrupts the VM, abandons the obsolete future, and drops cached
frames without waiting for the worker. The worker retains its own state until
the current bounded native inference/script finishes. The owner must destroy
its planner on disable; no polling remains after that.
`Counts()` retains atomic source/NN/solver/worker totals after cancellation for
diagnostics. `Prophecy.FootIK.PlannerLifecycle` checks asynchronous cancellation,
zero recurring disabled work, bounded frame export and exact prefix extension.

Plain stair/down/uneven/flat courses run the exact accepted `K.prepare` planner,
using a full real NN source. That planner needs whole future stance spans and
trajectory smoothing, so it computes the complete supplied source once;
extensions merely expose more already solved frames. Incline/edited-surface
courses use the exact causal surface coupling and can extend actual solver/NN
generation only as far as the requested horizon. Neither path runs on the game
thread or replaces the original planner with a visually different solver.

The course is generated from current settings and native NN recurrence. It is
not prerecorded controller playback. Changing its terrain/course settings
requires a new plan; do not describe this mode as an arbitrary player-input
controller. The separate causal live input below is experimental until its
visual behavior is validated against the intended game use.

All vectors use **metres, Y up**, and all rotations use `[x,y,z,w]` quaternions.
Poses contain26bones, including virtual `root`, in the lab rig order. The owner
must convert Unreal centimetres/axes once at the boundary; do not convert NN
joint vectors separately from their root frame.

## Experimental live game inputs

### Canonical root-only host

A dedicated small VM can run root physics without NN inference or limb solving:

```js
{ op: 'rootInit', settings, height: 0.9, speed: 2, gravity: 9.81,
  time: 0,
  root: { position, velocity, normal, bodyRotation, surface },
  previousRoot, surfaces, rootSurfaces,
  travelVelocity: [0, 0, 2] }
{ op: 'rootForecast', supports, ticks: 32,
  futureDrive: [{time, velocity}] }
{ op: 'rootStep', ticks: 2, supports, travelVelocity }
{ op: 'rootStatus' }
{ op: 'rootClose' }
```

All positions and velocities are world/course metres, Y up. `height` is the
fixed rig calibration, never the current crouched pelvis height. `root.position`
is the surface ground reference; the canonical capsule mass is calculated using
the supplied normal and body rotation. An optional exact `snapshot` can restore
all root dynamics, slide state, collision IDs and contact history.

Each support is `{surface: stableId, point, normal?}` from an actually accepted
foot contact. An unknown material ID is an error. Separate `rootSurfaces` let
the capsule follow a navigation ramp while feet see finite stair treads; both
sets retain their IDs. Geometry uses the plane schema documented below. The
controller's horizontal velocity is rotated from world up onto the actual
surface, preserving its magnitude. A forward command facing a vertical wall
therefore becomes uphill thrust, not zero projection. Root yaw stays independent.

`rootStep` commits exactly the requested 120 Hz substeps (normally 2 or 4), then
returns `{root,receipts,frames,snapshot,metrics,events,tick,time}`. `root.position`
is the next current carrier; each receipt describes its preceding physics step.
`frames` includes the starting context followed by every committed context, so
the native owner can display exact intermediate carrier poses.
`rootForecast` returns `{roots,virtualRoots,rootYawDegrees,frames,snapshot}`:
roots are previous/current plus
eight future 30 Hz positions for 32 substeps. Its full 120 Hz `frames` retain
velocity, normal, body rotation, mass, surface and slide state. It copies dynamics
and never commits them. A cached `begin` context prevents repeated forecasts
from re-entering slide or advancing alignment. Geometry/settings changes rebuild
that context from its saved pre-begin state.

`virtualRoot` and optional `previousVirtualRoot` seed the policy's flat root
frame. Every committed substep applies canonical `C.transport` between surface
contexts; forecasts copy this recurrence without advancing the actual virtual
root. `rootYawDegrees` is an independent previous/current plus eight future
heading window in degrees. Each returned root frame contains `virtualRoot`
and `yaw`. `verify-root-virtual.cjs` checks 405 actual substeps and 21 captured
NN windows with zero numeric differences and no forecast mutation.

`canonicalTerrain:true` is a parity-only initializer for replaying exact recorded
lab root physics. `verify-root-runtime.cjs` replays 405 recorded substeps and 22
forecasts from an independent unbundled generator; root positions, forces and
forecasts match exactly and no NN callback is permitted.

### Surface pose with an external root owner

`liveSurfaceInit` accepts `{source,parents,settings,height,speed,currentTick,
sourceStartTick,surfaces,rootSurfaces,rootFrames}`. It retains the canonical
surface foot solver, sliding posture, friction, arm motion and joint limits.
It does not create a root integrator or invoke the NN.

`liveSurfaceStep` accepts `{currentTick,ticks,rootFrames,source?,sourceStartTick?,
poses?,commands?,rootReceipt?}`. Supply complete 120 Hz poses in `poses`, or a
30 Hz source covering the requested ticks. `commands` additionally accepts
`{pose,stance,untilPlant}` when the owner already has exact contact intent.
Otherwise intent is calculated using the canonical velocity rule and the
actual previous sample. Optional initialization `previousPose` and
`previousPoseDt` describe an existing raw source history sample. A null
`untilPlant` value on the JSON wire means infinity.

Raw poses must remain in the NN's virtual ground frame, before surface/body
alignment. The canonical surface solver applies the root context's ground and
body rotations once. Feeding it already wall-aligned world poses would rotate
them twice. Preserve raw NN axes when available; replacing them with axes
reconstructed from quaternions changes the floating-point constraint input.

Root frames come from `rootForecast.frames`, beginning at the current tick.
The slide entry can request `ceil(slideLegBlend * 120)` forecast samples, up to
360; missing future contexts are an error. Root headings can be supplied in
`futureRoots` independently of movement. Each root context includes its exact
normal, body/gait rotation, position, mass, velocity, surface IDs and slide state.
No physics is integrated while advancing the pose solver.

Step returns `{tick,frame,frames,supports,externalRoot:true}`. Supports are the
actual solved foot contacts to return to the root owner. `rootReceipt` or timed
`rootReceipts:[{time,receipt}]` may attach existing physical diagnostics. When
omitted, the frame explicitly identifies external ownership rather than
inventing forces. `liveSurfaceStatus` reports retained state;
`liveSurfaceClose` releases it. Calls must be consecutive: speculative tails
cannot be rewound without a new solver/actual-state handoff.

`verify-external-surface.cjs` compares all 405 accepted-current frames, including
pose, slide, contact and root receipt fields, plus 50 support feedback samples.
It is exactly equal with zero NN/root integration calls. This establishes the
decomposition boundary only. A root step depends on the contacts solved during
that same substep. Advancing root physics first and returning asynchronous foot
contacts later changes the recurrence. Faithful surface gameplay therefore uses
the combined causal owner below, rather than this decomposition as two delayed
independent workers.

### Stair publication join

`liveJoin {candidate,current,previous?,parents,names,contacts?}` is a small,
independent command for the game thread. `current` is the actual uncorrected NN
pose at publication. It retains the real root and upper NN, transfers the
candidate's terrain corrections, and solves the two legs with canonical leg IK.
It never feeds its corrected pose into ordinary NN history.

An unchanged raw pose returns the candidate exactly. If only the upper NN
differs, both accepted legs remain bit-identical. Changed lower inputs use the
candidate's transported knee plane. Swing ankle correction is transferred in
calf space; active material contact is reconstructed about its real local
heel/toe point. An unreachable pin is reported as reach failure, not a false
contact. The native owner may override `contacts` only when surface, stance ID
and pivot key still agree; a canonical pivot transfer or replant is deliberate.
Flat zero-influence frames remain the actual NN pose exactly. Slide frames use
the combined causal surface owner instead.

`verify-live-join.cjs` checks 601 identity frames, 601 upper-only changes and
209 active pins with a changed actual hip position; contact and bone-length
errors stay below 1.1e-15 m. This is a publication invariant test, not a visual
approval of arbitrary abrupt player commands.

The accepted stair planner now has a separate prospective host API. It consumes
real current/history NN poses and a bounded future source; it does not run the
alternative causal `createFeet` algorithm documented further below.

```js
{
  op: 'liveEvaluate', epoch: 'agent-generation',
  currentTick: 104, sourceStartTick: 16, // absolute 120 Hz ticks; source starts at 30 Hz boundary
  origin: [0, 0, 0],                  // fixed course coordinate origin
  source, parents, settings,           // K.decode source, uncorrected policy poses
  terrain: {
    tiles: [{ id, x0, x1, z0, z1, y }], // stable IDs, horizontal finite treads
    start, end,
    rootProfile: [{ z, y }]            // actual root navigation elevation
  },
  initialHistory: {                    // first activation: already displayed actual poses
    previousTick: 0, currentTick: 4,
    previous: { points, q }, current: { points, q }
  },
  acceptedFrames: [{ tick, frame }]    // exact displayed pose AND material contact receipts
}
```

Raw source root Y is zero. The navigation profile adds absolute course Y once;
actual initial/history poses already contain their real elevation. The host must
keep the course frame fixed and supply `origin:[0,0,0]` if its own course transform
already owns that origin. Root position and thrust remain owned by the mover.

`liveFrames {start,count}` returns the ready prospective tail. `liveCommit
{acceptedFrames}` imports what was actually displayed. Every intervening 120 Hz
sample is required; the host interpolates between its real 60 Hz samples. An
asynchronously completed candidate is never evidence of which old-plan frames
the player saw. Changed actual history triggers a boundary solve. Actual samples
beyond the previous forecast are queued and require a newly supplied source that
covers them. Gaps are errors, not fabricated history.

`liveFrameTexts {start,count}` uses the same bounds, order and short-tail behavior
as `liveFrames`, but returns an array of JSON strings. Parsing each string gives
exactly the existing frame object on the wire, including JSON's normalization
of signed zero. This lets the native owner retain immutable frame payloads
without rebuilding hundreds of numeric JSON objects per frame. The source and
packaged transport proofs compare 284 complete frames across 20 range cases.

The solver keeps approximately 0.75 s of recent history, crops on 30 Hz boundaries,
and replans a prospective tail (normally 1.2 s). The game clock is unbounded; the
8 s input limit is the maximum retained window, not a total course duration. A
20 s test covered 2,401 ticks and 19 rebases with at most 213 accepted frames.
Accepted poses, contacts and contact velocities form constraints for new future
plans. No UI or canonical two-argument `K.prepare` behavior changes.

This prospective API is still being integrated and is **not certified as an
arbitrary player controller**. The existing K algorithm is oriented along the
course +Z axis and assumes horizontal rectangular treads. General turning path
frames, rotated finite terrain, wall/root ownership, and changed-input realtime
budgets still require direct game tests. A flat fixed-future check is not proof
of those regimes. Useful checks are `verify-live-stair-planner.cjs`,
`verify-live-stair-rebase.cjs`, and `verify-live-applied-history.cjs`.

### Combined causal surface owner

This is the accepted inclined/slide solver, with root, limb contacts and NN
recurrence in one owner. It is not a substitute for the accepted stair planner.
The native manager must suspend its ordinary root/NN advancement only while
this surface owner is active, and publish the owner's root and pose together.

The API is:

```js
{
  op: 'init',
  names, parents,
  seeds: [previousPose, currentPose], // 30Hz pair; points + q or axes
  height: 0.9,                     // rig calibration, not current crouch
  speed: 2,                       // commanded gait speed, m/s
  settings: { /* existing Foot IK option names */ },
  policy: true,                   // full same-tick root/feet/NN recurrence
  root: { position, velocity, normal, yaw },
  surfaces,
  rootSurfaces                   // optional navigation planes, stairs use ramp
}
```

Alternatively `source` (existing lab NN source object) and `parents` initialize
the exact same rig/calibration. For actual gameplay, also supply
`initialPair:{previous,current}` when using `source`; `seeds` already supplies
that pair in the rig-only form. These are the actual 30 Hz NN poses in virtual
ground coordinates, including original axes. The first displayed pose is the
current sample; the first policy request at local tick 0 receives the supplied
history pair unchanged, with no warmup or invented pin flags. A new owner epoch
starts at local tick 0. Live state is incremental and has no recording
duration. The default `policy:true` runs the canonical coupling, requesting the
native NN every4substeps. Slide suspends inference; exit resumes its normal
current/history contract. `policy:false` never calls the native NN.

```js
{
  op: 'tick', ticks: 2,             // 120Hz ticks; 2 per60Hz authored game tick
  currentTick,                     // optional sequence check
  root: { position, velocity, normal, yaw }, // only with teleport:true
  futureRoots: [                   // previous/current +8future roots at30Hz
    { position, yaw }, /* ... */
  ],
  travelVelocity,                  // desired horizontal ground-frame drive, m/s
  pose, previousPose,              // required when policy:false; 30Hz history
  stance, untilPlant,              // optional host intent; otherwise inferred
  surfaces, rootSurfaces,          // optional geometry update
  surfaceRevision,                // unchanged revision skips geometry rebuild
  settings                        // optional tuning update, preserves history
}
```

An omitted `root` continues the root's gravity/thrust/inertia state. A supplied
root requires `teleport:true`; normal controller updates cannot silently replace
the canonical root. The desired horizontal drive is rotated from up onto the
surface, preserving speed. The
forecast is a copied root state and cannot advance the real simulation.
Yaw is degrees; heading is independent of travel. Each future-root row may use
`heading:[x,y,z]` instead of yaw. Explicit `time` on the first row changes its
default timestamp of current tick minus1/30second.

Each surface is either a lab platform record `{id,position,rotation,size}` or
`{id,origin,normal,tangent,bounds:[x0,x1,z0,z1],thickness}`. IDs must remain stable
for material contacts. `rootSurfaces` supplies separate navigation geometry,
allowing roots to follow ramp planes while feet query individual treads.

Tick returns `{enabled,tick,time,nextTime,frame,frames,outputs,previousFrame,
nextRoot,supports,policySteps}`. Each output contains its local tick, root context
(including virtual root and heading), raw source, corrected frame, and solved
supports. All requested 120 Hz frames are returned in order.
The frame is the canonical solver frame with full corrected/raw poses, feet,
surface forces/velocity and slide receipts. `nextRoot` is the integrated next
carrier. The public owner publishes every second substep and supplies physical
tracking the corrected target, so existing feedback compares like with like.

The NN callback `__footikNN(requestJson)` must return the surface stream response
`{pose:{points,q or axes}, ...}` for the exact request. Requests include policy
`run` for both walk/run, previous/current plus8future root positions, upcoming
root yaw, initial/reset seed pairs, and2frames. Ordinary calls preserve the
native stream. This is **not** Bodyflip's fixed-heading model adapter.

`FProphecyFootIKSurfaceLive::InitializeCausal` retains this session on one
serialized, transient worker with a 1 MB stack. Its native policy callback and
cancellation callback are supplied by the game owner. `Submit` requires every
120 Hz interval exactly once and enforces a bounded outstanding queue; a full
queue returns an explicit error without dropping input. `TakeCompleted` is
nonblocking and ordered. `Cancel` interrupts script/native inference, abandons
queued results, and leaves no recurring game-thread work. Diagnostic counters
report queue depth and measured solve time. Native build/lifecycle validation
is still required; these are not realtime certification claims.

`verify-causal-live.cjs` compares all 405 recorded frames plus same-tick root and
support outputs exactly, and separately verifies actual-history takeover at
tick 0. Before the native brace-fit acceleration, this case took 9.844 seconds
of Node process CPU for 3.375 seconds of motion, about 24.3 ms per 120 Hz tick.
The current implementation therefore cannot yet claim the 8.33 ms tick budget.

`ProphecyFootIKSurfaceOwner` is the game-facing synchronous baseline for this
combined recurrence. It receives actual previous/current 30 Hz game poses,
finite collider geometry and the selected lower/upper runtime contracts. It
verifies Run181751 and Upper82500 hashes, seeds the actual pair, and calls native
`Prepare/Generate` directly; it never calls course initialization or warmup.
The native graph currently has fixed unarmed/neutral gaze inputs, so incompatible
upper commands are rejected explicitly. Root capsule height uses the selected
game rig's fixed pelvis rest calibration, not the current crouched pose.

The owner starts at frame 0 and advances exactly two 120 Hz steps for each
authored 60 Hz game tick. `Root/History/Apply` expose the same solved root, actual
30 Hz history and complete pose; presentation publishes at alpha 1 to avoid a
second interpolation delay. Manager-selected future heading rows and desired
horizontal velocity remain live inputs. Geometry updates preserve stable IDs.
No fixed course duration or background replay clock exists. Disable destroys
the VM, model sessions and world cleanup registration. The synchronous baseline
establishes causal integration only; it must not be described as performant
until the native kernel and actual-agent timing tests pass.

`policyHandoff` is read-only: it returns the raw previous/current30Hz recurrent
pair, actual root pair, velocity and headings without running inference or
advancing time. While sliding, it uses the canonical paused-policy resume rule
to rotate and rebase the saved pair. The game encodes this clean pair when
ordinary locomotion resumes; the separate visible slide pair remains the
physical target history. `verify-causal-live.cjs` checks13handoffs as well as
the405coupled frames. Active configuration changes cancel the old epoch and
seed a new one from the actual game pair; old worker results cannot publish.

An explicitly empty finite surface array means empty space. It does not restore
the lab's default floor. Removing the current material releases slide/support
ownership immediately while retaining root inertia and gravity. Forecast
copies retain only a removed surface's orientation reference, never its
collision. `verify-live-void.cjs` checks no remaining pins, finite poses and
exact−9.81m/s² acceleration after removal.

## General live stair terrain

The optional prospective K snapshot accepts `rootRows:[{time,position}]` plus
`rootStartTick` (absolute120Hz tick for time0). Rows remain in traversal order.
Repeated horizontal locations at different heights, lateral travel and reversal
therefore do not alias a single-valued Z profile. Raw NN sources retain flat
rootY0; the timed navigation height is added once. The fixed world course origin
is0 unless explicitly supplied.

Finite horizontal treads accept `{id,point,u,v,bounds:[u0,u1,v0,v1],shaped}`.
The two horizontal unit axes may have any yaw. Whole-shoe floor clipping and
landing use the exact oriented rectangle, not an enclosing AABB. Material
contact coordinates remain local to that rectangle. `shaped` is explicit,
because game collider IDs do not have the lab's `step`/`tile` prefixes.

Only this optional host path uses travel-relative swing recovery, roll margins
and a course-aligned horizontal smoothing basis. Existing two-argument K calls
retain the accepted behavior. Four original walk/run ascent/descent cases still
match all2404frames exactly. New301-frame courses rotated0°,90°,180°,37° retain
145pins each; inverse-rotated pose differences are below2.1e−8m, root errors
below9e−16m and penetration below3.6e−7m. A uniform0.5m floor with all treads
marked shaped retains301frames exactly equal to raw NN plus navigation height.
The constant-height fast path is separately deep-compared against full K for
601complete frames. A paired Node run measured406→219ms CPU and231→110ms wall;
that local result does not certify the live game's repeated-replan budget.
These are geometry/coordinate tests,
not evidence of a natural new NN gait for arbitrary changed commands.

The native capture/manager must provide timed rows and separate root-navigation
versus foot-tread collision selection before this interface is a completed
arbitrary-route gameplay integration. The old `rootProfile` snapshot remains
supported solely for existing diagnostics and compatibility.

The prepared native capture patch supports component tags without changing
Blueprint wiring: `FootIKRoot` marks navigation-only collision and `FootIKFeet`
marks contact-only collision. A root-only ramp is excluded before tread shape
validation. Foot-only query collision can ignore the agent's capsule channel
(`ProphecyAgentCapsule`, currently GameTraceChannel8) while remaining visible
to this adapter. Ignoring Pawn alone does not prevent root collision in this
project. Untagged primitives blocking the actual capsule channel participate
in both. Tagging
both explicitly includes a component in both queries. Root and foot components
still need query-enabled collision and WorldStatic/WorldDynamic object types.
These tags select existing collision; they do not create geometry or make a
complex triangle mesh equivalent to boxes. Horizontal K capture accepts actual
box tops and convex hulls proven to be boxes. Other shapes fail explicitly.
The game mover remains responsible for the navigation height sampled by K.
The accepted planner still classifies ascent/descent across one prediction
window; a future window containing both directions needs a separate natural
motion check, even though timed roots no longer alias its path.
This patch is staged pending the normal native build and actual-world test.

## Delayed live publication and bounded actual history

`liveEvaluate.acceptedFrames` is the exact contiguous sequence of120Hz frames
the host displayed, including ordinary-NN fallback while the worker was busy.
Each frame includes its corrected `pose`, uncorrected actual `raw`, two `feet`
contact receipts, and `rootHeading`. The latter is a normalized **direction
vector `[x,y,z]` in the fixed Y-up course frame**, not an angle or root quaternion.
At ticks divisible by4, `raw` and heading must be the actual30Hz sample; an
interpolated prediction is not a replacement for that history.

Once a completed worker request acknowledges a tick, subsequent requests need
only the last three acknowledged ticks and every newer displayed tick. The
three-tick overlap preserves replacement of the last published 60 Hz target
and its intervening sample; older acknowledged frames are immutable. Local
publication history remains available for contact joins. The full contiguous
range is still required for an explicit capped-history checkpoint. Source and
packaged proofs compare 990 complete frames with full-history delivery,
including six same-tick receipt replacements and real stair material pins.

Native receipt retention is bounded to1,201frames (10seconds). If that cap
removes an unacknowledged prefix, the next `liveEvaluate` must explicitly supply
`acceptedHistoryCheckpoint:{startTick,endTick}` alongside the retained frames.
Those bounds must exactly match the first/last supplied tick. The planner checks
every120Hz tick for continuity and requires complete final0.75second history,
including exact raw30Hz poses/headings. Ordinary `liveCommit`/`accept` still
reject a missing frame; the checkpoint is an explicit replacement of obsolete
forecast history, not permission to invent an unobserved prefix.

When a delayed future source no longer overlaps the old predicted tail, the
planner uses the same reconstruction automatically from its complete actual
receipts. It retains0.75seconds of actual history plus the supplied prospective
tail. It subtracts each raw root's navigation height once before encoding the
policy source, restores that height through timed `rootRows`, and unwraps
`atan2(heading.x,heading.z)` into `rootYawDegrees`. Actual poses, material pin
points/IDs and contact states are imported through the existing boundary API
before planning the future. Invalid raw/headings/checkpoint bounds fail without
accepting the new checkpoint. A new epoch starting at a nonzero tick needs only
its actual initial pair; it does not claim ownership of earlier frames.

`node Tools/FootIK/verify-live-delayed-history.cjs --packaged` passes through the
generated synchronous runtime:301 delayed actual frames, a1,201frame capped
checkpoint, a real canonical stair pin, strict gap/raw/heading rejection and a
nonzero initial epoch. After recovery, four fresh stop/reverse/turn/stop commands
advance192consecutive120Hz frames with maximum root error5.03e-15m, at most141
retained accepted frames and a1.967second source window. This is an input/history
and publication proof with supplied poses, **not** a neural motion quality or
Unreal frame-budget claim. Actual-world native consumption remains a separate
test. Reports are `Saved/Diagnostics/FootIKPort20261030/live-delayed-history*.json`.

## Exact offline reference parity

`prepare` accepts `{source,parents,settings,policySteps?,coupled?,endTime?}`.
With `policySteps`, it replays the canonical surface coupling against captured
NN replies. Without it, stairs/down/flat/uneven run the exact offline stair
planner; incline/custom planes use the exact surface solver. `extend` advances
only the requested tail. `frames` returns an array using `start/count`;
`windows` returns the root-input window array; `status` reports counters.
`close`/`reset` releases the session.
Exported planned frames also contain `rootHeading`, from the canonical
controller facing window. The synthetic root quaternion is not a heading.

The offline staircase planner detects complete future stance spans and performs
whole-trajectory clearance/smoothing. The live stair owner uses that same K
planner on bounded predicted history/future with accepted boundary constraints.
Inclines and slides use the separately accepted causal surface algorithm.
Substituting its `createFeet` for stair planning is not an accepted shortcut.
Live state retains8frames,2policy replies,10windows and9pose/root contexts.

## Current verification boundaries

The optional `__footikTerrainFloor(input, output)` host call executes one complete
finite horizontal terrain-floor query. Both arguments are Float64Array views;
the output view has exactly one value. Input begins with tile count, corner
count and ankle XYZ, followed by each tile's point/u/v/bounds (13 values), then
corner XYZ offsets in groups of eight. It supports at most 256 tiles and 64
corners. Invalid or unsupported inputs return false without changing output,
and the JavaScript caller uses its original query. Missing host support also
keeps the JavaScript path. The terrain prefix belongs to an immutable snapshot;
shoe offsets are copied anew on every query. Both overlap tests, ordered box
face clipping, empty-clip fallback and signed-zero arithmetic remain canonical.
The native dependency guard covers terrain.js, recovery.js and the live query
and packing helpers. This optimization changes neither the planned horizon nor
the acceptance rules for real game history.

The initial native floor receipt checks 3,866 scalar outputs bit-for-bit,
131 offset-view cases and 14,001 invalid calls without partial publication.
Six complete walk/run courses and two seeded contact-history continuations
preserve 1,928 frames and eight checkpoints exactly, with 189,554 confirmed
native calls in the original course/continuation corpus. A strengthened replay
chooses an actually planted boundary for both continuations: its 964 frames and
four checkpoints include 25 contact-frame observations and 113,840 native calls.
The packaged runtime passes both proofs. A same-V8
ABBA comparison of rotated stairs plus its accepted-history continuation
measured mean CPU time 2,266 ms in JavaScript versus 1,273 ms with the native
query. This is a planner benchmark, not a live-game throughput guarantee.
The receipt is `Saved/Diagnostics/FootIKPort20261030/floor-native/proof.json`.

The native floor helper also retains one successful query result per immutable
terrain snapshot. Every ankle and shoe-offset double must match with Object.is,
including signed zero; mutable arrays are re-read and validated before lookup.
There is no approximate key and no solver iteration is skipped. The cache
proof preserves the same 1,928 frames/eight checkpoints and passes 107 mutation,
signed-zero and unsupported-input checks. In the delayed-history profile it
avoids 36,603 of 63,837 native calls. A separately warmed same-V8 ABBA test
measured mean planner CPU 2,070 ms before versus 1,555 ms with the cache (25%
less); laptop load affects absolute times. The receipt is `floor-native/cache-proof.json`
in the same diagnostic directory. Live Unreal throughput still needs its own
measurement.

- The independent unbundled Node oracle and packaged/native V8 runtime match
  exactly for48cases,26,296frames and1,024actual NN requests/windows, including
  six complete browser handoffs and the native brace/entry/leg batches.
- The experimental live causal stairs path is **not** accepted staircase parity:
  `node Tools/FootIK/parity-live-stairs.cjs` recorded43.6cm Walk and67.3cm Run
  bone differences despite matching root trajectories. Default planned mode
  exists specifically to retain the accepted whole-trajectory planner.
- Plain Chakra originally diverged from V8 in constrained slide search and
  root forecasts. The strict reproductions are
  `node Tools/FootIK/parity-jsrt.cjs --corpus=Saved/Diagnostics/FootIKPort20261030/slide-first-divergence --diagnostic`
  and the same command with `wall-first-divergence`. Matching V8 native math
  now removes these forks: the accepted current slide's405frames/21callbacks
  and the217frame/53callback wall forecast match exactly in the standalone
  native probe. The broader native matrix and Unreal integration validation
  are separate; do not interpret the V8 oracle alone as game certification.
- Live slide entry measured roughly517ms and warmed steps8–9ms in plain V8 in
  the arbitrary-wall protocol probe. Planned work runs off the game thread;
  the causal live mode has no claim of meeting realtime frame budgets yet.

### Exact native reach projection

The packaged K planner may call `__footikTerrainReach` through the optional live-terrain `reachable` hook. The browser remains on the canonical JS loop. The input is the existing finite terrain-floor vector followed by hip XYZ and nonnegative reach; output is exactly three doubles. All twelve projection iterations retain the canonical V8 hypot and arithmetic order. Unsupported/nonfinite inputs return failure without publishing partial output, then use the JS fallback. A one-query memo inside the native loop only reuses an identical pure floor request; it does not terminate iterations early.

`verify-terrain-reach.cjs` compares the frozen independent six-course oracle plus two actual-contact continuation checkpoints: 1,928 complete frames, eight checkpoints, 25 retained contact observations, and 1,610 exact edge queries. Warm same-V8 ABBA against the existing one-entry native-floor cache measured 570.3 ms to 507.8 ms CPU (12.3% faster) on the rotated walk continuation. The bounded fixture receipt is `Saved/Diagnostics/FootIKPort20261030/reach-native/proof.json`. Native dependency hashes include footik.js, recovery.js, terrain.js and the live/native wrappers.

### Exact native ankle rotation clearance

The optional `__footikTerrainRotationClearance` typed-buffer call owns a complete canonical free-ankle clearance search. Mode 0 retains the 16 samples and 9 bisections; mode 1 retains the anticipated blend/zero tests and 16 bisections. It performs the same quaternion interpolation, world-space toe addition/subtraction, two-box construction and finite-tread clipping. Contact state, blend weighting, smoothing and final pose ownership remain in canonical K. The browser and unsupported inputs retain the original loop.

The input uses TerrainFloor's tile prefix with cornerCount16, followed by baseFoot3, toeLocal3, side sign, fromFootQ4, fromToeQ4, toFootQ4, toToeQ4, ceiling, amount and mode. Output is one blend amount; invalid inputs do not publish partial output. Aliased and offset typed views are supported. The dependency guard also covers support.js.

`verify-rotation-clearance.cjs` passed 2,402 exact search comparisons, 14 rejection/atomicity cases, 1,928 complete frames, eight complete checkpoints and 25 material-contact observations against independent frozen oracles. Warm same-V8 ABBA against the existing native reach/floor-cache path measured 570.3→500.0 ms CPU (1.14× throughput; 12.3% less CPU), reducing floor callbacks 19,238→11,283 with 530 whole-search calls. Receipt: `Saved/Diagnostics/FootIKPort20261030/rotation-native/proof.json`. Timing is diagnostic CPU evidence, not a claim about sustained Unreal publication throughput.
