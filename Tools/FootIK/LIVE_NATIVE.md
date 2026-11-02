# Live native boundary

`ProphecyFootIKLive` is separate from the diagnostic reference-course owner.
The `Set Foot IK Enabled` node in `UProphecyFootIKLiveLibrary` retains an opt-in
post-NN solver for one registered agent. The actual game stream selects Run181751
at both walking and running speeds, matching the lab; the existing policy blend
handles enable/disable without changing actor tuning. Forecasting waits for that
blend to finish before collecting its actual history pair. It does not install
another horizontal root mover or tick clock. Disabling cancels its private worker,
removes its cache and releases the world-cleanup delegate when no agents remain.
All authored timing remains in game ticks: 60 display ticks, 30 NN samples,
120 solver ticks per authored second.

The manager supplies `FInput` at a 30 Hz boundary:

- A fixed, unit-scale `CourseWorld` for the enable epoch.
- Actual previous/current and prospective real-NN body samples as `SourceJson`.
  `BuildSource` converts 25 world body transforms, real navigation roots and
  upcoming root headings. It removes navigation elevation once. The imported
  bone-axis conversion is the inverse of `ProphecyThrow::ToUnreal`.
- `SourceStartTick` identifies row zero in absolute solver ticks and must be
  divisible by four. Windows are bounded; the planner retains its own history.
- `InitialHistoryJson` on activation, created from the two actual displayed
  poses. These positions include actual navigation elevation. Unshown forecast
  frames are not a substitute for actual history.
- `TerrainJson` contains finite collider faces and the actual navigation-root
  height profile. Command and geometry revisions independently invalidate stale
  candidates.

For Blueprint-driven locomotion, the command revision follows the held world
input, gait, speed/turn scales, resolved facing and agent time scale. The
directional speed cap changes naturally while that same input turns the body;
it is already present in the controller's future root window and must not
repeatedly cancel the forecast. Other input owners retain conservative resolved
velocity invalidation. Actual input/tuning changes still cancel pending work.

At a clear terrain exit, both actual corrected poses seed the normal NN. Its
reduced feature vector cannot store every interpolated joint transform, and
decoding it applies the ordinary leg-length clamps again. The full accepted
pose is therefore also retained as the previous endpoint of the first new
publication, including repeated publication of that same source time. It is
retired at the following policy sample or on disable/action takeover. This
preserves the displayed handoff exactly without changing the controller or
adding special NN inputs. The canonical clearance event may occur after the
terrain correction has naturally faded to zero; no artificial minimum
correction is imposed on the exit pose.

Only copied data enters the worker. There is one running job and one replaceable
pending input per agent, and a serial worker lane bounds simultaneous CPU work.
`ConsumeJoined` accepts the preceding final displayed 60 Hz pose and current raw
60 Hz NN pose. A separate preinitialized publication VM runs the cheap canonical
two-leg join without waiting for the planning isolate. It retains the actual
root and upper-body NN motion, transports planned terrain corrections to the
current carrier, and keeps active material contacts. `PoseWorld` is already the
final result; it must not receive another correction-delta pass.

Frames actually consumed while a new plan runs are retained as `acceptedFrames`
and sent before the next replan. During preparation/fallback, `ObserveActualPose`
records ordinary NN poses that were actually displayed. A matching candidate is
joined to current motion rather than requiring exact predicted-pose equality,
which would prevent asynchronous activation while the player keeps moving.
The join retains a prior contact only when surface, stance and pivot all match;
canonical heel/toe transfers and new steps may change the pivot. Unshown
prediction frames are never accepted as historical game motion.

When no usable candidate exists, `liveIdentity` can separately verify the raw
fallback already being displayed. Both prior feet must be NN with no contacts,
the preceding displayed pose must equal raw with zero influence, and the fresh
query must cover both whole shoes plus the32cm influence margin. Current terrain
influence must be exactly zero. This never preempts an available candidate or
an active return and cannot initiate recurrent reseeding. Diagnostics count
`verifiedIdentityFrames` separately from planned/uniform joins. It does not
represent a computed terrain correction or solve a late terrain forecast.

`CaptureTerrain` supplies horizontal finite box tiles for the stair solver.
`CaptureSurfaceTerrain` separately supplies exact oriented finite box faces for
the incline/wall surface adapter, with real normals, local bounds and thickness.
Both read real `UBoxComponent` extents or body-setup box elements; unsupported
complex collision is reported rather than replacing it with an AABB floor.
`TerrainGeometryHash` hashes sorted collider records alone. Moving forecast
root-height samples do not invalidate an unchanged geometry cache. Inclined
pose/root ownership still requires the separate external-surface mover path;
feeding those faces to the horizontal stair solver is deliberately rejected.

`FProphecyFootIKForecast` validates the selected game Run181751 checkpoint hash
and resets a private matching policy stream from actual raw current/previous
poses. It preserves all ten controller root-window samples, extends only the
unknown tail with the last supplied velocity/heading rate, and produces a 1.2 s
prospective source on the same serial worker. It never runs a canned warmup or
advances the game's recurrent state. The selected game upper-body policy stays
authoritative at publication. Do not mix corrected previous pose with raw
current pose when seeding recurrence: terrain's actual corrected history is
provided separately through accepted frames.

Native boundary test: `Prophecy.FootIK.Live.CoordinatesAndTerrain`. It verifies
coordinate/bone-axis round trips, root-height handling, actual history, finite
collider bounds, and explicit rejection of unsupported collision. Manager
forecast, asynchronous activation and complete live-motion parity must also be
tested before claiming the live gameplay port is complete.
