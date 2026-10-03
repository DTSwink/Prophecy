# Attack-start FK core inertia

**Current source contract (October3,02:09): NN pose and NN velocity in every simulation mode.** Automatic physical sampling and the physical attachment-position correction below were removed at the user's request. Ordinary NN entry also no longer rewrites its history through the physical-entry path. [Current implementation and head/hand replay checks](NNEntry20261003.md). Physical-mode experiments later in this document are historical.

`Set Attack Start FK Core Inertia` is a separate, opt-in attack-entry control. Its Enabled pin defaults to **false** and unconfigured agents have no feature state. Configure before starting a full or half attack. Retargeting and half/full switches do not restart it. It ends when its window finishes or the attack ends; the existing lab FK return handles exit from the final accepted pose.

| Pin | Default | Meaning |
| --- | --- | --- |
| Enabled | false | Enable the next attack entry; false cancels immediately |
| Hold Out Time | 0.1 | Keep full Alpha for this duration |
| Blend Time | 0.3 | Smoothly fade influence to the authored attack |
| Response Time | 0.25 | Angular spring softness; larger responds more slowly; zero bypasses |
| Momentum Scale | 1 | Scale outgoing local angular velocity; zero removes initial momentum, retaining lag |
| Alpha | 1 | Overall influence; zero bypasses |

All durations use **60 unpaused game ticks per authored second**, independent of FPS, hitches and time dilation. Spring integration uses the fixed NN publication interval. Repeated publication at the same clock tick does not integrate twice. Settings latch at entry; changing them while active configures the next entry.

The ten FK core joints are spine_01 through spine_05, neck_01/02, head and both clavicles. Angular momentum and spring targets are measured in each bone's immediate parent space using NN history. NN attachment translations are retained unchanged. Descendants are rebuilt parent-first with their existing local transforms, so arms and hands follow the core without getting independent local inertia. Pelvis and legs are untouched. The separately enabled attack-start hand inertia runs afterward.

Full attacks feed accepted core rotations and carried arm channels into the attack recurrence. Half attacks retain the existing independent ghost/carrier convention, matching hand entry inertia. Actual accepted presentation still feeds the normal upper pose and outgoing FK return.

Implementation is included from the existing hand-inertia translation unit to preserve live unity grouping. No additional inference, per-tick allocation or rolling history. Disabled agents do no sampling, spring or hierarchy work; active joints cache hierarchy indices at entry. Reset, attack stop, upper recovery cancellation, manager removal and world cleanup release state.

Focused checks: `Prophecy.NN.AttackEntry.FKCoreSpace`, `FKCoreClock`, `FKCoreBoundary`, `FKCoreNNSeed`, `FKCoreAttachment`, and `PelvisRegression`. Editor verification script: `Saved/Diagnostics/RunNNEntryChecks.py` also checks hands, feet and physical-start default bypass. No automatic Blueprint insertion or enablement.

Validation October 2: Live Coding loaded 21:58:58 UTC; both focused checks passed 21:59:23 UTC. Canonical reflection verified and pose BP compiled status 3 after repairing archived library defaults, preserving values/wiring. No explicit asset save or gameplay replay; user visual testing remains. Rebuild the normal Editor DLL before a future cold launch.

October3 entry fix: physically seeded full attacks now retain the active core’s outgoing local endpoint when preparing first-publication history, avoiding a repeated displayed core pose while pelvis inertia advances. Alpha-weighted, once per entry, with no extra integration/inference. Three focused checks and matched169–171 replay passed; see [handoff evidence](HeadAttackEntry20261003.md).

## Mode-synchronized pelvis/core sources — October 3

**Current result (01:48 patch13, superseding the remaining-twitch notes below):** synchronized correction timing removes505–506 snap-back; matching physical attachment offsets to physical rotations removes the artificial0.399cm head-target kick at170. Final physical/Kinematic550-tick replays and six tests passed. Kinematic motion matches the previous baseline exactly; physical offsets fade to NN smoothly. [Cause and measured results](Head50520261003.md#final-correction--october3-0148-warsaw).

Both entry features now select the source from agent simulation mode: Sim/Half Sim use physical pose and velocity; Kinematic uses NN pose and velocity. The manager selects one physical sample for both, reusing the existing physical NN seed when available, or sampling once on entry independently of SetSpecialStartFromPhysical. That node still controls the attack NN's initialization only. Disabled inertia adds no sampling. If physical sampling is unavailable, both use the NN fallback instead of mixing sources.

Core physical angular velocity is derived from the same physical previous/current transforms in parent space. The physical local rotation is advanced only through the remaining fixed publication fraction to align the first endpoint. Pelvis now seeds its output pose from physical Current in simulation, rather than combining the displayed orientation with physical velocity. In Kinematic, it retains displayed NN pose and uses NN history delta. Stale correction history from a previous attack cannot override the newly selected source. Existing Alpha/Momentum controls and60-tick timing remain.

Live Coding loaded October3 at01:01:45 Warsaw. Four FKCore checks plus PelvisRegression passed01:04:28. Three owned240-tick replays covered physical, physical with NN physical initialization disabled, and a transient Kinematic switch before entry. Physical pelvis/core matched the expected physical seed to8.83e-8/4.33e-6degrees; Kinematic matched NN to2.11e-14degrees; disabling the NN seed toggle left the physical entry core unchanged to4.53e-14degrees. Half Sim uses the same mode-selection branch but was not separately replayed. Evidence: Saved/Diagnostics/HeadAttackEntry20261003/sync-verification.json and verify_sync.py.

The head twitch is NOT fully resolved: full physical-pose seeding still shows a smaller entry movement/reversal (physical lateral positions169/170/171 approximately-0.0718/0.4527/0.2456cm; target0.0884/0.4512/0.1670cm). The earlier inverse calculation changed velocity only while retaining displayed pose; the requested mode-based implementation selects physical pose as well, so do not equate that one-frame calculation with this full runtime result. Source synchronization is verified; remaining visible transition needs separate diagnosis.

No Blueprint changes, tuning changes or explicit asset saves. All diagnostic Play worlds ended. Default disabled behavior retained. Normal DLL rebuild required before a future cold launch.

October3 01:35 synchronization correction: pelvis entry correction now becomes visible on the same game tick as the core's first attack pose. Its existing internal tick progression is retained so both seeds refer to the same instant. This removes the large505–506 reversal in the current full Pike replay, adds no state/inference, and leaves earlier165–176 motion identical. The documented smaller170 twitch remains. Five focused tests passed; [measured results](Head50520261003.md#synchronization-correction-october3-0135-warsaw).
