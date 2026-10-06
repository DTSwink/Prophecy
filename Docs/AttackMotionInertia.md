# Attack motion inertia

`Set Attack Motion Inertia` is an opt-in Blueprint function on an agent. Call it
before triggering an attack. Existing agents are unaffected until enabled.

| Pin | Default | Meaning |
| --- | --- | --- |
| Enabled | false | Enables the configuration for subsequent attacks. False cancels immediately. |
| Inertia | 0.03 | Angular spring response time, in authored seconds. Larger values carry motion longer; zero bypasses. |
| Frames After Armed | 1 | Additional 60 Hz game ticks after the first Armed prediction. Zero excludes the Armed prediction. |
| Core Only Throughout Attack | false | Replaces the short full-upper window with spine/neck/head filtering until attack end. Clavicle and arm local joints are excluded. |
| After Hit | false | Resumes filtering all 16 upper joints from the first Hit prediction until upper attack end, using the same Inertia value. With core-only mode, arms and clavicles join at Hit. |

Settings latch at attack entry, so repeated configuration calls do not reseed an
active spring. Explicit disabling still takes effect immediately. At the 30 Hz
policy rate, the default one-tick allowance filters the Armed endpoint and ends
before the following policy endpoint. Ordinary 60 Hz presentation interpolates
those endpoints; this does not add a render-tick filter.

The filter is a critically damped angular spring in each bone's parent space.
It retains angular velocity, uses shortest-arc quaternion errors, and preserves
the source local translations and scales, including forearm length leeway.
All 16 upper joints participate in the normal mode. The optional whole-attack
core mode filters the five spine bones, two neck bones and head. Descendants
follow the core while retaining their source local transforms.

The filter runs on the final accepted 30 Hz upper pose, after mounting,
forearm convention, existing entry modifiers and NN history publication. It
changes the displayed pose and physical drive targets, but does not encode that
smoothed pose into the attack's recurrent history. Armed/Hit remain the NN's
learned gates. Older hand/core entry inertia, general hand inertia, arm cones and
the extra left-wrist constraint retain their original feedback by default.
[Set Attack NN Feedback](AttackNNFeedback.md) can opt their direct writes out
separately; all five off enables the isolated behavior from the fidelity audit.
Previous-pose reads use the source before this motion filter. With wrist feedback
off, the extra wrist constraint instead runs on the final pose after smoothing.

This isolation is within an attack. Physical interactions, subsequent attack
initialization and other explicitly enabled feedback controls can still change
future inputs. It is not a guarantee that every learned attack reaches Armed.

With After Hit enabled, the Armed-to-Hit gap observes the latest unfiltered local
rotations and angular velocities without applying the spring. Reactivation uses
that current motion, not the old wind-up state. Hit latches for this attack only.
At upper attack end the attack filter is cancelled. Existing FK return captures
the final two accepted, already filtered poses and derives its starting momentum
from them. It does not restart from raw NN poses or apply both filters together.
The return's per-bone inertia weights and intentional hand behavior still apply;
this does not force identical angular velocity through every return profile.

Filtering uses the final Unreal forearm roll convention after the existing
entry controls. Core-only mode keeps the local clavicle/arm joints unchanged.
Presented poses, physical drives and defender collision samples consume the
same final accepted pose. The raw attack ghost remains available independently.

The hot path uses fixed stack scratch, cached bone/parent indices and cached
spring coefficients. It adds no inference. Name lookup and state allocation are
attack-entry work. A source-pose cache is allocated only for enabled attacks and
retained while smoothing or waiting for After Hit; disabled agents take the empty-map fast paths. Attack end,
defense replacement, reset, agent removal and world cleanup release active state.

## Reproduction and validation

Earlier results below used recurrent smoothing and are historical; October 5
changes isolate motion inertia from recurrence. See [stall investigation](ThirdAttackStall20261005.md).

### After Hit extension (October 3)

Live Coding loaded at 21:18:48 UTC. All eight focused checks passed at 21:19:35:
six MotionInertia tests (including AfterHit and ReturnHandoff), plus FKReturn
AcceptedHistory and ExitInterval. ReturnHandoff checks all 16 joints' accepted
boundary poses, momentum source, and absence of attack filtering after stop.
The moving solver benchmark measured 1.691 microseconds per policy step, including
input copying, excluding inference/encoding/rendering/physics.

Five owned physical captures are in `Saved/Diagnostics/MotionAfterHit20261003/`.
The current random setup's first attack is slashRD. The unchecked option matches
the pre-change 160-frame capture exactly, including every native trace byte.
At response .03, checking After Hit preserves every recorded pose before Hit134,
Armed126/end146 and all 41 native lower output channels. Core+AfterHit also
completes with those gates. A .15 stress run completes attack/end184 and recovery
through240 with finite poses (the larger wind-up response delays Armed/Hit to
164/170). This is not a claim that stronger smoothing preserves learned timing.

Blueprint node refresh preserves all previous pins/wiring and adds AfterHit=false.
The user's current Enabled=true/.03 settings and random-attack selector remain.
Blueprint compiled status3, native_properties0/pin_types0 and was saved; map was
not saved. Play ended and tracing was restored. `verification.json` and
`editor-verification.json` hold receipts. Existing runtime exit ownership needed
no change. Normal editor DLL rebuild is still required before a cold launch.

### Original pre-Armed feature

The isolated fixture and comparison scripts are under
`Saved/Diagnostics/AttackMotionInertia20261003/`. The fixture retains the corrected
sixth `slashL` from the frame-743 investigation, including its incoming history
and native predictions. Live comparisons enable this option only at tick 730;
the preceding five attacks remain untouched. `offline_filter.py` is an open-loop
prototype only; use the live captures for recurrent behavior and phase timing.

Focused Unreal automation checks: `Prophecy.Attack.MotionInertia` (window,
geometry/core exclusions, lifecycle, and cost).

Seven owned 790-tick physical replays compared the original, explicit disabled,
full-upper response 0.02/0.03/0.04/0.06, and core-only response 0.04. All captured
poses through tick 730 matched exactly. Explicit disabled also matched the entire
original displayed trajectory and every native trace record exactly.

The selected 0.03 default preserves Armed 742, Hit 758 and attack end 770 in this
slash. Presented right-hand travel at tick 743 is 8.628 cm rather than 3.542 cm;
the physical body travels 8.654 cm rather than 3.645 cm. Peak change in the hand's
per-tick displacement vector across ticks 740–748 falls from 13.003 to 6.424 cm
(50.6%). The first fully unfiltered displayed interval, tick 745, changes that
vector by 5.569 cm, below the original brake. Over the broader 737–756 interval,
the peak falls from 13.003 to 10.505 cm (19.2%); the remaining peak is during the
swing at 755, not the filter release.

All 41 primary lower-policy output channels match exactly at steps 732–768.
This does not imply that every downstream physical contact/leg trajectory is
identical. The hand deviates by as much as 21.65 cm during the smoothed wind-up,
converges to 2.70 cm from the original at Hit and 0.37 cm at attack end. This is a
motion filter, not a correction to the learned target/phase model. The learned
wind-up reversal remains. Response 0.04 and 0.06 shift Armed two/four ticks later;
that timing tradeoff is why 0.03 was selected.

All four focused tests passed after the final defaults were loaded. The moving
16-joint solver measured 2.073 microseconds per policy step over 10,000 alternating
poses, including scratch input copying; this microbenchmark excludes the existing
pose encoder, NN, rendering and physics. It is not a whole-agent tick benchmark.
The existing PoseAgent Blueprint compiles with status 3, no native-property or pin
type issues, and its audited graph is byte-identical. No assets were saved.

This change is loaded in the current TestNN editor through Live Coding. Rebuild
the normal Development Editor DLL before a cold launch so saved nodes cannot
refer to an older reflected DLL. Preserve the user's unsaved Blueprint/map when
doing so. No custom launcher was added.
