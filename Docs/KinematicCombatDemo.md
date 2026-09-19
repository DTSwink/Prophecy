# Kinematic attack/defense scene

In `testNN`, `BP_ProphecyManualPoseAgent` (Player 0) attacks `BP_ProphecyManualPoseAgent4`. Their authored transforms are preserved. Agent2 is not opted in.

The manual Blueprint's **Kinematic Attack Defense Demo** function is called from Event Tick. Setup, frame counter, target capture, attack and defense nodes are all inside that function. When disabled, it calls the original `input debugging` function. The existing visual/print path remains connected.

Select the possessed actor and open **Debug > Combat Demo**:

- **Combat Demo Use Dodge**: true = Dodge; false = right-arm Parry. The choice applies when the next attack starts. Saved as Dodge.
- **Combat Demo Attack Every Frames**: 60 by default; actor/game frames, not 30 Hz policy steps. At 60 FPS this is one second.
- **Combat Demo Opponent**: the other placed agent. Both participants have reciprocal references.
- **Combat Demo Enabled**: enabled only on this pair. Turn off on both before Play to use the original debug behavior.

To remove the demo wiring, reconnect Event Tick to the original `input debugging` node directly below the demo call. Its original output remains connected. Restart Play after changing the setup; disabling the call mid-PIE does not undo already-applied simulation/collision settings.

The random pool is visible in the function: jab L/R, hook L/R, overhand L/R, headbutt and kick L/R. Both swords are hidden for these unarmed attacks. The current interpolated authored head position is captured once per launch; it is not retargeted as the defender dodges. Full-body attacks start before requesting defense. The runtime waits for that attack's learned Armed output before taking defender ownership or capturing defense history. Until then, normal locomotion and NN attacks remain available. Replacing the incoming attack cancels its previous waiting request; the demo requests the newly chosen response for the new attack.

Both participants are kinematic. The function retires each Magic Cube's Jolt adapter before turning collision and simulation off. Simply removing the cube's query receiver while its adapter is live violates the existing Jolt binding contract. The initialization guard also handles this Blueprint's deferred `begin_f2`, which otherwise re-enables physical simulation after the first Tick. Attack foot/calf presentation clamps are disabled in the demo.

The function contains no native controller, timer, or new production Tick. The installer in `Source/ProphecyEditor/Private/ProphecyCombatDemoSetup.cpp` only authors ordinary Blueprint nodes. It backs up the current Blueprint before installation. Pre-edit map and Blueprint backups are under `Saved/Diagnostics/CombatDemo`.

## Reference verification

The supplied viewer at `http://127.0.0.1:8941/?attack=nn` uses the saved headbutt sample 3257 and Dodge checkpoint 198044. Its attack is regenerated from accepted `good.pt` step 265458, with a fixed world target.

Unreal's native attack was seeded from the two original primers and evaluated for all 11 generated transitions. Its maximum joint-position error versus the supplied attacker was **0.001091 mm**, with identical Armed/Hit latches. Those native attack outputs were placed through the original harness and fed into native Dodge, preserving the reference defender primers. The original full comparator passed **all 462 tensors**, at unchanged absolute/relative tolerance `1e-5`; maximum defender joint-position difference was **0.001946 mm**. No cached predicted attacker or defender outputs were substituted as native recurrence inputs.

Evidence: `Saved/Diagnostics/CombatDemo/AttackReference/unreal_chain_audit.json`, `attack_to_dodge.json`, `native_attack_and_dodge_comparison.json`. The native Dodge trace test accepts both the original padded 16-frame fixture and this unpadded 8-frame fixture; its six completed-transition check remains unchanged. Original fixture inputs were restored after comparison. Reference/training data and network assets were not modified.

The live scene begins from its own idle/history and close spacing, rather than the reference episode primers. Numerical reference agreement does not promise every random live attack will be successfully evaded or parried.

Live Blueprint check passed: seven random attacks launched at demo frames 60, 120, 180, 240, 300, 360 and 420. Dodge was selected for the first four and Parry for the final three (PIE-only switch). Both agents stayed kinematic, both cubes had No Collision, published targets stayed finite, and active defense consumed the matching completed attacker frame. See `Saved/Diagnostics/CombatDemo/PIE.json`. The editor remains on testNN, Play stopped, saved mode Dodge. Installed using Live Coding without restarting Unreal.

## Reverse roles (2026-09-17)

Set **CombatDemoReverseRoles** on the possessed agent (Debug | Combat Demo). Default false keeps the possessed agent attacking; true makes CombatDemoOpponent attack the possessed agent. CombatDemoUseDodge still chooses Dodge versus Parry for whichever agent is defending. The player-owned timer/attack selection stays unchanged. Role selection is ordinary Blueprint wiring inside KinematicAttackDefenseDemo; head targeting and existing per-role clamp settings follow the selected agents. An unplugged Victim pin stays unplugged.

Verified three normal and three reversed Parry episodes plus two reversed Dodge episodes. Parry returns to locomotion on the attack's first Hit frame, independently of actual collision.
