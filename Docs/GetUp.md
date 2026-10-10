# Simulated get-up

October 10, 2026. Built and numerically verified in Play; user motion acceptance is pending.

Six Blueprint nodes in **Prophecy / Agent / Get Up**:

| Node | Purpose |
| --- | --- |
| Get Up | Start once from the completed physical pose; Play Rate Multiplier controls animation playback. |
| Get Up Profile | Entry blend duration/curve, handoff curve, magnetization restore duration, and advanced clip/snapshot/height controls. |
| Set Get Up Lowerbody Tempering | Feet and pelvis XY/Z/rotation follow; independent lower Handoff Alpha. |
| Blend Get Up Lowerbody Tempering | Store feet and pelvis hold/blend timings for automatic use. |
| Set Get Up Upperbody Tempering | Left/right hand XY/Z/rotation follow and FK core rotation; independent upper Handoff Alpha. |
| Blend Get Up Upperbody Tempering | Store separate left hand, right hand and core hold/blend timings. |

Call the profile, setters and blend nodes during setup, then call **Get Up** when
the fallen agent should rise. Configuration calls do not start recovery or a
clock; each Get Up snapshots the current configuration. Edits during a rise apply
to the next rise. Repeated Get Up during a rise returns false without restarting.

The automatic PHAT floor-clearance lift and its toggle node were removed at the
user’s request on October10. Get Up retains the original clip-height alignment
and explicit Ground Offset; no collider-support cache or per-sample height lift
remains.

Handoff Alpha is normalized **clip playback**: 0 begins after the initial pose
blend, .5 halfway through the clip, 1 at its end. Default is 1 independently for
both regions. At that marker each group's hold starts; after its hold the group
blends from the animation to the NN while its configured follow values return to
1. Disabled tempering means ordinary follow, while timed handoff still occurs.
Zero duration snaps after the hold. All durations use the project's 60 unpaused
game ticks per authored second. Play rate changes clip/marker timing only.

The upper controls reuse the normal spine_05-local hand tempering and parent-local
FK core tempering. Lower controls reuse root-local feet/pelvis tempering. These
are separate profiles and do not replace regular, kick, Dodge or Parry settings.

The default clips are `/Game/_mygame/animations/AS_GetUp_Front1` and
`AS_GetUp_Back1`, both on `SK_UEFN_Mannequin`. The versions without `1` use source
skeletons and are not interchangeable with the mannequin clips. Front/back is
selected from actual pelvis orientation relative to gravity, with yaw fitted to
the selected clip. The test Blueprint's `bool codex` remains untouched.

Get Up captures the physical pose once, aligns to a supporting floor and blends
parent-local transforms into clip frame zero, then plays the clip with its root
displacement retained. The early animation bypasses the reduced locomotion pose
decoder. At handoff, upper joints remain carried by the accepted pelvis while
the lower region returns independently. Accepted mixed poses update both NN
history samples in their proper root frames.

Simulation stays active. On accepted entry, PhysicalMesh's physical-material
override snaps to the value saved with physical-profile slot `1` (including None).
Missing slot `1` leaves the material unchanged. This uses the existing mesh setter
to update Jolt bodies as well as UE's receiver material. It is independent of the
profile's configurable magnetization-strength snapshot name.

Both arms' anti-jiggle is forced on during entry and playback up to the lower-body
Handoff Alpha marker. At that marker, the temporary arm override is released and
the previous independent selections resume. Existing timed disables and attack
gates remain intact; explicit preference edits during recovery are retained.
Magnetization **mode** snaps to0 on entry, then1 at that same lower marker, before
any lower tempering hold or blend completes. Entry duration is included; playback
rate changes the clip time to that marker. Cancellation releases the arm override
and snaps mode1 too. A zero-time lower marker releases immediately. No new node or
recurring timer is needed for these transitions.

After publishing the initial snapshot target,
magnetization blends back to the snapshot selected by the profile (default `1`).
If that snapshot is absent, body strengths blend to 1. Existing physical
tolerance, damping, joint limits and simulation membership are not retuned.
The mover/automatic balancing cannot pull the body away during the initial rise;
movement input fades in with the lower handoff. A ground-height offset is exposed
for clip-specific sole alignment. Ground support includes WorldStatic and the
project's named `floor` object channel. Moving-platform recovery is outside this
implementation.

Inference is suspended until the earliest regional handoff marker. It then uses
the normal inference batches. No extra predictor, mesh, Control Rig, continuous
pose search or permanent get-up tick is added. The shared bounded game-tick clock
and active pose cache retire after both regions reach their endpoint. New
specials/animation layers and reset cancel recovery. Reset preserves configured
get-up settings. World/agent teardown releases active state and clip references.

All six nodes are reflected and available. The requested follow-up wires Get Up
in the agent Blueprint's `tick debugging` function at `absolute tick debug == 30`,
restricted to the player-controlled agent, at playback1x. The existing tick10
knockdown, other links and tuning are preserved. The Blueprint is compiled and
saved; actual Play confirmed inactive through29 and active at30. Profile and
tempering setup nodes can be added to customize the default recovery settings.

Validation: six focused native tests passed. Owned front/back Play runs used
2x playback, lower Handoff Alpha .85, upper 1, follow values .35, and .3-second
blends. Both selected the expected clip, preserved the initial physical target,
stayed in Physical mode, completed separate handoffs and continued for60 ticks
after completion with finite poses. Physical pelvis ended near90cm above the
floor. This verifies integration and timing, not visual smoothness. During those
initial tests, saved BP bytes and fall-direction default were unchanged. The
subsequent tick30 wiring is recorded separately in the receipt.
Compact receipt: `Tools/Recovery/GetUpValidation20261009.json`. Full numeric tests
and build/reflection receipts: `Saved/Diagnostics/GetUp20261009/`.

The removed floor-correction experiment and toggle validation are preserved as
[historical evidence](Journal/GetUp-floor-correction-history-2026-10-10.md). They do
not describe an available feature.

October10 arm/mode/material follow-up: applied by Live Coding with no restart.
Three owned Play checks passed, preserving the complete Blueprint graph. Actual
motor counts changed from right-only(0,3) to both(3,3), then back at the lower
marker; mode .7->0->1, saved material and None restored at tick30, and animation
layer interruption released the effects at35. Both actual and accepted poses
remained finite in Physical mode. Source unit tests were extended/compiled;
validation here is actual Play, not a claim of visual smoothness. Normal DLLs
require building before cold launch. Receipt: `Tools/Recovery/GetUpPhysics20261010.json`.

Removal verification: normal native build succeeded (final editor rebuild58.59s);
actual Play remained Physical, inactive at absolute29 and active at30 through65,
with finite poses. The user-added floor-correction call was removed and its exec
flow bypassed directly into Set Arms Anti Jiggle. All other nodes, defaults and
links were preserved exactly; Blueprint compiled/saved healthy and map unchanged.
One necessary editor restart handled retained native layout and API removal.
Current receipt: `Tools/Recovery/GetUpFloorRemoval20261010.json`; full evidence:
`Saved/Diagnostics/GetUpFloorRemoval20261010/`.
