# FK follow-through experiment — October 4

User clarified the example as **slashRU, variant16**, not slashRD. Latest
snapshot is9; published desktop/current settings then used world inertia,
hold.8, decay.5, return.31s, easing0, yaw−29, spine/clavicle0, upperarm1,
lowerarm.36. These current settings, rather than snapshot9's earlier settings,
are the basis of the comparison in `arc-study.json`.

The prior world-space method adds a fading correction to an idle blend that
starts immediately. More hold retains the correction, but does not stop that
idle blend from redirecting the arm. Merely changing correction coordinates
therefore does not preserve the visible swing.

## Techniques compared

A fitted circular hand path has speed2.807m/s, radius.292m and turn9.603rad/s
from the final three spine-relative hand points. Against the returning shoulder,
it exceeds the .494m arm reach on its first extrapolated frame, and requires
.531m by frame2 and .563m by frame3. A wrist-only circle would require clamping,
moving the shoulder, or changing limb length. It was not installed as an IK fix.

The implemented opt-in **Follow through before return** instead continues the
connected FK pose before beginning idle attraction. During hold its angular
clock advances at the captured velocity. After hold, exponential slowing is
integrated analytically into a monotonically increasing extrapolation time.
That continued motion is smoothly weighted out while fixed endpoint orientations
blend to idle. World mode uses the captured world rotation and the canonical
world idle pose derived from the frozen pelvis; local mode uses FK local motion.
No new hand-local inertia, IK solver, stretch, neural inference or frame history.

Current-profile first30Hz-frame hand speeds:

| Return frame | Existing method | Follow-through |
| --- | ---: | ---: |
| 1 | 2.136 m/s | 2.21 m/s |
| 2 | 1.738 m/s | 2.34 m/s |
| 3 | 1.357 m/s | 2.48 m/s |
| 6 | .589 m/s | 2.88 m/s |

The terminal authored chord speed is2.807m/s. This is improved continuation,
not exact trajectory preservation: current zero spine/clavicle inertia means
the shoulder returns immediately and changes the hand path. With every upper
joint extrapolated, the exploratory FK version retained roughly3m/s initially.
User profiles were not changed. Hold80% of .31s leaves only .062s to return,
which can still produce a quick final motion; lower hold or longer return is
appropriate for a smoother end.

An early prototype slerped a moving predicted orientation directly to idle.
The all-variant sweep caught a178-degree shortest-arc branch flip on jabR7;
the shipped version blends fixed endpoint orientations and weights the analytic
rotation separately, removing that branch switch.

## Verification

`test_follow_through.cjs`:1920 cases across all320 variants, both spaces and
hold0/.25/.8, plus a2ms sweep of all320 aggressive world holds. Checks outgoing
angular velocity, continuous hold release, finite poses, fixed lengths/lower
body, excluded hand inertia, exact idle deadline and zero-inertia parity.
The aggressive sweep's largest2ms rotation is20.812degrees (a fast final return,
not a claim that high holds are gentle). Existing modes are still available.
Isolated UI verified old profiles defaultoff, per-attack selection, refresh,
copy/snapshot persistence, slider commit and no browser errors.

Evidence: `Saved/Diagnostics/LabSpine20261004/arc-study.cjs` and JSON,
`follow-ui.cjs`; live lab source and `test_follow_through.cjs`.
