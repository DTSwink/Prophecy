from pathlib import Path
p=Path('Docs/ForearmRollConvention.md');s=p.read_text(encoding='utf-8');s=s.replace('parry, dodge and the legacy arm-inertia reconstruction path.', 'parry, dodge, cached Armed-pose targets and the legacy arm-inertia reconstruction path.');s+='''

October 2 Armed-target follow-up: the original refactor missed the GT pose bank
used by Set/Get Upper Body Armed Pose. Its source-controller forearms differed
from the runtime convention by up to 173 degrees (jabR right: 169.546 degrees).
LoadTargets now canonicalizes both forearms in all 16 families before deriving
parent-local goals. Hands keep their original authored component rotations, so
the corresponding wrist locals are rebased against the corrected parent.
The bank conversion is cached; there is no additional per-tick work.

ProphecyForearmConvention.h now owns the shared shortest-swing implementation
and canonical Unreal idle reference. Locomotion, attack, defense and legacy arm
reconstruction continue through the existing manager wrapper; Armed targets use
the same helper in UE basis. FK return continues its accepted parent-local curves
using that same idle data. Direct Unreal animation poses remain authored poses;
physics/presentation transport existing frames rather than inferring a different
roll. Repository search found no other runtime reader of the GT pose rotations.

Live Coding loaded 18:23:39 UTC. The user's subsequent Play test confirmed the
full sword turn is gone. Cross-family and source-boundary checks pending. No
Blueprint tuning, assets, normal DLL or user Play lifecycle changes.
''';p.write_text(s,encoding='utf-8')
p=Path('Docs/UpperBodyArmedPose.md');s=p.read_text(encoding='utf-8');s=s.replace('October 2 forearm convention follow-up (build/checks pending):','October 2 forearm convention follow-up (loaded; final checks pending):');s+='\nThe user confirmed the full turn is gone in the Play session started after the 18:23:39 UTC Live Coding load. That session was left running.\n';p.write_text(s,encoding='utf-8')
