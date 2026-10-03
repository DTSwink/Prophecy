# Forearm roll convention

The forearm follows its upper arm using the parent-local rotation from `M_Neutral_Stand_Idle_Loop`, frame 0. This is the same canonical idle data used by the FK return. From that reference orientation, apply the shortest swing needed to point the forearm from elbow to wrist. The hand retains its independently authored rotation; rotating it alone does not rotate the forearm.

The shared reconstruction covers upper NN locomotion (including idle), full/half attacks, parry, dodge, cached Armed-pose targets and the legacy arm-inertia reconstruction path. Special correction remains enabled by default; the existing `Set Special Forearm Roll Correction` diagnostic switch can still explicitly bypass it. FK return keeps its authored parent-local curve; it is not projected again onto the reconstruction rule during the return.

This replaces the earlier hand-derived roll rule. That rule forced near-zero wrist axial twist during locomotion and attacks, but the canonical idle has a different hand/forearm relationship. With Alpha Hold 1, the captured slashLU returned from roughly 0 to 74 degrees of wrist-local twist and then jumped back toward 0 at NN takeover. The lab instead derived authored forearm roll from an upper-arm-carried reference. Runtime now uses one common neutral reference for every family, rather than a separate attack-frame-0 reference.

Only reconstruction changes: cached two-arm neutral quaternions, no new inference, timers, history, per-agent state or reflected pins. The hand transform and elbow/wrist positions are preserved by the roll correction. Existing fixed-length attachment remains separate.

Focused checks cover canonical idle orientation, shortest-swing reconstruction on both arms, independence from a complete hand rotation, degenerate directions, idempotence, and the parry/dodge coordinate boundary. Evidence and compile scripts are under `Saved/FKReturn/wrist-investigation/`. Visual acceptance remains with the user.

Validation: Live Coding compiled successfully and loaded into TestNN at 17:20:21 UTC on October 2. All three focused tests (`ForearmRollFromUpperArm`, `SpecialForearmBoundary`, `DefenseForearmBoundary`) passed at 17:20:55 UTC. No gameplay replay or explicit asset save. This change is currently Live Coding coverage only; rebuild the normal editor DLL before a future cold launch, following the existing launch rule.


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
full sword turn is gone. All eight focused Armed/forearm checks passed at 18:25:49 UTC, including both arms in all 16 GT families, unchanged authored hand rotations, canonical parent-relative roll and native/UE boundary parity. Evidence: Saved/Diagnostics/ArmedSpineHitch/forearm-tests.log and forearm-target-mismatch.json. No
Blueprint tuning, assets, normal DLL or user Play lifecycle changes.
