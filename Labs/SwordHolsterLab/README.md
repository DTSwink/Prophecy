# D/S Sword Holster Lab

The solid-body view includes a separate darker pelvis box rigidly following the pelvis bone, also in upper-body-only mode. The lowest spine block remains above it; its shape is not a pelvis orientation reference.

Temporary viewport diagnostic **Distance to pelvis · temp** draws a yellow line from the selected holster rotation pivot to the displayed pelvis bone and labels its measured length in centimetres. It updates during playback/scrubbing and changes no motion. The HTML distance label is viewport-only; saved pose data includes endpoints/distance and image capture includes the line.

The viewport's **Right hand · holster frame** counter shows actual hand speed in
cm/s and angular speed in °/s relative to the holster. It measures one
authored tick (1/60 s), independent of playback speed or rendering FPS. Pausing
or scrubbing shows that interval's speed; body-pose editing shows dashes while
previewing. These are measured hand speeds, not target speeds; inherited holster
motion is excluded. During attraction the grip target translates and rotates
independently under the reach limits. Rotation pivots about the grip so blade
rotation cannot add hand travel. Alignment preserves the captured axial grip position;
the tip can now curve during the approach. Unreachable arms retain visible error.

**Shrink duration · seconds**, under Set Sword Holster Profile, is the time from
S start to reach the chosen shrink amount. Default.25s; independent of curves.
Previously saved shrink rates migrate to the equivalent duration automatically.
Attachment still freezes length; any remaining shrink finishes using the existing
slide correction. Drawing keeps its separate unshrink duration. The setting is
persistent. Actual shrink percentage appears below the viewport velocity counters.

**Reach / Attached** columns share two speed rows. Attached values control maximum
hand translation (cm/s) and angular speed (°/s) relative to the holster after
attachment and before sliding. They initially copy the existing sheathing reach
limits; subsequent edits are independent and persistent. Sliding retains its
own speed control. **Slide %** appears below Shrink in the viewport:0% is the
entrance,100% fully sheathed; drawing counts downward.

Open **D-S Sword Holster Lab** on the Windows desktop. The teal D/S sword icon launches its own window and local service at `http://127.0.0.1:8818`. Unreal is not required to run the lab. The original Attack Recovery Lab and its saved state are untouched.

**D/S** means **drawing (unsheathing) / sheathing** in this project.

**Leeway attachment phase** is a saved viewport checkbox, on by default.
On keeps the current early attachment → tip alignment → sliding behavior.
Off keeps S in the hand until the actual blade tip is within2cm of the entrance
and full rotation is within the selected tolerance, then attaches and slides
directly (no Align tip phase). It captures actual rotation, tip offset and scale
at transfer, using the existing slide correction to close those residuals.
Holster compensation starts at that transfer. Unreachable cases remain waiting;
there is no early-attachment fallback. Drawing is unaffected. This motion control
is separate from **Show sheathing leeway**, which only controls the overlay.
Both planners and sequence actions use the same selected rule.

**Show sheathing leeway**, beneath **No cheat** at viewport top-left, persists as a view setting. During S reach and tip alignment it draws the same Unreal colors: tilt cone that turns from cyan to green when full rotation is within tolerance, cyan perfect axis, green/red actual blade ray (full rotation including roll), adjacent roll dial with its remaining cyan allowance, and a green/amber 2cm entrance sphere with actual tip/connector. The readout shows rotation, roll, tip distance and body readiness. It follows the displayed sword including shrink, works in both planners and sequence orders, and does not change motion.

**Sheathing attachment and tip alignment (October13):** the first tick inside the full rotation tolerance captures the sword relative to the holster without changing its world transform or scale. The **Align tip** phase aims the blade toward the mouth, projects that rotation inside the allowed full-rotation angle, and aligns sideways while preserving the grip position along the holster. Grip translation and rotation independently run at their respective max reach speeds in the holster frame on normal time, each stopping at its own target; there is no shared duration or rotational travel budget. Reach/slide timing curves do not retime this stage. Shrink freezes during alignment, then resumes the existing slide correction. **The holster owns the sword path from capture onward; the arm follows.** Sliding starts at the insertion depth reached by that alignment, independently of hand reach. It covers the remaining distance to 100%; it does not reset to 0%. A negative starting value means the tip is still outside the entrance. Sheathing FK/head thresholds still refer to actual insertion, while rotation correction keeps its own elapsed slide clock. An unreachable hand leaves a visible tracking gap, reported in the existing hand-error readout; it cannot drag or stall the sword, and the arm is not stretched. Integer and fractional playback use the same ownership. The authored body retains its reach schedule, then blends from the body pose reached at slide entry toward the seated target. No added controls. Drawing is unchanged. `test_tipalign.cjs` and `test_sword_owner.cjs` cover both planners, motion/curve/shrink cases, speed limits, ownership under a deliberately displaced arm, and sequence orders.

**No cheat · live target planning** (viewport top-left) is a persistent,
shared D/S checkbox. Off uses the original future-recording reach planner.

**Attachment body continuity:** attaching the sword does not change the spine
or clavicle speed rule. They retain their original reach-curve schedule during
tip alignment; sliding starts from the body pose actually reached. The angular
speed ceiling is not used as a new requested speed at attachment. Regression:
`test_attach_body_schedule.cjs`.

Both planning modes share the selected sheathing arrival rule.
On prepares the trajectory chronologically at60Hz: only the current gait pose
and observed history are available, while authored body/curve targets remain
known. Initial reach duration uses the current holster, followed by native-style
four-tick destination refits/filtering and per-tick pursuit after the deadline.
Torso/pole/head timing uses the estimated deadline, not a future successful
arrival. Slide guides use the current holster; the shared sheathing continuation and
its early held-arm return advance at60Hz (the older off-mode return used240Hz). Head/return and underlying locomotion retain
their independent clocks. Curves rerun the causal calculation instead of
replaying a trajectory planned with later gait samples. The worker still caches
output for smooth playback/scrubbing; rendering performs no destination solves.
Both sequence actions and body previews support this mode. It is a kinematic
recorded-input test of Unreal's information constraints, **not** a Jolt/NN
recurrence simulator or proof of full engine pose parity. Refit phase is fixed
for the single lab agent; holster stabilization remains the explicit lab-only
control. Tests: `test_online.cjs`, `test_online_ui.cjs` (future-input and time-budget
independence, motion/sequence/curves, persistence and isolated UI).

**Play both actions:** the checkbox below Base motion/Action follows the selected
mode: Drawing plays **D → S**, Sheathing plays **S → D**. The selected action
starts at the configured tick; the other starts after its complete FK/head
return (and drawing’s unshrink), with no second delay. Changing **First action**
rebuilds the order while preserving each action’s tuning. Its controls and
endpoint previews follow the selected mode. Idle/walk/run continues on one
clock; the timeline and captures cover both actions. Each retains independent
speeds, body poses, curves and FK return. Duration is a time budget per action.
An incomplete first action or disabled first FK return prevents the second and
shows a status message. Checkbox and selected mode persist in settings/snapshots.
Head/FK clocks remain unmodulated. Tests: `test_sequence.cjs`,
`test_sequence_ui.cjs`, `test_sequence_speeds.cjs` cover both orders, continuous
joins, independent motion/timing, worker edits, retiming and save/reload.

**Body poses → Holster rotation compensation**, at the top of the right panel,
is shared by D/S. S captures rotation at attachment and holds through alignment
and sliding; D holds only during sliding. 0 follows pelvis rotation, 1 holds the
world orientation captured at grip. **Holster return duration** (default .25s)
returns to the original pelvis-relative placement after sliding on the normal
clock. Each sequence action captures its own reference.

**Holster axial pivot** is shared and saved: 0% is the bottom of the exported
holster mesh, 50% its current centre, 100% the entrance end (local Z bounds).
Default50 preserves the previous pivot. Compensation rotates about this point,
which remains attached to the pelvis; the component centre consequently moves
when an off-centre pivot is selected. Neutral placement is unchanged and restored
at return completion. The temporary distance overlay measures this same selected pivot,
not the component centre. Fractional playback anchors the pivot to the displayed pelvis as well.
Slider edits use the background planner without pausing or seeking. These are
lab controls; no Unreal changes were made in this update. No-cheat-off drawing
with compensation retains reference reach and uses the shared current-tick
continuation thereafter; zero compensation retains its original planner.

**Drawing/Sheathing speeds are independent.** Max reach speed, max reach rotation
speed and sliding speed follow the Action selector and persist with its profile,
including in S → D. Older files clone their shared speeds into both actions;
existing per-action values take precedence.

**Drawing hand release inertia:** at0% insertion the returning right hand now
preserves its incoming rotation and local positional motion using the existing
FK inertia engine. Position inertia rotates the local bone offset while retaining
its length. Most global hand translation already inherits arm inertia; enabling
the hand-local contribution has only a small effect in the current saved setup.
Drawing FK return → Per-bone inertia → **Right hand · draw release** defaults1;
0 disables that hand’s local inertia. Main inertia and its existing
decay/hold/space/spring settings apply. Sliding is unchanged;
sheathing and the left hand remain as before. Current captured first-tick turn
fell6.65→.11deg. Broader running/early-return spring cases still have residual
rotation discontinuities; this is not a complete return-continuity repair.

**Body poses has independent Drawing and Sheathing profiles.** The panel follows
the selected action. Both insertion poses, elbow settings, reach/pole speed caps
and pelvis compensation are saved per action. Older settings and snapshots copy
the existing shared values into both profiles, preserving the original motion.

**Max pole speed is an upper bound.** During D/S reach, the elbow preference
slows to arrive at its entry target with the hand, using unwarped reach time.
If the cap prevents arrival, it continues catching up during sliding. Zero holds
the starting preference. Sliding keeps its existing target pursuit and reference;
entry inertia remains a separate transient contribution.

**Body poses → Pelvis rotation compensation** is saved per action.
Default1 keeps full correction;0 follows pelvis rotation. Intermediate values
blend the live and entry pelvis orientations, applied to the whole authored
chain including its first offset. Translation is unchanged. Slider edits use
the background planner without pausing or seeking playback.


**D/S authoring with pelvis counterrotation, October12 — current lab contract:** the user
superseded additive spine/right-arm motion. Capture the local FK chain at D/S
entry. Spine01–05, right clavicle and right arm use that captured geometry and
are authored from that geometry; ongoing locomotion rotations/offsets
on those bones are discarded until FK return. Spine05 uses the pelvis orientation
captured at D/S entry: cancel the current pelvis rotation before continuing the
authored turn. Right clavicle targets are relative to corrected spine05. Lower
spines receive20/40/60/80/100% of the change from the captured spine05 rotation;
their entry shape is retained, with no ongoing gait underneath. Existing target
sliders, reach schedule/caps, curves, pole controls and saved values remain.
Pelvis translation remains. The holster still follows the actual pelvis; the arm
follows its moving grip. **Head-position correction:** the initial implementation
only corrected the top's orientation by distributing inverse pelvis rotation down
the spine. Its lower joints still moved spine05 sideways. Now the entire authored
spine chain, including the spine01 offset, uses the entry pelvis orientation plus
the live pelvis position. Only the authored spine turn is distributed20..100%.
This cancels pelvis rotational transport of both position and orientation, keeps
bone lengths and preserves entry continuity. The spine01 local offset counterturns
with the chain; the pelvis itself is not changed. No positional filter or new knob.
The calculation is stateless, so seek/frame rate cannot accumulate drift. Slider
previews use the same entry orientation. Early FK return still resumes locomotion;
independent head look is unchanged. This is not a promise of a stationary head.

`test_pelvis_counterrotation.cjs` now verifies positions as well as orientations
for361 combined yaw/pitch/roll samples, unchanged translation and lengths, plus4
walk/run D/S reverse-scrub trajectories. Six body motion cases pass(max grip.081cm),
12 entry-inertia cases and head-clock checks pass. In the captured run/S123..143,
spine05 sideways position relative to pelvis, after removing the endpoint-linear
authored trend, falls from2.99530cm peak-to-peak to.000466cm. Integer/fractional
head-position seams before the fix were already below.000002cm: the problem was
spatial transport, not sampling discontinuities. Evidence and prior source:
`Saved/Diagnostics/SwordHeadPosition20261012/`. User state/Unreal untouched.

Left clavicle through hand retains current parent-local animation, including the
existing additive left-clavicle target. Entry inertia covers all13 FK joints
(spine01–05 plus both clavicle/upperarm/forearm/hand chains), using the existing
amount and duration. The residual runs after pole correction so the elbow cannot
erase incoming arm velocity. As with reach inertia already, this transient is
additional to planned speed bounds; the pole cap governs the authored preference
and is exact again after the fade. Sliding is unaffected by entry inertia.
Head/neck keep the existing independent look controller. Existing early FK
return still resumes locomotion on its selected schedule; the gripping right
branch remains held until release. No new controls or playback hand-target solve.

Verification:27 pose cases check pelvis invariance, fixed authored right side,
live left locals and lengths;6 idle/walk/run D/S cases complete with max slide
grip.09004cm and entry position step.00002515cm across.2us. An adversarial D/S
replay replacing every future driven gait rotation leaves the authored trajectory
unchanged (max1.64e-13cm). Twelve linear/curved inertia cases check local angular
velocity continuity on all13 joints, arm geometry and fade;8 arrival/cap schedules,
both pole-reference tests, independent head clock and isolated slider/worker/
preview/persistence tests pass. In the user's bypassed run/S segment, tick100→105
hand-target distance now54.55→38.46cm (previously57.01→65.97cm). This removes
that measured retreat; no global monotonic-path or all-extreme-profile guarantee.
Tests: `test_bodyreach.cjs`, `test_pelvis_authoring.cjs`, `test_entry_inertia.cjs`.
Evidence/backups: `Saved/Diagnostics/SwordPelvisAuthoring20261012/`.
**Lab only; refresh.** User tuning and Unreal untouched.

**Sword-relative sliding pole, October12 — lab-only:** **Body poses → Right
elbow direction → Sword-relative pole while sliding** is saved, shared by D/S,
and off by default. Reach keeps its existing reference. At slide entry capture
that reference's zero direction in sword-local space; carry it with the sword
and project perpendicular to shoulder–wrist during sliding. Existing endpoint
angles interpolate in this reference under the same unwarped scalar speed cap.
The transfer preserves the current elbow direction. Sword rotation carries the
reference without spending the preference speed budget. Fractional sampling,
early return and preview use the same track; ordinary arm return resumes at
release. Saved key `swordRelativeSlidePole` is included in settings/snapshots/JSON.
Toggle reuses source planning and the existing240Hz track/O(1) lookup, with no
new playback hand-target solve.

`test_sword_pole.cjs` passes12 idle/walk/run × D/S × FK-return start70%/100%
cases:25°/s cap, max grip.08222cm, entry/release elbow step.00002149cm across
.2µs, unchanged reach within numerical precision, preserved lengths, restored
motion on unchecking and preview parity. Existing pole tests pass. Isolated
`test_sword_pole_ui.cjs` verifies save/reload, shared D/S, unchanged targets/time
and uninterrupted playback. Additional immediate-return0% stress probe retains
the existing folded-arm guide limitation: idle/D, pole−40→70°,25°/s, tick133.875
grip error.7513cm with old reference and1.0801cm with sword reference. That probe
is not included in the12-case pass and was not repaired by this change.
User settings and Unreal were untouched; refresh lab.

**Earlier entry inertia implementation (superseded scope above):** below the curves, **Inertia amount** defaults1
(0 disables it) and **Fade time · s** defaults0.2. At reach entry, capture the
incoming animation's parent-local angular/offset-direction velocities and the
new reach's outgoing velocities. Their difference becomes a compact FK momentum
residual, `elapsed * (1 - elapsed / duration)^3`, on the driven spine, clavicles
and right arm. Including the ancestors avoids a new torso turn kicking the hand.
Pelvis/legs and left-arm local animation stay untouched; segment lengths are
preserved. No hand-path IK or per-frame velocity fitting. Work retires after the
fade, capped at reach end so sliding and its grip poses remain unchanged.
The fade uses normal authored time even with curve modulation; changing these
controls reuses the prepared path. The planned reach speed bounds still govern
that path; incoming inertia is an additional transient motion contribution.

Eight idle/walk × D/S × linear/curved cases pass entry/exit pose continuity,
lengths, held sword attachment, zero-duration bypass and unchanged plan/slide
timing. In the captured walking/S/tick70 case, hand velocity mismatch relative
to pelvis falls121.55→8.06cm/s and247.36→0.054deg/s: reduced, not a claim of exact
world-space velocity continuity. Numerical evidence is in
`Saved/Diagnostics/SwordEntryInertia20261012/numerical.json`. Head-clock, gait-clock
and elbow-cap tests pass; earlier extreme-gaze limitations below remain.

Each curve has its own **Reset curve** button. It resets only that phase for
the selected action; the combined reset button has been removed. Shared inertia settings and all four independent resets pass isolated UI persistence/playback checks. Repeated-refresh connection failures found during testing were addressed by increasing the backend listen queue to64 (takes effect on its next launch).

**Debug curve bypass:** **Bypass timing curves · linear D/S**, above the timing
curve panel, temporarily uses linear reach/slide timing for both actions. Saved
curve points remain editable and unchanged by the switch; uncheck to restore
them. The checkbox is saved with view/debug controls, separately from the four
curve profiles, including snapshots. Switching does not stop playback or seek.
Other edits and background body planning respect the bypass. This bypasses the
four time-modulation curves. Reach progress is linear when bypassed; requested entry inertia, head and FK return profiles still apply.

**Earlier additive body poses, October12 — superseded for spine/right arm:** the saved spine/clavicle poses
now add offsets to current locomotion instead of cancelling its rotations.
Zero leaves the animation untouched. Spine offsets use the pelvis frame and
clavicle offsets use spine_05; existing0%/100% sliders and saved values remain.
The authored poses are reference poses, not fixed orientations during walking.
Reach starts with zero addition, sliding interpolates the two additions, and
existing early FK return removes them. No new controls or playback IK.
Checkpoint `ef4ed92` was pushed before this change.

Current-profile idle/walk D/S complete with maximum fractional grip error
0.0574cm and continuous phase boundaries. A held target retains the walk's
32.284° spine and10.950° clavicle rotation ranges instead of cancelling them.
Neutral,30 pose cases,8 speed schedules,4 gait-clock cases, elbow-pole speed,
head-clock and isolated slider/persistence checks pass. Extended early-return
coverage completes48 cases with one grip-tolerance failure: walk/S, gaze−162°,
return at slide start,0.8673cm between guides near the fully folded arm. The
return guard now checks minimum as well as maximum arm reach; this does not
eliminate that fractional interpolation error. The historical `test_head_arc`
fixed-tick deceleration assertion also fails after this trajectory change.
Follow-up diagnosis found a real reach stall in that fixture's170° gaze setup,
lasting even with a30s timeline: sliding never starts, so neither does head
look-out. The tested98–112 interval has no head reversal or speed-cap violation;
this must not be dismissed as only a stale timing assertion. Its old307
completion tick was already stale at checkpoint299. Neither test was
weakened. Evidence: `Saved/Diagnostics/SwordBodyAdditive20261012/`.

**Elbow pole authoring, October12 — lab-only:** **Body poses → Right elbow
direction** adds a saved angle to each0%/100% insertion target.0° means down,
±90° either side and±180° up. The reference frame follows shoulder→hand and uses
spine_05 vertical to establish down, so a horizontal arm sweep or torso turn
carries the same preference without spending its speed budget. **Max pole speed**
is shared by D/S, defaults180°/s, and bounds changes in this scalar preference;
0 holds its starting value. Endpoints interpolate by insertion along the shortest
angular route. The starting preference comes from the actual arm at D/S entry;
the cap may prevent reaching an authored angle before release. Curves move the
desired insertion/angle, but the speed budget uses unwarped60Hz authored time.
After release, the normal FK return profile controls the arm.

`elbowpole.js` constructs the moving reference and swivels the elbow about the
existing shoulder–wrist axis, retaining wrist pose and both bone lengths. Near
vertical alignment it carries the previous reference branch instead of picking
a world-axis direction. Source FK paths, sliding guides and early return use the
same prepared angle track. A small rigid-swivel correction after fractional FK
sampling keeps the displayed angle within the cap: guide interpolation alone
was measured at33.36°/s with a25°/s setting; corrected rendering peaks at25.0000000002.
It is not a new hand-target IK solve; the moving wrist path remains unchanged.

**Preview/playback parity:** endpoint previews now sample the actual prepared
motion, stopping at early FK return start if it precedes the chosen endpoint. The removed independent preview IK could
put the elbow27.73cm from its playback position in the captured setup. During
editing a cheap provisional body/pole adjustment remains responsive; the worker
prepares the full result on release and the display smoothly settles to it.
Slider edits sample the current playback time, including while playing; they
never seek to the selected endpoint or freeze the clock. Early return
can therefore move the displayed torso away from the raw authored endpoint.
Settings, endpoint copy/reset, snapshots and JSON include each `bodyTargets.*.pole`
and `maxElbowPoleAngularSpeed`; old settings inherit0°/180°s. No Unreal changes.

Verification:181 horizontal sweep samples at zero preference-turn budget,
world/torso rotation invariance, vertical crossing(max.1° step at.1° input),
angular wrap,4 current idle/walk D/S cases at25°/s, exact settled preview/playback
poses including fractional insertion, wrist/length preservation and48 early
return scenarios. Browser checks cover both pole values/speed, live edit,
background planning, stale results, Play handoff and persistence. Tests:
`test_elbowpole.cjs`, `test_bodyreach_ui.cjs`, `test_early_return.cjs`.

**Authored body poses, October12 — lab-only:** **Body poses →** at the viewport's
upper right opens the separate right panel. Choose **0% · blade outside** or
**100% · blade seated**, then edit XYZ rotations for spine_05 relative to pelvis
and both clavicles relative to spine_05. These are two shared insertion poses:
S traverses0→100%; D traverses100→0%. Dragging previews edits at the current playback time; no Preview click is
needed. Input events are coalesced to display frames and the visible rotations
follow a35ms exponential smoothing time constant, settling exactly on the saved
values. This is editor-only smoothing, not a change to D/S timing. Release prepares
the full trajectory in a background worker; newer edits invalidate older results.
The Play state and clock are retained while editing: paused time stays fixed,
and playing time continues advancing through dragging and background preparation.
Receiving a new trajectory does not seek to its recalculated endpoint.
**Changing the0%/100% selector snaps the viewport and timeline to that point.**
If the active action starts FK return before that point, it snaps to the return
start instead. The explanation block and Preview/Back buttons were removed.
Playback or scrubbing leaves editing preview. Each bone group folds closed.
**Copy other target** and **Neutral target** affect only the selected endpoint.
All targets, panel visibility and selected endpoint persist in settings,
snapshots and JSON; preview itself is temporary. User explicitly retained early
FK return: spine/left clavicle return early, gripping right branch stays until
release. Unreal still uses its previous automatic body search; this change is
not ported. A settings backup and seeded endpoint evidence are in
`Saved/Diagnostics/SwordBodyTargets20261012/`. Refresh the lab.

**Prior lab palm-in grip, October11 (measurements before authored body targets):** D and S now use a half-turn of the seated sword
about its blade-local Z axis at the blade-base/entrance point. The exported setup,
holster placement, insertion axis, scale and ordinary held grip remain unchanged.
Both reach and slide targets, holstered display and final handoff use the same
orientation. There is no grip swap or orientation snap at transfer. Reach timing
is recalculated normally under the existing speed limits. Refresh the lab.

This is **lab-only**, newer than the overnight Unreal port. Current saved curved
profile passes idle/walk D/S with maximum fractional grip error.0864cm; twelve
additional action/motion/gaze cases complete. Three wider regressions expose
unreachable folded-arm geometry under the new wrist position: idle70% shrink
with clavicle limit0, and two plateau-curve fixtures. Shoulder-to-target distance
falls below the arm's~4.3cm minimum reach; the strict tests remain failing rather
than accepting extra grip error. See `Saved/Diagnostics/SwordGripSide20261011/`.
The head's old fixed completion tick changes298->307 with this new reach geometry;
its signed direction, angular budget and continuity still pass. Head-only scope
uses numerical precision rather than bitwise equality of reconstructed transforms.

**Unreal port status, October11:** the overnight algorithms and frozen tuning are loaded through the existing JSON-profile node; the newer authored body targets and palm-in change above is not ported. The native math/kinematic/timing checks pass. The user-authorized native override frees neck/head angular limits during D/S and restores their entry settings on completion/interruption; existing Blueprint reset calls remain unchanged. See [current native contract and verification](../../Docs/SwordHolster.md). Earlier lab-only statements below describe the dates of those individual changes.

## Playback and capture performance (October11)

Automatic desktop-view PNGs were repeatedly blocking playback: the original full-size canvas readback/encoding produced61–113ms main-thread tasks. `capture.js` now sends the exact displayed pose, camera and dimensions to `capture-worker.js`, which reuses the viewport renderer on an OffscreenCanvas. It queues a WebGL2 pixel-buffer read, polls its fence without blocking, and encodes a CPU-backed PNG in the worker. Merely moving `convertToBlob` to a worker was insufficient: it still drained the shared GPU queue and caused periodic frame gaps. Playback previews are capped at640px on the longest edge; paused views and numbered snapshots retain full viewport resolution. Unchanged paused captures reuse the previous image. Pose/settings/trajectory data retain full precision. Browsers without OffscreenCanvas keep the original capture fallback; the tested desktop Edge supports the worker/WebGL2 path.

The renderer also reuses half-capsule templates and equipment vertex storage, uses scalar quaternion/vector math without intermediate arrays, caches curve preparation and viewport size, and avoids unchanged DOM writes. Mesh topology, colours, lighting, motion curves, interpolation, body/head/FK return algorithms and authored tick timing are unchanged. There is no new frame skipping, reduced motion sampling or motion smoothing. Existing fractional FK sampling remains between prepared source samples.

`node test_capture.cjs` compares worker PNGs with actual framebuffer PNGs, including a later seek/camera change during encoding, resize, full-body ghost and rotation markers. All three full-resolution captures matched pixel-for-pixel. `test_retime_ui.cjs` passed keyboard, four-curve editing during playback, isolated persistence, refresh and snapshot restoration. Eight paired ±162gaze × idle/walk × D/S trajectories had identical phase/completion ticks and maximum position difference4.86e-10cm / quaternion-angle rounding difference0.0000042deg. Twenty bicolour/equipment geometry comparisons differed by at most3.33e-13. Large-turn and bicolour regressions passed.

A paired hardware-WebGL run (Intel UHD,1462×1173 viewport, same frozen user settings,12s capture-enabled intervals) reduced average main-thread frame work6.64→2.60ms,99th-percentile frame interval41.7→20.2ms and worst interval97.2→34.9ms. Main-thread tasks over50ms fell7→0. A separate optimized run measured14.2ms at the99th percentile; these are measured runs, not a zero-hitch guarantee. Details: `Saved/Diagnostics/SwordPlayback20261011/receipt.json`.

`node benchmark_playback.cjs` runs a read-only hardware-WebGL browser against8818, records per-frame CPU timings, requestAnimationFrame intervals, long tasks and regular live-preview capture, and saves JSON/PNG to `Saved/Diagnostics/SwordPlayback/`. Optional `HARNESS_OUTPUT_DIR`, `HARNESS_STATE_FILE` and `HARNESS_BASELINE_DIR` select output, a frozen settings fixture and prior JS files for a paired comparison. It does not register as the desktop or save shared state. October11 evidence and paired source copies: `Saved/Diagnostics/SwordPlayback20261011/`. Headless hardware measurements are diagnostic evidence, not a promise of desktop frame pacing under every system load. Click **Refresh lab** to load; the user's running lab, settings, camera and Unreal were not changed.

## Tip entry and underlying gaze (October11)

Sheathing aims for **perfect sword alignment**, with the shortened mesh tip at the holster entrance. **Rotation tolerance** defaults15 degrees (0-90) and is only an acceptance gate, never a destination offset or a half-limit target. The prepared FK reach is checked every authored tick using the actual sword pose and current scale. Sliding starts on the first tick with tip distance<=2cm and full orientation error<=tolerance, including roll. It can interrupt the reach before the perfect endpoint; an unfinished reach can also qualify later as its moving base changes. Drawing is unchanged.

The accepted reach is a prefix of the original speed-bounded FK curve: it is not sped up or redirected toward the cone boundary. Spine/clavicle retain their coordinated perfect-reach schedule until entry; early acceptance captures the reached spine addition and releases the reached clavicle addition over insertion. There is no torso rescheduling or pose jump at transfer. This means early acceptance can stop the body turn before its planned perfect-endpoint optimum. A zero rotation tolerance retains the complete-alignment timing checks.

**Rotation correction · time fraction** defaults0.1. On entry the sword keeps its actual reached orientation, position and scale. The remaining holster-relative rotation closes using elapsed playback ticks since slide entry, independently of the sliding curve:0.1 finishes after10% of the nominal slide duration,1 at slide end, and0 immediately after entry. This is authored playback time (60 ticks/second), not wall time. Tip insertion, any accepted tip-position residual and remaining shrink still follow their existing insertion clock and curve. The tip path ends at the existing seated reference, preserving final placement. Nonlinear sheathing curves prepare an additional quarter-tick parent-local FK arm track, including the exact angular cutoff, so the hand follows the separately timed sword; its final pose seeds FK return continuously. Head/return-profile edits reuse this track. Playback never solves the arm. Linear curves retain the original slide guides; nonlinear drawing also prepares guides against the steady base-motion clock.

`test_slide_rotation_clock.cjs` checks36 idle/walk,0/+170 gaze, correction0/.25/1 and slow/fast/plateau curve combinations, including early/90%/100% FK return. Relative rotation agrees with the elapsed-time formula within0.000004°, while tip insertion and scale retain their original curve. Maximum tested grip error0.952cm; bone lengths, entry/release continuity, exact cutoff, guide reuse and no-playback-solve checks pass. Disabled return and truncated slides are also covered. Retiming,48-case early return,16-mode return, head-arc and isolated UI persistence/curve-edit regressions pass. Evidence: `Saved/Diagnostics/SwordSlideRotationTime20261011/`. No Unreal changes or human motion acceptance claimed.

**Underlying upper-body gaze** is a persistent yaw slider from-170 to170 degrees, default0. It reuses the accepted `apply_gaze_overlay_global_pose` yaw algorithm from `stepper/training/ik/train_upper_pose_autoencoder.py`: subtree turns about each current bone's local X, incremental weights1..8 /36 across spine_01..05, neck_01/02 and head. Arms inherit torso turning; pelvis/legs retain their authored movement and segment lengths are unchanged. This modifies the base animation before D/S planning, the base ghost and FK-return destination. During D/S, authored head forward is the ungazed animation's independent world orientation. The user rejected transporting that target with spine_05; neck/head application instead cancels inherited spine rotation. It is the training/viewer augmentation, not an NN inference or the independent D/S head-look strength. Changes apply on slider release and preserve playing/paused state.

All three controls persist through ordinary settings, JSON and snapshots. Sheathing entry controls hide during Drawing. The previous user settings/camera were not overwritten. This is lab-only; no Unreal changes or restart. Click **Refresh lab** to load the new implementation.

`test_tip_entry.cjs` covers12 idle/walk/tolerance/correction cases, exact entry continuity, fractional alignment, perfect reach targets, first-eligible-tick triggering, an unchanged reach prefix, continuous residual shrink, unchanged drawing and gaze invariants. Entry position difference<6e-14cm and rotation-curve error<0.000004deg. FK reach-speed/guide checks, return and zero-tolerance spine timing pass. Current saved15% configuration (rotation tolerance15, correction.25) starts sliding at71 idle /72 walk instead of the planned perfect endpoints75/76; slide ends102/103 and actions complete164/165. Entry orientation errors7.735/3.844deg; entry retained scales.850679/.850641 converge to.85 during correction. These are numerical lab checks; user playback inspection remains necessary. The earlier gaze parity and UI persistence evidence remains in `Saved/Diagnostics/SwordTipEntry20261011/`; no gaze/control schema changes in this correction.

## Controls

- Choose **Idle**, **Walk forward · in place** or **Run forward · in place**, then **Sheathe** or **Draw / unsheathe**.
- **D/S start tick** schedules entry; one authored second is60 ticks. The timeline supports any start point, playback, seeking and single-tick stepping.
- Playback ends at D/S completion if earlier than **Timeline length**, including FK return, drawing unshrink and any remaining head look-out. The timeline, End button, stepping and .35s loop pause use that endpoint; pose and base-motion ghost freeze there. Stalled or unfinished actions retain the configured limit. The configured length remains saved, so changing parameters can lengthen the action again. `node test_duration.cjs` verifies completion and transport behavior.
- **FK return controls →**, always visible at the top-right of the viewport, opens a separate panel on the right. It shows the selected action’s independent return profile, saved for Drawing and Sheathing separately; panel open/closed state also persists. Start at insertion fraction runs S0→1 and D1→0; drawing defaults.3 (mirroring current S=.7), while the factory S default remains.9. The gripping right clavicle/arm stays with the sword until fully inserted for S or fully out for D, then starts its own return. Return time, easing and main inertia are visible; method/space/hold/decay/spine-angle extra time/twist removal and per-bone weights are under expandable sections. Defaults reuse the previous lab: enabled,1s, easing1, inertia1, hold0, decay1, parent-local, blend+inertia, extra.29s/90°, twist removal0, bone weights1.
- **Draw Sword** exposes the Unreal Sheathe direction, Max Reach Speed (cm/s), Max Reach Rotation Speed (degrees/s), and Sliding Speed (cm/s).
- **Drawing / Sheathing timing curves** shows only the selected action’s pair: **Reaching** and **Sliding velocity**. Drawing and sheathing each keep an independent pair (four curves total). Each starts linear with four draggable interior points and fixed0→1 endpoints. Horizontal position is time within that phase; vertical position is recorded phase progress. Steeper sections play faster; flatter sections play slower. Release a point to apply; **Linear** resets only that curve. **Reset both curves** restores the selected action’s reach and slide curves to linear defaults; the other action and all other tuning stay unchanged. Editing or resetting preserves playback: running stays running, paused stays paused. Reach planning is reused; sheathing slide-curve changes also rebuild the arm alignment guides. Head and return tracks keep their independent clocks. All four persist across action switches, refresh, saved settings, snapshots and JSON import/export.
- **Body poses →** replaces automatic spine/clavicle optimization and its angle-limit control. The right panel contains both saved endpoints, all three bones, preview and **Max reach angular speed** (the existing saved speed,90°/s factory default). The old angle-limit setting is ignored by authored poses.
- **Head look** replaces the old head correction control. **Look-at alpha** defaults1:0 keeps original forward facing,1 aims directly at the holster entrance, intermediate values partially look toward it. **Look-in** and **Look-out** each have speed limits at0° gaze and maximum ±170° gaze, all default180°/s. Speeds interpolate linearly using absolute gaze: starting gaze for look-in and current gaze for look-out. Existing saves initialize the new maximum-gaze endpoint from their old speed, preserving tuning. Only speeds are duplicated; each direction keeps one shared exponent. The lab records a constant underlying gaze per run; editing that gaze rebuilds the run. Independent **Draw threshold** .3 and **Sheathe threshold** .5 start the gaze-facing return at30% of the outward slide and50% of insertion respectively;0 means slide start,1 means slide end. **Look-in exponent** and **Look-out exponent** independently shape the turns:1 preserves the current motion; higher values (up to8) give a slower start and finish with a faster middle. Both default1. Stronger easing can take longer because the maximum speeds still apply. All head controls persist with settings, snapshots and JSON.
- **Set Sword Holster Profile** exposes Shrink Percent and Unshrink Duration (authored seconds).10% is10% shorter along the blade axis only. Initial tuning matches the current Unreal node:35%, .5s,100/180/60, start25.
- **Holster placement** provides XYZ and Pitch/Yaw/Roll offsets from the imported pelvis-relative reference. Values use Unreal local axes and cm/degrees. Zero restores the imported placement. The seated sword reference follows the holster.
- Readouts show hand-to-target distance, reach shortfall, retained blade scale and insertion percentage. Reach-limited poses remain stalled, matching the current algorithm's lack of a fallback; the lab does not silently increase shrink or loosen arrival tolerances.

Space plays/pauses; arrows step one60Hz tick and wrap; P saves a snapshot. Drag orbits, right-drag pans, wheel zooms, double-click resets the camera. View contains upper-body/pelvis visibility, full body, skeleton, base-motion ghost, arm rotation gizmos and **Two-colour limbs** (on by default). Both hands also have a yellow palm face, with opposite face signs for the mirrored left/right hand frames; their backs/edges retain the body colour. Cyan longitudinal halves follow each upper/lower arm and thigh/calf rotation; the markers are visual only. Playback loops with a .35s inspection pause. Timeline scrubbing pauses playback and updates the pose and time readout continuously while dragging; it reuses the prepared trajectory. Parameter changes still commit on change/release.

Space and left/right arrows belong exclusively to playback even while an input, dropdown, slider, checkbox or button is focused. Their press/release events cannot reach other lab controls or trigger native widget actions. Holding Space toggles once; holding an arrow repeats tick stepping. Other editing keys remain available. `node test_keyboard.cjs` verifies these cases using a read-only inspection client against8818, without changing desktop settings.

Snapshots preserve a numbered PNG, exact displayed pose, equipment transforms, parameters and camera. Refresh, snapshots and ordinary saved settings preserve your view. Settings can be exported/imported as JSON for later Unreal port work. The desktop client alone writes shared settings; plain browser visits are inspection views. Snapshot and state files live in this lab, independently of Attack Recovery Lab.

## Data and fidelity

`data/motions.json` retains the301-frame30Hz idle asset and now uses actual presented Unreal NN recordings for forward walk/run, sampled every authored60Hz tick. Each owned kinematic session sets neutral gaze, stabilizes for180 moving ticks, then records721 poses over12seconds. All26 lab bones are captured; component coordinates use the ordinary Mesh (capsule-to-skeleton offset included), not detached PhysicalMesh. Horizontal travel is removed for inspection; gait height, sway and rotations remain. **User-corrected WalkF:** run checkpoint, movement input length0.4, speed scale1 (about200cm/s). Run retains full input/500cm/s. The original walk-policy/half-speed100cm/s capture was an incorrect assumption and is superseded. No physical response is baked in.

`Tools/SwordHolster/RecordLocomotion.py --motion walk|run --output <folder>` records through existing remote Python without saving editor assets. `node Labs/SwordHolsterLab/import_recorded_motion.cjs <folder> [walk|run]` verifies the recordings, backs up data/settings and selects matching gait phases spanning at least10seconds. Only the final fractional sample is interpolated; no crossfade or speed change. Corrected WalkF loop10.8424s (652frames), endpoint difference0.19892cm/0.33943deg; run remains10.0369s,0.1511cm/0.2414deg. Corrected WalkF raw capture/import/verification: `Saved/Diagnostics/LocomotionCapture20261012/run-policy-walk/`; unchanged run: `Saved/Diagnostics/LocomotionCapture20261012/gc-verified/`. All721 corrected WalkF samples verify checkpoint weights walk0/run1 and speed199.9969..200.0027cm/s; imported whole-tick poses match raw capture exactly. Idle/run clips remain byte-equivalent as JSON values. No editor restart or asset writes; isolated UI migration/persistence passes. `export_motion.py` preserves recorded clips when regenerating asset samples.

Each clip has its own sampling rate; locomotion stays independent of D/S curves. Existing autosaved settings migrate only from explicitly recorded previous source hashes, preserving tuning/camera. Exact historical snapshots still reject a different source hash. `test_recorded_motion.cjs` checks recorded ticks, finite two-loop sampling, independent gait time and current-profile D/S completion for both motions; max fractional grip0.0757cm. Isolated UI checks cover migration, both selections, reload persistence and snapshot protection.

`data/unreal-setup.json` contains the current placed agent's holster transform relative to pelvis, the SwordRef seated local transform, grip transform, A_Sword component scale, blade-base marker and actual triangle geometry. The displayed sword uses the same Training mesh substituted by runtime Equip; length comes from the reference sword mesh. Scale is applied once. `export_setup.py` reads the editor scene without modifying it. Re-export intentionally changes the source fingerprint; old snapshots then require their original dataset.

`holster.js` retains progressive axial shrink around the grip,0↔100% slide, parenting and timed unshrink. Drawing retains its2cm/5degree hand gate; sheathing now uses the tip/angle gate described above. Its lab arm path now uses the FK interpolation described below, with automatic guide-pose generation. It builds a deterministic60Hz trajectory; seeking and playback speed never alter the result. Drawing starts seated; sheathing starts held. Both actions use the previous lab’s FK return framework at their configured slide fraction, retaining the gripping arm until slide completion. Drawing unshrink runs alongside return with its own duration. The current native port is documented above.

**This is a pose/reach lab, not Jolt or a running NN.** It samples authored idle/walk and uses a pelvis rest attachment. It does not reproduce motor lag, physical hand/joint lag, collision impulses or recurrent NN changes. The original arm-only target setup was reach-limited by roughly4cm at35%, rather than the14cm measured in live Unreal. The corrected shrink-aware mouth target changes that historical comparison. The same arm solver, when fed the captured Unreal geometry, reproduces its14.143cm shortfall. With the seeded authored body targets, the tested35% idle/walk cases complete. Use the lab to develop the pose solution, then validate/port it in Unreal; passing this lab alone is not a physics-parity claim.

### Authored body targets

`bodyreach.js` now applies saved orientations; the shoulder-distance optimizer is
removed. `bodyTargets.clear` and `.seated` each contain `spine`, `right`, `left`
XYZ-degree triplets. The UI values are parent-frame Euler offsets from a fixed
imported neutral reference (ungazed idle tick0), composed Rz*Ry*Rx before that
reference rotation. Subtracting that fixed reference gives an additive rotation
in the named parent frame. Zero preserves current animation, including gaze;
the final orientations follow that animation around the authored pose.
Defaults were sampled once from the prior current S
pose; there is no background fitting. Left clavicle starts neutral.

Reach starts with zero added rotation and interpolates to S's0% or
D's100% offset. All three are scheduled to arrive with the hand, under the shared
per-bone angular-speed cap; a slow body extends the reach. Slide admission keeps
the existing hand/tip tolerances and additionally requires the authored entry
pose to be reached, preventing an endpoint snap. During sliding the three local
offsets slerp between the saved endpoints by actual insertion, including
fractional samples and sliding curves. Sliding is governed by insertion speed,
not the reach angular cap. The former automatic S clavicle-to-neutral fade is
replaced by the user's100% target.

The net spine_05 correction is distributed at20/40/60/80/100% over spine_01…05,
retaining underlying animation throughout the spine. Pelvis/legs and segment
lengths are preserved. Both clavicles receive their authored additions relative
to the resulting spine_05. The left arm keeps its moving animation relative to
that clavicle. Right-arm FK, independent gait/head clocks and existing early FK
return remain: spine/left can return early; the gripping right branch follows
the sword until release. Unreachable authored poses still report reach limits;
the lab does not secretly move the chosen shoulder or increase shrink.

`test_bodyreach.cjs` verifies30 parent-frame/rotation-distribution cases plus
idle/walk D/S endpoint/fractional/preview/early-return cases; `test_spine_timing.cjs`
checks8 slow/normal-speed arrival schedules for all three bones. Before the
additive change above, the48-case early
return suite passes (max grip error.0402cm), current profile/palm-in checks pass,
and4 nonlinear motion-clock cases preserve gait with no playback solves (max
grip error.0149cm). Independent head clock and signed-direction checks pass.
`test_bodyreach_ui.cjs` uses an isolated server/state store: automatic smoothed preview,
background release-only planning, stale-result rejection, shared D/S targets, global playback keys, disk/reload and
snapshot persistence pass. Screenshot/layout reviewed. A240-event drag produced36 display-frame previews, zero main-thread trajectory
builds, max.5ms per12-event batch and max.4ms preview calculation in the isolated
browser; these are scripting costs, not whole-viewport FPS. Shared desktop capture
waits during dragging/settling. User live state and Unreal are untouched. Evidence: `Saved/Diagnostics/SwordBodyTargets20261012/`.

### FK return insertion control

The contextual **Start at insertion fraction** follows the sword’s insertion readout. S runs0→1; D runs1→0. Current S=.7 is mirrored by D=.3 (30% still inserted); drawing’s factory default is now.3. Each action remains independently editable. The existing saved `startFraction` continues to mean completed slide progress for compatibility with Unreal/export, so D stores `1 - displayed insertion`. Older tuned profiles keep their timing. Body return starts on the first playback tick crossing that threshold; the gripping arm follows the sword through the remaining slide until S=1 or D=0. Return speed remains independent of timing curves. Focused browser checks cover descending threshold crossing, arm timing, independent settings and refresh.

### Head look

**Max head tilt · °** is a persistent shared D/S control, default70, range0–90. As explicitly clarified by the user, it limits the angle between the head vertical axis and spine_05 vertical axis (localX for both bones).0 means aligned/upright;90 disables the limit. It shortens the head's swing away from the spine vertical while preserving twist around that vertical, so yaw remains unrestricted. This replaces the incorrect nose-elevation clamp, which could meet a30° downward-facing limit while the head's actual vertical tilt was69.353° because of sideways roll. Desired aim and final authored orientation are constrained; fractional samples use the actual interpolated spine axis. Neck distribution and the signed world reference remain. Existing angular speeds govern movement along the boundary; if the spine moves the allowed region faster than the head can turn, only the minimum required correction takes precedence. Pre-action animation remains untouched.

Existing saves keep `headMaxDownAngle` for compatibility and inherit70 when absent. Edits keep playback running, reuse arm/body planning and persist in settings/snapshots/JSON. `test_head_down_limit.cjs` covers180 projection cases with combined pitch/roll/yaw, tilted anchors, q/−q, legal-pose preservation and unchanged vertical twist;12 D/S × idle/walk × gaze cases, fractional limits, body preservation, completion and moving-boundary correction also pass. The reported walk/S fixture at1.17s is saved in `data/head-tilt-regression.json`: at30 the actual head-axis angle is29.9995° rather than69.353°, with completion unchanged at161. Signed-direction and independent-clock tests pass. Isolated browser verification reproduces the saved current setup and verifies the rendered axes; screenshot reviewed. Evidence: `Saved/Diagnostics/SwordHeadDownAxis20261011/`. Refresh lab; live tuning (including30), camera/snapshots and Unreal untouched. Earlier nose-elevation evidence under `SwordHeadDownLimit20261011` is superseded.

**October11 direction correction; artificial head limit removed.** The user rejected the90° head/spine orientation limit. That removed combined-angle constraint remains absent. The newly requested vertical-axis tilt limit above is applied separately; otherwise a torso turn does not alter the independent world target.

Look-in and look-out now use one **ungazed world orientation captured at action start** to represent signed rotations. Each phase captures its starting rotation in those same coordinates. It interpolates toward the current world target with the existing exponent and timing profile, retaining the target's continuous rotation branch as it moves through180°. The angular budget advances those signed coordinates, rather than selecting a new shortest quaternion arc. Look-at alpha retains a continuous aim branch too. This preserves a route such as+170°→−40°→+170° through forward, instead of shortcutting around the back or reversing as a quaternion changes sign. The reference stays fixed while animation, spine and gaze targets move; look-out does not replace it with the gaze orientation. Cached subframe head samples still interpolate adjacent, speed-bounded orientations.

The distributed neck reference retains the gaze animation's local neck detail, transported onto the actual spine. Its aggregate gaze turn is removed with inverse1/3,2/3,1 shares before the authored world-head correction is applied with those same shares. This avoids double gaze/winding while allowing an exact return to the original neck and head positions, not just the head quaternion. The previous ungazed-only replacement changed the pre-action neck by up to5.67° and displaced the current fixture's completed head by0.752cm. Pre-action poses now remain exactly untouched, including fractional playback. Neck lengths, spine, arms, holster and sword remain unchanged by head authoring.

`test_head_direction.cjs` directly checks signed routes for both gaze signs, linear and sigmoid profiles, q/−q equivalence, moving targets across180°, partial look-at alpha, targets beyond90° and changing look-out gaze. `test_head_arc.cjs` retains the reported98–112 regression: zero reversals and maximum angular-velocity change0.13377°/tick. The frozen+170/S setup now completes at296 rather than the clipped-path266; reach, slide and body/arm return timing are unchanged. `test_owl.cjs` checks12 idle/walk × D/S ×−170/0/+170 cases without any backward-facing restriction: strict whole/fractional speed caps, no extra neck winding or flips, unchanged body/arm, exact pre-action pose and full neck/head return within0.001°/0.0001cm. The independent-clock and head-profile tests contain no boundary exemptions. Evidence: `Saved/Diagnostics/SwordHeadAudit20261011/`. Refresh the lab to load; live settings/camera/snapshots and Unreal were untouched. Numerical checks do not claim human motion acceptance. This contract supersedes the earlier head-limit experiment.

**Look-in speed** is a persistent0–1 slider for both D and S:1 preserves the existing fastest turn under Max look-in and its exponent;0 stretches the turn to the hand-arrival tick. Intermediate values interpolate between those durations. The angular cap always takes priority: if the fastest permitted turn needs longer, it completes later. The existing exponent shapes the stretched turn, while target tracking and neck/spine compensation remain active. A stalled reach with no predicted arrival keeps the fastest behavior. Look-out is unchanged. The head uses ordinary playback ticks; reaching/sliding curves do not accelerate its clock. Changes apply on release without pausing or rebuilding arm/body planning. `headLookInSpeedAlpha` is saved in settings/snapshots/JSON and defaults1 for older saves. `test_head_timing.cjs` checks exact stationary deadlines, intermediate values, shaped timing, cap precedence, moving idle/walk D/S targets and default equivalence; the isolated UI test checks persistence and playback.

**Sheathing look target** is a persistent0–1 slider, shown only for S:0 follows the actual scaled blade tip,0.5 follows the midpoint,1 follows the holster entrance (default, exactly preserving earlier behavior). The point moves with both objects throughout look-in; the existing look-out threshold still starts the return toward gaze. This selects the point to aim at; **Look-at alpha** still controls how strongly the head aims at that point. The slider applies on release, keeps playback running, and reuses the existing arm/body plan. Settings, snapshots and JSON include `sheatheHeadTargetAlpha`; older saves default to1. `test_head_target.cjs` covers both motions, three target weights, drawing/default equivalence, speed caps and unaffected body/arm; isolated `test_retime_ui.cjs` covers visibility, plan reuse, playback and persistence.

`headlook.js` authors the head toward the actual holster entrance: the seated reference blade-base point transformed by the moving holster. Look-in starts with D/S. It uses the rendered head’s local+Y facing axis and blends its target quaternion from independent world forward toward direct aim using **Look-at alpha**. It then advances under Max look-in angular velocity. At the selected action’s slide threshold, it starts returning to the gaze-modified animation’s world-facing head orientation under Max look-out velocity. This follows the lab’s underlying gaze setting and is independent of the procedural spine turn. Alpha controls only how strongly it aims inward; look-out fully reaches gaze. The superseded `headCorrectionAlpha` field is discarded on import.

For exponent greater than1, each phase uses the symmetric power sigmoid `u^p / (u^p + (1-u)^p)` between its starting signed rotation and its moving target, in the fixed action reference described above. Duration uses that vector path length divided by maximum speed, multiplied by the exponent (the sigmoid's peak slope). Each tick limits the vector step, which also bounds the resulting world head rotation. Exponent1 uses capped pursuit without sigmoid shaping. Look-out captures the current rotation even if look-in is unfinished, retaining the same reference. After the shaped transition, capped tracking follows the moving target. Both phases use independent exponents and ordinary playback time, unaffected by D/S curves.

Head authoring has total shares1/3 at neck_01,2/3 at neck_02, and1 at the head.
Authored and current-base head rotations retain separate signed coordinates in
one world reference; their weighted factors cancel exactly at handoff. Inherited
spine rotation is canceled separately with complementary shares. Combining these
rotations into one continuous logarithm previously retained a whole turn at exit,
leaving120deg neck error despite a correct head. Fractional playback uses the same
separate factors. The frozen Unreal replay in `test_head_handoff.cjs` guards this.
Spine motion cannot drag the independent head target or retime its profile.
Look-in aims at the mouth for D and selected tip-to-mouth point for S, accounting
for the moving eye position. Positions follow FK with unchanged segment lengths;
torso, arms and equipment are unaffected. The angular budget applies once per
60Hz tick; reach/slide curves do not multiply it. Look-out starts when actual slide
progress crosses the threshold and returns to the current gaze-modified base.

The head continues looking at the moving entrance until slide progress crosses its threshold. Its overlay stays independent while FK return changes the underlying body pose. If the arm never reaches the slide, look-out does not start. D/S completion now also waits for the head’s gaze-facing return, capped by the configured Timeline length; slow limits never cause an end snap. Existing draw unshrink and sword parenting remain intact. Seeking is deterministic because head poses are prepared with the rest of the recording.

`test_head_exponent.cjs` verifies sigmoid velocity in both directions, independent exponents, default linear motion, interrupted look-in, speed caps and completed return. `test_head_clock.cjs` covers both linear and shaped head motion under nonlinear D/S curves. `test_headlook.cjs` verifies0/.5/1 alpha, direct aim, both angular limits, independent/default/endpoint thresholds, weighted neck rotation, fixed spine anchor, preserved lengths, slow-look behavior and unchanged arm/equipment. FK, retiming and completion regressions pass. `test_retime_ui.cjs` also verifies all head controls survive actual disk save, refresh, snapshot restore and JSON round-trip on an isolated test server. Still images: `Saved/Diagnostics/SwordHolsterRetime/head-look-in.png` and `head-look-out.png`. User motion inspection remains the final quality check.

`test_large_turn.cjs` reproduces the user’s162-degree gaze setup plus both gaze signs, idle/walk and D/S (eight complete actions). Before the fix: no slide; tick133 neck jump119.62deg and head displacement8.42cm (later peak8.88cm). With the subsequent gaze-facing look-out correction, the162-degree idle S fixture enters slide129, finishes insertion160 and completes298; maximum head displacement0.112cm/tick and neck rotation2.35deg/tick. The longer head return is the additional turn toward gaze at the same configured speed, not a retimed arm return. Checks include head speed caps, retained bone lengths, no full neck winding, independent world-space look-out, and fractional/180-degree continuity. Existing head, exponent, independent-clock, FK reach, tip-entry, spine-timing and return checks pass. Earlier read-only browser captures at133/187/244 predate the user’s world-target correction. The corrected math passes the same eight large-turn cases and a90-tick comparison proving identical world head motion under different spine turns; live state is untouched. Evidence: `Saved/Diagnostics/SwordLargeTurn20261011/`. Human motion review remains necessary.

### Independent reach and sliding retiming

The curves work like retiming separate sections of the existing recording. Each action owns a reach curve and a sliding curve; the UI reuses two contextual editors when the action changes. `retime.js` uses a monotone cubic through four editable points plus fixed endpoints. The reach curve remaps D/S start through hand arrival; the sliding curve remaps hand arrival through slide completion. Only the authored D/S spine/clavicle turn, arm transition, insertion and shrink follow source time. Idle/walk, pelvis, untouched limbs and the pelvis-mounted holster always use playback time. The authored body addition is reapplied to that current base pose and the authored arm remains parent-local. Both D and S prepare quarter-tick slide guides when sliding is retimed so the hand follows the normally moving holster; neighboring early-return guides reuse the preceding solved arm as their bend reference to avoid elbow flips. Sheathing's sword-alignment rotation instead uses elapsed slide time; an additional prepared FK arm track follows that sword path. Head/neck gaze is overlaid afterward on its independent playback clock. The base-motion ghost uses playback time too. Linear defaults preserve authored tick samples; fractional samples carry the current base animation consistently.

Start, hand-arrival, slide-end and total duration stay fixed. Changing a reach curve cannot change sliding playback, and changing sliding cannot affect reach. Drawing’s unshrink/return phase keeps its existing timing. Edited points cannot reverse motion; horizontal sections may hold the authored D/S progress while locomotion continues. The existing velocity controls constrain the original prepared action, before intentional playback acceleration/deceleration. Unfinished phases use the available timeline endpoint; absent phases do not remap time. Diagnostics include playback and source time; captured model trajectories contain final displayed60Hz poses (including independent head and FK return); source body/arm frames are separately retained for curve edits.

The original `drawCurve` / `sheatheCurve` settings are retained as reach curves, preserving earlier edits; new `drawSlideCurve` / `sheatheSlideCurve` settings default linear. All are sanitized and copied independently. `test_retime.cjs` verifies phase/action independence, unchanged source body/arm poses, boundaries, independent base-motion/holster playback, curved insertion, independently timed sword alignment, forward head return and incomplete/unreachable cases. `test_retime_ui.cjs` uses its own temporary server/state directory to verify four distinct pointer-edited profiles, contextual display/action switching, numeric-setting retention, JSON round-trip, actual settings and snapshot disk writes, refresh and snapshot restore, independent reset and exclusive playback keys. Screenshot: `Saved/Diagnostics/SwordHolsterRetime/contextual-curves.png`. The user’s live lab state is untouched by testing.

`test_motion_clock.cjs` verifies D/S with slow/fast and plateau curves at fractional ticks: base pelvis/lower-body error below2e-11cm, unchanged left-arm local gait before return, holster attachment, phase continuity, plan reuse and no playback IK. Four tested cases have max fractional grip error.172cm. The source walk clip has a small native loop-end mismatch; it is not a curve-timing effect. All48 early-return cases and36 independent slide-rotation cases pass; maximum tested grip errors.062cm and.936cm respectively. Head-clock and retiming checks pass. Isolated browser checks verify Walk forward, both actions, a steady base-motion ghost and running playback without runtime errors. Evidence: `Saved/Diagnostics/SwordMotionClock20261011/`. User live tuning/camera/snapshots were not changed; Refresh lab to load. No motion-quality acceptance is claimed from screenshots.

### Shrink-aware holster mouth alignment

The seated hand target is derived from the **shortened sword**, keeping the authored blade-base marker at its original seated point. The old full-size hand target left the shortened base above the mouth; at35% shrink this produced a4.08cm axial tip gap at0% insertion despite the hand being on target. The correction first preserves the seated blade-base point, then inverts the scaled grip transform to obtain the hand target. The0% target moves outward by the shortened blade length, putting the tip at that same mouth plane. Axial-only shrink and grip pivot behavior remain intact; no asset or holster placement changes.

`test_mouth_alignment.cjs` covers five shrink values under two equipment orientations, and actual FK sheath/draw clear endpoints. Maximum axial error is0.000011cm (mesh/reference export precision); the authored small lateral placement offset is preserved. Read-only current-view comparison: `Saved/Diagnostics/SwordHolsterBodyReach/gap-live.json` and `gap-fixed.png`.

### FK arm interpolation and two-colour limbs

The user approved calculating destination poses automatically, then interpolating the bones as in Attack Recovery Lab. `armfk.js` reuses that lab's parent-local quaternion slerp, length-preserving offset interpolation and forward kinematics. The reach plan predicts the destination on the moving, turned body, solves that destination pose, and interpolates upperarm_r/lowerarm_r/hand_r local rotations from the captured starting pose. A few planning iterations reconcile destination time with the speed controls. The hand's orientation now interpolates with the arm instead of being assigned directly each tick.

Reach duration is bounded by the FK wrist arc and wrist/joint angular motion. **Max reach speed** and **Max reach rotation speed** limit the arm transition relative to its moving clavicle; inherited locomotion and body turning are additional movement. Reaching a close hand target does not allow a large elbow/wrist rotation to snap. Drawing still waits for the torso turn before gripping.

Sliding uses automatically prepared guide poses, spaced at most four ticks / about2cm along the sheath, then parent-local FK between them. Each guide reuses the previous arm orientation as its reference. The old analytic arm solver is used only to construct these guide/destination poses during preparation; sampling/playback never calls it. Tested35% idle/walk × draw/sheathe uses33–35 guide solves across full actions and stays within0.47cm of the intended grip while sliding. This is an approximation, not an exact hand constraint for every possible tuning. The former draw-only arm return tied to Unshrink Duration has been replaced by the common FK return below. Unshrink Duration now controls only sword size. Fractional playback samples also use FK, avoiding bone shortening from world-position interpolation.

The cyan half-capsules are reused from `ParryHarness/build_parry_harness.py` (`dhAddArmLongAxisHalf`), also used in Defense Harness. They follow each bone's own basis with the original quarter-turn / right-arm tint convention and0.8mm shell offset. Base tessellation matches the half-shell to avoid flicker. **View → Two-colour limbs** toggles them, persists with settings/snapshots and changes no solver data. Legs show the markers in full-body view.

Validation: `test_armfk.cjs` checks FK rotations, local-frame speed bounds, guide-only IK, fractional bone lengths, sheath tracking and continuous unshrink entry; `test_bicolor.cjs` checks bone-relative marker rotation and pose immutability. Body, original arm-only numerical fixtures, playback clamp, keyboard and bone-display regressions pass. Read-only UI checks cover marker toggle/state round-trip and screenshots. Evidence: `Saved/Diagnostics/SwordHolsterBodyReach/`. Playback quality still needs user inspection.

### FK return after drawing and sheathing

`fkreturn.js` adapts the unchanged `recovery.js` engine copied from Attack Recovery Lab. Both actions capture the body at the first60Hz playback tick reaching the selected actual slide fraction (default90%), including the sliding curve. The gripping right clavicle/arm captures its own return at100%. Reaching and the original source sliding guides remain unchanged. Drawing returns the sword with the hand while unshrinking. Sheathing leaves the sword parented to the holster while the hand releases and the upper body returns. During the overlap, additional arm destination guides are prepared on the returning torso at quarter-tick intervals, then sampled with parent-local FK. No solver runs during playback. The sword stays on its holster slide path until100%; only then can drawing transfer it to the returning hand. The arm branch is composed under the currently returning torso, preserving attachment and lengths. If an early body return would exceed the held arm’s reach, its progress waits at that boundary and resumes at release. This can extend body completion; it does not alter the sword’s slide timing.

The engine operates on the outgoing residual relative to the moving idle/walk base, in a fixed reference pose. Its parent-local FK interpolation, analytic angular momentum envelope, optional continuous spring, world/parent inertia modes, spine-angle duration adjustment and upperarm axial-inertia removal are reused directly. The result is transported back onto the current moving base pose, reaching it exactly at the return deadline. Root/pelvis/legs continue baseline motion. The World option refers to the recovery engine’s fixed reference before transport onto the moving base, not unconstrained world-space physics. Drawing’s right hand has rotation inertia at release; the other hand/action retains ordinary inheritance. Head/neck aiming is applied afterward and retains its independent timing/velocity limits.

Body and gripping-arm return clocks advance at ordinary playback speed from their respective start ticks, never accelerated by reach/slide curves. The geometric reach-boundary hold above is the sole body-clock exception. During overlap, underlying locomotion and the holster continue sharing recorded slide time; after release they resume ordinary playback time. Curves can affect the incoming velocity used to seed momentum; they do not alter return duration or its clock. Timeline completion waits for both FK returns, unshrink and head look-out, within the configured limit. Turning off return skips the recovery and retains the source action’s body pose. Profile edits preserve playing/paused state and reuse the planned body/arm trajectory. Drawing and Sheathing profile objects and bone weights are copied independently and saved in settings/snapshots/JSON; reopening the panel loads the active action’s profile.

`test_early_return.cjs` covers48 idle/walk, D/S, gaze,0/50/90/100% start cases with nonlinear slide timing and blend/spring/local/world profiles: grip, continuous entry/release, preserved arm lengths/source frames and both completed destinations. `test_head_gaze_speed.cjs` checks speed endpoints, interpolation, shared exponents and old-setting migration. `test_fkreturn.cjs` explicitly retains100% start and covers16 combinations of idle/walk, D/S, blend/spring and local/world inertia: exact entry, moving-base destination, lower-body preservation, attached drawing sword, unmodulated return duration, disable, independent profiles and sheath clavicle0→100% release. Updated FK/head/retiming/completion tests pass. `test_retime_ui.cjs` verifies right-side layout, contextual independent profiles, save/refresh/snapshot restoration and still captures on an isolated server. Evidence: `Saved/Diagnostics/SwordHolsterRetime/fk-return-panel.png`. Default sheath sliding hand error after clavicle release is0.019cm idle /0.183cm walk. User playback inspection remains necessary for motion quality and body/sword clearance; this is not a collision solver.

## Reuse and validation

The recovery lab's WebGL renderer, geometry buffers, camera, quaternion/FK math, styling, desktop identity, snapshot/capture service and launcher were copied and adapted. `reuse-receipt.json` records the originals and their digests. No original lab files were edited. The renderer has a pelvis-block adjustment and an equipment adapter for the exported meshes; `recovery.js` remains unchanged.

Validation:12 idle/walk × draw/sheathe × shrink cases; finite poses; position/angular reach caps; axial-only scale; repeated evaluation and seeking; reachable70% endpoints; captured Unreal stall geometry. Browser checks cover playback, keyboard stepping, gizmos, snapshots, refresh restoration and live desktop capture. Evidence: `Saved/Diagnostics/SwordHolsterLabQA/` in the project.

Run `node test_holster.cjs` for math checks. UI checks use an isolated service on8819 and separate state directory, never the user's8818 session. `check_ui.cjs` accepts `HARNESS_PLAYWRIGHT_MODULE` for the Playwright module location.

`/desktop-view` returns `state`, `displayedPose`, equipment and diagnostics at the top level with fingerprint/client identity. `/desktop-view.png?sequence=...` returns matching pixels. The reused read-only trajectory command is available through `/app-control`; numbered snapshots remain the durable tuning record. The launcher uses the existing stepper Python runtime and Edge/Chrome app mode, with an independent browser profile.

### Bone display basis correction

The reused renderer expects world XZY coordinates and a local X,-Y,Z bone basis. Converting the entire quaternion by the world Y/Z swap also swapped local bone axes, turning torso/head shapes sideways. `displayAxes` now converts each UE bone basis vector into the renderer convention directly, including reference ghosts and gizmos. Solver and equipment transforms remain in UE space unchanged. `node test_display.cjs` compares all26 frame-zero bones against the accepted recovery-lab idle axes (max4.75e-6 difference on toe bones from float32 source export). Idle/walk visual evidence is under `Saved/Diagnostics/SwordHolsterAxes20261010/`.
