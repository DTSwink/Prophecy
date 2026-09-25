# Physical foot above kinematic target — September25

Initial investigation used the height-guided knee implementation, historical September20 checkpoint, repeated kickL, Physical/Jolt. The user subsequently requested locomotion physical feet inherit their calf-clamp leeway; implementation is described below. The diagnostic8cm kick override was not retained.

## Shared locomotion allowance — implementation

An explicitly enabled `Set Locomotion Calf Clamp` now supplies its current leeway to both physical foot drive targets and ankle joints during locomotion. Because calf clamping allows shortening and lengthening, a2cm value permits translation from−2 to+2cm along each calf axis. The existing physical-foot target leeway can remain larger if explicitly configured; it cannot silently remove the active calf allowance. Turning the calf clamp off or setting its leeway to0 restores the prior physical-range behavior. This does not automatically infer unlimited joint travel from a disabled presentation clamp or inherit manager-level multiplier defaults.

Snapshot restore/blends write the same live calf-clamp fields, so publication reads the current value and synchronizes changed joint limits. No added blend clock/tick callback or bone reconstruction. A rig-identity/value cache skips native updates, skeleton-axis reads, reflection calls and waking when the range is unchanged; a zero/unconfigured range with no prior applied range exits immediately. Reset/rebind/world teardown remove or reapply the appropriate ranges. No retained component layout changed.

Specials do not inherit the locomotion allowance. The existing `Set Kick Foot Joint Leeway` node remains separate and extension-only during attacks. Its default is0cm; the diagnosed5cm is user configuration, not a hard-coded attack limit. During the kick's existing return, locomotion adds its symmetric compression allowance and supplies a minimum extension allowance, using max(current kick return, locomotion clamp). The same native calf-axis joint implementation serves both without modifying angular constraints. The old native extension bridge is preserved for callers; the new internal range bridge adds compression.

Compiled and loaded13:15:24UTC. The first build caught an incorrect settings-field name; using Jolt's `SetLimitedAxis` completed the incremental rebuild15.62s. Five focused native checks passed13:15:48UTC: physical-target leeway, clamp snapshots/blends, kick-leeway lifecycle, native ankle-axis constraint and rig range/recreation lifecycle. The broader recovery check also invoked the old normalized-knee trial oracle, which is obsolete after the user-requested restoration; it failed only those stale comparison assertions. That frozen-pose test now checks the accepted floor-level foot-front plane/forward branch while retaining endpoint/rotation/length/continuity checks. This test-only update compiled13:21:08UTC but was not rerun: user requested their active Play remain running and will test themselves. No knee gameplay was altered by the test repair.

Live300-tick capture (`FootHoverShared-live.json/-drive.log/-metrics.json`) confirms locomotion drive leeway2 and current blended values such as2.504cm. At the original left tick14, drive/authored gap2.000011→0.000011cm and physical height error1.470241→0.053256cm; tick15 becomes−0.020381cm instead of+1.480692cm. Authored calf lengths in these comparisons are identical. Signed physical length now changes rather than remaining locked at rest. This removes the diagnosed clamp mismatch; smaller dynamic rotation/tracking errors remain. No graph or saved-value changes, no restart. Capture ended and tracing reset0. Later user Play is preserved. These Live Coding changes need the next authorized normal build before editor restart.

## Kick mismatch: authored extension exceeds the physical joint allowance

At tick222, right supporting foot is2.261702cm higher than its authored target (total position error2.338886cm). The native foot drive target equals the authored target exactly. Magnetisation is enabled with linear/angular scales1 and gravity cancellation enabled. The authored calf-to-foot distance is50.349430cm; the physical distance is47.580268cm. Reference calf length is42.563465cm, so the animation requests7.785965cm extension while the physical joint reaches roughly its5cm allowance. Similar mismatches recur at312/402/492/582. This is not missing magnetisation or the newly changed knee direction losing its foot endpoint.

Causal test in a separate owned Play session: change only `Set Kick Foot Joint Leeway` to8cm at216, during the second kick. Stop at260; never save settings. All physical bone positions through216 match baseline exactly. Authored positions through230 remain identical, so the result cannot be explained by altering the NN rollout.

| Tick | Baseline foot height error | With8cm joint allowance | Authored pose difference |
|---|---:|---:|---:|
|220|1.646334cm|0.105232cm|0cm|
|222|2.261702cm|0.131762cm|0cm|
|224|1.388400cm|0.181819cm|0cm|
|230|1.733587cm|0.144078cm|0cm|

At222 the physical calf-to-foot distance reaches50.121806cm rather than stopping at47.580268cm. Tick233 recovery height error also falls0.910872→0.075206cm, though by then small physical-feedback differences reach0.003105cm in the authored pose. Increasing allowance was a diagnostic experiment, not a permanent change or a proposed universal8cm default.

## Smaller locomotion mismatch: different target lengths

Before the first attack, the left authored calf is44.563343cm long (reference42.563332cm plus2cm). Locomotion physical foot target leeway is0, so the packet builder deliberately redirects the foot drive to the reference calf endpoint. At tick14 this redirects the target upward1.934143cm (total2.000011cm); the displayed physical foot is1.470241cm above the authored foot. This is the physical-target clamp doing its documented job, while the kinematic leg admits extra length. Loosening only the drive clamp would not by itself grant the physical joint that extension.

## Remaining scope

Some smaller recovery discrepancies also remain with matching drive/authored targets, including left tick376: vertical error1.339558cm, rotation error17.794degrees, target calf42.809780cm versus physical42.437117cm. The joint-limit test isolates the dominant kick-support hover; it does not prove every remaining physical tracking/rotation discrepancy has the same cause. Matching visible targets and physical motion consistently requires compatible authored calf lengths, drive-clamp leeway and physical joint range. Higher magnetisation alone cannot satisfy incompatible lengths.

Evidence: `Saved/Diagnostics/FootHoverCurrent-live.json`, `FootHoverCurrent-drive.log`, `FootHoverCurrent-metrics.json`, `FootHoverLimit-live.json`, `FootHoverLimit-drive.log`, `FootHoverLimit-comparison.json`; capture/analyzer scripts alongside. Baseline600 ticks, paired test260 ticks. All owned PIE sessions ended, trace counter reset0, temporary allowance removed with test-world teardown. No compile/restart/save performed.
