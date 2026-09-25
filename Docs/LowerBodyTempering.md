# Root-local locomotion tempering

## Separate kick recovery profile

`Set Kick Locomotion Lower Body Tempering` stores Enabled and independent XY/Z/rotation
controls for **Kicking Foot**, **Non Kicking Foot** and **Pelvis**. Foot roles automatically
swap between left and right for kickL/kickR. It is selected automatically when
kickL/kickR returns to locomotion, before On Attack Ended runs. The regular setter
configures the normal profile; during a kick handoff it cannot overwrite the kick
profile. A kick setter called during that handoff applies immediately. Configure
both profiles in BeginPlay, then use the existing **Blend Locomotion Lower Body
Tempering To Normal** in On Attack Ended to blend from whichever profile was selected.
Feet/pelvis holds and durations remain independent and use 60 unpaused game ticks
per authored second. Both feet use the existing feet timing, each starting from its
own values. The kick setter does not create its own return schedule. Foot rotation
also drives that foot's toe, reconstruction source and calf twist continuity.
Normal feet with a normal pelvis bypass tempering reconstruction unless regional
Run/Walk mixing still requires chain repair. Reset preserves both feet's values.

For separate timing, call **Blend Kick Locomotion Lower Body Tempering To Normal**
after the kick setter in Special Ended. It has Feet Duration/Hold and Pelvis
Duration/Hold (defaults1/0 and1/0); both feet retain their own role-specific values
while sharing the feet timing. It runs only for the selected kick return. Using
it opts that agent into separated return routing: subsequent regular return calls
leave kicks untouched, and the kick return leaves ordinary attacks/parry/dodge
returns untouched. Existing graphs which never use the kick node keep the shared
return behavior. This routing is checked only when a node is called, reuses the
existing clocks, and retains zero-duration and completed-return bypasses.

The pose-agent's two kick return calls now use the kick variant. Their duration
inputs are independent0.25 literals (15 ticks), with holds0; they no longer share
the regular branch's duration literal. Gameplay Live build213.86s loaded17:33:36UTC;
all five focused tests passed17:34:15UTC, including SeparatedKickReturns across
30/60/120FPS, kick sides, hold/blend separation, zero duration and retirement.
Editor conversion compiled BP status3 at17:36:24UTC; node265/266 now call the kick
variant with canonical library/Agent references and unchanged execution links.
Blueprint subsequently compiled and saved for the user-authorized scripts/BP backup. No scene rollout or Play interruption/restart.
Include the new reflected function in the next authorized normal build.

September25 Special Ended graph repair: both live kick branches applied the kick
tempering setter and the Walk/Run recovery setter but never reached a tempering
return. The existing regular tempering return was in a disconnected chain. Initially added
`Blend Locomotion Lower Body Tempering To Normal` immediately after each kick
tempering setter, before its existing checkpoint-blend setter. Both new nodes use
the existing tempering literal0.25 for feet/pelvis duration (15 game ticks), holds0,
and the same Agent links as their setters. Those two calls now use the separate
kick variant described above. Kick coefficients and Walk/Run timings
are unchanged. This is an undoable Blueprint wiring repair, not a change to native
tempering/reconstruction. Live editor repair helper built14.06s; BP compiled status3
at17:22:28UTC and remains unsaved. KickProfiles, FootRoles and SeparateReturns all
passed17:22:39UTC. No scene rollout, Play interruption or restart. Before/after
graphs: `Saved/Diagnostics/KickTemperingReturn-{before,after}.txt`.

Final knee stance-plane guidance also follows the foot's Rotation tempering:
it approaches the frozen hinge at zero and full plane guidance at one. This
prevents a full-strength final knee correction from overriding a slowly following
foot. It adds no timer or work outside active reconstruction. Current Walk
recovery substantially reduces supporting-knee popping, with partial pelvis
improvement; see [measured results and limits](WalkRecoveryPelvisKneeDiagnosis.md).

Until a kick profile is configured, the old immediate-set behavior is unchanged.
Once configured, a non-kick attack exit selects the last regular profile. Disabled
or all-one kick settings explicitly disable kick recovery tempering; they do not
fall back to the regular values. Completed return blends remove active values and
timelines, while keeping the configured profiles for the next attack. Active
specials still bypass tempering, and knee reconstruction/pinning math is unchanged.
Reset cancels active blends and clears the selected kick context before restoring
its captured tempering values. Profile storage adds no ticking or inference.


`Set Locomotion Lower Body Tempering` takes **Agent**, **Enabled**, and six values:

| Pin | Controls |
| --- | --- |
| Feet Translation XY | Both ankle positions horizontally in the root frame |
| Feet Translation Z | Both ankle heights |
| Feet Rotation | Both feet, toe articulation and the knee-frame motion used by IK |
| Pelvis Translation XY | Horizontal pelvis position in the root frame |
| Pelvis Translation Z | Pelvis height |
| Pelvis Rotation | Pelvis orientation |

Pins appear in this table's order: the full Feet group, then the full Pelvis group,
each ordered XY translation, Z translation, Rotation. Internal pin names are retained
when refreshing older nodes, so connections and defaults survive reordering.

All six default to **1** (normal locomotion). **0** holds the previous completed
pose in its own root-local frame. Intermediate values interpolate toward the new
lower NN prediction on each 30 Hz policy step: linear for positions, shortest-path
quaternion interpolation for rotations. This is per-step following, not a blend
duration or a blend toward a permanently captured initial pose. All six at zero
keep the lower body as a statue carried by the root, except for pinning and required
reach/floor correction. Values outside [0,1] or nonfinite values are rejected.

XY/Z revision validated2026-09-20: TranslationAxes, ReturnTimeline, SeparateReturns,
SixtyTickClock and PhysicalBaseline passed after a normal Editor build. Existing
pose-agent Set nodes copy their old translation wires into both XY and Z to keep
their previous behavior until edited. Blueprint compiled successfully and was saved.
The accepted knee-guidance algorithm is unchanged.

For diagnosis, **Set Leg Chain Reconstruction** takes Agent and Enabled (default
true). Set false to bypass the added chain-repair passes for tempering, pelvis
inertia (including attacks), and Dodge's lower-body modifications. Pelvis/foot
modifiers still apply, while their chain solver no longer adjusts the thigh or
projects ankle reach/floor. This can deliberately produce inconsistent leg lengths.
Normal NN pose decoding, existing pinning/clamps and physical constraints remain
active. True restores the normal path. The per-agent override survives tempering
completion or reconfiguration; it is removed on manager teardown/world cleanup.
No tick, timer or inference is added; the switch is checked only inside active
modifier paths. Turning it back on removes the per-agent debug entry.

To return to ordinary motion, call **Blend Locomotion Lower Body Tempering To Normal**
after setting your values. The menu exposes only **Set** and **Blend**. The Blend
node has Agent plus four timing pins:
- **Feet Duration Seconds** (default1)
- **Feet Hold Duration Seconds** (default0)
- **Pelvis Duration Seconds** (default1)
- **Pelvis Hold Duration Seconds** (default0)

It captures the current values, then independently holds and smoothstep restores
feet XY/Z/rotation and pelvis XY/Z/rotation to1. Both translation axes follow their
part's existing timing; no additional timing node is needed. Reset captures and
restores all six values and cancels active returns. For example, feet
duration1/hold0.5 waits30 ticks then returns over60 ticks, while pelvis
duration0.5/hold0 returns in30 ticks. One authored second always means60 unpaused world
ticks, regardless of actual FPS or time dilation. Repeated reads in one tick do
not advance the timer.
The return clock starts when this node executes, including time spent in a full
attack/defense where tempering itself does not affect the pose (including half attacks).

At completion the settings and return timeline are removed, so the ordinary path
has no tempering, history copy, extra IK or timing work. Only active returns use
the shared blend-clock callback, which unregisters when no timelines remain.
A subsequent Set cancels the scheduled return; another Blend captures the
currently interpolated values and replaces the prior return. Disabled/all-one
settings cancel it too. Already-normal agents allocate nothing. Duration0 snaps to
normal after the optional hold;0/0 returns immediately. Negative/nonfinite times
are rejected. Completion is resolved on the next eligible lower-policy evaluation.

A completed part retires independently; once both are normal all tempering pose/IK
work is bypassed. A new Blend replaces both return schedules. The briefly exposed
Feet/Pelvis-only functions are hidden from the menu, retained only for existing
graph references. Existing Duration/Hold pins on the combined node retain their
internal names and connections but now label feet timing; set the added pelvis
pins explicitly. Refresh an already-placed Blend node to expose its new pins.

Validated via Live Coding without restart on2026-09-19 at13:19UTC:
SeparateReturns, ReturnTimeline and SixtyTickClock passed. The focused check verifies
exactly two exposed Blueprint functions and different feet/pelvis holds and durations
through the single Blend node, together with timer retirement and zero-duration paths.
No Blueprint/scene edits.

Order:

1. Lower NN prediction and normal state cleanup.
2. Temper against the previous **published root-local** lower state. Do not use
   the current recurrent state, which is already rebased to preserve world motion.
3. Existing foot-roll/pinning and floor logic. Pins use the usual rebased state,
   so a selected pin stays in global space even with Feet Translation = 0.
4. Existing walk/run output blending.
5. Apply at least15cm inward clearance, including the ankle's projection into
   the foot-forward vertical plane. A sphere alone permitted sideways passes
   almost through the hip in that plane and caused knee flips. Preserve the
   lateral component relative to that plane; distant targets remain unclamped
   when the existing Calf Clamp is off. Raised feet retain the previous coherent
   hinge. Near the floor, gradually admit the untouched NN source hinge, with
   a20-degree source handover bound per policy step, then solve the knee circle
   against a plane retaining the source knee's lateral stance offset. Choose
   the circle branch nearest the transported coherent hinge, fading guidance
   at branch ties and undefined source/target horizontal foot headings.
   Do not switch branches at hip height and do not use the discarded upright
   reference guidance. Guidance fades for undefined toe heading or an infeasible
   plane; Feet Rotation=0 retains transported orientation. Existing foot/toe
   floor handling remains. Commit the corrected ankle and thigh to lower state.
6. Existing pelvis inertia (if separately enabled), recurrent commit and upper NN
   conditioning use the corrected pose.
7. During publication, Feet Rotation also controls calf twist. The reduced
   lower NN state does not store calf rotation, so retain the actual preceding
   published calf, swing it onto the newly decoded calf axis, and interpolate
   only the remaining twist toward the decoder. Preserve that actual preceding
   rotation as the interpolation start; re-decoding it as locomotion would erase
   an outgoing attack's calf roll immediately. Same-time republishes reuse the
   same preceding sample. This does not move knees or change future ankle targets.
   All-one/inactive tempering bypasses calf blending. There is no family-specific
   gate, separate clock, timer or extra persistent history.

**Wide-stance and calf continuity correction2026-09-21:** forcing a zero lateral
knee offset was responsible for the overL inward knee snap. Source stance now
supplies that offset. A separate31–54-degree calf-roll snap came from switching
decoder conventions and reconstructing the outgoing sample with the incoming
decoder. The publication step above carries its real rotation through the
existing tempering blend. See [measurements and bounded validation](OverLRecoveryKnee.md).

**Support-leg recovery refinement2026-09-20:** repeatedly transporting the old
supporting thigh could make its orientation stall/twist during post-kick walking.
Those corrected rotations and their differences then disturbed the next NN pelvis
prediction. The near-floor source weight is1 up to2cm sole clearance, smoothly
falls to0 at12cm, and is bounded so the previous-to-NN source rotation advances
by at most20 degrees per30Hz policy step. This is a source-frame handover bound,
not a clamp on final joint rotation or a new duration/clock. The source pelvis,
ankle and thigh are blended together before the existing connected-leg solve.
Each leg uses its own Run/Walk mixture, including its source pelvis. Frozen
Feet Rotation=0 retains the previous source exactly. Raised-foot source selection,
the15cm inner safeguard and outer-clamp choice remain. The2026-09-21 correction
replaces zero-offset guidance with source-stance guidance as described above.

No alternate hidden pose is fed to the NN: recurrence and upper conditioning
still receive the final corrected pose. No persistent history, timer, additional
inference or reflected layout is added. Inactive/all-one tempering bypasses source
capture and math. Editor-only comparison: `Prophecy.Tempering.SupportSource 0`
restores the previous-source behavior;1 is the default refinement. Packaged games
use the refinement without an editor comparison CVar.

An11-recovery comparison in the current kickR/backward-walk setup reduced the
measured pelvis hitch each cycle and reduced both legs' largest thigh rotation
steps. The high kick foot descended monotonically and its knee stayed in the
forward plane. The trajectory is not identical: maximum early foot-relative-pelvis
differences were1.17cm forward,2.61cm lateral and4.45cm vertical; later descents
reached20cm height one NN step later. Some initial right-knee positional acceleration
peaks increased9–18%, while foot acceleration and retirement discontinuities
improved. This is bounded numerical validation, with visual acceptance still
with the user. Full evidence and rejected candidates:
[Pelvis recovery investigation](PelvisRecoveryHitchDiagnosis-20260920.md).

This affects locomotion only. Every active special bypasses tempering, including
half attacks even though they use the locomotion lower policy, plus full attacks,
parry and dodge. The settings are retained for locomotion; scheduled returns keep
their existing clock and do not restart or freeze on special entry. Pending defense
requests do not suppress locomotion tempering until the defense actually activates.
The former half-attack exception was removed and loaded through Live Coding on
2026-09-19 at13:55UTC. Compile/source-path verification only; no scene replay,
Blueprint edits or restart for this gate change.

Current knee version loaded2026-09-20 at15:17:05UTC; user explicitly accepted its
motion. The20-kick replay `ThighOutward-20260920-171739` contains384 recovery policy
samples per leg: no reversed hinge in the measured stable samples, left knee
sideways target residual below0.000016cm. Presented recovery knee abduction p95
was0.382 degrees; largest presented thigh step21.13 degrees. These are bounded
measurements, not a universal no-snap guarantee. The earlier15cm sphere-only
candidate still snapped and was replaced by the plane-clearance version.

The prior1.2-times-length-difference node still exists; effective minimum is now
`max(15cm, abs(thigh-calf)*Multiplier)`. It cannot lower the15cm floor. No node
signature or user Blueprint was changed. Earlier minimum-distance validation
below describes the superseded formula-only version.

The user's subsequent inward-foot observation is separate from knee orientation.
Read-only analysis of the accepted replay confirms recovery peak inward ankle
travel relative to its own hip7.19/15.36/16.00/18.93cm after kicks1–4. Kick4 goes
11.18cm past the pelvis midline. At that sample the blended raw NN already asks
for18.81cm; tempering gives18.89cm and the clearance correction contributes about
0.05cm, yielding18.93cm. Both Run and Walk predict inward placement (19.81 and
17.58cm). This occurs after attack mode ends, during the descending recovery.
The minimum distance is not a between-legs exclusion rule. Later complete kicks
fluctuate around13–19cm rather than growing without limit. Recovery feeds future
NN inputs and attack seeds; no controlled ablation has attributed the entire
cross-kick change to one specific feedback setting. No gameplay changes made
for this follow-up. Evidence: `FootDriftAudit.py`, capture `foot-drift.json`.

### Repeated full attacks from a zero-tempered finishing stance

Bounded current-scene diagnosis on2026-09-19: the live Blueprint issued two full
`overL` attacks (the user described hooks), with all four tempering values0 and
Hold=100 (6000 game ticks). Three360-frame PIE captures preserved the
Blueprint/map and restored diagnostic CVars; no restart or gameplay changes.

- Baseline second attack: pelvis per-axis ranges3.88/3.54/0.89cm in the attack
  state, compared with20.49/33.59/9.98cm on the first attack.
- Disable tempering after the second Trigger but before its first prediction:
  **all18 attack inputs and outputs matched baseline exactly**, including the
  weak lower movement. This rules out direct tempering of that full attack.
- Disable tempering in the locomotion gap at2.7167s instead: pelvis recovered
  from77.66cm to90.75cm before attack2; attack2 ranges became22.80/21.87/8.80cm.
  Its Blueprint re-enabled zero tempering at Trigger as in baseline.

The zero setting retains the previous attack's finishing stance. A fresh full
attack correctly seeds its two recurrent frames from the current published pose;
it does not restore a ready stance. The lower attack model receives current pose,
frozen-lower prediction, family and target height, with no new-attack/Armed/Hit
phase input. Restarting the upper attack therefore does not imply repeating the
first lower-body movement from this different stance. Supporting a visible
preparation/recovery on new attack would be a behavior change, not another
tempering bypass. No automatic pose reset or invented lower motion was added.

Evidence: `Saved/Diagnostics/TemperingHooks`, `TemperingHooksDisabled`,
`TemperingHooksGap`; capture helper `Saved/Diagnostics/CaptureTemperingHooks.py`.

**Set Locomotion Minimum Leg Reach** selects the minimum hip-to-ankle distance
for both legs during active tempering reconstruction:
**abs(thigh length - calf length) × Multiplier**, with Multiplier default **1.2**.
The distance is derived separately from each leg's skeleton geometry. Multiplier
1 restores the mathematical minimum; smaller/nonfinite values are rejected.
The numerical safety epsilon remains. Values larger than total leg length are
capped to feasible reach.
It moves only endpoints inside that boundary and does not alter foot rotation.
The boundary wins over an impossible pin. There is no additional tick or work
when tempering/reconstruction is inactive.

Validated2026-09-20 after Live Coding: the reflected node is callable and the
pose-agent Blueprint compiles. `RootLocalPinAndChain` and `PelvisInertia.LegChain`
passed, including coincident/near-hip targets, outside endpoints with outer clamp
off, unchanged foot rotation and connected reachable geometry. Current skeleton
defaults are4.2685cm left and4.4379cm right. A600-frame/10-attack replay completed
(`ThighOutward-20260920-155954`); recovery knee abduction p95 was17.98 degrees,
but maximum per-frame thigh change was29.31 degrees. The inner-bound feature is
verified; it does not by itself eliminate the remaining recovery snapping.

Outer reach projection follows the existing locomotion Calf Clamp enable state.
With that clamp disabled, the reconstruction retains even endpoints beyond full
extension and aims the thigh toward them; the existing unclamped decoder handles
the remaining calf/endpoint mismatch. The new inner boundary never enables an
outer distance clamp. With the calf clamp enabled, fixed bone lengths take
priority over an unreachable pinned endpoint.
Simulated-body motion and other explicitly enabled modifiers remain independent.

**Disabled or all-one settings remove the per-agent entry.** No tempering math,
history copies, additional inference, or additional leg solving runs. The dormant
registry returns immediately when empty. No extra tick or retained pose history is
needed: the existing published lower state supplies the previous pose.

Implementation: `ProphecyLowerTemperingLibrary`, `ProphecyLowerTempering.inl`, the
locomotion correction stage and the existing `ResolvePelvisLeg` solver. No changes
to Blueprint graphs, scene transforms, checkpoints or authored collider geometry.

Earlier source-frame correction (superseded by the current recovery solver): the previous implementation saved its source
after independently tempering pelvis, feet and thigh. This no longer matched
Dodge's untouched-baseline workflow. It now uses the separate source frames in
step5 above, including changed foot rotation. Live Coding and the two focused
`RootLocalPinAndChain`/`LegChain` checks passed; the new check covers deeply folded
legs with independently prescribed foot rotation and knee bend direction.

The unchanged kickL loop ran for4,731 captured frames (78 attacks). The largest
left-knee bend-direction change between captured frames fell from138.28 degrees
in the baseline to26.77 degrees (startup); no comparable sideways flips appeared.
This metric is the knee's projected bend direction in pelvis space, excluding
nearly straight legs with bend radius below3cm, not the calf's full rotation.
The physical calf still makes abrupt46–60-degree changes on many attack exits.
Two exits captured with `ReadNNFutureWorldPose` also show59.76/62.72-degree changes
in the future calf target,45.44/48.28 in its presented target and46.86/49.76 in the
visible physical calf. That remaining recovery discontinuity is not fixed here.
Evidence: `Saved/Diagnostics/KickKnee-20260920-125101` and
`Saved/Diagnostics/KickKnee-20260920-130855` (`capture.json`, `target-check.json`).
Temporary readback callbacks were removed; only the diagnostic PIE was stopped.

Validation (2026-09-19): normal Editor target build succeeded (111.38 s; Unreal
was already closed). A temporary headless Entry-map process passed four focused
tests: `LowerTempering.RootLocalPinAndChain`, `PelvisInertia.LegChain`, and both
`PolicyBlend` tests. Covered exact identity/zero pose endpoints, separate controls,
root-local following, world pin precedence, fixed-length/floor solving, and zero
attack-recovery bypass. The process exited successfully. No current-scene rollout
or performance benchmark was run; scene testing remains with the user.

Hold/return extension: Live Coding compiled and both reflected signatures loaded
on2026-09-19, without restarting or editing user assets. `ReturnTimeline` and
`PolicyBlend.AttackRecovery` passed: hold boundaries, separate four-value return,
normal endpoint/removal, setter cancellation, zero-duration snap/bypass, pure Run
hold without dual inference, and residual time across the hold/blend boundary.

September22 kick-profile/Hit validation: normal editor build succeeded (108.36s),
testNN reopened, both new nodes reflected, and all three existing recovery nodes
refreshed with other values/connections preserved. Pose Blueprint compiled and saved.
Six focused tests passed at19:14:49UTC: KickProfiles, AttackRecovery, ReturnTimeline,
SeparateReturns, SixtyTickClock, and Jolt Sword AttackCollisionPhases. The latter
checks native owner-pair restoration at Hit for simulated and attached swords,
retained attack context, repeated refresh, and stable body/joint counts. No scene
rollout. Evidence: `Saved/Diagnostics/KickProfilesValidation.txt`.


September22 kicking/non-kicking refinement: Normal editor build passed115.26s; final test-only rebuild passed60.75s. Unreal reopened on testNN, both role nodes refreshed with existing values/links preserved, new non-kicking inputs copied from shared feet, and pose Blueprint compiled status3 and saved. All11 focused tests passed20:21:05UTC (role mirroring, per-axis pose/toes, return/hold retirement, reset, regional policy, calf continuity and60-tick clock). Initial role-test rotation assertion differed by one float ULP; corrected its tolerance to1e-6, with no gameplay change. No gameplay rollout. Evidence `Saved/Diagnostics/KickRolesValidation.txt` and `KickRolePinValidation.json`; asset backup `KickRoles-BeforeRefresh.uasset`.
