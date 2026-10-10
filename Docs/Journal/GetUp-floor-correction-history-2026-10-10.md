# Removed get-up floor correction — historical evidence

The user requested removal of the automatic PHAT clearance lift and its toggle on October10,2026. This record is historical; do not restore the feature from these measurements. Current behavior: [GetUp](../GetUp.md).

The subsequent jiggle investigation compared identical falls with physical,
kinematic, freed-PHAT-limit and ignored-floor-contact playback. All prefixes
through absolute29 and all animation targets through560 were identical. Kinematic
pelvis/hands followed those targets exactly; freeing angular limits did not remove
the main shaking. The old height alignment targeted PHAT surfaces up to7.86cm below
the actual floor (Z=-.5cm). Ignoring body-floor contact removed most of the pelvis
and left-hand disturbance, establishing a contact/drive conflict.

The collider-based ground fit fixes that alignment error. In matched front
captures at ticks151-400, pelvis positional second-difference RMS fell2.198->.117,
left hand1.944->.193 and left foot2.521->.439cm/tick². Initial targets and pre-entry
physics are bit-identical. The maximum sampled interpolated penetration during
the clip fell7.86->.263cm; interpolation between source samples is not a continuous
collision solve. Regional NN handoff still governs the final pose.

Right-hand jitter remained .764cm/tick². A separate matched control disabling only
held-sword collision reduced it to .098, with mean target error2.56->.067cm and
rotation error16.45->.328degrees. Freeing PHAT limits instead gave .369cm/tick².
Held-sword contact is the main remaining front-recovery cause; deciding how the
sword should collide during recovery is a user behavior choice, not an automatic
PHAT or servo retune. The saved setup retains both sword collision and PHAT limits.

The ground-fit build took127.83s; three get-up tests passed (GroundFit, PoseMath,
TimingAndIsolation). Both default1x front/back recoveries completed through
absolute660 in Physical mode. These checks do not establish smooth back-recovery
motion; user motion review remains pending. BP/map bytes and all meaningful graph
values/links were preserved, editor outside Play with no dirty assets. Latest
receipt: `Tools/Recovery/GetUpGroundFit20261009.json`; full captures, numerical
metrics, source-plane inspection and build logs: `Saved/Diagnostics/GetUpJiggle20261009/`.

The October10 toggle follow-up built normally in235.34s and passed the same three
tests, including default-on, disabled lift, profile preservation and active-rise
snapshot checks. Short on/off Play runs through65 used Front1 in both clip slots
on temporary actors to isolate the toggle. Prefixes and initial targets matched
exactly; at65 the only pose difference was the enabled3.6411cm vertical lift.
Disabled state cached zero supports; enabled cached68. Initial automatic-selection
smokes selected different clips, so they were not used as the lift comparison.

Before restart, the user's unsaved BP edits were preserved and saved: Y force10000
and the disconnected execution link into Set PhysicalMaterial Override. No toggle
call was inserted into the graph. The graph, saved BP and map were unchanged by
the subsequent restart/checks. TestNN is open outside Play with no dirty packages.
Current receipt: `Tools/Recovery/GetUpFloorToggle20261010.json`; full evidence:
`Saved/Diagnostics/GetUpFloorToggle20261010/`.
