# Physical right-hand angle at tick 200

October 2, 2026: reproduced in the current TestNN setup. The cause is held-sword
contact with its owner becoming eligible on the first learned Hit output. The
contact response propagates through the grip and pushes the physical arm away
from its authored target. The exact contacting owner body was not recorded.

The current pike starts at game tick 174, becomes half-body/Armed at 186, first
reports Hit at 200 (attack frame 14), and ends at 204. Sword-owner contact and
body-body self-collision both lose their temporary attack suppression on Hit;
they are separate controls. See [collision phase rules](SwordAttackCollision.md).

## Controlled comparison

Three owned 260-game-tick PIE captures used the same scene/Blueprint settings.
The two controls changed only their transient PIE agent, immediately after
recording tick 199. All recorded bone orientations from ticks 30 through 199
were identical across all three runs. Authored target orientations at ticks
200 through 203 were also identical.

| Run | Right hand error at 200 | Right lowerarm error at 200 |
| --- | ---: | ---: |
| Current setup | 25.8451 degrees | 14.4944 degrees |
| Own-sword collision disabled before Hit | 0.2876 degrees | 0.8352 degrees |
| Body-body self-collision disabled before Hit | 25.8451 degrees | 14.4944 degrees |

The baseline hand error falls to 13.5261 degrees at 201 and 0.1495 degrees at
202. At 200 its position error is about 2.60 cm. The authored hand target turns
only about 1.07 degrees from 199 to 200 while the physical hand turns about
23.19 degrees. This is a transient collision response rather than a persistent
unreachable wrist orientation.

The physics target exactly matches the presented NN pose. PhysicalMesh bone
orientation matches the actual Jolt body orientation to numerical precision.
Both wrists and elbows have Free angular modes during the measured interval;
the remaining numeric PHAT angle fields are inactive. The right hand has full
linear/angular magnetization and no added wrist damping. No forearm convention
or kinematic/physical-target mismatch was found for this event.

## Existing control and scope

**Set Own Sword Collision Enabled**, Enabled = false, keeps this particular
contact disabled across Hit/end. It preserves sword contact with other agents
and the world. The global **Set Sword Collision Enabled** node is a different
control and is not needed for this case.

This investigation made no production source, Blueprint, map, or persistent
setting change. The controls existed only in owned PIE worlds, which were ended
after capture. No user Play session was stopped. There is no new build or visual
acceptance claim.

Evidence: `Saved/Diagnostics/HandPhysical200/` contains `capture.py`, the three
JSON captures (`baseline`, `no_owner_sword`, `no_body_self`), `compare.py`,
`comparison.json`, and the earlier detailed `analysis.json`. Numerical errors
compare actual body orientation against its exact authored physics target.

## Accepted follow-up: held forearm exclusion

The user requested a permanent held-sword exclusion for the gripping forearm,
restored only on drop. `ProphecySwordComponent.cpp` now includes the configured
hand bone's parent in both Jolt grip/body exclusions and Chaos owned pairs.
Hit/end, explicit owner-collision enable, attached/simulated mode and backend
refresh retain it. Existing drop cleanup removes it. No added ticking or NN work.

Live Coding loaded the gameplay change at 21:03:11 UTC on October 2. A fresh
owned 260-tick TestNN capture (`fixed_forearm.json`, `fixed-result.json`) measured
0.287607 degrees right-hand error at tick 200, matching the earlier own-sword-off
control. Only the hand/forearm exclusions are permanent; other owner body contact
retains its existing phase rules. No Blueprint/map changes or saved settings.
The normal editor DLL still needs a successful rebuild before a cold launch.
