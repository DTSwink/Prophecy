# Local magnetisation after the punch, recurring tick 70

Investigated the current unsaved Blueprint setup on October 7. User explicitly
authorized owned Play captures and comparisons. No production algorithm, Blueprint
graph or saved map was changed.

Victim: BP_ProphecyManualPoseAgent4. First recurring tick70 was also absolute tick70.
Spine_01 and descendants are in mode0. Their absent per-body strength entries use
native defaults: linear1, angular1, magnetisation enabled, gravity cancellation true.
The earlier suggestion that this victim was driven at .02 was incorrect: that
Blueprint setup value was not its live setting.

| Capture | Head world error at70 | Spine_05 world angle error |
| --- | ---: | ---: |
| Original | 25.939cm | 31.112deg |
| Zero world gravity and zero gravity compensation | 24.419cm | 29.890deg |
| Original through55, then victim mode1 | .353cm | .309deg |
| Zero gravity through55, then upper linear0/angular1 | 10.834cm | 11.529deg |
| Original through55, then victim external/self contact disabled | 25.819cm | 30.852deg |
| Original with read-only native servo trace | 25.939cm | 31.112deg |

Each intervention-at55 comparison has exactly identical measured body positions
to its control at every captured tick before55 (10/20/30/40/50, all three agents).
Gravity-free runs change the whole world's gravity from initialization, so they
are not identical post-impact initial-state ablations; the large bend nonetheless
persists without gravity. Baseline head error decreases to15.952cm by100: recovery
is slow, not permanently frozen.

At70, approximate relative-angle errors down pelvis -> spine01..05 are
9.2,7.1,6.5,3.3,1.1deg. Modest local errors accumulate into a large upper-body error.
The implementation constructs each target from the authored relative transform
and the actual physical parent, then applies independent world-space linear and
angular velocity corrections. It is not an articulation joint motor solving the
relative rotation directly. The angular-only control demonstrates that the local
position drive materially impedes angular recovery in this constrained chain.
It does not establish that removing linear drives is a complete or production-safe
fix; that control deliberately removes gravity as well. Gravity is not the primary
cause of the reported bend. No fix applied or universal mode0 failure claimed.

Implementation: `ProphecyJoltCharacterComponent.cpp` publishes physical-parent
targets; `Plugins/ProphecyJolt/.../ProphecyJoltVelocityServo.cpp::CalculateRewrite`
reframes the target and computes the independent velocity corrections.

Receipts and scripts: `Saved/Diagnostics/LocalMagSpine20261007/`, including six
completed captures, `findings.json`, `analyze.py`, and `final-state.json`. An initial
capture failed because the resettable BP variable is now `ttick debug`, not
`tick debug`; that owned Play was ended before retrying. Earlier passive observation
timed out while Play was stopped. All final owned sessions ended. Original editor
gravity values restored exactly (global_gravity_z0, global_gravity_set=false).
At final check the BP remains dirty, while the map is clean after editor autosave.
No explicit asset save or discard was performed by the investigation.


## Native trace: conflicting local commands confirmed

A temporary editor-only trace sampled the existing servo commands and completed
Jolt body states. The traced replay exactly reproduced the baseline at70; no
behavioral change was introduced. Source instrumentation was removed afterward.
Raw receipt: `Saved/Diagnostics/LocalMagSpine20261007/native-trace.log`.

At native step70 (first recurring/absolute70):

| Body | Command angular speed rad/s | Solved angular speed rad/s |
| --- | ---: | ---: |
| spine_01 | 9.825 | .632 |
| spine_02 | 7.532 | .867 |

At the spine_01 joint, the commanded velocities of the two attachment points
would separate them at131.084cm/s. After solving they differ by just.229cm/s.
Other spine joints show31.4–70.7cm/s commanded separation, reduced to.055–.133cm/s.
The commands are incompatible with the connected skeleton; the constraint solve
removes most of the requested straightening motion to keep the joints attached.

Why: local mode moves each bone's target into its parent's **current** physical
frame, but still treats the resulting position as a stationary world-space target
when computing velocity. A child already at its correct local attachment asks
for nearly zero origin velocity, even when its parent is commanded to rotate and
move that attachment. Its own rotation correction and COM conversion do not add
this missing parent-carried motion. Consequently the linear drives resist the
motion required by the angular drives throughout the chain. Repeated correction
causes slow recovery rather than the requested strong local straightening.

Continued contact is not the main obstacle: disabling external and self contact
at55 leaves25.819cm error instead of25.939. Pre55 sampled positions are exactly
identical. The zero-gravity angular-only comparison also isolates the linear
drive's substantial contribution (24.419 ->10.834cm), without claiming it removes
all other constraints or implements a complete fix.

This is an implementation limitation of our local magnetisation controller, not
evidence that the NN requests the bend or that gravity prevents straightening.
A correction must make local drives compatible with movement of the connected
parent, or solve local rotation at the joint. Simply reinjecting the previous
measured parent velocity was already rejected in the implementation for feedback;
switching to global targets would change the requested semantics. No production
behavior change or unvalidated substitute was installed in this investigation.

Cleanup patch compiled successfully (120.74s) and loaded at00:31:36UTC with no object changes. Character-component source is identical to its pre-investigation state. All captured physical/target pose and velocity components in the traced baseline match the original exactly (maximum difference0).


## Accepted correction

User requested the fix and accepted the improved behavior. Local servo commands
now run in cached parent-first order, while diagnostics retain original packet
indices. The parent's clamped command predicts its origin/rotation endpoint for
this integration step; local child targets use that frame. This accounts for
parent-carried motion without adding the old solved velocity to a second absolute
correction. Origin-to-COM conversion is retained. Gravity cancellation is removed
from the inherited parent endpoint so it is not multiplied down the spine.
Global-only packets bypass this path. Parents without published drives retain
the prior physical-frame fallback. Mixed strengths and per-bone modes remain
supported. There is no new node or setting.

Initial live replay: head error at70 is0.135969cm (previous25.939223cm), spine05
angle0.142983deg (previous31.112142deg). A1500-absolute-tick run completed with
five captured recurring70 samples, head errors0.136-0.142cm, all recorded poses
finite. Owned Play ended and user settings were preserved. Receipts:
`Saved/Diagnostics/LocalMagFix20261007/stability-summary.json` and the original
folder's `fixed_candidate1.json`.

Topology changes rebuild the parent ordering; ordinary ticks reuse it. Only
parents used by local children require endpoint prediction. Activation computes
ancestor commands lazily for sleeping local children, rather than duplicating
servo calculations for awake crowds. No per-step heap allocation or extra NN
inference. Native tests cover packet order, intermediate modes, parent strengths,
and recovery of a connected five-body bent chain.

Loaded through a non-reflected Live Coding patch. Rebuild the normal editor DLL
before any future cold launch; do not reopen an older DLL.

Final validation: all14 `Prophecy.Jolt.Servo` native tests passed. Final optimization/lock-scope patch compiled and loaded at00:39:17UTC. The completed final100-tick live capture matches every recorded physical/authored pose component of the accepted candidate exactly (maximum difference0).
