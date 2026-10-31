# Throws in Bodyflip

The jump marker's Attack menu includes **Big throw** (Imperial Spear) and
**Small throw** (Bomb). Charge % and Throw speed append beneath the existing
marker controls; charge is enabled for Small throw. The upper body starts at
spine_01. Throw Lab's original prefix, fractional release, partial-charge arc,
grip edits, weapon scale, recovery and axial twist are retained.

`export-throws.mjs` imports the approved `a193d263` evaluator/profile through
`Tools/Throws/lab-reference.mjs`. It writes `throw-source.js` and
`data/throws.json`; it does not change either lab's state. The source evaluator
is isolated from Bodyflip's globals and creates no runtime physics world.

`throw-attack.js` maps bones by name, checks parent relationships and exposes
the same attack-track contract as the other timeline attacks. Release is
`start + model.releaseFrame / 60`, including partial-charge fractional frames.
`launchAt(pose, carrierVelocity, carrierOmega)` returns the exact object frame,
linear velocity and angular velocity. The two transport functions measure the
actual attached object's COM/orientation derivatives, subtract the mapped
authored derivatives, then add only the remaining body motion to the approved
throw. This includes root drift, bodyflip and aiming motion without counting
the original arm movement twice. Positions use metres/Y-up, linear velocity
uses m/s, and angular velocity uses rad/s.

The aim solver evaluates the complete release velocity from the projectile COM
toward the fixed target. The geometry origin is retained separately for spawning.
Its neighboring-pose callback receives time as well as pose, so short partial
throws account for the remaining aim acceleration. Once released, the object
does not home. A weak throw cannot necessarily overcome an incoming root
velocity in the opposite direction; no charge or speed is secretly increased.
When the first aim estimate stalls, a second rigid estimate subtracts COM drift
before choosing the turn: drift stays in world space while relative launch
velocity rotates. The exact transported release velocity still decides the fit.

`bodyflip-throws.js` owns held meshes and immutable release plans.
`projectile-world.mjs` creates released bodies in the existing Bodyflip Jolt
world. It uses the approved convex/compound geometry, physical scale, mass,
gyro, CCD and dissipative spear aerodynamics. The app advances its one world;
kinematic seeking caches projectile states and does not step while paused or
scrubbing through an already cached interval. Fractional release boundaries
split a step. Released objects participate in existing actor/platform
collisions; there is no added temporary collision gate.

Validation commands (offline; no desktop or saved-scene writes):

```text
node Labs/BodyflipLab/verify-throws.mjs
node Labs/BodyflipLab/verify-projectiles.mjs
node Labs/BodyflipLab/verify-throw-hulls.mjs
node Labs/BodyflipLab/verify-throw-aim.mjs
node Labs/BodyflipLab/verify-throw-drift.mjs
node Labs/BodyflipLab/verify-throw-app.mjs
node Labs/BodyflipLab/verify-jump-track.mjs
node Tools/Bodyflip/verify-throw-embedded.mjs
node Tools/Bodyflip/verify-app-parity.mjs
node Labs/BodyflipLab/verify-native-profile-throws.mjs
node Tools/Bodyflip/verify-release-cache.mjs
```

Reference parity checks 49,314 pose/launch values, maximum difference
1.55e-14. The aiming check covers both throws, Small charge 10/37/100%,
stationary and +/-360 degrees/s bodyflip plus twist, and six target directions:
72 cases, maximum direction-vector error 9.91e-9 from the projectile COM.
The drift check adds 60 assertions across eight known-reachable mixed-spin cases
(including 11 m/s upward drift), three deliberately unreachable weak throws,
and scene-translation/source-rotation invariance. Reachable error is at most
8.41e-9; impossible cases remain finite misses, without changing source impulse,
and beat an independent 24-orientation rigid sweep.

Native and app aim use the same initial centered physical reference; a globally
transformed equivalent reference had introduced roundoff that selected visibly
different weak-throw solutions. The solve now scales its LM regularizer with
Jacobian sensitivity and reuses each projected candidate. Fourteen Node/Chakra
frames at Small 0.37% and 37%, mixed spin and a rear target, agree within
1.62e-8 m and 5.38e-9 in launch direction. This includes the fractional release
frame. The planner retains its 120 s whole-job watchdog and memory guard;
the VM Command MaxSeconds argument currently does not enforce a separate
per-command deadline. Probe timings cover whole cases.

The app smoke loads all browser scripts and actual assets against an in-memory DOM/GL sink and the
real single Jolt world; it verifies release/UI integration but does not
rasterize a browser image. Existing simulated foot/one-hand/two-hand replay
also passed 1,296 frames with maximum pose tracking error 1.54 cm and no hinge
limit excess.

Final app/adapter boundary checks pass 24 samples across four fixtures: sweep
with mixed spin aimed behind, Small throws at 37% and 0.37% in that setup, and
an idle foot push with surface correction. Positions match exactly; the
quaternion-angle comparator reports at most 5.97e-8 radians. This is Node
running the actual app scripts and packaged native adapter; the separate
Chakra comparison above covers cross-engine arithmetic. The idle landing uses
the same deterministic NN stub on both sides, so this check does not establish
trained native NN or native physics parity. All ten recorded source/package
hashes remained unchanged during the run. Receipts:
Saved/Diagnostics/BodyflipPort20261030/app-parity-final-summary.json and
app-parity-hashes-before.json / app-parity-hashes-after.json.

The explicit native rig profile (23 bodies, 78.25452959537506 kg) also passes
six mixed-spin throw endpoints, including COM drift and rear/diagonal targets.
Maximum launch-direction error is 5.37e-10. Across 36 intermediate samples,
joint-limit error stays below 4.85e-16 rad, connector error below 4.58e-16 m,
and COM displacement from the aiming correction below 1.81e-15 m. Source
hashes remained fixed during this run. This verifies the profile-aware source
planner; it does not replace native Jolt flight or servo validation.

The native adapter caches each completed throw's release packet until its
target, sequence, preparation horizon or scene changes. Sample time still
updates the release remainder; callers receive a fresh copy of cached data.
With BODYFLIP_RELEASE_PROFILE=Labs/BodyflipLab/fixtures/native-rig.json, the
cache test compares 52 commands against an uncached copy of the same source
adapter. Repeated samples, backward seeks, target edits, preparation extensions,
scene changes and caller mutation all produce exactly equal output. Release
calculations fall from 54 to 10; wall-time measurements were noisy and do not
establish a native performance gain. The profile run uses source modules in
memory and a deterministic NN stub for its ground continuation. Receipts are
native-profile-throws.json and release-cache-native-profile.json under
Saved/Diagnostics/BodyflipPort20261030/; both record unchanged source hashes.

Native integration uses the same packaged evaluator and a scoped
FProphecyBodyflipProjectiles owner. It shares the existing Jolt coordinator;
an optional per-call schedule splits only active projectile steps at release
fractions and preserves unrelated forces for the full requested interval.
Its opt-in authored-convex preparation keeps the approved 1 mm bevel before
physical scaling; ordinary imported convex geometry uses its existing path.
Authored preparation bypasses the preliminary zero-tolerance Chaos hull pass,
which rejected two approved spear hulls. It uses the measured WASM settings
(hull tolerance 0.001 m, convex-radius error 0.05 m, bevel 0.001 m), retaining
the exported mass/COM/inertia. All 18 hulls pass the coordinate/scale check;
maximum bounds difference from approved WASM construction is 9.33e-8 m.
The native tests are Prophecy.Jolt.Bodyflip.FractionalRelease and
Prophecy.Bodyflip.ProjectileGeometry. Native seeks restore recorded owned
projectile position, orientation, linear/angular velocity and activation without
stepping the shared world. Released objects require an exact recorded frame and
matching launch settings; an uncomputed/evicted frame returns an explicit error
before changing the playback state. Pre-release frames remain freely seekable.
History retains at most 32,768 body states; scene edits invalidate old collision
history. Resuming a recorded state simulates against the current shared world;
other actors and old contact solver history are not rewound. Pause clears only
the owned body's queued forces, preserves its release velocity, and excludes it
from fractional-step force callbacks.
The isolated material bake is Tools/Bodyflip/create_projectile_material.py.
